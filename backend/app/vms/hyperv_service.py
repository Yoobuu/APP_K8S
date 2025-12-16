# filepath: app/vms/hyperv_service.py
from __future__ import annotations
from typing import List, Optional
import logging
import os

from cachetools import TTLCache
from pydantic import ValidationError
from app.providers.hyperv.remote import RemoteCreds, run_inventory
from app.providers.hyperv.schema import (
    VMRecord,
    VMRecordSummary,
    VMRecordDetail,
    VMRecordDeep,
)
from app.vms.hyperv_host_models import HyperVHostSummary

logger = logging.getLogger("hyperv.service")

# Cache por nivel
_BASE_SUMMARY_TTL = os.getenv("HYPERV_CACHE_TTL")
_CACHE_TTLS = {
    "summary": int(_BASE_SUMMARY_TTL or os.getenv("HYPERV_CACHE_TTL_SUMMARY", "300")),
    "detail": int(os.getenv("HYPERV_CACHE_TTL_DETAIL", "120")),
    "deep": int(os.getenv("HYPERV_CACHE_TTL_DEEP", "30")),
}
_HOST_CACHE: dict[str, TTLCache] = {
    level: TTLCache(maxsize=64, ttl=ttl) for level, ttl in _CACHE_TTLS.items()
}
_HOST_INFO_CACHE = TTLCache(maxsize=64, ttl=int(os.getenv("HYPERV_CACHE_TTL_HOSTS", "300")))

# ─────────────────────────────────────────────
# Helper para normalizar porcentajes
# ─────────────────────────────────────────────
def _clamp_pct(val):
    """Evita que valores como 100.01 o 149.26 rompan la validación."""
    try:
        v = float(val)
        if v < 0:
            v = 0.0
        if v > 100:
            v = 100.0
        return round(v, 2)
    except Exception:
        return None


def collect_hyperv_inventory_for_host(
    creds: RemoteCreds,
    ps_content: str,
    *,
    level: str = "summary",
    vm_name: Optional[str] = None,
    use_cache: bool = True,
) -> List[VMRecord]:
    """
    Ejecuta el colector de Hyper-V en el host indicado y valida el
    resultado contra el esquema VMRecord. Devuelve una lista de VMRecord.
    """
    level_norm = (level or "summary").lower()
    cache = _HOST_CACHE.get(level_norm)
    cache_key = ((creds.host or "").lower(), vm_name or "")
    if use_cache and cache is not None and cache_key in cache:
        logger.debug("HyperV cache hit para host %s level %s", creds.host, level_norm)
        return cache[cache_key]

    logger.debug("HyperV inventory miss para host %s level %s -> ejecutando colector", creds.host, level_norm)
    raw_items = run_inventory(
        creds,
        ps_content=ps_content,
        level=level_norm,
        vm_name=vm_name,
    )
    if vm_name:
        raw_items = [i for i in raw_items if i.get("Name") == vm_name]

    validated: List[VMRecord] = []
    dropped = 0

    for idx, item in enumerate(raw_items):
        # ─── Normalizar porcentajes ───
        item["RAM_UsagePct"] = _clamp_pct(item.get("RAM_UsagePct"))
        disks = item.get("Disks")
        if isinstance(disks, list):
            for d in disks:
                if isinstance(d, dict):
                    d["AllocatedPct"] = _clamp_pct(d.get("AllocatedPct"))

        # ─── Validación con Pydantic ───
        try:
            if level_norm == "deep":
                validated.append(VMRecordDeep.model_validate(item))
            elif level_norm == "detail":
                validated.append(VMRecordDetail.model_validate(item))
            else:
                validated.append(VMRecordSummary.model_validate(item))
        except ValidationError as ve:
            dropped += 1
            logger.warning("Descartada VM #%s de %s: %s", idx, creds.host, ve.errors())

    if dropped:
        logger.info("Host %s: %s VMs válidas, %s descartadas", creds.host, len(validated), dropped)

    if cache is not None:
        cache[cache_key] = validated
    return validated


def _dedupe_switches(raw_switches: Optional[List[dict]]) -> List[dict]:
    if not raw_switches:
        return []
    seen = set()
    deduped: List[dict] = []
    for sw in raw_switches:
        if not isinstance(sw, dict):
            continue
        name = sw.get("Name") or sw.get("name")
        key = (name, sw.get("NetAdapterInterfaceDescription"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(sw)
    return deduped


def collect_hyperv_host_info(
    creds: RemoteCreds,
    ps_content: str,
    *,
    use_cache: bool = True,
) -> HyperVHostSummary:
    """
    Obtiene información del host Hyper-V ejecutando inventario nivel deep y
    consolidando HostInfo/Switches. Cacha por host para evitar reejecuciones.
    """
    cache_key = creds.host.lower()
    if use_cache and cache_key in _HOST_INFO_CACHE:
        return _HOST_INFO_CACHE[cache_key]

    records = collect_hyperv_inventory_for_host(
        creds,
        ps_content=ps_content,
        level="deep",
        use_cache=use_cache,
    )

    if not records:
        raise RuntimeError(f"Inventario vacío en host {creds.host}")

    host_info = None
    switches: List[dict] = []
    nics: List[dict] = []
    storage: List[dict] = []
    cluster = None

    for rec in records:
        if rec.HostInfo and not host_info:
            host_info = rec.HostInfo
        if rec.Switches:
            switches.extend(rec.Switches)
        if isinstance(rec.HostInfo, dict):
            if rec.HostInfo.get("Nics"):
                nics.extend(rec.HostInfo.get("Nics"))
            if rec.HostInfo.get("Storage"):
                storage.extend(rec.HostInfo.get("Storage"))
        if not cluster and rec.Cluster:
            cluster = rec.Cluster

    switches = _dedupe_switches(switches)

    payload = HyperVHostSummary(
        host=creds.host,
        cluster=cluster,
        version=(host_info or {}).get("Version") if isinstance(host_info, dict) else None,
        logical_processors=(host_info or {}).get("LogicalProcessorCount") if isinstance(host_info, dict) else None,
        memory_capacity_bytes=(host_info or {}).get("MemoryCapacity") if isinstance(host_info, dict) else None,
        uptime_seconds=(host_info or {}).get("UptimeSeconds") if isinstance(host_info, dict) else None,
        cpu_usage_pct=(host_info or {}).get("CpuUsagePct") if isinstance(host_info, dict) else None,
        memory_usage_pct=(host_info or {}).get("MemUsagePct") if isinstance(host_info, dict) else None,
        virtual_machine_migration_enabled=(host_info or {}).get("VirtualMachineMigrationEnabled")
        if isinstance(host_info, dict)
        else None,
        total_vms=len(records),
        switches=switches or None,
        nics=nics or None,
        storage=storage or None,
    )

    _HOST_INFO_CACHE[cache_key] = payload
    return payload
