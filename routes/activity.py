from fastapi import APIRouter, Depends,Query
from uuid import UUID
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from core.db import get_db
from schemas.activitySchema import ActivityRes
from services.activityServices import get_activities
from schemas.commonSchema import Response
from utilities.utils import handle_request

router = APIRouter(prefix="/activity")

@router.get("/getActivities", response_model=Response[list[ActivityRes]])
async def GetActivity(
    user_id: Optional[UUID] = Query(None, description="Filter by user_id"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Number of records to return"),
    db: AsyncSession = Depends(get_db)):
    
    return await handle_request(get_activities, db, user_id,skip,limit)