from pydantic import BaseModel, EmailStr
from pydantic import BaseModel

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class JobCreate(BaseModel):
    company: str
    role: str

class JobOut(BaseModel):
    id: int
    company: str
    role: str
    status: str

    class Config:
        from_attributes = True

class JobUpdate(BaseModel):
    status: str

