from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import random
from typing import List

from db import get_db
from schemas import *

import random
import sqlite3

def generate_user_id(db: sqlite3.Connection) -> str:
    prefix = "ur"

    while True:
        # 產生 0 ~ 999999 的數字，補成 6 位
        number = random.randint(0, 999_999)
        user_id = f"{prefix}{number:06d}"

        cur = db.execute(
            "SELECT 1 FROM users WHERE user_id = ?",
            (user_id,)
        )
        if cur.fetchone() is None:
            return user_id



app = FastAPI(title="Movie Review API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500", "http://localhost:5500"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, db: sqlite3.Connection = Depends(get_db)):
    #檢查 email 是否重複
    cur = db.execute("SELECT 1 FROM users WHERE email = ?", (payload.email,))
    if cur.fetchone():
        raise HTTPException(status_code=409, detail="Email already exists")

    user_id = generate_user_id(db)

    db.execute(
        "INSERT INTO users (user_id, name, email, password, age) VALUES (?, ?)",
        (user_id, payload.name, payload.email, payload.password, payload.age)
    )
    db.commit()

    cur = db.execute(
        "SELECT user_id, name, email, join_date, age FROM users WHERE email = ?",
        (payload.email,)
    )
    row = cur.fetchone()
    return UserOut(
        user_id=row["user_id"],
        name=row["name"],
        email=row["email"],
        join_date=row["join_date"],
        age=row["age"]
    )


@app.get("/users/{name}", response_model=UserOut)
def get_user(name: str, db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute(
        "SELECT user_id, name, email, join_date, age FROM users WHERE name = ?",
        (name,)
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut(
        user_id=row["user_id"],
        name=row["name"],
        email=row["email"],
        join_date=row["join_date"],
        age=row["age"]
    )
