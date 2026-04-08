from fastapi import Request, UploadFile
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlmodel import select,func,case,literal
from typing import List,Optional
from models.models import Activity
from schemas.activitySchema import LogActivity,ActivityRes

from schemas.commonSchema import Response,WithoutData
from utilities.utils import hash_password,verify_password,MyHTTPException

async def log_activity(db: AsyncSession, body: LogActivity):
    activity = Activity(**body.model_dump())
    db.add(activity)
    await db.flush()
    return activity

async def get_activities(
    db: AsyncSession,
    user_id: Optional[UUID] = None,
    skip: int = 0,
    limit: int = 100
):
    query = select(*Activity.__table__.c)

    # Apply filter only if user_id is provided
    if user_id:
        query = query.where(Activity.user_id == user_id)

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    rows = result.mappings().all()
    print(type(rows[0]))
    print([ActivityRes.model_validate(row) for row in rows])
    return Response[List[ActivityRes]](
        status="success",
        data= rows,
        message="Activities retrieved successfully"
    )