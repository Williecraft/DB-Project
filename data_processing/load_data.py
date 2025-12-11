# load_data.py
import sqlite3
import csv
from pathlib import Path

# ===== 全域設定 =====
DB_PATH = "db_project.db"

TABLE_DIR = Path("data/generated")

MOVIE_CSV = TABLE_DIR / "movie.csv"
DIRECTOR_CSV = TABLE_DIR / "director.csv"
COMPANY_CSV = TABLE_DIR / "company.csv"
ACTOR_CSV = TABLE_DIR / "actor.csv"
ROLE_CSV = TABLE_DIR / "role.csv"
GENRE_CSV = TABLE_DIR / "genre.csv"
USER_CSV = TABLE_DIR / "user.csv"
REVIEW_CSV = TABLE_DIR / "review.csv"


def insert_csv(conn, table, csv_path, columns, extra_values=None):
    """
    columns: 要插入的欄位順序（list）
    extra_values: {欄位名: 固定值}，例如 User.password = "1234"
    """
    extra_values = extra_values or {}

    placeholders = ", ".join(["?"] * len(columns))
    col_names = ", ".join(columns)
    sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"

    print(f"\n=== 插入 {table}，來源檔案：{csv_path} ===")
    inserted = 0
    skipped = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            values = []
            for col in columns:
                if col in extra_values:
                    values.append(extra_values[col])
                else:
                    val = row.get(col)
                    values.append(val)
            try:
                conn.execute(sql, values)
                inserted += 1
            except sqlite3.Error as e:
                skipped += 1
                print(f"[SKIP {table}] row={row}  error={e}")

    conn.commit()
    print(f"→ {table} 插入完成：成功 {inserted} 筆，略過 {skipped} 筆")


def main():
    conn = sqlite3.connect(DB_PATH)
    # 啟用 FK（SQLite 預設關掉）
    conn.execute("PRAGMA foreign_keys = ON;")

    try:
        # 1. Director
        insert_csv(
            conn,
            table="Director",
            csv_path=DIRECTOR_CSV,
            columns=["director_id", "name", "birth_year", "nationality"],
        )

        # 2. Company
        insert_csv(
            conn,
            table="Company",
            csv_path=COMPANY_CSV,
            columns=["company_id", "name", "founded_year", "country"],
        )

        # 3. Actor
        insert_csv(
            conn,
            table="Actor",
            csv_path=ACTOR_CSV,
            columns=["actor_id", "name", "birth_year", "nationality", "gender"],
        )

        # 4. Role
        insert_csv(
            conn,
            table="Role",
            csv_path=ROLE_CSV,
            columns=["role_id", "name"],
        )

        # 5. Genre
        insert_csv(
            conn,
            table="Genre",
            csv_path=GENRE_CSV,
            columns=["genre_id", "name"],
        )

        # 6. User（password 一律填 "1234"）
        insert_csv(
            conn,
            table="User",
            csv_path=USER_CSV,
            columns=["user_id", "name", "email", "password", "join_date", "age"],
            extra_values={"password": "1234"},
        )

        # 7. Movie（有 FK → Director）
        insert_csv(
            conn,
            table="Movie",
            csv_path=MOVIE_CSV,
            columns=["movie_id", "director_id", "title", "release_year",
                     "duration", "language", "country"],
        )

        # 8. Review（有 FK → User, Movie）
        insert_csv(
            conn,
            table="Review",
            csv_path=REVIEW_CSV,
            columns=["review_id", "user_id", "movie_id", "rating", "comment", "date"],
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()
