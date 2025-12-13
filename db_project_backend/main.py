from pydantic import BaseModel
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import random
from datetime import date, datetime
from typing import List, Optional, Literal

from db import get_db
from schemas import *


def generate_user_id(db: sqlite3.Connection) -> str:
    prefix = "ur"

    while True:
        # 產生 0 ~ 999999 的數字，補成 6 位
        number = random.randint(0, 999_999)
        user_id = f"{prefix}{number:06d}"

        cur = db.execute(
            "SELECT 1 FROM User WHERE user_id = ?",
            (user_id,)
        )
        #如果上面那句SQL沒有結果回傳，代表user_id不重複
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
    cur = db.execute("SELECT 1 FROM User WHERE email = ?", (payload.email,))
    #如果上面那句SQL有結果回傳，代表email重複
    if cur.fetchone():
        raise HTTPException(status_code=409, detail="Email already exists")

    user_id = generate_user_id(db)
    join_date = date.today().isoformat()

    #執行一條SQL語句
    db.execute(
        "INSERT INTO User (user_id, name, email, password, join_date, age) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, payload.name, payload.email, payload.password, join_date, payload.age)
    )
    #把之前對資料庫做的變更寫入檔案
    db.commit()

    cur = db.execute(
        "SELECT user_id, name, email, join_date, age FROM User WHERE email = ?",
        (payload.email,)
    )
    #從查詢結果取出"一筆"資料
    row = cur.fetchone()
    return UserOut(
        user_id=row["user_id"],
        name=row["name"],
        email=row["email"],
        join_date=row["join_date"],
        age=row["age"]
    )


# ===================== 共用轉換函式 =====================

def row_to_movie_out(row: sqlite3.Row) -> MovieOut:
    return MovieOut(
        movie_id=row["movie_id"],
        director_id=row["director_id"],
        title=row["title"],
        release_year=row["release_year"],
        duration=row["duration"],
        language=row["language"],
        country=row["country"],
    )


def row_to_genre_out(row: sqlite3.Row) -> GenreOut:
    return GenreOut(
        genre_id=row["genre_id"],
        name=row["name"],
    )


def row_to_director_out(row: sqlite3.Row) -> DirectorOut:
    return DirectorOut(
        director_id=row["director_id"],
        name=row["name"],
        birth_year=row["birth_year"],
        nationality=row["nationality"],
    )


def row_to_company_out(row: sqlite3.Row) -> CompanyOut:
    return CompanyOut(
        company_id=row["company_id"],
        name=row["name"],
        founded_year=row["founded_year"],
        country=row["country"],
    )


def row_to_actor_out(row: sqlite3.Row) -> ActorOut:
    return ActorOut(
        actor_id=row["actor_id"],
        name=row["name"],
        birth_year=row["birth_year"],
        nationality=row["nationality"],
        gender=row["gender"],
    )


def row_to_role_out(row: sqlite3.Row) -> RoleOut:
    return RoleOut(
        role_id=row["role_id"],
        name=row["name"],
    )


def row_to_review_out(row: sqlite3.Row) -> ReviewOut:
    return ReviewOut(
        review_id=row["review_id"],
        user_name=row["user_name"],
        movie_id=row["movie_id"],
        rating=row["rating"],
        comment=row["comment"],
        date=row["date"],
    )


def get_reviews_for_movie(db: sqlite3.Connection, movie_id: str) -> tuple[list[ReviewOut], int]:
    cur = db.execute(
        """
        SELECT r.review_id,
               u.name AS user_name,
               r.movie_id,
               r.rating,
               r.comment,
               r.date
        FROM Review r
        JOIN User u ON r.user_id = u.user_id
        WHERE r.movie_id = ?
        ORDER BY r.date ASC
        """,
        (movie_id,),
    )
    rows = cur.fetchall()
    reviews = [row_to_review_out(r) for r in rows]
    if not reviews:
        return [], 0
    avg = sum(r.rating for r in reviews) / len(reviews)
    return reviews, int(round(avg))


def generate_review_id(db: sqlite3.Connection) -> str:
    prefix = "rev"
    while True:
        number = random.randint(0, 999_999)
        review_id = f"{prefix}{number:06d}"
        cur = db.execute(
            "SELECT 1 FROM Review WHERE review_id = ?",
            (review_id,),
        )
        if cur.fetchone() is None:
            return review_id

# ===================== User 頁面 =====================
@app.get("/user_detail/{user_id}", response_model=UserDetailOut)
def get_user_detail(user_id: str, db: sqlite3.Connection = Depends(get_db)):
    try:    
        # 抓使用者資料
        get_user = db.execute('''
            SELECT *
            FROM User u
            WHERE user_id = ?''',
            (user_id,)
        )

        row = get_user.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="User not found")
        else :
            user = UserOut(
                user_id=row["user_id"],
                name=row["name"],
                email=row["email"],
                join_date=row["join_date"],
                age=row["age"]
            )

        # 抓評論過的電影
        get_commented_movie = db.execute('''
            SELECT DISTINCT m.movie_id, m.title
            FROM Movie m
            JOIN Review R on m.movie_id = R.movie_id
            WHERE R.user_id = ?''',
            (user_id,)
        )

        get_commented_movie_result = get_commented_movie.fetchall()
        movies = []
        for row in get_commented_movie_result:
            movie = MovieOut(
                movie_id=row['movie_id'],
                title=row['title']
            )
            movies.append(movie)

        # 統計評論最多的類型
        get_most_commented_genre = db.execute('''
            SELECT g.name, g.genre_id, COUNT(*) as r_count
            FROM Review r
            JOIN MovieGenre mg ON r.movie_id = mg.movie_id
            JOIN Genre g ON mg.genre_id = g.genre_id
            WHERE r.user_id = ?
            GROUP BY g.name
            ORDER BY r_count DESC''',
            (user_id,)
        )

        get_most_commented_genre_result = get_most_commented_genre.fetchall()
        genres = []
        for row in get_most_commented_genre_result:
            genre = GenreOut(
                genre_id=row['genre_id'],
                name=row['name']
            )
            genres.append(genre)

        return UserDetailOut(
            user_info=user,
            movie_list=movies,
            genre_list=genres
        )
    
    except Exception as e:
        print("發生錯誤：", e)
        raise HTTPException(status_code=500, detail=str(e))

# ===================== Sign In 頁面 =====================

class SignInRequest(BaseModel):
    email: str
    password: str

@app.post("/login", response_model=UserOut)
def get_user_by_email(payload: SignInRequest, db: sqlite3.Connection = Depends(get_db)):
    """
    Sign in：用 email & password 取得使用者基本資料。
    """
    cur = db.execute(
        "SELECT user_id, name, email, password, join_date, age FROM User WHERE email = ?",
        (payload.email,),
    )
    row = cur.fetchone()
    if row is None or row["password"] != payload.password:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return UserOut(
        user_id=row["user_id"],
        name=row["name"],
        email=row["email"],
        join_date=row["join_date"],
        age=row["age"],
    )


# ===================== 導覽列 get_by_name =====================

@app.get("/nav", response_model=NavOut)
def get_by_name(
    name: str,
    type: str = Query("all", description="all / movie / company / director / actor / genre / user / role"),
    db: sqlite3.Connection = Depends(get_db),
):
    """
    導覽列模糊搜尋。type = all 時會同時查所有類別。
    """
    keyword = f"%{name}%"
    t = type.lower()

    movie_list = None
    genre_list = None
    actor_list = None
    company_list = None
    director_list = None
    user_list = None
    role_list = None

    if t in ("all", "movie"):
        cur = db.execute(
            """
            SELECT movie_id, director_id, title, release_year, duration, language, country
            FROM Movie
            WHERE title LIKE ?
            """,
            (keyword,),
        )
        movie_list = [row_to_movie_out(r) for r in cur.fetchall()]

    if t in ("all", "genre"):
        cur = db.execute(
            "SELECT genre_id, name FROM Genre WHERE name LIKE ?",
            (keyword,),
        )
        genre_list = [row_to_genre_out(r) for r in cur.fetchall()]

    if t in ("all", "actor"):
        cur = db.execute(
            "SELECT actor_id, name, birth_year, nationality, gender FROM Actor WHERE name LIKE ?",
            (keyword,),
        )
        actor_list = [row_to_actor_out(r) for r in cur.fetchall()]

    if t in ("all", "company"):
        cur = db.execute(
            "SELECT company_id, name, founded_year, country FROM Company WHERE name LIKE ?",
            (keyword,),
        )
        company_list = [row_to_company_out(r) for r in cur.fetchall()]

    if t in ("all", "director"):
        cur = db.execute(
            "SELECT director_id, name, birth_year, nationality FROM Director WHERE name LIKE ?",
            (keyword,),
        )
        director_list = [row_to_director_out(r) for r in cur.fetchall()]

    if t in ("all", "user"):
        cur = db.execute(
            "SELECT user_id, name, email, join_date, age FROM User WHERE name LIKE ?",
            (keyword,),
        )
        user_list = [
            UserOut(
                user_id=r["user_id"],
                name=r["name"],
                email=r["email"],
                join_date=r["join_date"],
                age=r["age"],
            )
            for r in cur.fetchall()
        ]

    if t in ("all", "role"):
        cur = db.execute(
            "SELECT role_id, name FROM Role WHERE name LIKE ?",
            (keyword,),
        )
        role_list = [row_to_role_out(r) for r in cur.fetchall()]

    return NavOut(
        movie_list=movie_list,
        genre_list=genre_list,
        actor_list=actor_list,
        company_list=company_list,
        director_list=director_list,
        user_list=user_list,
        role_list=role_list,
    )


# ===================== Movie 頁面 =====================

@app.get("/movies/{movie_id}", response_model=MovieDetailOut)
def get_movie_by_id(movie_id: str, db: sqlite3.Connection = Depends(get_db)):
    """
    取得單一電影詳細資訊：
    MovieOut + GenreOut[] + ActorOut[] + CompanyOut[] + DirectorOut + 平均評分 + ReviewOut[]
    """
    # Movie + Director
    cur = db.execute(
        """
        SELECT m.movie_id,
               m.director_id,
               m.title,
               m.release_year,
               m.duration,
               m.language,
               m.country,
               d.director_id AS d_director_id,
               d.name        AS d_name,
               d.birth_year  AS d_birth_year,
               d.nationality AS d_nationality
        FROM Movie m
        LEFT JOIN Director d ON m.director_id = d.director_id
        WHERE m.movie_id = ?
        """,
        (movie_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Movie not found")

    movie_info = row_to_movie_out(row)
    if row["d_director_id"] is None:
        raise HTTPException(status_code=500, detail="Director not found for this movie")
    director = DirectorOut(
        director_id=row["d_director_id"],
        name=row["d_name"],
        birth_year=row["d_birth_year"],
        nationality=row["d_nationality"],
    )

    # Genres
    cur = db.execute(
        """
        SELECT g.genre_id, g.name
        FROM MovieGenre mg
        JOIN Genre g ON mg.genre_id = g.genre_id
        WHERE mg.movie_id = ?
        """,
        (movie_id,),
    )
    genre_list = [row_to_genre_out(r) for r in cur.fetchall()]

    # Companies
    cur = db.execute(
        """
        SELECT c.company_id, c.name, c.founded_year, c.country
        FROM Owns o
        JOIN Company c ON o.company_id = c.company_id
        WHERE o.movie_id = ?
        """,
        (movie_id,),
    )
    company_list = [row_to_company_out(r) for r in cur.fetchall()]

    # Actors
    cur = db.execute(
        """
        SELECT DISTINCT a.actor_id, a.name, a.birth_year, a.nationality, a.gender
        FROM RoleInMovie_Played rim
        JOIN Actor a ON rim.actor_id = a.actor_id
        WHERE rim.movie_id = ?
        """,
        (movie_id,),
    )
    actor_list = [row_to_actor_out(r) for r in cur.fetchall()]

    review_list, average_rating = get_reviews_for_movie(db, movie_id)

    return MovieDetailOut(
        movie_info=movie_info,
        genre_list=genre_list,
        actor_list=actor_list,
        company_list=company_list,
        director=director,
        average_rating=average_rating,
        review_list=review_list,
    )

@app.post("/reviews", response_model=ReviewOut, status_code=201)
def create_review(payload: ReviewIn, db: sqlite3.Connection = Depends(get_db)):
    """
    新增一則評論。日期由後端自動填入現在時間。
    （ReviewIn 裡沒有 date，所以這邊自己填）
    """
    # 確認 user / movie 存在
    cur = db.execute("SELECT 1 FROM User WHERE user_id = ?", (payload.user_id,))
    if cur.fetchone() is None:
        raise HTTPException(status_code=404, detail="User not found")

    cur = db.execute("SELECT 1 FROM Movie WHERE movie_id = ?", (payload.movie_id,))
    if cur.fetchone() is None:
        raise HTTPException(status_code=404, detail="Movie not found")

    review_id = generate_review_id(db)
    now = datetime.now().replace(second=0, microsecond=0)
    now_str = now.strftime("%Y-%m-%d %H:%M")

    db.execute(
        """
        INSERT INTO Review (review_id, user_id, movie_id, rating, comment, date)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (review_id, payload.user_id, payload.movie_id, payload.rating, payload.comment, now_str),
    )
    db.commit()

    # 重新撈出，補上 user_name
    cur = db.execute(
        """
        SELECT r.review_id,
               u.name AS user_name,
               r.movie_id,
               r.rating,
               r.comment,
               r.date
        FROM Review r
        JOIN User u ON r.user_id = u.user_id
        WHERE r.review_id = ?
        """,
        (review_id,),
    )
    row = cur.fetchone()
    return row_to_review_out(row)


# ===================== Company 頁面 =====================

@app.get("/companies/{company_id}", response_model=CompanyDetailOut)
def get_company_by_id(company_id: str, db: sqlite3.Connection = Depends(get_db)):
    """
    用 company_id 撈公司基本資料 + 該公司擁有的所有電影。
    """
    cur = db.execute(
        "SELECT company_id, name, founded_year, country FROM Company WHERE company_id = ?",
        (company_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Company not found")

    company_info = row_to_company_out(row)

    cur = db.execute(
        """
        SELECT m.movie_id, m.director_id, m.title, m.release_year,
               m.duration, m.language, m.country
        FROM Owns o
        JOIN Movie m ON o.movie_id = m.movie_id
        WHERE o.company_id = ?
        """,
        (company_id,),
    )
    movie_list = [row_to_movie_out(r) for r in cur.fetchall()]

    return CompanyDetailOut(
        company_info=company_info,
        movie_list=movie_list,
    )


# ===================== Actor 頁面 =====================

@app.get("/actors/{actor_id}", response_model=ActorDetailOut)
def get_actor_by_id(actor_id: str, db: sqlite3.Connection = Depends(get_db)):
    """
    用 actor_id 撈演員基本資料 + 演出的電影 + 對應角色。
    """
    cur = db.execute(
        "SELECT actor_id, name, birth_year, nationality, gender FROM Actor WHERE actor_id = ?",
        (actor_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Actor not found")

    actor_info = row_to_actor_out(row)

    cur = db.execute(
        """
        SELECT m.movie_id,
               m.director_id,
               m.title,
               m.release_year,
               m.duration,
               m.language,
               m.country,
               r.role_id,
               r.name AS role_name
        FROM RoleInMovie_Played rim
        JOIN Movie m ON rim.movie_id = m.movie_id
        JOIN Role r ON rim.role_id = r.role_id
        WHERE rim.actor_id = ?
        ORDER BY m.release_year, m.title
        """,
        (actor_id,),
    )
    rows = cur.fetchall()

    movie_list: list[MovieOut] = []
    role_list: list[RoleOut] = []

    for r in rows:
        movie_list.append(row_to_movie_out(r))
        role_list.append(RoleOut(role_id=r["role_id"], name=r["role_name"]))

    return ActorDetailOut(
        actor_info=actor_info,
        movie_list=movie_list,
        role_list=role_list,
    )


# ===================== Advanced Search 頁面 =====================

@app.post("/advanced-search", response_model=NavOut)
def advanced_search(
    params: AdvancdeSearchParams,
    db: sqlite3.Connection = Depends(get_db),
):
    result_type = params.result_type

    # 特殊查詢不能一起用
    if params.actor_director_combination is not None and params.top_rating_of_year_limit is not None:
        raise HTTPException(status_code=400,detail="特殊查詢參數不能一起使用")

    # =========================================================================
    # 邏輯分流 1：Actor-Director 合作頻率
    # =========================================================================
    if params.actor_director_combination is not None:
        k_value = params.actor_director_combination
        
        # 找出合作次數 >= K 的演員與導演，將結果拆成 actor_list 和 director_list 回傳
        sql = """
            SELECT 
                a.actor_id, a.name as a_name, a.birth_year as a_birth, a.nationality as a_nation, a.gender,
                d.director_id, d.name as d_name, d.birth_year as d_birth, d.nationality as d_nation,
                COUNT(m.movie_id) as collab_count
            FROM Actor a
            JOIN RoleInMovie_Played rim ON a.actor_id = rim.actor_id
            JOIN Movie m ON rim.movie_id = m.movie_id
            JOIN Director d ON m.director_id = d.director_id
            GROUP BY a.actor_id, d.director_id
            HAVING collab_count >= ?
            ORDER BY collab_count DESC
        """
        
        cur = db.execute(sql, (k_value,))
        rows = cur.fetchall()

        # 使用 set 避免重複 (例如同一個導演跟兩個不同演員都合作過 K 次，導演會出現兩次)
        pairs = []
        for row in rows:
            actor = ActorOut(
                actor_id=row["actor_id"],
                name=row["a_name"],
                birth_year=row["a_birth"],
                nationality=row["a_nation"],
                gender=row["gender"]
            )
        
            director = DirectorOut(
                director_id=row["director_id"],
                name=row["d_name"],
                birth_year=row["d_birth"],
                nationality=row["d_nation"]
            )

            pairs.append(ActorDirectorPair(actor=actor, director=director, collab_count=row['collab_count']))

        return NavOut(actor_director_list=pairs)

    # =========================================================================
    # 邏輯分流 2：年度高分電影 Top K
    # =========================================================================
    if params.top_rating_of_year_limit is not None:
        year = params.top_rating_of_year
        limit = params.top_rating_of_year_limit

        sql = """
            SELECT m.movie_id, m.director_id, m.title, m.release_year, m.duration, m.language, m.country,
                AVG(r.rating) as avg_rating
            FROM Movie m
            JOIN Review r ON m.movie_id = r.movie_id
        """
        
        args = []
        wheres = ["m.release_year = ?"]
        args.append(year)

        # 如果有指定類型
        if params.genre_name:
            sql += """
                JOIN MovieGenre mg ON m.movie_id = mg.movie_id
                JOIN Genre g ON mg.genre_id = g.genre_id
            """
            wheres.append("g.name LIKE ?")
            args.append(f"%{params.genre_name}%")

        # 組合 Where 條件
        sql += " WHERE " + " AND ".join(wheres)

        # Group By + Order By + Limit
        sql += """
            GROUP BY m.movie_id
            ORDER BY avg_rating DESC
            LIMIT ?
        """
        args.append(limit)

        cur = db.execute(sql, tuple(args))
        rows = cur.fetchall()
        movies = [row_to_movie_out(r) for r in rows]
        
        return NavOut(movie_list=movies)

    # =========================================================================
    # 一般功能
    # =========================================================================

    # 目前用 Movie 當作 base table
    base_sql = """
        FROM Movie m
    """
    joins: list[str] = []
    where_clauses: list[str] = []
    args: list = []

    # ===== Movie 條件 =====
    if params.movie_language:
        where_clauses.append("m.language = ?")
        args.append(params.movie_language)

    if params.movie_duration_value is not None:
        op_map = {"gt": ">", "lt": "<", "eq": "="}
        op = op_map.get(params.movie_duration_op or "gt", ">")
        where_clauses.append(f"m.duration {op} ?")
        args.append(params.movie_duration_value)

    if params.movie_release_year is not None:
        where_clauses.append("m.release_year = ?")
        args.append(params.movie_release_year)

    if params.movie_country:
        where_clauses.append("m.country = ?")
        args.append(params.movie_country)

    if params.movie_title:
        where_clauses.append("m.title LIKE ?")
        args.append(f"%{params.movie_title}%")

    # ===== Actor 條件 =====
    need_actor_join = any(
        [
            params.actor_gender,
            params.actor_birth_year is not None,
            params.actor_nationality,
            params.actor_name,
        ]
    )
    if need_actor_join:
        joins.append("JOIN RoleInMovie_Played rim ON rim.movie_id = m.movie_id")
        joins.append("JOIN Actor a ON rim.actor_id = a.actor_id")

        if params.actor_gender:
            where_clauses.append("a.gender = ?")
            args.append(params.actor_gender)

        if params.actor_birth_year is not None:
            where_clauses.append("a.birth_year = ?")
            args.append(params.actor_birth_year)

        if params.actor_nationality:
            where_clauses.append("a.nationality = ?")
            args.append(params.actor_nationality)

        if params.actor_name:
            where_clauses.append("a.name LIKE ?")
            args.append(f"%{params.actor_name}%")

     # ===== Genre 條件（這裡先實作 genre_name） =====
    need_genre_join = params.genre_name is not None
    if need_genre_join:
        joins.append("JOIN MovieGenre mg ON mg.movie_id = m.movie_id")
        joins.append("JOIN Genre g ON mg.genre_id = g.genre_id")
        where_clauses.append("g.name LIKE ?")
        args.append(f"%{params.genre_name}%")

    # ===== Director 條件 =====
    need_director_join = any(
        [
            params.director_birth_year is not None,
            params.director_nationality,
            params.director_name,
        ]
    )
    if need_director_join:
        joins.append("JOIN Director d ON m.director_id = d.director_id")
        if params.director_birth_year is not None:
            where_clauses.append("d.birth_year = ?")
            args.append(params.director_birth_year)
        if params.director_nationality:
            where_clauses.append("d.nationality = ?")
            args.append(params.director_nationality)
        if params.director_name:
            where_clauses.append("d.name LIKE ?")
            args.append(f"%{params.director_name}%")

    # ===== Company 條件 =====
    need_company_join = any(
        [
            params.company_founded_year is not None,
            params.company_name,
        ]
    )
    if need_company_join:
        joins.append("JOIN Owns o ON o.movie_id = m.movie_id")
        joins.append("JOIN Company c ON o.company_id = c.company_id")
        if params.company_founded_year is not None:
            where_clauses.append("c.founded_year = ?")
            args.append(params.company_founded_year)
        if params.company_name:
            where_clauses.append("c.name LIKE ?")
            args.append(f"%{params.company_name}%")

    # ===== Role 條件 =====
    need_role_join = params.role_name is not None
    if need_role_join and not need_actor_join:
        joins.append("JOIN RoleInMovie_Played rim ON rim.movie_id = m.movie_id")
        joins.append("JOIN Role r ON rim.role_id = r.role_id")
    elif need_role_join and need_actor_join:
        # 已經 join 過 rim 與 Actor，只要再 join Role
        joins.append("JOIN Role r ON rim.role_id = r.role_id")

    if need_role_join:
        where_clauses.append("r.name LIKE ?")
        args.append(f"%{params.role_name}%")

    # 組出最終 SQL
    join_sql = " ".join(joins)
    where_sql = ""
    order_sql = "ORDER BY m.release_year"
    if where_clauses:
        where_sql = " WHERE " + " AND ".join(where_clauses)

    # 依 result_type 決定 SELECT 欄位與對應輸出
    t = result_type.lower()

    if t == "movie":
        sql = (
            "SELECT DISTINCT "
            "m.movie_id, m.director_id, m.title, m.release_year, m.duration, m.language, m.country "
            + base_sql
            + join_sql
            + where_sql
        )
        cur = db.execute(sql, tuple(args))
        movies = [row_to_movie_out(r) for r in cur.fetchall()]
        return NavOut(movie_list=movies)

    if t == "actor":
        if not need_actor_join:
            joins.append("JOIN RoleInMovie_Played rim ON rim.movie_id = m.movie_id")
            joins.append("JOIN Actor a ON rim.actor_id = a.actor_id")
            join_sql = " ".join(joins)
        sql = (
            "SELECT DISTINCT a.actor_id, a.name, a.birth_year, a.nationality, a.gender "
            + base_sql
            + join_sql
            + where_sql
        )
        cur = db.execute(sql, tuple(args))
        actors = [row_to_actor_out(r) for r in cur.fetchall()]
        return NavOut(actor_list=actors)

    if t == "director":
        if not need_director_join:
            joins.append("JOIN Director d ON m.director_id = d.director_id")
            join_sql = " ".join(joins)
        sql = (
            "SELECT DISTINCT d.director_id, d.name, d.birth_year, d.nationality "
            + base_sql
            + join_sql
            + where_sql
        )
        cur = db.execute(sql, tuple(args))
        directors = [row_to_director_out(r) for r in cur.fetchall()]
        return NavOut(director_list=directors)

    if t == "company":
        if not need_company_join:
            joins.append("JOIN Owns o ON o.movie_id = m.movie_id")
            joins.append("JOIN Company c ON o.company_id = c.company_id")
            join_sql = " ".join(joins)
        sql = (
            "SELECT DISTINCT c.company_id, c.name, c.founded_year, c.country "
            + base_sql
            + join_sql
            + where_sql
        )
        cur = db.execute(sql, tuple(args))
        companies = [row_to_company_out(r) for r in cur.fetchall()]
        return NavOut(company_list=companies)

    if t == "genre":
        if not need_genre_join:
            joins.append("JOIN MovieGenre mg ON mg.movie_id = m.movie_id")
            joins.append("JOIN Genre g ON mg.genre_id = g.genre_id")
            join_sql = " ".join(joins)
        sql = (
            "SELECT DISTINCT g.genre_id, g.name "
            + base_sql
            + join_sql
            + where_sql
        )
        cur = db.execute(sql, tuple(args))
        genres = [row_to_genre_out(r) for r in cur.fetchall()]
        return NavOut(genre_list=genres)

    if t == "role":

        if not need_role_join:
            if not need_actor_join:
                joins.append("JOIN RoleInMovie_Played rim ON rim.movie_id = m.movie_id")
            # 無論如何都要把 Role 加進來
            joins.append("JOIN Role r ON rim.role_id = r.role_id")

        join_sql = " ".join(joins)

        sql = (
            "SELECT DISTINCT r.role_id, r.name "
            + base_sql
            + join_sql
            + where_sql
        )
        cur = db.execute(sql, tuple(args))
        roles = [row_to_role_out(r) for r in cur.fetchall()]
        return NavOut(role_list=roles)

    raise HTTPException(status_code=400, detail=f"Unsupported result_type: {result_type}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)