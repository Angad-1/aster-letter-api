from fastapi import Request
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlmodel import select,func,case,literal
from typing import List
from models.models import Users
from schemas.userSchema import CreateUser, UpdUser, UserRes,ChangePassword,ChangePfp,PfpRes,ToggleStatus
from services.activityServices import log_activity
from services import get_current_user_id,get_current_user_role
from schemas.activitySchema import LogActivity
from utilities.constant import ActivityType, ActivityModule, ActivityMessage, ActivityStatus
from schemas.commonSchema import Response,WithoutData
from utilities.utils import hash_password,verify_password,MyHTTPException,get_object_if_exists,save_upload_file,_safe_delete_file,get_client_ip,build_file_url

Creator = aliased(Users)
Updater = aliased(Users)

def get_activity_meta(
    is_self,
    self_type,
    admin_type,
    self_msg,
    admin_msg,
    user,
    current_user_id
):
    if is_self:
        return (
            self_type,
            ActivityModule.PROFILE,
            self_msg,
            None,
            user.id
        )

    return (
        admin_type,
        ActivityModule.USER_MASTER,
        f"{admin_msg} {user.first_name} {user.last_name}",
        user.id,
        current_user_id
    )

# def _safe_delete_file(path_str: str | None) -> None:
#     """
#     Deletes a file if it exists. Never throws to avoid breaking API response.
#     Only deletes local filesystem paths.
#     """
#     if not path_str:
#         return
#     try:
#         p = Path(path_str)
#         if p.exists() and p.is_file():
#             p.unlink()
#     except Exception:
#         # log if you have logging; don't raise
#         pass

def user_base_select(base_url: str,with_pwd: bool = False):
    """
    Common SELECT for Users with:
    - gender / role mapped
    - created_by / updated_by resolved
    - optional inclusion of password column
    """
    exclude_cols = ("created_by", "updated_by", "dsg","pfp")
    if not with_pwd:
        exclude_cols += ("pwd",)
    media_base = base_url.rstrip("/") + "/api/media/getMedia/"
    return (
        select(
            # --- Base columns (exclude internal) ---
            *(c for c in Users.__table__.c if c.name not in exclude_cols),
            Users.dsg.label("designation"),
            case(
              (  Users.pfp.isnot(None),
                literal(media_base) + func.file_stem(Users.pfp),
                ),
                else_=None,
            ).label("profile_picture"),
            # --- Gender mapping ---
            # case(
            #     (Users.gender == "m", "Male"),
            #     (Users.gender == "f", "Female"),
            #     (Users.gender == "o", "Other"),
            #     else_="Unknown"
            # ).label("gender"),

            # # --- Role mapping ---
            # case(
            #     (Users.role == "u", "User"),
            #     (Users.role == "a", "Admin"),
            #     (Users.role == "s", "Super Admin"),
            #     else_="Unknown"
            # ).label("role"),

            # --- Creator / Updater ---
            func.concat(Creator.first_name, " ", Creator.last_name).label("created_by"),
            func.concat(Updater.first_name, " ", Updater.last_name).label("updated_by"),
        )
        .outerjoin(Creator, Users.created_by == Creator.id)
        .outerjoin(Updater, Users.updated_by == Updater.id)
    )

async def is_exist(db: AsyncSession,key,value: str) -> bool:
    stmt = select(Users.id).where(key == value)
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None

async def create_user(db: AsyncSession, body: CreateUser, req: Request) -> Response[UserRes]:
    """
    Create a new user in the system.

    Steps:
    1. Validate uniqueness of contact number.
    2. Prepare user data dictionary (excluding password).
    3. Hash the password securely.
    4. Persist Users model.
    5. Build UserRes .
    """ 

    if body.contact_no and await is_exist(db, Users.contact_no,body.contact_no):
        raise MyHTTPException(status_code=400, content=WithoutData(status="error", message="Contact number already exists"))
    
    if body.email and await is_exist(db, Users.email,body.email):
        raise MyHTTPException(status_code=400, content=WithoutData(status="error", message="Email already exists"))
    
    if body.username and await is_exist(db, Users.username,body.username):
        raise MyHTTPException(status_code=400, content=WithoutData(status="error", message="Username already exists"))
    
    new_user = Users(
        **{
            k: v
            for k, v in vars(body).items()
            if k not in ("profile_picture", "password", "designation")
        },
        pwd=hash_password(body.password),
        dsg=body.designation,
    )
    db.add(new_user)
    await db.flush()  
    await db.refresh(new_user)
    
    updated=False
    if body.profile_picture:
        profile_info=await save_upload_file(body.profile_picture,"pfp")
        new_user._skip_audit = True 
        new_user.pfp = profile_info["path"]
        updated=True
    if updated:
        await db.flush()
        await db.refresh(new_user)
        
    await log_activity(
        db=db,
        body=LogActivity(
            user_id=get_current_user_id(),
            type=ActivityType.USER_CREATED,
            module=ActivityModule.USER_MASTER,
            message=f"Created user {new_user.first_name} {new_user.last_name}",
            status=ActivityStatus.SUCCESS,
            ref_id=new_user.id,
            ip=get_client_ip(req),
        )
    )
        
    stmt = user_base_select(str(req.base_url)).where(Users.id == new_user.id)

    result = await db.execute(stmt)
    row = result.mappings().one()
    res_data = UserRes(**row)
    # res_dict = res_data.model_dump()
    # res_dict["profile_picture"] = build_file_url(req, res_dict.get("profile_picture"))

    return Response[UserRes](
        status="success",
        data=res_data.model_dump(),
        message="User created successfully"
    )
    
async def update_user(db: AsyncSession, user: UpdUser,req:Request) -> Response[UserRes]:
    """
    Updates an existing user's profile in the Auth table.

    Steps:
    1. Resolve internal user ID from the provided UUID.
    2. Fetch the current user record from the database.
    3. Check for contact uniqueness if updated.
    4. Update fields (including optional password).
    5. Commit changes and build a user response.
    """
    existing_user = await get_object_if_exists(db,Users, user.id,"User")
    update_fields = user.model_dump(exclude_unset=True)

    # Check contact_no uniqueness if updated and different
    if 'contact_no' in update_fields and update_fields['contact_no'] != existing_user.contact_no:
        stmt = select(Users).where(Users.contact_no == update_fields['contact_no'], Users.id != existing_user.id)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise MyHTTPException(status_code=400, content=WithoutData(status="error", message="Contact number already exists"))
        
    if 'email' in update_fields and update_fields['email'] != existing_user.email:
        stmt = select(Users).where(Users.email == update_fields['email'], Users.id != existing_user.id)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise MyHTTPException(status_code=400, content=WithoutData(status="error", message="Email already exists"))
        
        
    update_fields["dsg"]=update_fields["designation"]
    
    # Update fields except id
    for field, value in update_fields.items():
        if field not in ("id","designation"):
            setattr(existing_user, field, value)

    await db.flush()
    await db.refresh(existing_user)
    
    is_self = str(get_current_user_id()) == str(existing_user.id)

    activity_type, module, message, ref_id, actor_id = get_activity_meta(
        is_self,
        ActivityType.PROFILE_UPDATED,
        ActivityType.USER_UPDATED,
        ActivityMessage.PROFILE_UPDATED,
        "Updated user details for",
        existing_user,
        get_current_user_id()
    )

    await log_activity(
        db=db,
        body=LogActivity(
            user_id=actor_id,
            type=activity_type,
            module=module,
            message=message,
            status=ActivityStatus.SUCCESS,
            ref_id=ref_id,
            ip=get_client_ip(req),
        )
    )

    stmt = user_base_select(str(req.base_url)).where(Users.id==existing_user.id)

    result = await db.execute(stmt)
    row = result.mappings().one()
    res_data = UserRes(**row)

    return Response[UserRes](
        status="success",
        data=res_data.model_dump(),
        message="User updated successfully"
    )

async def get_user(req:Request,db:AsyncSession,id:UUID | None = None):
    # conditions = []

    # for table in Base.metadata.tables.values():
    #     for col_name in ["created_by", "updated_by"]:
    #         if col_name in table.c:
    #             subq = select(literal(True)).where(table.c[col_name] == Auth.id).limit(1)
    #             # Convert to EXISTS
    #             conditions.append(subq.exists())

    # is_ref_expr = or_(*conditions) if conditions else literal(False)
    stmt = user_base_select(str(req.base_url))
    if id:
        stmt = stmt.where(Users.id == id)

    result = await db.execute(stmt)
    rows = result.mappings().all() 
    
    if id and not rows[0]:
        raise MyHTTPException(
            status_code=404,
            content=WithoutData(status="error", message="User not found")
        )

    return Response[UserRes if id else List[UserRes]](
        status="success",
        data=rows[0] if id else rows,
        message="User retrieved successfully" if id else "Users retrieved successfully"
    )

async def delete_user(req:Request,db: AsyncSession, id: UUID) -> Response[WithoutData]:
    user= await get_object_if_exists(db,Users,id,'User')
    await db.delete(user)
    await db.commit()

    await log_activity(
        db=db,
        body=LogActivity(
            user_id=get_current_user_id(), 
            type=ActivityType.USER_DELETED,
            module=ActivityModule.USER_MASTER,
            message=f"Deleted user {user.first_name} {user.last_name}",
            status=ActivityStatus.SUCCESS,
            ref_id=id,
            ip=get_client_ip(req),
        )
    )

    return Response[WithoutData](
        status="success",
        message="User deleted successfully"
    )

async def change_password(db: AsyncSession, body:ChangePassword,req:Request) -> Response[WithoutData]:
    """
    Change password for a user.

    Steps:
    1. Fetch user by ID
    2. Verify old password
    3. Hash new password and update
    4. Commit
    """
    user = await get_object_if_exists(db, Users, body.id, "User")

    if not verify_password(body.old_password, user.pwd):
        raise MyHTTPException(
            status_code=400,
            content=WithoutData(status="error", message="Old password is incorrect")
        )

    if body.old_password == body.new_password:
        raise MyHTTPException(
            status_code=400,
            content=WithoutData(status="error", message="New password cannot be same as old password")
        )

    user._skip_audit = True
    user.pwd = hash_password(body.new_password)

    await db.commit()
    
    is_self = str(get_current_user_id()) == str(user.id)

    activity_type, module, message, ref_id, actor_id = get_activity_meta(
        is_self,
        ActivityType.PASSWORD_CHANGED,
        ActivityType.USER_PASSWORD_CHANGED,
        ActivityMessage.PASSWORD_CHANGED,
        "Changed password for",
        user,
        get_current_user_id()
    )

    await log_activity(
        db=db,
        body=LogActivity(
            user_id=actor_id,
            type=activity_type,
            module=module,
            message=message,
            status=ActivityStatus.SUCCESS,
            ref_id=ref_id,
            ip=get_client_ip(req),
        )
    )

    return Response[WithoutData](
        status="success",
        message="Password changed successfully"
    )

async def change_profile_picture(db: AsyncSession, body:ChangePfp, req: Request) -> PfpRes:
    if not body.profile_picture:
        raise MyHTTPException(
            status_code=400,
            content=WithoutData(status="error", message="Profile picture is required")
        )

    user = await get_object_if_exists(db, Users, body.id, "User")

    # 1) Remember old file path (for deletion later)
    old_pfp = user.pfp

    # 2) Save new file FIRST
    profile_info = await save_upload_file(body.profile_picture, "pfp")
    new_pfp_path = profile_info["path"]

    # 3) Update DB to new path
    user._skip_audit = True
    user.pfp = new_pfp_path

    await db.flush()
    await db.refresh(user)

    # 4) Delete old file AFTER successful commit
    # Optional: don't delete if same path or empty
    if old_pfp and old_pfp != new_pfp_path:
        _safe_delete_file(old_pfp)
        
    is_self = str(get_current_user_id()) == str(user.id)

    activity_type, module, message, ref_id, actor_id = get_activity_meta(
        is_self,
        ActivityType.PROFILE_PICTURE_CHANGED,
        ActivityType.USER_PROFILE_PICTURE_CHANGED,
        ActivityMessage.PROFILE_PICTURE_CHANGED,
        "Updated profile picture for",
        user,
        get_current_user_id()
    )

    await log_activity(
        db=db,
        body=LogActivity(
            user_id=actor_id,
            type=activity_type,
            module=module,
            message=message,
            status=ActivityStatus.SUCCESS,
            ref_id=ref_id,
            ip=get_client_ip(req),
        )
    )

    return PfpRes(
        status="success",
        profile_picture=build_file_url(req,new_pfp_path),
        message="Profile picture updated successfully"
    )
         
async def toggle_user_active(db: AsyncSession,body:ToggleStatus,req: Request) -> WithoutData:
    
    if get_current_user_role() == body.id:
        raise MyHTTPException(
            status_code=400,
            content=WithoutData(
                status="error",
                message="You cannot activate or deactivate your own account"
            )
        )
        
    if get_current_user_role() not in ("a", "s"):
        raise MyHTTPException(
            status_code=403,
            content=WithoutData(
                status="error",
                message="You are not allowed to change user status"
            )
        )

    user = await get_object_if_exists(db, Users, body.id, "User")

    if user.is_active == body.is_active:
        return Response[WithoutData](
            status="success",
            message=f"User already {'active' if body.is_active else 'inactive'}"
        )
    user._skip_audit = True
    user.is_active = body.is_active

    await db.flush()
    await db.refresh(user)

    await log_activity(
        db=db,
        body=LogActivity(
            user_id=get_current_user_id(),
            type= ActivityType.USER_ACTIVATED if body.is_active else ActivityType.USER_DEACTIVATED,
            module=ActivityModule.USER_MASTER,
            message=f"{'Activated' if body.is_active else 'Deactivated'} user {user.first_name} {user.last_name}",
            status=ActivityStatus.SUCCESS,
            ref_id=body.id,
            ip=get_client_ip(req),
        )
    )

    return WithoutData(
        status="success",
        message=f"User {'activated' if body.is_active else 'deactivated'} successfully"
    )