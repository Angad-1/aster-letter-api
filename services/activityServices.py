from fastapi import Request, UploadFile
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlmodel import select,func,case,literal
from typing import List
from models.models import Activity
from schemas.activitySchema import LogActivity,ActivityRes

from schemas.commonSchema import Response,WithoutData
from utilities.utils import hash_password,verify_password,MyHTTPException

async def log_activity(db: AsyncSession, body: LogActivity):
    activity = Activity(**body.model_dump())
    db.add(activity)
    await db.flush()
    return activity