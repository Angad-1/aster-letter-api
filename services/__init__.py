from uuid import UUID
from contextvars import ContextVar
from typing import Optional

_current_user_id: ContextVar[Optional[UUID]] = ContextVar("_current_user_id", default=None)
_current_user_role: ContextVar[Optional[str]] = ContextVar("_current_user_role", default=None)

def set_current_user_id(user_id: UUID) -> None:
    _current_user_id.set(user_id)

def get_current_user_id() -> Optional[UUID]:
    return _current_user_id.get()

def set_current_user_role(role: str) -> None:
    _current_user_role.set(role)

def get_current_user_role() -> Optional[UUID]:
    return _current_user_role.get()
