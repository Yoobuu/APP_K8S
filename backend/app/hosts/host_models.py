from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class HostSummary(BaseModel):
    id: str
    name: Optional[str]
    connection_state: Optional[str]
    power_state: Optional[str]
    cluster: Optional[str]
    cpu_cores: Optional[int]
    cpu_threads: Optional[int]
    memory_total_mb: Optional[int]
    overall_cpu_usage_mhz: Optional[int]
    overall_memory_usage_mb: Optional[int]
    version: Optional[str]
    build: Optional[str]
    total_vms: Optional[int]


class HostDetail(BaseModel):
    id: str
    name: Optional[str]
    datacenter: Optional[str]
    cluster: Optional[str]
    hardware: Dict[str, Any]
    esxi: Dict[str, Any]
    quick_stats: Dict[str, Any]
    networking: Dict[str, Any]
    datastores: List[Dict[str, Any]]
    vms: List[Dict[str, Any]]


class HostDeep(BaseModel):
    id: str
    name: Optional[str]
    sensors: List[Dict[str, Any]]
    networking: Dict[str, Any]
    storage: Dict[str, Any]
    security: Dict[str, Any]
    profiles: Dict[str, Any]
    hardware: Dict[str, Any]
    runtime: Dict[str, Any]
    datastores: List[Dict[str, Any]]
    vms: List[Dict[str, Any]]
