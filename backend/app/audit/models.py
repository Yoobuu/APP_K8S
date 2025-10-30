from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditLog(SQLModel, table=True):
    """Audit trail entry persisted for sensitive operations."""

    id: Optional[int] = Field(default=None, primary_key=True)
    when: datetime = Field(default_factory=utcnow, nullable=False, index=True)

    actor_id: Optional[int] = Field(default=None, index=True)
    actor_username: Optional[str] = Field(default=None, index=True)

    action: str = Field(nullable=False, index=True, max_length=128)

    target_type: Optional[str] = Field(default=None, index=True, max_length=64)
    target_id: Optional[str] = Field(default=None, index=True, max_length=128)

    meta: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON(none_as_null=True), nullable=True),
    )

    ip: Optional[str] = Field(default=None, max_length=64)
    user_agent: Optional[str] = Field(default=None, max_length=512)
    correlation_id: Optional[str] = Field(default=None, index=True, max_length=64)
