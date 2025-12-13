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
    join_date : str
    age: int

class MovieOut(BaseModel):
    movie_id: str
    director_id: str | None = None
    title: str
    release_year: int | None = None
    duration: int| None = None
    language: str| None = None
    country: str| None = None

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
    user_name : str
    movie_id: str
    rating: int
    comment: str
    date: str

# 呈現movie頁面的payload
class MovieDetailOut(BaseModel):
    movie_info: MovieOut
    genre_list: list[GenreOut]
    actor_list: list[ActorOut]
    company_list: list[CompanyOut]
    director: DirectorOut
    average_rating: int
    review_list: list[ReviewOut]

# 呈現user頁面的payload
class UserDetailOut(BaseModel):
    user_info: UserOut
    movie_list: list[MovieOut]
    genre_list: list[GenreOut]

# 呈現company頁面的payload
class CompanyDetailOut(BaseModel):
    company_info: CompanyOut
    movie_list: list[MovieOut]

# 呈現actor頁面的payload(movie_list的index對應到role_list必須有關聯)
class ActorDetailOut(BaseModel):
    actor_info: ActorOut
    movie_list: list[MovieOut]
    role_list: list[RoleOut]

class ActorDirectorPair(BaseModel):
    actor: ActorOut
    director: DirectorOut
    collab_count: int

# 呈現導覽列搜尋結果的payload
class NavOut(BaseModel):
    movie_list: list[MovieOut] | None = None
    genre_list: list[GenreOut] | None = None
    actor_list: list[ActorOut] | None = None
    company_list: list[CompanyOut] | None = None
    director_list: list[DirectorOut] | None = None
    user_list: list[UserOut] | None = None
    role_list: list[RoleOut] | None = None

    actor_director_list: list[ActorDirectorPair] | None = None

# 處理進階搜尋頁面的參數。"="前面是type，後面是預設值
class AdvancdeSearchParams(BaseModel):
    result_type: Literal["movie", "company", "director", "actor", "genre", "role"] = "movie"
    
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

    # specaial operation
    actor_director_combination: int | None = None #找出合作最頻繁的演員與導演組合。
    top_rating_of_year: int | None = None
    top_rating_of_year_limit: int | None = None