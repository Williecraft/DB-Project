from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
import sqlite3
from typing import List

from db import get_db
from schemas import *

app = FastAPI(title="Movie Review API")


@app.post("/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, db: sqlite3.Connection = Depends(get_db)):
    #檢查 email 是否重複
    cur = db.execute("SELECT 1 FROM users WHERE email = ?", (payload.email,))
    if cur.fetchone():
        raise HTTPException(status_code=409, detail="Email already exists")

    db.execute(
        "INSERT INTO users (name, email, password, age) VALUES (?, ?)",
        (payload.name, payload.email, payload.password, payload.age)
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
