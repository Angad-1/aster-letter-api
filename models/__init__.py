from sqlalchemy import event
from sqlmodel import SQLModel
from datetime import datetime, timezone
from services import get_current_user_id


@event.listens_for(SQLModel, "before_insert", propagate=True)
def before_insert(mapper, connection, target):
    if hasattr(target, "created_by") and getattr(target, "created_by") is None:
        target.created_by = get_current_user_id()


@event.listens_for(SQLModel, "before_update", propagate=True)
def before_update(mapper, connection, target):
    if getattr(target, "_skip_audit", False):
        return
    if hasattr(target, "updated_at"):
        target.updated_at = datetime.now(timezone.utc)
    if hasattr(target, "updated_by"):
        target.updated_by = get_current_user_id()