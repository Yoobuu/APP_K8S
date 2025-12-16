"""Imprime la respuesta cruda de /rest/vcenter/host usando la sesión REST existente."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

# Asegura que el paquete app sea importable desde el script
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Carga variables de entorno (VCENTER_HOST, VCENTER_USER, VCENTER_PASS, etc.)
load_dotenv(BASE_DIR / ".env")

from app.vms.vm_service import get_hosts_raw  # noqa: E402


def main() -> int:
    try:
        payload = get_hosts_raw()
    except Exception as exc:  # pragma: no cover - script manual
        print(f"[ERROR] {exc}")
        return 1

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover - entrada script
    raise SystemExit(main())
