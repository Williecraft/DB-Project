import csv
import json
import re
import time
import uuid
import random
from pathlib import Path
from typing import Dict, Any
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup
import pandas as pd

# ========= 使用者可調變數 =========
INPUT_CSV = "data/kaggle/industry/movies.csv" 
TITLE_COLUMN = "name"           # 哪一欄是電影標題
GET_REV_COUNT = 20               # 每部電影最多抓幾篇評論
MAX_MOVIES = 100                # 最多處理幾部電影，避免一次抓太多（可設為 None 不限數量）

PROGRESS_PATH = Path("data/progress.json")

MOVIE_CSV = Path("data/generated/movie.csv")
REVIEW_CSV = Path("data/generated/review.csv")
USER_CSV = Path("data/generated/user.csv")
ROLE_CSV = Path("data/generated/role.csv")

# 每次 request 之間隨機 sleep 秒數，避免太兇
REQUEST_SLEEP_RANGE = (1.0, 3.0)

# ========= HTTP Session =========
SESSION = requests.Session()
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ========= 小工具 =========

def make_id(prefix: str) -> str:
    """產生簡短的 UID，例如 mov_ab12cd34"""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def normalize_title(title: str) -> str:
    """標題正規化，用來當 movies 的 key，避免大小寫 / 空白差異"""
    return re.sub(r"\s+", " ", title).strip().lower()


def sleep_a_bit():
    time.sleep(random.uniform(*REQUEST_SLEEP_RANGE))


# ========= 進度檔處理 =========

def load_progress(path: Path) -> Dict[str, Any]:
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    # 初始結構
    return {
        "movies": {},   # title_norm -> { movie_id, title, imdb_id }
        "users": {},    # imdb_user_id -> { user_id, name }
        "reviews": {},  # key -> review data
        "roles": {}     # key -> role data
    }


def save_progress(path: Path, data: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ========= IMDb 爬蟲邏輯 =========

def search_imdb_title(title: str) -> str | None:
    """
    在 IMDb 搜尋電影標題，回傳第一個結果的 ttID（例如 tt1375666）。
    若找不到則回傳 None。
    """
    print(f"[search] Searching IMDb for title: {title!r}")
    base_url = "https://www.imdb.com/find/"
    params = {
        "q": title,
        "s": "tt",
        "ttype": "ft",  # feature film
        "ref_": "fn_ft"
    }
    url = f"{base_url}?{urlencode(params)}"
    resp = SESSION.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"[search] HTTP {resp.status_code} when searching {title!r}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # IMDb 搜尋頁結構常見為 table.findList > tr.findResult
    result = soup.select_one("table.findList tr.findResult td.result_text a")
    if not result:
        print(f"[search] No result found for {title!r}")
        return None

    href = result.get("href", "")
    m = re.search(r"/title/(tt\d+)", href)
    if not m:
        print(f"[search] Cannot parse ttID from href={href!r}")
        return None

    tt_id = m.group(1)
    print(f"[search] Found ttID={tt_id} for title={title!r}")
    return tt_id


def scrape_reviews_for_movie(tt_id: str, get_count: int, progress: Dict[str, Any]):
    """
    從 /title/ttID/reviews 抓前 get_count 篇評論，
    更新 progress["reviews"] 與 progress["users"]。
    """
    url = f"https://www.imdb.com/title/{tt_id}/reviews"
    print(f"[reviews] Fetching reviews from {url}")
    resp = SESSION.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"[reviews] HTTP {resp.status_code} for {url}")
        return

    soup = BeautifulSoup(resp.text, "html.parser")

    # 每一個 review 通常在 div.review-container 裡
    containers = soup.select("div.review-container")
    if not containers:
        print(f"[reviews] No review containers found for ttID={tt_id}")
        return

    added = 0
    for container in containers:
        if added >= get_count:
            break

        # user 資訊
        user_link = container.select_one("span.display-name-link a")
        if not user_link:
            continue

        user_name = user_link.get_text(strip=True)
        user_href = user_link.get("href", "")
        um = re.search(r"/user/(ur\d+)", user_href)
        imdb_user_id = um.group(1) if um else user_href

        # 評分
        rating_span = container.select_one("span.rating-other-user-rating span")
        rating = rating_span.get_text(strip=True) if rating_span else ""

        # 日期
        date_span = container.select_one("span.review-date")
        date_text = date_span.get_text(strip=True) if date_span else ""

        # 評論內容
        text_div = container.select_one("div.text.show-more__control") or \
                   container.select_one("div.text")
        comment = text_div.get_text(" ", strip=True) if text_div else ""

        # 用 ttID + user_id + date 當 key 避免重複
        review_key = f"{tt_id}|{imdb_user_id}|{date_text}"

        if review_key in progress["reviews"]:
            # 已存在就跳過
            continue

        review_id = make_id("rev")

        # 先更新 user 表（user_id 就是 IMDb 的 user ID）
        users = progress["users"]
        if imdb_user_id not in users:
            users[imdb_user_id] = {
                "user_id": imdb_user_id,
                "name": user_name
            }

        progress["reviews"][review_key] = {
            "review_id": review_id,
            "movie_imdb_id": tt_id,
            "user_id": imdb_user_id,
            "rating": rating,
            "comment": comment,
            "date": date_text
        }

        added += 1

    print(f"[reviews] Added {added} new reviews for ttID={tt_id}")


def scrape_roles_for_movie(tt_id: str, progress: Dict[str, Any]):
    """
    從 /title/ttID/fullcredits 抓 cast list，
    更新 progress["roles"]。
    """
    url = f"https://www.imdb.com/title/{tt_id}/fullcredits"
    print(f"[roles] Fetching cast from {url}")
    resp = SESSION.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"[roles] HTTP {resp.status_code} for {url}")
        return

    soup = BeautifulSoup(resp.text, "html.parser")
    cast_table = soup.select_one("table.cast_list")
    if not cast_table:
        print(f"[roles] No cast_list table found for ttID={tt_id}")
        return

    roles = progress["roles"]
    added = 0

    # cast_list 通常每一列是 tr，內含 avatar, actor, character 等欄位
    rows = cast_table.select("tr")
    for row in rows:
        actor_cell = row.select_one("td:nth-of-type(2) a")
        character_cell = row.select_one("td.character")

        if not actor_cell or not character_cell:
            continue

        actor_name = actor_cell.get_text(strip=True)
        # 角色欄位可能有多個 <a>，或包含換行，用 get_text(" ", strip=True) 一次整理
        character_name = character_cell.get_text(" ", strip=True)
        # 簡單清掉多餘空白
        character_name = re.sub(r"\s+", " ", character_name).strip()

        if not character_name or not actor_name:
            continue

        role_key = f"{tt_id}|{character_name}|{actor_name}"
        if role_key in roles:
            continue

        role_id = make_id("role")
        roles[role_key] = {
            "role_id": role_id,
            "name": character_name,
            "actor": actor_name,
            "movie_imdb_id": tt_id
        }
        added += 1

    print(f"[roles] Added {added} new roles for ttID={tt_id}")


# ========= CSV 輸出 =========

def write_csvs(progress: Dict[str, Any]):
    """
    根據 progress 內容重建 4 個 CSV：
    movie.csv, review.csv, user.csv, role.csv
    """

    # 建一個 imdb_id -> movie_id 的 map
    imdb_to_movie_id: Dict[str, str] = {}
    movies_rows = []

    for title_norm, m in progress["movies"].items():
        movie_id = m["movie_id"]
        title = m["title"]
        imdb_id = m["imdb_id"]
        imdb_to_movie_id[imdb_id] = movie_id
        movies_rows.append((movie_id, title))

    # movie.csv
    with MOVIE_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["movie_id", "title"])
        writer.writerows(movies_rows)
    print(f"[csv] Wrote {MOVIE_CSV} with {len(movies_rows)} rows")

    # user.csv
    users_rows = []
    for imdb_user_id, u in progress["users"].items():
        users_rows.append((u["user_id"], u["name"]))

    with USER_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["user_id", "name"])
        writer.writerows(users_rows)
    print(f"[csv] Wrote {USER_CSV} with {len(users_rows)} rows")

    # review.csv
    reviews_rows = []
    for key, r in progress["reviews"].items():
        movie_imdb_id = r["movie_imdb_id"]
        movie_id = imdb_to_movie_id.get(movie_imdb_id)
        if not movie_id:
            # 理論上不應發生，如果有就跳過
            continue
        reviews_rows.append((
            r["review_id"],
            r["user_id"],   # IMDb user ID
            movie_id,
            r["rating"],
            r["comment"],
            r["date"],
        ))

    with REVIEW_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["review_id", "user_id", "movie_id", "rating", "comment", "date"])
        writer.writerows(reviews_rows)
    print(f"[csv] Wrote {REVIEW_CSV} with {len(reviews_rows)} rows")

    # role.csv
    roles_rows = []
    for key, r in progress["roles"].items():
        roles_rows.append((
            r["role_id"],
            r["name"],   # 角色名
            r["actor"],  # 演員名
        ))

    with ROLE_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["role_id", "name", "actor"])
        writer.writerows(roles_rows)
    print(f"[csv] Wrote {ROLE_CSV} with {len(roles_rows)} rows")


# ========= 主流程 =========

def main():
    progress = load_progress(PROGRESS_PATH)
    movies = progress["movies"]

    # 讀入原始 CSV 取得所有標題
    df = pd.read_csv(INPUT_CSV)
    if TITLE_COLUMN not in df.columns:
        raise ValueError(f"Column {TITLE_COLUMN!r} not found in {INPUT_CSV}")

    titles = df[TITLE_COLUMN].dropna().tolist()

    for title in (titles[:MAX_MOVIES] if MAX_MOVIES is not None else titles):
        title = str(title)
        title_norm = normalize_title(title)

        # 如果這個 title 已經處理過就跳過
        if title_norm in movies:
            print(f"[main] Skipping already processed movie: {title!r}")
            continue

        # 1. 搜尋 IMDb，取得 ttID
        tt_id = search_imdb_title(title)
        if not tt_id:
            print(f"[main] Cannot find IMDb ID for title={title!r}, skipping.")
            continue

        # 2. 建立 movie 記錄
        movie_id = make_id("mov")
        movies[title_norm] = {
            "movie_id": movie_id,
            "title": title,
            "imdb_id": tt_id
        }

        # 3. 抓評論
        sleep_a_bit()
        scrape_reviews_for_movie(tt_id, GET_REV_COUNT, progress)

        # 4. 抓角色 & 演員
        sleep_a_bit()
        scrape_roles_for_movie(tt_id, progress)

        # 5. 每處理完一部電影就儲存 JSON + 重寫 CSV
        save_progress(PROGRESS_PATH, progress)
        write_csvs(progress)

        # 小休息一下，避免連續打太快
        sleep_a_bit()

    print("[main] All titles processed. Final writing CSVs...")
    write_csvs(progress)
    save_progress(PROGRESS_PATH, progress)
    print("[main] Done.")


if __name__ == "__main__":
    main()
