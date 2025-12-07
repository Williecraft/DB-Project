import csv
import json
import re
import time
import uuid
import random
from pathlib import Path
from typing import Dict, Any
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
import pandas as pd

# ========= 使用者可調變數 =========
INPUT_CSV = "data/kaggle/industry/movies.csv" 
TITLE_COLUMN = "name"           # 哪一欄是電影標題
GET_REV_COUNT = 20               # 每部電影最多抓幾篇評論
GET_ROLE_COUNT = 10                # 每部電影抓幾個主要角色
MAX_MOVIES = 200                # 最多處理幾部電影，避免一次抓太多（可設為 None 不限數量）

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

def _normalize_title(s: str) -> str:
    """簡單 normalization：小寫、移除非字母數字。"""
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s

def search_imdb_id_by_find(title: str) -> str | None:
    """
    用 IMDb /find 頁面，從 __NEXT_DATA__ 的 JSON 中抓出最適合的 titleId。
    找不到就回傳 None。
    """
    # 1. 拼 URL（只查 Title / Feature Film）
    q = quote(title)
    url = f"https://www.imdb.com/find/?q={q}&s=tt&ttype=ft"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    resp = SESSION.get(url, headers=headers, timeout=10)
    resp.raise_for_status()

    # 2. 用 BeautifulSoup 找出 __NEXT_DATA__ script
    soup = BeautifulSoup(resp.text, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if not script or not script.string:
        print("[search] __NEXT_DATA__ not found")
        return None

    # 3. 解析 JSON
    try:
        data = json.loads(script.string)
    except json.JSONDecodeError:
        print("[search] JSON decode error")
        return None

    # 4. 走到 titleResults.results
    page_props = (data.get("props") or {}).get("pageProps") or {}
    title_results = (page_props.get("titleResults") or {}).get("results") or []

    if not title_results:
        print(f"[search] No titleResults for '{title}'")
        return None

    target_norm = _normalize_title(title)
    best_item = None

    for r in title_results:
        item = r.get("listItem") or {}
        cand = item.get("originalTitleText") or item.get("titleText")
        if not cand:
            continue

        cand_norm = _normalize_title(cand)

        # 完全 match（忽略大小寫、標點）直接用這個
        if cand_norm == target_norm:
            best_item = item
            break

        # 否則就先記第一個當備用
        if best_item is None:
            best_item = item

    if not best_item:
        print(f"[search] No suitable match for '{title}'")
        return None

    imdb_id = best_item.get("titleId")
    print(f"[search] Found IMDb ID {imdb_id} for title '{title}' (matched: {best_item.get('originalTitleText') or best_item.get('titleText')})")
    return imdb_id


def scrape_reviews_for_movie(tt_id: str, get_count: int, progress: Dict[str, Any]):
    """
    從 IMDb /title/ttID/reviews 抓前 get_count 篇評論（HTML 版），
    頁面結構：
      - 每篇 review 最外層：<article class="... user-review-item">
      - 評分：span.ipc-rating-star--rating
      - 標題：div[data-testid="review-summary"]
      - 內容：div[data-testid="review-overflow"]
      - 日期：li.review-date
      - 使用者：a[data-testid="author-link"]  (href="/user/urXXXXXXX/")

    寫入 progress["reviews"] 和 progress["users"]。
    """
    url = f"https://www.imdb.com/title/{tt_id}/reviews"
    print(f"[reviews] Fetching reviews from {url}")
    resp = SESSION.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"[reviews] HTTP {resp.status_code} for {url}")
        return

    soup = BeautifulSoup(resp.text, "html.parser")

    # ★ 每篇評論都是一個 article.user-review-item
    articles = soup.select("article.user-review-item")
    if not articles:
        print(f"[reviews] No review <article> found for ttID={tt_id}")
        return

    users = progress["users"]
    reviews_store = progress["reviews"]

    added = 0
    for article in articles[:get_count]:
        # ---- 使用者 ----
        user_link = article.select_one('a[data-testid="author-link"]')
        if not user_link:
            continue

        user_name = user_link.get_text(strip=True)
        href = user_link.get("href", "")
        m = re.search(r"/user/(ur\d+)", href)
        if not m:
            continue
        imdb_user_id = m.group(1)

        # ---- 評分 ----
        rating_span = article.select_one("span.ipc-rating-star--rating")
        rating = rating_span.get_text(strip=True) if rating_span else ""

        # ---- 日期 ----
        date_li = article.select_one("li.review-date")
        date_text = date_li.get_text(strip=True) if date_li else ""

        # ---- 內容 ----
        content_div = article.select_one('div[data-testid="review-overflow"]')
        comment = content_div.get_text(" ", strip=True) if content_div else ""

        # （可選）標題，如果你之後想用得到
        # summary_div = article.select_one('[data-testid="review-summary"]')
        # title_text = summary_div.get_text(" ", strip=True) if summary_div else ""

        # ---- 去重 key：ttID + user + date ----
        review_key = f"{tt_id}|{imdb_user_id}|{date_text}"
        if review_key in reviews_store:
            continue

        review_id = make_id("rev")

        # 更新 user 表（用 IMDb user id 當 user_id）
        if imdb_user_id not in users:
            users[imdb_user_id] = {
                "user_id": imdb_user_id,
                "name": user_name
            }

        reviews_store[review_key] = {
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
    從新版 IMDb /title/ttID/fullcredits 的 __NEXT_DATA__ JSON 抓 Cast，
    只取前 GET_ROLE_COUNT 個主要角色，更新 progress["roles"]。
    每一筆 roles 存成：
      - role_id: 自動產生
      - name: 角色名稱
      - actor: 演員名稱
      - movie_imdb_id: ttID（之後寫 CSV 用）
    """
    url = f"https://www.imdb.com/title/{tt_id}/fullcredits"
    print(f"[roles] Fetching cast from {url}")
    resp = SESSION.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"[roles] HTTP {resp.status_code} for {url}")
        return

    soup = BeautifulSoup(resp.text, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if not script or not script.string:
        print(f"[roles] __NEXT_DATA__ not found for ttID={tt_id}")
        return

    try:
        data = json.loads(script.string)
    except json.JSONDecodeError:
        print(f"[roles] JSON decode error for ttID={tt_id}")
        return

    # 走到 contentData.categories，找 name == "Cast" 的那一組
    content_data = (
        data.get("props", {})
            .get("pageProps", {})
            .get("contentData", {})
    )
    categories = content_data.get("categories") or []
    cast_cat = None
    for cat in categories:
        if cat.get("name") == "Cast":
            cast_cat = cat
            break

    if not cast_cat:
        print(f"[roles] Cast category not found in JSON for ttID={tt_id}")
        return

    section = cast_cat.get("section") or {}
    items = section.get("items") or []
    if not items:
        print(f"[roles] Cast items empty for ttID={tt_id}")
        return

    roles = progress["roles"]
    added = 0

    # 只取前 GET_ROLE_COUNT 個 cast item
    for item in items:
        if added >= GET_ROLE_COUNT:
            break

        actor_name = (item.get("rowTitle") or "").strip()
        if not actor_name:
            continue

        characters = item.get("characters") or []
        if not characters:
            # 沒標角色名就略過
            continue

        for char in characters:
            character_name = (char or "").strip()
            if not character_name:
                continue

            # 用 ttID + 角色名 + 演員名 當 key，避免重複
            role_key = f"{tt_id}|{character_name}|{actor_name}"
            if role_key in roles:
                continue

            role_id = make_id("role")
            roles[role_key] = {
                "role_id": role_id,
                "name": character_name,
                "actor": actor_name,
                "movie_imdb_id": tt_id,
            }
            added += 1

            if added >= GET_ROLE_COUNT:
                break

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
        tt_id = search_imdb_id_by_find(title)
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
