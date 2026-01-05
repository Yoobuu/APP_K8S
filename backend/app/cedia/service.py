from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import requests
from fastapi import HTTPException, status
from app.settings import settings

logger = logging.getLogger(__name__)

API_VERSION = "38.1"
LOGIN_PATH = "/cloudapi/1.0.0/sessions"
LIST_VMS_PATH = "/api/query"
VM_DETAIL_PATH = "/api/vApp/{vm_id}"
VM_METRICS_PATH = "/api/vApp/{vm_id}/metrics/current"
VM_HW_SECTION_PATH = "/api/vApp/{vm_id}/virtualHardwareSection/"
VM_HW_DISKS_PATH = "/api/vApp/{vm_id}/virtualHardwareSection/disks"
VM_NETWORK_SECTION_PATH = "/api/vApp/{vm_id}/networkConnectionSection/"


@dataclass
class CediaConfig:
    base_url: str
    user: str
    password: str


@dataclass
class TokenState:
    token: str
    expires_at: datetime


_token_state: Optional[TokenState] = None


def _resolve_config() -> CediaConfig:
    base = (settings.cedia_base or "").rstrip("/")
    user = settings.cedia_user or ""
    password = settings.cedia_pass or ""
    if not base or not user or not password:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Faltan credenciales CEDIA (CEDIA_BASE, CEDIA_USER, CEDIA_PASS)",
        )
    return CediaConfig(base_url=base, user=user, password=password)


def _auth_header_basic(user: str, password: str) -> str:
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _build_headers(*, accept_variant: str = "application/json") -> Dict[str, str]:
    return {
        "Accept": f"{accept_variant};version={API_VERSION}",
    }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_token() -> str:
    global _token_state
    if _token_state and _token_state.expires_at > _now():
        return _token_state.token

    cfg = _resolve_config()
    url = f"{cfg.base_url}{LOGIN_PATH}"
    headers = _build_headers()
    headers["Authorization"] = _auth_header_basic(cfg.user, cfg.password)

    try:
        resp = requests.post(url, headers=headers, timeout=10)
    except requests.RequestException as exc:
        logger.exception("Error conectando a CEDIA /sessions")
        raise HTTPException(status_code=502, detail=f"Error conectando a CEDIA: {exc}") from exc

    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"Fallo de autenticación CEDIA ({resp.status_code})",
        )

    token = resp.headers.get("X-VMWARE-VCLOUD-ACCESS-TOKEN")
    if not token:
        raise HTTPException(
            status_code=500,
            detail="Respuesta de login CEDIA sin token",
        )

    # El token expira en ~240 minutos; usamos un margen.
    expires_at = _now() + timedelta(minutes=230)
    _token_state = TokenState(token=token, expires_at=expires_at)
    return token


def reset_token() -> None:
    global _token_state
    _token_state = None


def _cedia_get(path: str, *, params: Optional[Dict[str, Any]] = None, accept_variant: str = "application/*+json"):
    token = _ensure_token()
    cfg = _resolve_config()
    url = f"{cfg.base_url}{path}"
    headers = _build_headers(accept_variant=accept_variant)
    headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
    except requests.RequestException as exc:
        logger.exception("Error conectando a CEDIA %s", path)
        raise HTTPException(status_code=502, detail=f"Error conectando a CEDIA: {exc}") from exc

    if resp.status_code == 401:
        # token expirado, reintenta una vez
        reset_token()
        token = _ensure_token()
        headers["Authorization"] = f"Bearer {token}"
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
        except requests.RequestException as exc:
            logger.exception("Error conectando a CEDIA %s tras reintento", path)
            raise HTTPException(status_code=502, detail=f"Error conectando a CEDIA: {exc}") from exc

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Recurso no encontrado en CEDIA")

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=f"Error CEDIA ({resp.status_code})")

    try:
        return resp.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Respuesta CEDIA inválida (no JSON)") from exc


def login() -> Dict[str, Any]:
    token = _ensure_token()
    return {"token": token, "expires_at": _token_state.expires_at.isoformat() if _token_state else None}


def list_vms() -> Dict[str, Any]:
    params = {
        "type": "vm",
        "format": "records",
        "page": 1,
        "pageSize": 200,
        "links": "true",
    }
    return _cedia_get(LIST_VMS_PATH, params=params, accept_variant="application/*+json")


def get_vm_detail(vm_id: str) -> Dict[str, Any]:
    path = VM_DETAIL_PATH.format(vm_id=vm_id)
    detail = _cedia_get(path, accept_variant="application/*+json")

    # Enriquecemos con hardware y red si están disponibles.
    def _safe_get(extra_path: str) -> Optional[Dict[str, Any]]:
        try:
            return _cedia_get(extra_path, accept_variant="application/*+json")
        except HTTPException as exc:  # noqa: PERF203 (fastapi HTTPException)
            # Ignora 404 para secciones que el tenant no expone.
            if exc.status_code == status.HTTP_404_NOT_FOUND:
                return None
            raise

    hw_section = _safe_get(VM_HW_SECTION_PATH.format(vm_id=vm_id))
    disks_section = _safe_get(VM_HW_DISKS_PATH.format(vm_id=vm_id))
    net_section = _safe_get(VM_NETWORK_SECTION_PATH.format(vm_id=vm_id))

    if hw_section:
        detail["virtualHardwareSection"] = hw_section
    if disks_section:
        detail["virtualHardwareSectionDisks"] = disks_section
    if net_section:
        detail["networkConnectionSection"] = net_section

    return detail


def get_vm_metrics(vm_id: str) -> Dict[str, Any]:
    path = VM_METRICS_PATH.format(vm_id=vm_id)
    return _cedia_get(path, accept_variant="application/*+json")
