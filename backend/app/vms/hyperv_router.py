from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path as FsPath
from typing import List, Optional

from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException, Query, Path as PathParam
from sqlmodel import Session

from app.audit.service import log_audit
from app.auth.user_model import User
from app.db import get_session
from app.dependencies import require_permission
from app.permissions.models import PermissionCode
from app.providers.hyperv.remote import RemoteCreds, run_power_action
from app.providers.hyperv.schema import VMRecord, VMRecordDetail, VMRecordSummary, VMRecordDeep
from app.vms.hyperv_service import collect_hyperv_inventory_for_host, collect_hyperv_host_info
from app.vms.hyperv_host_models import HyperVHostSummary
from app.vms.hyperv_power_service import hyperv_power_action

router = APIRouter(prefix="/api/hyperv", tags=["hyperv"])
logger = logging.getLogger(__name__)

CACHE_TTL = int(os.getenv("HYPERV_CACHE_TTL", "300"))
_BATCH_CACHE = TTLCache(maxsize=32, ttl=CACHE_TTL)

# Ruta al script PowerShell (puedes overridear con HYPERV_PS_PATH)
# Usamos Path(__file__) para anclar la ruta al propio módulo sin depender del cwd.
# parents[2] sube dos niveles: app/vms/hyperv_router.py -> app/vms -> app.
DEFAULT_PS_PATH = (
    FsPath(__file__).resolve().parents[2] / "scripts" / "collect_hyperv_inventory.ps1"
).resolve()


def _load_ps_content() -> str:
    ps_path = os.environ.get("HYPERV_PS_PATH", DEFAULT_PS_PATH)
    try:
        with open(ps_path, "r", encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        logger.error("Hyper-V PowerShell script not found at '%s'", ps_path)
        raise HTTPException(
            status_code=500,
            detail=f"No se encontró el script PowerShell en '{ps_path}'. "
            f"Define HYPERV_PS_PATH o crea el archivo.",
        )


def get_creds(
    host: Optional[str] = Query(
        default=None,
        description="Hostname/FQDN/IP del host Hyper-V (si se omite, usa HYPERV_HOST del entorno).",
    )
) -> RemoteCreds:
    resolved_host = host or os.environ.get("HYPERV_HOST", "")
    if not resolved_host:
        raise HTTPException(400, "Define HYPERV_HOST en el entorno o pasa ?host= en la URL.")
    return RemoteCreds(
        host=resolved_host,
        username=os.environ.get("HYPERV_USER"),
        password=os.environ.get("HYPERV_PASS"),
        transport=os.environ.get("HYPERV_TRANSPORT", "ntlm"),
        use_winrm=True,
    )


def _normalize_level(level: str, allowed: set[str]) -> str:
    lvl = (level or "summary").lower()
    if lvl not in allowed:
        raise HTTPException(status_code=400, detail=f"Nivel no soportado. Usa uno de: {', '.join(sorted(allowed))}")
    return lvl


@router.get("/vms", response_model=List[VMRecordDetail])
def list_hyperv_vms(
    refresh: bool = Query(False, description="Forzar refresco desde los hosts, ignorando cache"),
    level: str = Query("summary", description="Nivel de detalle: summary, detail o deep"),
    creds: RemoteCreds = Depends(get_creds),
    _user: User = Depends(require_permission(PermissionCode.HYPERV_VIEW)),
):
    lvl = _normalize_level(level, {"summary", "detail", "deep"})
    ps_content = _load_ps_content()
    items = collect_hyperv_inventory_for_host(
        creds,
        ps_content=ps_content,
        level=lvl,
        use_cache=not refresh,
    )
    return items


def _parse_hosts_env(raw: str | None) -> list[str]:
    """Parse comma/semicolon-separated hostnames into a unique, ordered list."""
    if not raw:
        return []
    hosts = [h.strip() for h in raw.replace(";", ",").split(",")]
    return list(dict.fromkeys([h for h in hosts if h]))


def _resolve_host_list(query_hosts: str | None) -> list[str]:
    if query_hosts:
        return _parse_hosts_env(query_hosts)
    env_hosts = os.environ.get("HYPERV_HOSTS")
    if env_hosts:
        return _parse_hosts_env(env_hosts)
    single = (os.environ.get("HYPERV_HOST") or "").strip()
    return [single] if single else []


@router.get("/vms/batch")
def list_hyperv_vms_batch(
    hosts: str | None = Query(
        default=None,
        description="Lista de hosts separada por comas (overridea HYPERV_HOSTS).",
    ),
    max_workers: int = Query(4, ge=1, le=16, description="Paralelismo de consultas"),
    refresh: bool = Query(False, description="Forzar refresco y omitir cache"),
    level: str = Query("summary", description="Nivel soportado solo summary en batch"),
    _user: User = Depends(require_permission(PermissionCode.HYPERV_VIEW)),
):
    lvl = _normalize_level(level, {"summary"})
    # 1) resolver lista de hosts
    host_list = _resolve_host_list(hosts)
    if not host_list:
        raise HTTPException(400, "No hay hosts. Define HYPERV_HOSTS en .env o pasa ?hosts=...")

    cache_key = (tuple(sorted(host_list)), lvl)
    if not refresh and cache_key in _BATCH_CACHE:
        return _BATCH_CACHE[cache_key]

    # 2) script PS
    ps_content = _load_ps_content()

    # 3) función worker por host
    def _work(h: str):
        creds = RemoteCreds(
            host=h,
            username=os.environ.get("HYPERV_USER"),
            password=os.environ.get("HYPERV_PASS"),
            transport=os.environ.get("HYPERV_TRANSPORT", "ntlm"),
            use_winrm=True,
        )
        items = collect_hyperv_inventory_for_host(
            creds, ps_content=ps_content, use_cache=not refresh, level=lvl
        )
        # devolvemos lista ya validada (VMRecord -> dict)
        return h, [i.model_dump() for i in items]

    results: dict[str, list[dict]] = {}
    errors: dict[str, str] = {}

    # 4) ejecución paralela (controlada)
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        fut_map = {ex.submit(_work, h): h for h in host_list}
        for fut in as_completed(fut_map):
            h = fut_map[fut]
            try:
                host, data = fut.result()
                results[host] = data
            except Exception as e:
                logger.warning("Error collecting Hyper-V inventory for host '%s': %s", h, e)
                errors[h] = str(e)

    payload = {
        "ok": len(errors) == 0,
        "total_hosts": len(host_list),
        "hosts_ok": list(results.keys()),
        "hosts_error": errors,
        "total_vms": sum(len(v) for v in results.values()),
        "results": results,  # dict {host: [VMRecord...]}
    }
    _BATCH_CACHE[cache_key] = payload
    return payload


@router.get("/vms/{hvhost}", response_model=List[VMRecordDetail])
def list_hyperv_vms_by_host(
    hvhost: str,
    level: str = Query("summary", description="Nivel de detalle: summary o detail"),
    refresh: bool = Query(False, description="Forzar refresco desde el host"),
    _user: User = Depends(require_permission(PermissionCode.HYPERV_VIEW)),
):
    lvl = _normalize_level(level, {"summary", "detail"})
    ps_content = _load_ps_content()
    creds = RemoteCreds(
        host=hvhost,
        username=os.environ.get("HYPERV_USER"),
        password=os.environ.get("HYPERV_PASS"),
        transport=os.environ.get("HYPERV_TRANSPORT", "ntlm"),
        use_winrm=True,
    )
    items = collect_hyperv_inventory_for_host(
        creds,
        ps_content=ps_content,
        level=lvl,
        use_cache=not refresh,
    )
    return items


@router.post("/vms/{hvhost}/{vm_name}/power/{action}")
def hyperv_vm_power_action(
    hvhost: str = PathParam(..., description="Host Hyper-V objetivo"),
    vm_name: str = PathParam(..., description="Nombre EXACTO de la VM tal como aparece en Hyper-V"),
    action: str = PathParam(..., description="Acción: start, stop o reset"),
    refresh: bool = Query(False, description="Forzar refresco de inventario antes de actuar"),
    _user: User = Depends(require_permission(PermissionCode.HYPERV_POWER)),
):
    """
    Ejecuta una acción de energía ('start', 'stop', 'reset') sobre una VM específica
    en el host indicado. Solo se permite si la VM es sandbox.
    """

    if action not in {"start", "stop", "reset"}:
        raise HTTPException(status_code=400, detail="Acción no válida")

    # Construimos las credenciales RemoteCreds para este host
    creds = RemoteCreds(
        host=hvhost,
        username=os.environ.get("HYPERV_USER"),
        password=os.environ.get("HYPERV_PASS"),
        transport=os.environ.get("HYPERV_TRANSPORT", "ntlm"),
        use_winrm=True,
    )

    # Reutilizamos el mismo script PowerShell que se usa para inventario,
    # porque hyperv_power_action necesita inventario fresco para validar sandbox.
    ps_content = _load_ps_content()

    return hyperv_power_action(
        creds=creds,
        vm_name=vm_name,
        action=action,
        ps_content_inventory=ps_content,
        use_cache=not refresh,
    )


@router.get("/vms/{hvhost}/{vm_name}/detail", response_model=VMRecordDetail)
def hyperv_vm_detail(
    hvhost: str,
    vm_name: str,
    refresh: bool = Query(False, description="Forzar refresco"),
    _user: User = Depends(require_permission(PermissionCode.HYPERV_VIEW)),
):
    ps_content = _load_ps_content()
    creds = RemoteCreds(
        host=hvhost,
        username=os.environ.get("HYPERV_USER"),
        password=os.environ.get("HYPERV_PASS"),
        transport=os.environ.get("HYPERV_TRANSPORT", "ntlm"),
        use_winrm=True,
    )
    records = collect_hyperv_inventory_for_host(
        creds,
        ps_content=ps_content,
        level="detail",
        vm_name=vm_name,
        use_cache=not refresh,
    )
    for rec in records:
        if rec.Name == vm_name:
            return rec
    raise HTTPException(status_code=404, detail="VM no encontrada")


@router.get("/vms/{hvhost}/{vm_name}/deep", response_model=VMRecordDeep)
def hyperv_vm_deep(
    hvhost: str,
    vm_name: str,
    refresh: bool = Query(False, description="Forzar refresco"),
    _user: User = Depends(require_permission(PermissionCode.HYPERV_VIEW)),
):
    ps_content = _load_ps_content()
    creds = RemoteCreds(
        host=hvhost,
        username=os.environ.get("HYPERV_USER"),
        password=os.environ.get("HYPERV_PASS"),
        transport=os.environ.get("HYPERV_TRANSPORT", "ntlm"),
        use_winrm=True,
    )
    records = collect_hyperv_inventory_for_host(
        creds,
        ps_content=ps_content,
        level="deep",
        vm_name=vm_name,
        use_cache=not refresh,
    )
    for rec in records:
        if rec.Name == vm_name:
            return rec
    raise HTTPException(status_code=404, detail="VM no encontrada")


@router.get("/hosts")
def list_hyperv_hosts(
    hosts: str | None = Query(
        default=None,
        description="Lista de hosts separada por comas (overridea HYPERV_HOSTS/HYPERV_HOST).",
    ),
    refresh: bool = Query(False, description="Forzar refresco (omite cache de host)"),
    max_workers: int = Query(4, ge=1, le=16, description="Paralelismo de consultas"),
    _user: User = Depends(require_permission(PermissionCode.HYPERV_VIEW)),
):
    host_list = _resolve_host_list(hosts)
    if not host_list:
        raise HTTPException(400, "No hay hosts. Define HYPERV_HOSTS o HYPERV_HOST en .env o pasa ?hosts=...")

    ps_content = _load_ps_content()

    results: List[HyperVHostSummary] = []
    errors: dict[str, str] = {}

    def _work(h: str) -> HyperVHostSummary:
        creds = RemoteCreds(
            host=h,
            username=os.environ.get("HYPERV_USER"),
            password=os.environ.get("HYPERV_PASS"),
            transport=os.environ.get("HYPERV_TRANSPORT", "ntlm"),
            use_winrm=True,
        )
        return collect_hyperv_host_info(creds, ps_content=ps_content, use_cache=not refresh)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        fut_map = {ex.submit(_work, h): h for h in host_list}
        for fut in as_completed(fut_map):
            h = fut_map[fut]
            try:
                results.append(fut.result())
            except Exception as e:
                logger.warning("Error collecting Hyper-V host info for '%s': %s", h, e)
                errors[h] = str(e)

    # Devolvemos parciales si hay errores, para no bloquear UI
    payload = {
        "ok": len(errors) == 0,
        "hosts_ok": [r.host for r in results],
        "hosts_error": errors,
        "results": [r.model_dump() for r in results],
    }
    return payload


@router.get("/hosts/{hvhost}", response_model=HyperVHostSummary)
def hyperv_host_detail(
    hvhost: str,
    refresh: bool = Query(False, description="Forzar refresco"),
    _user: User = Depends(require_permission(PermissionCode.HYPERV_VIEW)),
):
    ps_content = _load_ps_content()
    creds = RemoteCreds(
        host=hvhost,
        username=os.environ.get("HYPERV_USER"),
        password=os.environ.get("HYPERV_PASS"),
        transport=os.environ.get("HYPERV_TRANSPORT", "ntlm"),
        use_winrm=True,
    )
    try:
        return collect_hyperv_host_info(
            creds,
            ps_content=ps_content,
            use_cache=not refresh,
        )
    except Exception as exc:
        logger.warning("Error collecting Hyper-V host info for '%s': %s", hvhost, exc)
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/lab/power")
def lab_power_action(
    hvhost: str,
    vm_name: str,
    action: str,
    _user: User = Depends(require_permission(PermissionCode.HYPERV_POWER)),
):
    """
    Endpoint TEMPORAL de laboratorio (solo local).
    Ejecuta start / stop / reset en la VM indicada.
    NO usa _is_sandbox_vm todavía, asumo que voy a pasar yo manualmente una sandbox segura.
    """
    action = action.lower().strip()
    if action not in {"start", "stop", "reset"}:
        raise HTTPException(status_code=400, detail="Acción no válida")

    creds = RemoteCreds(
        host=hvhost,
        username=os.environ.get("HYPERV_USER"),
        password=os.environ.get("HYPERV_PASS"),
        transport=os.environ.get("HYPERV_TRANSPORT", "ntlm"),
        use_winrm=True,
    )

    ok, msg = run_power_action(creds, vm_name, action)
    if not ok:
        raise HTTPException(status_code=502, detail=msg)

    return {"ok": True, "message": msg}
