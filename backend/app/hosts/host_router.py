import logging
from typing import List

from fastapi import APIRouter, Depends, Path, Query

from app.auth.user_model import User
from app.dependencies import require_permission
from app.permissions.models import PermissionCode
from app.hosts.host_models import HostDeep, HostDetail, HostSummary
from app.hosts.host_service import get_host_deep, get_host_detail, get_hosts_summary

router = APIRouter(prefix="/hosts")
logger = logging.getLogger(__name__)


@router.get("/", response_model=List[HostSummary])
def list_hosts(
    refresh: bool = Query(False, description="Forzar refresco del cache de hosts"),
    current_user: User = Depends(require_permission(PermissionCode.VMS_VIEW)),
):
    logger.info("GET /api/hosts by '%s' (refresh=%s)", current_user.username, refresh)
    return get_hosts_summary(refresh=refresh)


@router.get("/{host_id}", response_model=HostDetail)
def host_detail(
    host_id: str = Path(..., description="MOID del host"),
    refresh: bool = Query(False, description="Forzar refresco del cache"),
    current_user: User = Depends(require_permission(PermissionCode.VMS_VIEW)),
):
    logger.debug("GET /api/hosts/%s by '%s' (refresh=%s)", host_id, current_user.username, refresh)
    return get_host_detail(host_id, refresh=refresh)


@router.get("/{host_id}/deep", response_model=HostDeep)
def host_deep(
    host_id: str = Path(..., description="MOID del host"),
    refresh: bool = Query(False, description="Forzar refresco del cache deep"),
    current_user: User = Depends(require_permission(PermissionCode.VMS_VIEW)),
):
    logger.debug("GET /api/hosts/%s/deep by '%s' (refresh=%s)", host_id, current_user.username, refresh)
    return get_host_deep(host_id, refresh=refresh)
