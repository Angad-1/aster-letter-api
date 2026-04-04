from uuid import UUID,uuid4
from sqlmodel import SQLModel, Field,Column,DateTime,Relationship
from typing import Optional,List
from datetime import datetime,timezone,date,time
from pydantic import EmailStr

class Users(SQLModel, table=True):
    __tablename__ = "AsterAuth"

    id: UUID = Field(default_factory=lambda: uuid4(),primary_key=True, nullable=False)
    first_name: str = Field(nullable=False,max_length=100)
    last_name: str = Field(nullable=False,max_length=100)
    username:str=Field(...,unique=True,index=True,max_length=50)
    email: Optional[EmailStr] = Field(None,unique=True,index=True, max_length=150)
    contact_no: Optional[str] = Field(default=None,max_length=15,unique=True)
    gender:str =Field(max_length=1,default='m',description="User gender: 'm' = Male, 'f' = Female, 'o' = Other")
    role: str = Field(max_length=1,default='u', description="User role: 's' = Super Admin, 'a' = Admin, 'u' = User")
    pwd:str=Field(max_length=200,nullable=False,alias="password")
    dsg:str=Field(max_length=100,nullable=False,alias="designation")
    pfp:Optional[str]=Field(max_length=250,alias="profile_picture")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    created_by: Optional[UUID] = Field(None,foreign_key="AsterAuth.id")
    updated_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    updated_by: Optional[UUID] = Field(None,foreign_key="AsterAuth.id")
    
    session: Optional["UserSession"] = Relationship(back_populates="user")
    activities: List["Activity"] = Relationship(back_populates="user")
    
class UserSession(SQLModel, table=True):
    __tablename__ = "AsterSessions"

    id: UUID = Field(default_factory=uuid4, primary_key=True, nullable=False)
    user_id: UUID = Field(foreign_key="AsterAuth.id",nullable=False, unique=True,index=True)
    refresh_token_hash: str = Field(nullable=False, max_length=255)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc),sa_column=Column(DateTime(timezone=True), nullable=False))
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc),sa_column=Column(DateTime(timezone=True), nullable=False))
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    revoked_at: Optional[datetime] = Field(default=None,sa_column=Column(DateTime(timezone=True), nullable=True))
    ip: Optional[str] = Field(default=None, max_length=50)
    user_agent: Optional[str] = Field(default=None, max_length=255)

    user: Optional[Users] = Relationship(back_populates="session")
    
class Activity(SQLModel, table=True):
    __tablename__ = "AsterActivity"

    id: UUID = Field(default_factory=lambda: uuid4(),primary_key=True, nullable=False)
    user_id: UUID = Field(foreign_key="AsterAuth.id",nullable=False,index=True)
    type: str = Field(nullable=False,max_length=50)
    message: str = Field(nullable=False)
    module: str = Field(nullable=False,max_length=50)
    status: str = Field(default="success",max_length=20)
    ip: str = Field(50)
    ref_id:Optional[UUID]=None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    
    user: Optional[Users] = Relationship(back_populates="activities")
