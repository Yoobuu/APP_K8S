from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class HyperVHostSummary(BaseModel):
    """Información básica del host Hyper-V."""

    host: str
    cluster: Optional[str] = None
    version: Optional[str] = None
    logical_processors: Optional[int] = None
    memory_capacity_bytes: Optional[int] = None
    uptime_seconds: Optional[int] = None
    cpu_usage_pct: Optional[float] = None
    memory_usage_pct: Optional[float] = None
    virtual_machine_migration_enabled: Optional[bool] = None
    total_vms: int
    switches: Optional[List[Dict[str, Any]]] = None
    nics: Optional[List[Dict[str, Any]]] = None
    storage: Optional[List[Dict[str, Any]]] = None
