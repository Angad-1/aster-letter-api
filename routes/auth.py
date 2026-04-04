from uuid import UUID
from fastapi import APIRouter, Depends,Query,Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from core.db import get_db
from schemas.authSchema import LoginRes, LoginReq,RefreshRes, RefreshReq,UserRes
from services.authServices import login_user,refresh_token,logout_user
from schemas.commonSchema import WithoutData
from utilities.utils import handle_request,MyHTTPException,decode_token

router = APIRouter(prefix="/auth")

@router.post("/login", response_model=LoginRes[UserRes])
async def login(req:Request,user: LoginReq, db: AsyncSession = Depends(get_db)):
    return await handle_request(login_user, db, user,req)

@router.post("/refreshToken", response_model=RefreshRes)
async def refresh(req: RefreshReq, db: AsyncSession = Depends(get_db)):
    if not req.refresh_token:
        raise MyHTTPException(status_code=400, content=WithoutData(status="error",message="Refresh token is required"))
    return await handle_request(refresh_token, db, req)

@router.post("/logout", response_model=WithoutData)
@router.post("/logout/{id}", response_model=WithoutData)
async def login(req:Request,id: Optional[UUID]=None, payload=Depends(decode_token), db: AsyncSession = Depends(get_db)):
    return await handle_request(logout_user, db,payload, id,req)