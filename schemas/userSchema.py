from fastapi import UploadFile,File,Form
from uuid import UUID
from typing import Optional, Generic, TypeVar,Union
from pydantic import BaseModel, EmailStr, Field,model_serializer
from datetime import datetime


T = TypeVar("T")


class Base(BaseModel):
    first_name: str
    last_name: str
    username:str
    email:Optional[EmailStr]=None
    contact_no:Optional[str]=None
    gender: str = Field(...,description="User gender: 'm' = Male, 'f' = Female, 'o' = Other")
    role: str =  Field(...,description="User role: 'u' = User,'a' =  Admin, 's' = Super Admin" )
    designation:str = Field(...)
    is_active:bool=True


class CreateUser():
    def __init__(
        self,
        first_name: str = Form(...),
        last_name: str = Form(...),
        username: str = Form(...),
        email: Optional[EmailStr] = Form(None),
        contact_no: Optional[str] = Form(None),
        role: str =  Form(...,description="User role: 'u' = User,'a' =  Admin, 's' = Super Admin" ),
        gender: str = Form(...,description="User gender: 'm' = Male, 'f' = Female, 'o' = Other"),
        designation: str = Form(...),
        profile_picture: Optional[UploadFile] = File(None), 
        password: str = Form(...),
        is_active: bool = Form(...)
    ):
        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.email = email
        self.contact_no = contact_no
        self.role = role
        self.gender = gender
        self.designation = designation
        self.profile_picture = profile_picture
        self.password = password
        self.is_active = is_active



class UpdUser(Base):
    id:UUID


class UserRes(UpdUser):
    profile_picture:Optional[str]=None
    created_at: datetime
    created_by: str = ""
    updated_at: Optional[datetime]
    updated_by: Optional[str] = ""
    is_ref:Optional[bool]=False
    @model_serializer
    def serialize(self):
        """Serialize InvtItemRes with controlled field order"""
        field_order = [
            "id", "first_name", "last_name","username", "email", "contact_no", "role",
            "gender", "designation", "profile_picture", "is_active", "is_ref",
            "created_at", "created_by", "updated_at", "updated_by"
        ]
        return {field: getattr(self, field) for field in field_order}
    
class ChangePassword(BaseModel):
    id:UUID
    old_password: str
    new_password: str
    
class ToggleStatus(BaseModel):
    id:UUID
    is_active: bool
    
class ChangePfp():
    def __init__(
        self,
        id: UUID = Form(...),
        profile_picture: Optional[UploadFile] = File(None)
    ):
        self.id = id
        self.profile_picture = profile_picture
        
class PfpRes(BaseModel):
    status: str = "success"
    message: str = ""
    profile_picture: str = ""
