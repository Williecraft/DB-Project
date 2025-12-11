import csv
import json
import re
import time
import uuid
import random
from pathlib import Path
from typing import Dict, Any, List, Tuple
from urllib.parse import quote
from datetime import date, datetime, timedelta

import requests
from bs4 import BeautifulSoup
import pandas as pd


# ========== 使用者可調變數 ==========

# 1. 輸入：哪一個 CSV、有哪一欄是 title
INPUT_TITLES_CSV = "data/kaggle/industry/movies.csv"
TITLE_COLUMN = "name"

# 2. IMDb 爬蟲設定
GET_REV_COUNT = 20       # 每部電影最多抓幾篇評論
GET_ROLE_COUNT = 10      # 每部電影最多抓幾個 cast
MAX_MOVIES = 200         # 最多成功處理幾部電影（用 while 計數器）

REQUEST_SLEEP_RANGE = (1.0, 3.0)

# 3. Kaggle 資料集位置
INDUSTRY_CSV = "data/kaggle/industry/movies.csv"
ACTORS_SOURCE_CSV = "data/kaggle/actors/names.csv"

# 4. 輸出資料夾
OUT_DIR = Path("data/generated")
OUT_DIR.mkdir(parents=True, exist_ok=True)

PROGRESS_PATH = OUT_DIR / "progress.json"
MOVIE_OUT = OUT_DIR / "movie.csv"
DIRECTOR_OUT = OUT_DIR / "director.csv"
COMPANY_OUT = OUT_DIR / "company.csv"
ACTOR_OUT = OUT_DIR / "actor.csv"
ROLE_OUT = OUT_DIR / "role.csv"
GENRE_OUT = OUT_DIR / "genre.csv"
USER_OUT = OUT_DIR / "user.csv"
REVIEW_OUT = OUT_DIR / "review.csv"


# ========== HTTP Session ==========

SESSION = requests.Session()
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ========== 小工具們 ==========

def sleep_a_bit():
    time.sleep(random.uniform(*REQUEST_SLEEP_RANGE))


def make_id(prefix: str) -> str:
    """產生短 UID，用在各種主鍵（varchar）。"""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def make_deterministic_id(prefix: str, key: str) -> str:
    """同一個 key 會產生同樣 ID（適合 director/company/genre）。"""
    import hashlib
    h = hashlib.md5(str(key).encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{h}"


def normalize_title_for_match(title: str) -> str:
    """用於 IMDb find 結果比對的簡單 normalizer。"""
    s = title.lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def truncate(s: str, max_len: int) -> str:
    s = s or ""
    return s[:max_len]

def load_progress() -> Dict[str, Any]:
    """
    若 progress.json 存在，載入並還原成內部用的結構；
    否則回傳一個空的樣板。
    """
    if not PROGRESS_PATH.exists():
        return {
            "movies": {},            # tt_id -> movie_row
            "directors": {},         # name -> director_row
            "companies": {},         # name -> company_row
            "genres": {},            # name -> genre_row
            "actors": {},            # name -> actor_row
            "roles": [],             # list of role_row
            "users": {},             # imdb_user_id -> {user_id,name}
            "reviews": [],           # list of review_row
            "seen_movie_ids": [],    # list of tt_id
            "title_index": 0,        # 目前跑到 titles_list 的第幾個 index
        }

    with PROGRESS_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # 確保類型正確
    data.setdefault("movies", {})
    data.setdefault("directors", {})
    data.setdefault("companies", {})
    data.setdefault("genres", {})
    data.setdefault("actors", {})
    data.setdefault("roles", [])
    data.setdefault("users", {})
    data.setdefault("reviews", [])
    data.setdefault("seen_movie_ids", [])
    data.setdefault("title_index", 0)

    return data


def save_progress(progress: Dict[str, Any]) -> None:
    """
    把目前進度寫回 progress.json。
    set / dict 之類先轉成 JSON 可以吃的型態。
    """
    # 不能存 set，所以手動處理
    to_dump = dict(progress)
    if isinstance(to_dump.get("seen_movie_ids"), set):
        to_dump["seen_movie_ids"] = list(to_dump["seen_movie_ids"])

    with PROGRESS_PATH.open("w", encoding="utf-8") as f:
        json.dump(to_dump, f, ensure_ascii=False, indent=2)


# ========== IMDb /find 搜尋 ttID ==========

def search_imdb_id_by_find(title: str) -> str | None:
    """
    用 IMDb /find 頁面，從 __NEXT_DATA__ 的 JSON 中抓 titleId。
    找不到就回傳 None。
    """
    q = quote(title)
    url = f"https://www.imdb.com/find/?q={q}&s=tt&ttype=ft"

    resp = SESSION.get(url, headers=HEADERS, timeout=10)
    if resp.status_code != 200:
        print(f"[search] HTTP {resp.status_code} for {url}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if not script or not script.string:
        print(f"[search] __NEXT_DATA__ not found for title={title!r}")
        return None

    try:
        data = json.loads(script.string)
    except json.JSONDecodeError:
        print(f"[search] JSON decode error for title={title!r}")
        return None

    page_props = (data.get("props") or {}).get("pageProps") or {}
    title_results = (page_props.get("titleResults") or {}).get("results") or []

    if not title_results:
        print(f"[search] No titleResults for '{title}'")
        return None

    target_norm = normalize_title_for_match(title)
    best_item = None

    for r in title_results:
        item = r.get("listItem") or {}
        cand = item.get("originalTitleText") or item.get("titleText")
        if not cand:
            continue

        cand_norm = normalize_title_for_match(cand)
        if cand_norm == target_norm:
            best_item = item
            break
        if best_item is None:
            best_item = item

    if not best_item:
        print(f"[search] No suitable match for '{title}'")
        return None

    imdb_id = best_item.get("titleId")
    print(f"[search] '{title}' -> {imdb_id}")
    return imdb_id


# ========== IMDb Reviews 爬蟲 ==========

def parse_review_date(date_text: str) -> str | None:
    """
    把 'Apr 8, 2007' 轉成 'YYYY-MM-DD HH:MM:SS' 的字串。
    若無法解析，回傳 None。
    """
    try:
        dt = datetime.strptime(date_text.strip(), "%b %d, %Y")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def scrape_reviews_for_movie(tt_id: str, get_count: int) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """
    回傳 (users_map, reviews_map)：
      users_map: imdb_user_id -> {user_id, name}
      reviews_map: review_id -> review_row(dict)
    """
    url = f"https://www.imdb.com/title/{tt_id}/reviews"
    print(f"[reviews] Fetching reviews from {url}")
    resp = SESSION.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"[reviews] HTTP {resp.status_code} for {url}")
        return {}, {}

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = soup.select("article.user-review-item")
    if not articles:
        print(f"[reviews] No review <article> found for ttID={tt_id}")
        return {}, {}

    users: Dict[str, Dict[str, Any]] = {}
    reviews: Dict[str, Dict[str, Any]] = {}
    count = 0

    for article in articles:
        if count >= get_count:
            break

        # user
        user_link = article.select_one('a[data-testid="author-link"]')
        if not user_link:
            continue

        user_name = user_link.get_text(strip=True)
        href = user_link.get("href", "")
        m = re.search(r"/user/(ur\d+)", href)
        if not m:
            continue
        imdb_user_id = m.group(1)

        rating_span = article.select_one("span.ipc-rating-star--rating")
        rating_text = rating_span.get_text(strip=True) if rating_span else ""
        try:
            rating = int(rating_text)
        except Exception:
            continue  # rating 不合法就略過

        date_li = article.select_one("li.review-date")
        date_text = date_li.get_text(strip=True) if date_li else ""
        date_iso = parse_review_date(date_text)
        if not date_iso:
            continue

        content_div = article.select_one('div[data-testid="review-overflow"]')
        comment = content_div.get_text(" ", strip=True) if content_div else ""
        if not comment:
            continue

        # 轉換換行
        comment = comment.replace("\r\n", "\\n").replace("\n", "\\n")

        review_id = make_id("rev")

        # user_map
        if imdb_user_id not in users:
            users[imdb_user_id] = {
                "user_id": imdb_user_id,
                "name": user_name,
            }

        reviews[review_id] = {
            "review_id": review_id,
            "user_id": imdb_user_id,
            "movie_id": tt_id,
            "rating": rating,
            "comment": comment,
            "date": date_iso,
        }

        count += 1

    print(f"[reviews] {tt_id} -> {len(reviews)} reviews")
    return users, reviews


# ========== IMDb fullcredits (Cast / Roles) 爬蟲 ==========

def scrape_roles_for_movie(tt_id: str, get_count: int) -> List[Tuple[str, str]]:
    """
    從 fullcredits 的 JSON 抓前 get_count 個 cast，
    回傳 [(role_name, actor_name), ...]
    """
    url = f"https://www.imdb.com/title/{tt_id}/fullcredits"
    print(f"[roles] Fetching cast from {url}")
    resp = SESSION.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"[roles] HTTP {resp.status_code} for {url}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if not script or not script.string:
        print(f"[roles] __NEXT_DATA__ not found for ttID={tt_id}")
        return []

    try:
        data = json.loads(script.string)
    except json.JSONDecodeError:
        print(f"[roles] JSON decode error for ttID={tt_id}")
        return []

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
        return []

    section = cast_cat.get("section") or {}
    items = section.get("items") or []
    if not items:
        print(f"[roles] Cast items empty for ttID={tt_id}")
        return []

    out: List[Tuple[str, str]] = []
    for item in items:
        if len(out) >= get_count:
            break

        actor_name = (item.get("rowTitle") or "").strip()
        if not actor_name:
            continue
        characters = item.get("characters") or []
        if not characters:
            continue

        for ch in characters:
            role_name = (ch or "").strip()
            if not role_name:
                continue
            out.append((role_name, actor_name))
            if len(out) >= get_count:
                break

    print(f"[roles] {tt_id} -> {len(out)} roles")
    return out


# ========== 讀取 Kaggle industry / actors ==========

def load_industry_df() -> pd.DataFrame:
    df = pd.read_csv(INDUSTRY_CSV)
    return df


def load_actors_source_df() -> pd.DataFrame:
    df = pd.read_csv(ACTORS_SOURCE_CSV)
    df["primaryName_clean"] = df["primaryName"].astype(str).str.strip()
    return df


# ========== Movie / Director / Company / Genre 建立 ==========

NATIONALITY_CODES = ["US", "UK", "FR", "DE", "JP", "TW", "KR", "IT", "ES", "CA"]


def random_nationality() -> str:
    return random.choice(NATIONALITY_CODES)


def random_year(start: int = 1940, end: int = 2010) -> int:
    return random.randint(start, end)


def map_country_to_code(country: str) -> str:
    if not country:
        return random_nationality()
    c = country.lower()
    if "united states" in c or "usa" in c or "u.s.a" in c:
        return "US"
    if "united kingdom" in c or "uk" in c or "england" in c:
        return "UK"
    if "france" in c:
        return "FR"
    if "germany" in c:
        return "DE"
    if "japan" in c:
        return "JP"
    if "korea" in c:
        return "KR"
    if "taiwan" in c:
        return "TW"
    if "italy" in c:
        return "IT"
    if "spain" in c:
        return "ES"
    if "canada" in c:
        return "CA"
    return random_nationality()


def build_movie_and_related_from_industry(
    tt_id: str,
    title: str,
    ind_df: pd.DataFrame,
    director_by_name: Dict[str, Dict[str, Any]],
    company_by_name: Dict[str, Dict[str, Any]],
    genre_by_name: Dict[str, Dict[str, Any]],
) -> Dict[str, Any] | None:
    """
    根據 title 從 industry df 找一筆 row 來填 movie / director / company / genre。
    若找不到或缺重大欄位就回傳 None（此 movie 放棄）。
    """
    # 先用 title 完整 match（大小寫敏感度依你需求）
    cand = ind_df[ind_df["name"] == title]
    if cand.empty:
        # 再試一次忽略大小寫
        cand = ind_df[ind_df["name"].str.lower() == title.lower()]

    if cand.empty:
        print(f"[industry] No industry row for title={title!r}, skip movie {tt_id}")
        return None

    # 若有多筆（如 Friday the 13th），取年份最早的那筆
    cand = cand.sort_values(by="year", ascending=True).iloc[0]

    year = cand.get("year")
    runtime = cand.get("runtime")
    country = cand.get("country")
    director_name = str(cand.get("director") or "").strip()
    company_name = str(cand.get("company") or "").strip()
    genre_str = str(cand.get("genre") or "").strip()

    if pd.isna(year) or pd.isna(runtime) or not country or not director_name:
        print(f"[industry] Incomplete data for title={title!r}, skip movie {tt_id}")
        return None

    # director
    if director_name not in director_by_name:
        director_id = make_deterministic_id("dir", director_name)
        birth_year = random_year(1940, 1990)
        nat = map_country_to_code(country)
        director_by_name[director_name] = {
            "director_id": director_id,
            "name": truncate(director_name, 30),
            "birth_year": birth_year,
            "nationality": nat,
        }
    director_id = director_by_name[director_name]["director_id"]

    # company
    if company_name:
        if company_name not in company_by_name:
            company_id = make_deterministic_id("com", company_name)
            founded_year = random_year(1900, int(year))
            comp_country = map_country_to_code(country)
            company_by_name[company_name] = {
                "company_id": company_id,
                "name": truncate(company_name, 30),
                "founded_year": founded_year,
                "country": comp_country,
            }

    # genre(s)
    if genre_str:
        for g in genre_str.split(","):
            g = g.strip()
            if not g:
                continue
            if g not in genre_by_name:
                gid = make_deterministic_id("gen", g)
                genre_by_name[g] = {
                    "genre_id": gid,
                    "name": truncate(g, 15),
                }

    # movie row
    movie_row = {
        "movie_id": tt_id,
        "director_id": director_id,
        "title": truncate(title, 30),
        "release_year": int(year),
        "duration": int(runtime),
        "language": "En",                       # 沒有語言就預設英文
        "country": truncate(str(country), 15),
    }
    return movie_row


# ========== Actor & Role 建立 ==========

def infer_gender_from_profession(prof: str) -> str:
    p = (prof or "").lower()
    if "actress" in p:
        return "F"
    if "actor" in p:
        return "M"
    return random.choice(["M", "F"])


def build_actor_from_name(
    name: str,
    actors_source: pd.DataFrame,
    actor_by_name: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    給一個演員名字：
    - 若 actor_by_name 已有，直接回傳
    - 否則試著用 Kaggle actors match name
    - 找不到就隨機生一個
    """
    clean = name.strip()
    if clean in actor_by_name:
        return actor_by_name[clean]

    # 用 Kaggle actors match
    subset = actors_source[actors_source["primaryName_clean"] == clean]
    if not subset.empty:
        row = subset.iloc[0]

        # actor_id 直接用 nconst
        actor_id = row["nconst"]

        # 處理 birthYear 可能是 NaN 或字串 "\N"
        raw_birth = row.get("birthYear")
        birth_str = str(raw_birth).strip()
        if not birth_str or birth_str in ("\\N", "nan", "NaN"):
            birth_year = random_year(1940, 2005)
        else:
            try:
                birth_year = int(float(birth_str))
            except ValueError:
                birth_year = random_year(1940, 2005)

        # nationality：IMDb / Kaggle 沒有，就隨機一個合規值
        nationality = random_nationality()

        # 性別從 primaryProfession 推，推不到就隨機
        prof = str(row.get("primaryProfession") or "")
        gender = infer_gender_from_profession(prof)

    else:
        # Kaggle 找不到這個人，就全隨機
        actor_id = make_deterministic_id("act", clean)
        birth_year = random_year(1940, 2005)
        nationality = random_nationality()
        gender = random.choice(["M", "F"])

    actor = {
        "actor_id": actor_id,
        "name": truncate(clean, 30),
        "birth_year": birth_year,
        "nationality": nationality,
        "gender": gender,
    }
    actor_by_name[clean] = actor
    return actor



# ========== User 假資料生成 ==========

EMAIL_DOMAINS = ["example.com", "mail.com", "moviefans.com", "imdbuser.net"]


def make_email(user_id: str, name: str, used_emails: set) -> str:
    local = re.sub(r"[^a-z0-9]+", "", name.lower()) or "user"
    digits = "".join(re.findall(r"\d+", user_id))
    base = f"{local}{digits}" if digits else local

    while True:
        suffix = random.randint(10, 99)
        domain = random.choice(EMAIL_DOMAINS)
        email = f"{base}{suffix}@{domain}"
        if email not in used_emails:
            used_emails.add(email)
            return email


def generate_birth_and_join(age: int) -> Tuple[date, date]:
    today = date.today()
    birth_year = today.year - age
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    birth_date = date(birth_year, month, day)
    delta_days = (today - birth_date).days
    if delta_days <= 0:
        join_date = today
    else:
        offset = random.randint(0, delta_days)
        join_date = birth_date + timedelta(days=offset)
    return birth_date, join_date


def build_user_rows_from_scraped_users(users_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    將 IMDb user (user_id, name) 補上 email, join_date, age。
    """
    MIN_AGE = 13
    MAX_AGE = 80
    used_emails: set = set()
    out_rows = []
    for imdb_user_id, u in users_map.items():
        name = u["name"] or "user"
        name = truncate(name, 10)
        age = random.randint(MIN_AGE, MAX_AGE)
        _, join_date = generate_birth_and_join(age)
        email = make_email(imdb_user_id, name, used_emails)
        out_rows.append({
            "user_id": imdb_user_id,
            "name": name,
            "email": email,
            "join_date": join_date.isoformat(),
            "age": age,
        })
    return out_rows


# ========== 主流程 ==========

def main():
    # 載入 Kaggle Dataset
    ind_df = load_industry_df()
    actors_source = load_actors_source_df()

    # 讀 input titles
    titles_df = pd.read_csv(INPUT_TITLES_CSV)
    if TITLE_COLUMN not in titles_df.columns:
        raise ValueError(f"Column {TITLE_COLUMN!r} not found in {INPUT_TITLES_CSV}")
    titles_list = [str(t) for t in titles_df[TITLE_COLUMN].dropna().tolist()]

    # ===== 讀取 / 初始化 progress =====
    progress = load_progress()

    movies: Dict[str, Dict[str, Any]] = progress["movies"]
    directors_by_name: Dict[str, Dict[str, Any]] = progress["directors"]
    companies_by_name: Dict[str, Dict[str, Any]] = progress["companies"]
    genres_by_name: Dict[str, Dict[str, Any]] = progress["genres"]

    actors_by_name: Dict[str, Dict[str, Any]] = progress["actors"]
    roles_rows: List[Dict[str, Any]] = progress["roles"]

    users_all: Dict[str, Dict[str, Any]] = progress["users"]
    reviews_rows: List[Dict[str, Any]] = progress["reviews"]

    seen_movie_ids: set = set(progress.get("seen_movie_ids", []))
    idx: int = int(progress.get("title_index", 0))
    processed_movies = len(movies)

    print(f"[progress] Loaded progress: {processed_movies} movies, next title index = {idx}")

    # ===== 主要爬蟲迴圈 =====
    while processed_movies < MAX_MOVIES and idx < len(titles_list):
        title = titles_list[idx]
        idx += 1  # 下次從下一個 title 開始

        # 1. 先找 IMDb ID
        tt_id = search_imdb_id_by_find(title)
        if not tt_id:
            # 更新 progress 中的 title_index（即使這部失敗，下次也不要重複試）
            progress["title_index"] = idx
            save_progress(progress)
            continue

        # 已處理過的 ttID 就略過
        if tt_id in seen_movie_ids:
            print(f"[main] Duplicate ttID {tt_id}, skip")
            progress["title_index"] = idx
            save_progress(progress)
            continue

        # 2. industry 要有這部電影，才能建 movie
        movie_row = build_movie_and_related_from_industry(
            tt_id=tt_id,
            title=title,
            ind_df=ind_df,
            director_by_name=directors_by_name,
            company_by_name=companies_by_name,
            genre_by_name=genres_by_name,
        )
        if movie_row is None:
            # 這部電影資料不夠 → 略過
            progress["title_index"] = idx
            save_progress(progress)
            continue

        # 3. 抓 reviews
        sleep_a_bit()
        users_map, reviews_map = scrape_reviews_for_movie(tt_id, GET_REV_COUNT)

        # 4. 抓 roles & actors
        sleep_a_bit()
        roles = scrape_roles_for_movie(tt_id, GET_ROLE_COUNT)

        # 把 roles 用來建 actor.csv & role.csv（role.csv 只存 role_id, name）
        for role_name, actor_name in roles:
            actor = build_actor_from_name(actor_name, actors_source, actors_by_name)
            role_id = make_id("role")
            roles_rows.append({
                "role_id": role_id,
                "name": truncate(role_name, 30),
            })

        # 5. 累積 user / review
        for uid, u in users_map.items():
            if uid not in users_all:
                users_all[uid] = u

        for _rid, r in reviews_map.items():
            reviews_rows.append(r)

        # 6. 累積 movie
        movies[tt_id] = movie_row
        seen_movie_ids.add(tt_id)
        processed_movies += 1
        print(f"[main] Processed movies: {processed_movies}/{MAX_MOVIES}")

        # 7. 更新 progress 並存檔（★ 這裡是關鍵：每部電影存一次）
        progress["movies"] = movies
        progress["directors"] = directors_by_name
        progress["companies"] = companies_by_name
        progress["genres"] = genres_by_name
        progress["actors"] = actors_by_name
        progress["roles"] = roles_rows
        progress["users"] = users_all
        progress["reviews"] = reviews_rows
        progress["seen_movie_ids"] = list(seen_movie_ids)
        progress["title_index"] = idx

        save_progress(progress)

        sleep_a_bit()

    # ===== 全部電影處理完後，一次性寫出 8 個 CSV =====

    # 1. movie.csv
    with MOVIE_OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "movie_id",
            "director_id",
            "title",
            "release_year",
            "duration",
            "language",
            "country",
        ])
        for m in movies.values():
            writer.writerow([
                m["movie_id"],
                m["director_id"],
                m["title"],
                m["release_year"],
                m["duration"],
                m["language"],
                m["country"],
            ])
    print(f"[out] {MOVIE_OUT} ({len(movies)} rows)")

    # 2. director.csv
    with DIRECTOR_OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["director_id", "name", "birth_year", "nationality"])
        for d in directors_by_name.values():
            writer.writerow([
                d["director_id"],
                d["name"],
                d["birth_year"],
                d["nationality"],
            ])
    print(f"[out] {DIRECTOR_OUT} ({len(directors_by_name)} rows)")

    # 3. company.csv
    with COMPANY_OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["company_id", "name", "founded_year", "country"])
        for c in companies_by_name.values():
            writer.writerow([
                c["company_id"],
                c["name"],
                c["founded_year"],
                c["country"],
            ])
    print(f"[out] {COMPANY_OUT} ({len(companies_by_name)} rows)")

    # 4. actor.csv
    with ACTOR_OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["actor_id", "name", "birth_year", "nationality", "gender"])
        for a in actors_by_name.values():
            writer.writerow([
                a["actor_id"],
                a["name"],
                a["birth_year"],
                a["nationality"],
                a["gender"],
            ])
    print(f"[out] {ACTOR_OUT} ({len(actors_by_name)} rows)")

    # 5. role.csv
    with ROLE_OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["role_id", "name"])
        for r in roles_rows:
            writer.writerow([r["role_id"], r["name"]])
    print(f"[out] {ROLE_OUT} ({len(roles_rows)} rows)")

    # 6. genre.csv
    with GENRE_OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["genre_id", "name"])
        for g in genres_by_name.values():
            writer.writerow([g["genre_id"], g["name"]])
    print(f"[out] {GENRE_OUT} ({len(genres_by_name)} rows)")

    # 7. user.csv（從 IMDb user + 假資料補全）
    user_rows = build_user_rows_from_scraped_users(users_all)
    with USER_OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["user_id", "name", "email", "join_date", "age"])
        for u in user_rows:
            writer.writerow([
                u["user_id"],
                u["name"],
                u["email"],
                u["join_date"],
                u["age"],
            ])
    print(f"[out] {USER_OUT} ({len(user_rows)} rows)")

    # 8. review.csv
    with REVIEW_OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["review_id", "user_id", "movie_id", "rating", "comment", "date"])
        for r in reviews_rows:
            writer.writerow([
                r["review_id"],
                r["user_id"],
                r["movie_id"],
                r["rating"],
                r["comment"],
                r["date"],
            ])
    print(f"[out] {REVIEW_OUT} ({len(reviews_rows)} rows)")

    # 全部輸出完成，progress.json 就可以刪掉
    if PROGRESS_PATH.exists():
        PROGRESS_PATH.unlink()
        print(f"[progress] Removed {PROGRESS_PATH}")

    print("[main] All done.")



if __name__ == "__main__":
    main()
