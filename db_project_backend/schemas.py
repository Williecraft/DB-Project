from pydantic import BaseModel
from typing import Optional
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
    join_date : Optional[date]
    age: int


