import pandas as pd
from pathlib import Path
import hashlib


# ========== 路徑設定（視需要自行調整） ==========
FOLDER = "data/generated/"
MOVIE_CSV = Path(FOLDER+"movie.csv")
REVIEW_CSV = Path(FOLDER+"review.csv")
ROLE_CSV = Path(FOLDER+"role.csv")
USER_F_CSV = Path(FOLDER+"user_f.csv")

INDUSTRY_CSV = Path("data/kaggle/industry/movies.csv")   # Movie Industry 資料集
ACTORS_SOURCE_CSV = Path("data/kaggle/actors/names.csv")  # Kaggle actors 資料集


# ========== 小工具：穩定的 ID 產生器（同一 key 產生相同 id） ==========
def make_deterministic_id(prefix: str, key: str) -> str:
    h = hashlib.md5(str(key).encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{h}"


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"找不到檔案: {path}")
    return pd.read_csv(path)


# ========== Director ==========
def build_director_real(industry_path: Path, out_path: Path) -> dict:
    df_ind = load_csv(industry_path)

    if "director" not in df_ind.columns:
        raise ValueError("industry.csv 缺少 'director' 欄位")

    directors = sorted(set(str(x).strip() for x in df_ind["director"].dropna()))
    records = []
    name_to_id = {}

    for name in directors:
        if not name:
            continue
        did = make_deterministic_id("dir", name)
        name_to_id[name] = did
        records.append({
            "director_id": did,
            "name": name,
            # birth_year, nationality 屬於❌資料，先不做
        })

    df_dir = pd.DataFrame(records)
    df_dir.to_csv(out_path, index=False)
    print(f"[director] 寫出 {out_path} ({len(df_dir)} 筆)")

    return name_to_id


# ========== Company ==========
def build_company_real(industry_path: Path, out_path: Path):
    df_ind = load_csv(industry_path)

    if "company" not in df_ind.columns:
        raise ValueError("industry.csv 缺少 'company' 欄位")

    companies = sorted(set(str(x).strip() for x in df_ind["company"].dropna()))
    records = []
    for name in companies:
        if not name:
            continue
        cid = make_deterministic_id("com", name)
        records.append({
            "company_id": cid,
            "name": name,
            # founded_year, country 屬於❌，先不做
        })

    df_comp = pd.DataFrame(records)
    df_comp.to_csv(out_path, index=False)
    print(f"[company] 寫出 {out_path} ({len(df_comp)} 筆)")


# ========== Genre ==========
def build_genre_real(industry_path: Path, out_path: Path):
    df_ind = load_csv(industry_path)

    if "genre" not in df_ind.columns:
        raise ValueError("industry.csv 缺少 'genre' 欄位")

    genres_set = set()
    for val in df_ind["genre"].dropna():
        for g in str(val).split(","):
            g = g.strip()
            if g:
                genres_set.add(g)

    records = []
    for name in sorted(genres_set):
        gid = make_deterministic_id("gen", name)
        records.append({"genre_id": gid, "name": name})

    df_gen = pd.DataFrame(records)
    df_gen.to_csv(out_path, index=False)
    print(f"[genre] 寫出 {out_path} ({len(df_gen)} 筆)")


# ========== Movie ==========
def build_movie_real(movie_path: Path,
                     industry_path: Path,
                     director_map: dict,
                     out_path: Path):
    df_movie = load_csv(movie_path)
    df_ind = load_csv(industry_path)

    if "title" not in df_movie.columns:
        raise ValueError("movie.csv 缺少 'title' 欄位")
    if "name" not in df_ind.columns:
        raise ValueError("industry.csv 缺少 'name' 欄位(電影名稱)")

    # 以 title (movie.csv) 對應 industry 的 name
    df = df_movie.merge(
        df_ind,
        left_on="title",
        right_on="name",
        how="left",
        suffixes=("", "_ind")
    )

    # 準備輸出欄位 (只做🟡部分)
    out = pd.DataFrame()
    out["movie_id"] = df["movie_id"]
    out["title"] = df["title"]

    if "year" in df.columns:
        out["release_year"] = df["year"]
    else:
        out["release_year"] = pd.NA

    if "runtime" in df.columns:
        out["duration"] = df["runtime"].astype("Int64")
    else:
        out["duration"] = pd.NA

    # language 在資料集中沒有，先統一設成 'En'（如果你之前把它標成❌，也可以事後刪掉）
    out["language"] = "En"

    if "country" in df.columns:
        out["country"] = df["country"]
    else:
        out["country"] = pd.NA

    # 對 director 產生 director_id（如果有對應 map）
    if "director" in df.columns and director_map:
        out["director_id"] = (
            df["director"]
            .astype(str)
            .str.strip()
            .map(director_map)
        )
    else:
        out["director_id"] = pd.NA

    out.to_csv(out_path, index=False)
    print(f"[movie] 寫出 {out_path} ({len(out)} 筆)")


# ========== Actor & Role ==========
def build_actor_and_role_real(role_path: Path,
                              actors_source_path: Path,
                              out_actor_path: Path,
                              out_role_path: Path):
    df_role = load_csv(role_path)
    df_src = load_csv(actors_source_path)

    # 檢查欄位
    required_cols = {"nconst", "primaryName"}
    if not required_cols.issubset(df_src.columns):
        raise ValueError("actors.csv 需要至少包含欄位: nconst, primaryName")

    if "actor" not in df_role.columns:
        raise ValueError("role.csv 需要有 'actor' 欄位 (演員名稱)")

    # 建立 name -> source row 的 lookup
    df_src["primaryName_clean"] = df_src["primaryName"].astype(str).str.strip()
    actor_lookup = (
        df_src
        .drop_duplicates("primaryName_clean")
        .set_index("primaryName_clean")
    )

    records = []
    name_to_id = {}

    for raw_name in df_role["actor"].astype(str):
        name = raw_name.strip()
        if not name:
            continue
        if name in name_to_id:
            continue

        if name in actor_lookup.index:
            row = actor_lookup.loc[name]
            actor_id = row["nconst"]
            birth_year = row.get("birthYear", pd.NA)
            death_year = row.get("deathYear", pd.NA)
            primary_profession = row.get("primaryProfession", pd.NA)
            known_for_titles = row.get("knownForTitles", pd.NA)
        else:
            # 找不到就用 deterministic id，其他欄位先留空
            actor_id = make_deterministic_id("act", name)
            birth_year = pd.NA
            death_year = pd.NA
            primary_profession = pd.NA
            known_for_titles = pd.NA

        name_to_id[name] = actor_id
        records.append({
            "actor_id": actor_id,
            "name": name,
            "birth_year": birth_year,
            "death_year": death_year,
            "primary_profession": primary_profession,
            "known_for_titles": known_for_titles,
        })

    df_actor_real = pd.DataFrame(records)
    df_actor_real.to_csv(out_actor_path, index=False)
    print(f"[actor] 寫出 {out_actor_path} ({len(df_actor_real)} 筆)")

    # 在 role 加上一個 actor_id 欄位，依照 actor 名稱對應
    df_role["actor_id"] = (
        df_role["actor"]
        .astype(str)
        .str.strip()
        .map(name_to_id)
    )
    df_role.to_csv(out_role_path, index=False)
    print(f"[role] 寫出 {out_role_path} ({len(df_role)} 筆，已加入 actor_id)")


# ========== main ==========
def main():
    # 1. Director
    director_map = build_director_real(
        industry_path=INDUSTRY_CSV,
        out_path=Path(FOLDER+"director_real.csv"),
    )

    # 2. Company
    build_company_real(
        industry_path=INDUSTRY_CSV,
        out_path=Path(FOLDER+"company_real.csv"),
    )

    # 3. Genre
    build_genre_real(
        industry_path=INDUSTRY_CSV,
        out_path=Path(FOLDER+"genre_real.csv"),
    )

    # 4. Movie (用 movie.csv + industry.csv + director_map)
    build_movie_real(
        movie_path=MOVIE_CSV,
        industry_path=INDUSTRY_CSV,
        director_map=director_map,
        out_path=Path(FOLDER+"movie_real.csv"),
    )

    # 5. Actor & Role (actor_real.csv + role_real.csv)
    build_actor_and_role_real(
        role_path=ROLE_CSV,
        actors_source_path=ACTORS_SOURCE_CSV,
        out_actor_path=Path(FOLDER+"actor_real.csv"),
        out_role_path=Path(FOLDER+"role_real.csv"),
    )

    print("全部實體表 (🟡 部分) 產生完成。")


if __name__ == "__main__":
    main()
