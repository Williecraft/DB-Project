import csv
import os
import re
import random
from datetime import date, timedelta

# ====== 檔案路徑設定 ======
INPUT_CSV = r"data\generated\user.csv"
OUTPUT_CSV = r"data\generated\user_f.csv"

# ====== 參數設定 ======
MIN_AGE = 13      # 最小年齡
MAX_AGE = 80      # 最大年齡
EMAIL_DOMAINS = ["example.com", "mail.com", "moviefans.com", "imdbuser.net"]


def make_email(user_id: str, name: str) -> str:
    """根據 user_id 和 name 產生一個看起來合理的隨機 email。"""
    # 把 name 整理成 email 可以用的字元
    local = name.lower()
    local = re.sub(r"[^a-z0-9]+", "", local)  # 只留英數字
    if not local:
        local = "user"

    # 從 user_id 抓數字
    digits = "".join(re.findall(r"\d+", user_id))
    # 隨機尾碼 + 網域
    suffix = random.randint(10, 99)
    domain = random.choice(EMAIL_DOMAINS)

    return f"{local}{digits}{suffix}@{domain}"


def generate_birth_and_join(age: int) -> tuple[date, date]:
    """根據年齡產生一個出生日期 & 一個 join_date（不早於出生）。"""
    today = date.today()
    birth_year = today.year - age

    # 隨機一個生日（避免月底 bug，日數取 1~28）
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    birth_date = date(birth_year, month, day)

    # join_date 介於出生 ~ 今天之間
    delta_days = (today - birth_date).days
    if delta_days < 0:
        # 理論上不會發生，保底：就用今天當 join_date
        join_date = today
    else:
        offset = random.randint(0, delta_days)
        join_date = birth_date + timedelta(days=offset)

    return birth_date, join_date


def main():
    # 確保輸出資料夾存在
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

    with open(INPUT_CSV, "r", encoding="utf-8", newline="") as f_in:
        reader = csv.DictReader(f_in)
        users = list(reader)

    out_rows = []
    for row in users:
        user_id = row["user_id"]
        name = row["name"]

        # 隨機年齡
        age = random.randint(MIN_AGE, MAX_AGE)
        _, join_date = generate_birth_and_join(age)

        email = make_email(user_id, name)

        out_rows.append({
            "user_id": user_id,
            "name": name,
            "email": email,
            "join_date": join_date.isoformat(),  # YYYY-MM-DD
            "age": age,
        })

    # 寫出 user_f.csv
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f_out:
        fieldnames = ["user_id", "name", "email", "join_date", "age"]
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"Generated {len(out_rows)} users -> {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
