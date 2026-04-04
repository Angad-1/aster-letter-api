from fastapi import APIRouter,Depends
from routes import (
    auth,users, letter,media
)
from utilities.utils import decode_token

api_router = APIRouter(prefix="/api")

api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(users.router,dependencies=[Depends(decode_token)], tags=["users"])
api_router.include_router(letter.router, dependencies=[Depends(decode_token)],tags=["letter"])
api_router.include_router(media.router, tags=["media"])

