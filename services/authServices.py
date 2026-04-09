import os
from uuid import UUID
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlmodel import select
from datetime import timedelta
from jose import jwt,JWSError,JWTError
from models.models import Users,UserSession
from schemas.authSchema import UserRes,LoginReq,LoginRes,RefreshReq,RefreshRes
from schemas.activitySchema import LogActivity
from services.usersServices import user_base_select,get_activity_meta
from services.activityServices import log_activity
from schemas.commonSchema import WithoutData,Response
from utilities.utils import MyHTTPException,verify_password,create_token,get_client_ip,hash_token,STALE_SESSION_MINUTES,utcnow,get_object_if_exists,normalize_utc
from utilities.constant import ActivityType, ActivityModule, ActivityMessage,ActivityStatus
from services import get_current_user_id

Creator = aliased(Users)
Updater = aliased(Users)

async def login_user(db: AsyncSession, body: LoginReq, req: Request) -> LoginRes[UserRes]:
    try:
        stmt = user_base_select(str(req.base_url), with_pwd=True).where(
            Users.username == body.username
        )
        result = await db.execute(stmt)
        row = result.mappings().one_or_none()

        if not row or not verify_password(body.password, row.pwd):
            raise MyHTTPException(
                status_code=400,
                content=WithoutData(status="error", message="Invalid username or password")
            )

        if not row.is_active:
            raise MyHTTPException(
                status_code=403,
                content=WithoutData(status="error", message="Your account is inactive")
            )

        refresh_exp_minutes = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES"))
        now = normalize_utc(utcnow())

        session_stmt = select(UserSession).where(UserSession.user_id == row.id)
        session_result = await db.execute(session_stmt)
        existing_session = session_result.scalar_one_or_none()

        refresh_exp_minutes = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES"))
        now = normalize_utc(utcnow())

        session_stmt = select(UserSession).where(UserSession.user_id == row.id)
        session_result = await db.execute(session_stmt)
        existing_session = session_result.scalar_one_or_none()

        if existing_session:
            expires_at = normalize_utc(existing_session.expires_at)
            last_seen_at = normalize_utc(existing_session.last_seen_at)
            revoked_at = normalize_utc(existing_session.revoked_at)

            is_active_session = (
                revoked_at is None
                and expires_at is not None
                and expires_at > now
            )

            is_recently_used = (
                last_seen_at is not None
                and last_seen_at > now - timedelta(minutes=STALE_SESSION_MINUTES)
            )

            if is_active_session and is_recently_used:
                raise MyHTTPException(
                    status_code=400,
                    content=WithoutData(
                        status="error",
                        message="User already logged in on another device"
                    )
                )

            session = existing_session
            session.created_at = now
            session.last_seen_at = now
            session.expires_at = now + timedelta(minutes=refresh_exp_minutes)
            session.revoked_at = None
            session.ip = get_client_ip(req)
            session.user_agent = req.headers.get("user-agent")
        else:
            session = UserSession(
                user_id=row.id,
                created_at=now,
                last_seen_at=now,
                expires_at=now + timedelta(minutes=refresh_exp_minutes),
                revoked_at=None,
                ip=get_client_ip(req),
                user_agent=req.headers.get("user-agent"),
                refresh_token_hash="tmp",
            )
            db.add(session)
            await db.flush()   # gets PK without committing

        token_data = {
            "id": str(row.id),
            "session_id": str(session.id),
            "first_name": row.first_name,
            "last_name": row.last_name,
            "role": row.role,
        }

        access_token = create_token(token_data, "access")
        refresh_token = create_token(token_data, "refresh")

        session.refresh_token_hash = hash_token(refresh_token)
        session.last_seen_at = now
        session.expires_at = now + timedelta(minutes=refresh_exp_minutes)
        session.revoked_at = None

        await db.commit()
        await db.refresh(session)

    except MyHTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise

    # logging should not break login
    try:
        await log_activity(
            db=db,
            body=LogActivity(
                user_id=row.id,
                type=ActivityType.LOGIN,
                module=ActivityModule.AUTH,
                message=ActivityMessage.LOGIN,
                status=ActivityStatus.SUCCESS,
                ip=get_client_ip(req),
            )
        )
    except Exception:
        pass

    user_res = UserRes(**{k: v for k, v in row.items() if k != "pwd"})

    return LoginRes[UserRes](
        status="success",
        access_token=access_token,
        refresh_token=refresh_token,
        data=user_res,
        message="Login successfully"
    )

async def refresh_token(db:AsyncSession, body:RefreshReq)->RefreshRes:
    invalid_excp = MyHTTPException(
            status_code=400,
            content=WithoutData(status="error",message="Invalid token")
        )
    
    try:
        payload = jwt.decode(
            body.refresh_token, os.getenv("SECRET_KEY"), algorithms=[os.getenv("ALGORITHM")]
        )
        user_id = UUID(payload.get("id"))
        session_id = UUID(payload.get("session_id"))
        token_type: str = payload.get("type")

        if user_id is None or token_type != "refresh":
            raise invalid_excp

    except (JWTError, JWSError):
        raise invalid_excp
    
    stmt = select(UserSession).where(
        UserSession.id == session_id,
        UserSession.user_id == user_id
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        raise invalid_excp

    now = utcnow()

    if session.revoked_at is not None:
        raise MyHTTPException(
            status_code=401,
            content=WithoutData(status="error", message="Session revoked")
        )

    if session.expires_at <= now:
        raise MyHTTPException(
            status_code=401,
            content=WithoutData(status="error", message="Session expired")
        )

    if session.refresh_token_hash != hash_token(body.refresh_token):
        raise MyHTTPException(
            status_code=401,
            content=WithoutData(status="error", message="Logged in from another device")
        )

    user_stmt = select(Users).where(Users.id == user_id)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if not user:
        raise MyHTTPException(
            status_code=404,
            content=WithoutData(status="error", message="User not found")
        )

    if not user.is_active:
        raise MyHTTPException(
            status_code=403,
            content=WithoutData(status="error", message="Your account is inactive")
        )

    access_exp_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    refresh_exp_minutes = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", "10080"))

    new_payload = {
        "id": str(user.id),
        "session_id": str(session.id),
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
    }

    new_access_token = create_token(new_payload, "access", access_exp_minutes)
    new_refresh_token = create_token(new_payload, "refresh", refresh_exp_minutes)

    session.refresh_token_hash = hash_token(new_refresh_token)
    session.last_seen_at = now
    session.expires_at = now + timedelta(minutes=refresh_exp_minutes)

    await db.commit()
    await db.refresh(session)

    
    return RefreshRes(
        status= "success",
        access_token= new_access_token,
        refresh_token= new_refresh_token,
        message= "Token refreshed successfully"
    )
    

async def logout_user(db: AsyncSession,payload: dict,id: UUID | None,req: Request) -> WithoutData:
    current_user_id = UUID(str(payload.get("id")))
    current_role = payload.get("role")
    current_session_id = UUID(str(payload.get("session_id")))

    # decide target user
    target_user_id = id or current_user_id

    # if trying to logout another user, only admin/super admin allowed
    if target_user_id != current_user_id and current_role not in ("a", "s"):
        raise MyHTTPException(
            status_code=403,
            content=WithoutData(
                status="error",
                message="You are not allowed to logout another user"
            )
        )

    # self logout -> revoke only current session
    if target_user_id == current_user_id:
        stmt = select(UserSession).where(
            UserSession.id == current_session_id,
            UserSession.user_id == current_user_id
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()

        if session and session.revoked_at is None:
            session.revoked_at = utcnow()
            await db.commit()

        await log_activity(
            db=db,
            body=LogActivity(
                user_id=current_user_id,
                type=ActivityType.LOGOUT,
                module=ActivityModule.AUTH,
                message=ActivityMessage.LOGOUT,
                status=ActivityStatus.SUCCESS,
                ip=get_client_ip(req),
            )
        )

        return Response[WithoutData](
            status="success",
            message="Logout successfully"
        )

    # admin logout another user -> revoke target user's active session
    stmt = select(UserSession).where(
        UserSession.user_id == target_user_id,
        UserSession.revoked_at == None
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if session:
        session.revoked_at = utcnow()
        await db.commit()

    target_user = await get_object_if_exists(db, Users, target_user_id, "User")

    await log_activity(
        db=db,
        body=LogActivity(
            user_id=current_user_id,
            type=ActivityType.USER_LOGOUT,
            module=ActivityModule.USER_MASTER,
            message=f"Logged out user {target_user.first_name} {target_user.last_name}",
            status=ActivityStatus.SUCCESS,
            ref_id=target_user_id,
            ip=get_client_ip(req),
        )
    )

    return WithoutData(
        status="success",
        message="User logged out successfully"
    )
    