from pydantic import BaseModel
from typing import Optional, Literal
from datetime import date, datetime

# 這邊定義前端送出去或資料庫送回來的JSON檔案格式

class UserCreate(BaseModel):
    name: str
    email: str
    password : str
    age: int

class UserOut(BaseModel):
    user_id : str
    name : str
    email: str
    join_date : date
    age: int

class MovieOut(BaseModel):
    movie_id: str
    director_id: str
    title: str
    release_year: int
    duration: int
    language: str
    country: str

class GenreOut(BaseModel):
    genre_id: str
    name: str

class DirectorOut(BaseModel):
    director_id: str
    name: str
    birth_year: int
    nationality: str

class CompanyOut(BaseModel):
    company_id: str
    name: str
    founded_year: int
    country: str

class ActorOut(BaseModel):
    actor_id: str
    name: str
    birth_year: int
    nationality: str
    gender: str

class RoleOut(BaseModel):
    role_id: str
    name: str

class ReviewIn(BaseModel):
    user_id : str
    movie_id: str
    rating: int
    comment: str

class ReviewOut(BaseModel):
    review_id: str
    user_id : str
    movie_id: str
    rating: int
    comment: str
    _date: date



# 處理進階搜尋頁面的參數。"="前面是type，後面是預設值
class AdvancdeSearchParams(BaseModel):
    # movie
    movie_language: str | None = None
    movie_duration_op: Literal['gt', 'lt', 'eq'] | None = 'gt'
    movie_duration_value: int | None = None
    movie_release_year: int | None = None
    movie_dircetor: str | None = None
    movie_country: str | None = None
    movie_title: str | None = None

    # actor
    actor_gender: str | None = None
    actor_birth_year: int | None = None 
    actor_nationality: str | None = None 
    actor_name: str | None = None 

    # genre
    genre_top_rating_of_year_limit: int | False = False # top rating of year會搜尋該年份最高評分的K個電影
    genre_top_rating_of_year: int | None = None
    genre_name: str | None = None

    # director
    director_birth_year: int | None = None
    director_nationality: str | None = None
    director_name: str | None = None

    # company
    company_founded_year: int | None = None
    company_name: str | None = None

    # role
    role_name: str | None = None

    # actor-director
    actor_director_combination: int | None = None #找出合作最頻繁的演員與導演組合。如果該參數不是None，其他參數全變None(因為其他參數加上這個參數我不知道資料庫會怎麼回傳)