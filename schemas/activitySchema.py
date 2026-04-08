from fastapi import UploadFile,File,Form
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, EmailStr, Field,model_serializer
from datetime import datetime

class LogActivity(BaseModel):
    user_id:UUID
    type: str
    message: str 
    module: str
    status: str 
    ip: str 
    ref_id:Optional[UUID] = None
    
class ActivityRes(LogActivity):
    id:UUID
    created_at: datetime
