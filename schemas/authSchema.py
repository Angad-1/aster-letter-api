from uuid import UUID
from typing import Generic
from pydantic import BaseModel, EmailStr, Field
from typing import Generic, TypeVar
from schemas.userSchema import UserRes

T = TypeVar("T")

class LoginReq(BaseModel):
    username: str
    password: str

class LoginRes(BaseModel, Generic[T]):
    status: str = "success"
    access_token: str = ""
    refresh_token: str = ""
    data: UserRes = Field(default_factory=lambda: T())
    message: str = ""

class RefreshReq(BaseModel):
    refresh_token: str


class RefreshRes(BaseModel):
    status: str = "success"
    access_token: str
    refresh_token: str
    message: str


class ChgPwdReq(BaseModel):
    id: UUID
    old_pwd: str = Field(..., alias="old_password")
    new_pwd: str = Field(..., alias="new_password")

    class Config:
        from_attributes = True
