from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import require_permission
from app.permissions.models import PermissionCode
from app.cedia import service as cedia_service

router = APIRouter(prefix="/api/cedia", tags=["cedia"])


@router.get("/login", dependencies=[Depends(require_permission(PermissionCode.CEDIA_VIEW))])
def cedia_login():
    """Obtiene un token nuevo de CEDIA."""
    return cedia_service.login()


@router.get("/vms", dependencies=[Depends(require_permission(PermissionCode.CEDIA_VIEW))])
def cedia_list_vms():
    """Listado de VMs en CEDIA."""
    return cedia_service.list_vms()


@router.get("/vms/{vm_id}", dependencies=[Depends(require_permission(PermissionCode.CEDIA_VIEW))])
def cedia_vm_detail(vm_id: str):
    """Detalle completo de una VM en CEDIA."""
    return cedia_service.get_vm_detail(vm_id)


@router.get("/vms/{vm_id}/metrics", dependencies=[Depends(require_permission(PermissionCode.CEDIA_VIEW))])
def cedia_vm_metrics(vm_id: str):
    """Métricas actuales de una VM en CEDIA."""
    return cedia_service.get_vm_metrics(vm_id)
