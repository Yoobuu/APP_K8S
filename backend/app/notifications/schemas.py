from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, SerializationInfo, field_serializer


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    vm_id: Optional[str] = None
    vm_name: str
    metric: str
    value_pct: float
    threshold_pct: float
    env: Optional[str] = None
    at: datetime
    status: str
    ack_by: Optional[str] = None
    ack_at: Optional[datetime] = None
    cleared_at: Optional[datetime] = None
    correlation_id: Optional[str] = None
    created_at: datetime
    archived: bool = False
    disks_json: Optional[List[Dict[str, Any]]] = None

    @field_serializer("status")
    def serialize_status(self, value: str, info: SerializationInfo) -> str:  # noqa: ARG002, ARG005
        if value is None:
            return value
        return value.upper()


class NotificationListResponse(BaseModel):
    items: List[NotificationRead]
    total: int
    limit: int
    offset: int


class AckResponse(BaseModel):
    ok: bool = True
    notification: NotificationRead


class ClearResolvedRequest(BaseModel):
    dry_run: bool = Field(default=False)


class ClearResolvedResponse(BaseModel):
    cleared_count: int
    dry_run: bool
