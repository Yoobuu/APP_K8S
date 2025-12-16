# filepath: backend/app/main.py
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Cargar variables de entorno desde .env anclado a /backend
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from app.audit import router as audit_router  # /api/audit
from app.auth import auth_router, user_admin_router  # /api/auth/...
from app.middleware import install_audit_middleware
from app.hosts import router as host_router  # /api/hosts
from app.notifications import router as notifications_router  # /api/notifications
from app.permissions.router import router as permissions_router  # /api/permissions
from app.cedia.router import router as cedia_router  # /api/cedia
from app.vms import vm_router  # /api/vms (VMware)
from app.vms.hyperv_router import router as hyperv_router  # /api/hyperv (Hyper-V)
# Import register_startup_events after TEST_MODE definition to avoid circular issues
from app.startup import register_startup_events

logger = logging.getLogger(__name__)
TEST_MODE = os.getenv("PYTEST_RUNNING") == "1"

# ─────────────────────────────
# FastAPI app
# ─────────────────────────────
app = FastAPI(title="VM Inventory API")
register_startup_events(app)
install_audit_middleware(app)


# Health checks
@app.get("/health")
def health():
    return {"ok": True}


@app.get("/healthz")
def healthz():
    return {"ok": True}


# CORS
frontend_origin = os.getenv("FRONTEND_ORIGIN")  # ej. https://tu-frontend
allow_origins = [frontend_origin] if frontend_origin else []

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",  # útil en dev (Vite)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers (orden no importa, pero manténlos agrupados)
app.include_router(auth_router.router, prefix="/api/auth")  # /api/auth/...
app.include_router(user_admin_router.router)  # /api/users (Admin)
app.include_router(vm_router.router, prefix="/api")  # /api/vms (VMware)
app.include_router(host_router, prefix="/api")  # /api/hosts (ESXi)
app.include_router(hyperv_router)  # /api/hyperv (Hyper-V)
app.include_router(permissions_router)  # /api/permissions (management)
app.include_router(notifications_router, prefix="/api/notifications", tags=["notifications"])
app.include_router(audit_router)  # /api/audit (Audit trail)
app.include_router(cedia_router)  # /api/cedia (CEDIA VMs)
