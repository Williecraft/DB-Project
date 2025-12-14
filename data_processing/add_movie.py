from typing import Dict, Any, List, Set, Optional
from difflib import SequenceMatcher

import pandas as pd

from generate_tables import (
    # Kaggle / IMDb 資料與設定
    load_industry_df,
    load_actors_source_df,
    search_imdb_id_by_find,
    scrape_reviews_for_movie,
    scrape_roles_for_movie,
    build_movie_and_related_from_industry,
    build_actor_from_name,
    scrape_poster_url,  # 抓海報網址

    # 進度管理
    load_progress,
    save_progress,

    # CSV 輸出
    write_all_csv,

    # 小工具
    sleep_a_bit,
    make_id,
    truncate,

    # 抓取上限
    GET_REV_COUNT,
    GET_ROLE_COUNT,
)


# ========= 找 industry 中對應的電影 =========

def find_industry_index_by_title(ind_df: pd.DataFrame, title: str) -> Optional[int]:
    """
    先用「完整片名、不分大小寫」在 industry 裡找，
    找到就回傳該 row 的 index，找不到回傳 None。
    """
    mask = ind_df["name"].astype(str).str.lower() == title.lower()
    cand = ind_df[mask]

    if cand.empty:
        return None

    # 若有多筆重名，選年份最早的那一筆
    if "year" in cand.columns:
        cand_sorted = cand.sort_values(by="year", ascending=True)
    else:
        cand_sorted = cand

    row = cand_sorted.iloc[0]
    idx = int(row.name)
    return idx


def find_similar_titles(ind_df: pd.DataFrame, title: str, limit: int = 10) -> List[dict]:
    """
    若沒有完全相同標題，就用簡單模糊搜尋找出「相似」電影名稱。
    回傳一個 list，每個元素包含 {idx, name, year, score}。
    """
    norm = title.lower().strip()
    if not norm:
        return []

    names = ind_df["name"].astype(str)
    years = ind_df["year"] if "year" in ind_df.columns else None

    candidates: List[tuple] = []  # (score, idx, name, year)

    for idx, name in names.items():
        name_str = name.strip()
        name_norm = name_str.lower()

        # 1) 如果是 substring 關係，給最高分 1.0
        if norm in name_norm or name_norm in norm:
            score = 1.0
        else:
            # 2) 否則用 SequenceMatcher 做簡單相似度
            score = SequenceMatcher(None, norm, name_norm).ratio()

        # 可以自己調門檻，0.5 ~ 0.6 比較合理
        if score >= 0.5:
            year_val = int(years.loc[idx]) if years is not None else None
            candidates.append((score, idx, name_str, year_val))

    # 依分數由高到低排序，只取前 limit 筆
    candidates.sort(key=lambda x: x[0], reverse=True)
    top = candidates[:limit]

    result: List[dict] = []
    for score, idx, name_str, year_val in top:
        result.append({
            "idx": int(idx),
            "name": name_str,
            "year": year_val,
            "score": score,
        })
    return result


# ========= 單一電影處理主流程（使用已載入的資料） =========

def process_single_title(
    title: str,
    ind_df: pd.DataFrame,
    actors_source: pd.DataFrame,
    progress: Dict[str, Any],
    seen_movie_ids: Set[str],
    seen_title_indices: Set[int],
) -> bool:
    """
    對單一電影名稱執行：
    - 先做精確比對（不分大小寫）
    - 找不到再用模糊搜尋，丟出相似電影清單給使用者
    - 若找到精確 match 且尚未處理過，就跑完整 generate_tables 的流程

    傳回值：
        True  = 有修改 progress（新增電影 / 評論 / 使用者 / seen 標記）
        False = 只列出相似電影或什麼都沒做
    """

    movies: Dict[str, Dict[str, Any]] = progress["movies"]
    directors_by_name: Dict[str, Dict[str, Any]] = progress["directors"]
    companies_by_name: Dict[str, Dict[str, Any]] = progress["companies"]
    genres_by_name: Dict[str, Dict[str, Any]] = progress["genres"]
    actors_by_name: Dict[str, Dict[str, Any]] = progress["actors"]

    roles_rows: List[Dict[str, Any]] = progress["roles"]

    # 讓同名角色共用同一個 role_id
    role_by_name: Dict[str, str] = {}
    for r in roles_rows:
        name = r.get("name")
        rid = r.get("role_id")
        if not name or not rid:
            continue
        if name not in role_by_name:
            role_by_name[name] = rid

    role_in_movie_rows: List[Dict[str, Any]] = progress["role_in_movie"]
    owns_rows: List[Dict[str, Any]] = progress["owns"]
    movie_genre_rows: List[Dict[str, Any]] = progress["movie_genre"]

    users_all: Dict[str, Dict[str, Any]] = progress["users"]
    reviews_rows: List[Dict[str, Any]] = progress["reviews"]

    # 3. 先用「完整片名」找 idx
    idx = find_industry_index_by_title(ind_df, title)

    if idx is None:
        # 沒有完全 match，改用模糊搜尋
        similar = find_similar_titles(ind_df, title, limit=10)
        if not similar:
            print(f"[single] 在 industry 裡找不到完全一樣的標題，也沒有相似電影：{title!r}")
            return False

        print(f"[single] 沒有找到完全一樣的標題：{title!r}")
        print("[single] 以下是名稱相似的電影，你可以下次直接複製正確的片名來用：")
        for i, item in enumerate(similar, start=1):
            year_str = f" ({item['year']})" if item["year"] is not None else ""
            print(f"  {i}. {item['name']}{year_str}")
        return False

    print(f"[single] 找到電影 {title!r} 在 industry idx = {idx}")

    # 4. 檢查是否已經嘗試過這個 idx
    if idx in seen_title_indices:
        print(f"[single] idx={idx} 已經在 seen_title_indices 中，代表之前已經嘗試過。")

        # 額外列出名稱相似的電影，讓使用者可以複製其他片名
        similar = find_similar_titles(ind_df, title, limit=10)
        if similar:
            print("[single] 以下是名稱相似的電影，你可以下次直接複製正確的片名來用：")
            for i, item in enumerate(similar, start=1):
                if item["idx"] == idx:
                    continue
                year_str = f" ({item['year']})" if item["year"] is not None else ""
                print(f"  {i}. {item['name']}{year_str}")
        else:
            print("[single] 沒有其他名稱相似的電影。")

        return False

    # ===== 以下為完整的一部電影處理流程 =====

    # 5. 先找 IMDb tt_id
    sleep_a_bit()
    tt_id = search_imdb_id_by_find(title)
    if not tt_id:
        print(f"[single] 無法從 IMDb 找到 {title!r} 對應的 ttID。")
        # 仍然把這個 idx 視為已嘗試，避免下次一直重複
        seen_title_indices.add(idx)
        progress["seen_title_indices"] = list(seen_title_indices)
        progress["title_index"] = len(seen_title_indices)
        return True  # 有更新 seen_title_indices

    print(f"[single] IMDb ttID = {tt_id}")

    # 若 ttID 已建立過 movie，就不重做（但 idx 還是標記為已嘗試）
    if tt_id in seen_movie_ids:
        print(f"[single] ttID {tt_id} 已經處理過，只更新 seen_title_indices。")
        seen_title_indices.add(idx)
        progress["seen_title_indices"] = list(seen_title_indices)
        progress["title_index"] = len(seen_title_indices)

        # 一樣順便列出名稱相近的電影
        similar = find_similar_titles(ind_df, title, limit=10)
        if similar:
            print("[single] 以下是名稱相似的電影，你可以下次直接複製正確的片名來用：")
            for i, item in enumerate(similar, start=1):
                if item["idx"] == idx:
                    continue
                year_str = f" ({item['year']})" if item["year"] is not None else ""
                print(f"  {i}. {item['name']}{year_str}")
        else:
            print("[single] 沒有其他名稱相似的電影。")

        return True  # 有更新 seen_title_indices

    # 6. 透過 industry 建立 movie / director / company / genre / owns / movie_genre
    movie_row = build_movie_and_related_from_industry(
        tt_id=tt_id,
        title=title,
        ind_df=ind_df,
        director_by_name=directors_by_name,
        company_by_name=companies_by_name,
        genre_by_name=genres_by_name,
        owns_rows=owns_rows,
        movie_genre_rows=movie_genre_rows,
    )
    if movie_row is None:
        print(f"[single] industry 中 {title!r} 資料不完整，無法建立 movie。")
        seen_title_indices.add(idx)
        progress["seen_title_indices"] = list(seen_title_indices)
        progress["title_index"] = len(seen_title_indices)
        return True  # 有更新 seen_title_indices

    # 6.5 抓海報網址並塞進 movie_row
    sleep_a_bit()
    poster_url = scrape_poster_url(tt_id)
    movie_row["poster_url"] = poster_url or ""

    # 7. 抓 reviews
    sleep_a_bit()
    users_map, reviews_map = scrape_reviews_for_movie(tt_id, GET_REV_COUNT)

    # 8. 抓 roles & actors
    sleep_a_bit()
    roles = scrape_roles_for_movie(tt_id, GET_ROLE_COUNT)
    actors_in_this_movie: Set[str] = set()

    for role_name, actor_name in roles:
        actor = build_actor_from_name(actor_name, actors_source, actors_by_name)
        actor_id = actor["actor_id"]

        if actor_id in actors_in_this_movie:
            # schema: PRIMARY KEY (actor_id, movie_id)，同一演員同一電影只允許一筆
            continue
        actors_in_this_movie.add(actor_id)

        # 先把角色名稱砍到 30 字，跟存進 DB / CSV 的實際值一致
        role_name_trimmed = truncate(role_name, 30)

        # 同名角色共用同一個 role_id
        if role_name_trimmed in role_by_name:
            role_id = role_by_name[role_name_trimmed]
        else:
            role_id = make_id("role")
            roles_rows.append({
                "role_id": role_id,
                "name": role_name_trimmed,
            })
            role_by_name[role_name_trimmed] = role_id

        role_in_movie_rows.append({
            "role_id": role_id,
            "actor_id": actor_id,
            "movie_id": tt_id,
        })

    # 9. 累積 user / review
    for uid, u in users_map.items():
        if uid not in users_all:
            users_all[uid] = u

    for _rid, r in reviews_map.items():
        reviews_rows.append(r)

    # 10. 累積 movie
    movies[tt_id] = movie_row
    seen_movie_ids.add(tt_id)

    # 11. 寫回到 progress 結構（dict 是同一個物件，其實前面都已經在改了）
    progress["movies"] = movies
    progress["directors"] = directors_by_name
    progress["companies"] = companies_by_name
    progress["genres"] = genres_by_name
    progress["actors"] = actors_by_name
    progress["roles"] = roles_rows
    progress["users"] = users_all
    progress["reviews"] = reviews_rows
    progress["role_in_movie"] = role_in_movie_rows
    progress["owns"] = owns_rows
    progress["movie_genre"] = movie_genre_rows
    progress["seen_movie_ids"] = list(seen_movie_ids)

    seen_title_indices.add(idx)
    progress["seen_title_indices"] = list(seen_title_indices)
    progress["title_index"] = len(seen_title_indices)

    print(f"[single] {title!r} 處理完成，ttID={tt_id} 已加入 progress。")
    return True


# ========= 互動主程式：一次載入，多次輸入 =========

def main():
    # 一次讀入 heavy 資料
    print("[init] 載入 industry 資料 ...")
    ind_df = load_industry_df()

    print("[init] 載入 actors source ...")
    actors_source = load_actors_source_df()

    print("[init] 載入 progress.json ...")
    progress: Dict[str, Any] = load_progress()

    # 這兩個 set 也只建立一次，之後持續更新
    seen_movie_ids: Set[str] = set(progress.get("seen_movie_ids", []))
    seen_title_indices: Set[int] = set(int(x) for x in progress.get("seen_title_indices", []))

    print("[init] 載入完成，可以開始輸入電影名稱（按 Enter 或輸入 q 結束）")

    # 一個 process 跑到底，不再 while True: main()
    while True:
        title = input("\n請輸入完整電影名稱（大小寫不拘，Enter / q 離開）：").strip()
        if not title or title.lower() == "q":
            print("結束輸入。")
            break

        changed = process_single_title(
            title=title,
            ind_df=ind_df,
            actors_source=actors_source,
            progress=progress,
            seen_movie_ids=seen_movie_ids,
            seen_title_indices=seen_title_indices,
        )

        # 只有在真的有更新時才存檔 & 重寫 CSV，省 I/O
        if changed:
            save_progress(progress)
            write_all_csv(
                movies=progress["movies"],
                directors_by_name=progress["directors"],
                companies_by_name=progress["companies"],
                actors_by_name=progress["actors"],
                roles_rows=progress["roles"],
                genres_by_name=progress["genres"],
                users_all=progress["users"],
                reviews_rows=progress["reviews"],
                role_in_movie_rows=progress["role_in_movie"],
                owns_rows=progress["owns"],
                movie_genre_rows=progress["movie_genre"],
            )
            print("[single] 變更已寫入 progress.json 與 data/generated/*.csv")
        else:
            print("[single] 本次沒有更改資料，不寫入檔案。")


if __name__ == "__main__":
    main()
