from fastapi import APIRouter, Depends,Query,Request
from uuid import UUID
from typing import Optional,Union, List
from sqlalchemy.ext.asyncio import AsyncSession
from core.db import get_db
from schemas.userSchema import CreateUser, UpdUser, UserRes,ChangePassword,ChangePfp,PfpRes,ToggleStatus
from services.usersServices import create_user,update_user,get_user,delete_user,change_password, change_profile_picture,toggle_user_active
from schemas.commonSchema import WithoutData, Response
from utilities.utils import handle_request,MyHTTPException

router = APIRouter(prefix="/users")

@router.post("/createUser", response_model=Response[UserRes])
async def AddUser(req:Request,body: CreateUser=Depends(), db: AsyncSession = Depends(get_db)):
    return await handle_request(create_user, db, body,req)

@router.put("/updateUserById", response_model=Response[UserRes])
async def UpdateUser(req:Request,body: UpdUser, db: AsyncSession = Depends(get_db)):
    if not body.id:
        raise MyHTTPException(status_code=400, content=WithoutData(status="error",message="User id required"))
    return await handle_request(update_user, db, body,req)

@router.get("/getUser", response_model=Response[Union[UserRes, List[UserRes]]])
async def GetUser(req:Request,id: Optional[UUID]= Query(default=None), db: AsyncSession = Depends(get_db)):
    return await handle_request(get_user, req,db, id)

@router.delete("/deleteUserById", response_model=WithoutData)
async def DelUserById(req:Request,id: Optional[UUID]= Query(default=None), db: AsyncSession = Depends(get_db)):
    if not id:
        raise MyHTTPException(status_code=400, content=WithoutData(status="error",message="User id required"))
    
    return await handle_request(delete_user,req, db, id)

@router.patch("/changePasswordById", response_model=WithoutData)
async def ChangePasswordById(req:Request,body: ChangePassword,db: AsyncSession = Depends(get_db)):
    if not body.id:
        raise MyHTTPException(
            status_code=400,
            content=WithoutData(status="error", message="User id required")
        )
    return await handle_request(change_password,db,body,req)
    

@router.patch("/changeProfilePictureById", response_model=PfpRes)
async def ChangeProfilePicture(req:Request, body:ChangePfp=Depends(), db: AsyncSession = Depends(get_db)):
    if not body.id:
        raise MyHTTPException(
            status_code=400,
            content=WithoutData(status="error", message="User id required")
        )

    return await handle_request(change_profile_picture,db,body,req )


@router.patch("/toggleStatusById", response_model=WithoutData)
async def ToggleStatusById(req:Request,body:ToggleStatus,db: AsyncSession = Depends(get_db)):
    if not body.id:
        raise MyHTTPException(
            status_code=400,
            content=WithoutData(status="error", message="User id required")
        )
    return await handle_request(toggle_user_active,db,body,req)
