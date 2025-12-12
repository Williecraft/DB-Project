# init_db.py
import sqlite3, os

# 取得目前這支 Python 程式碼所在的資料夾路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 組合出資料庫的完整路徑
db_path = os.path.join(BASE_DIR, "db_project.db")

def init_db():
    conn = sqlite3.connect(db_path, check_same_thread=False)
    try:
        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    print("DB initialized.")


