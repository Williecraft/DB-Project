from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

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


