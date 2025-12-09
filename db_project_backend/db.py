import sqlite3

DB_PATH = "db_project.db"

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # 查詢結果可以用欄位名稱取值
    try:
        yield conn
    finally:
        conn.close()

