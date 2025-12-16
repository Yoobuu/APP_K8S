from __future__ import annotations

import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.providers.hyperv.remote import RemoteCreds
from app.vms.hyperv_router import _load_ps_content
from app.vms.hyperv_service import collect_hyperv_inventory_for_host


def main() -> int:
    if len(sys.argv) < 2 and not os.getenv("HYPERV_HOST"):
        print("Uso: python test_hyperv_detail.py <host> [vm_name]")
        return 1

    host = sys.argv[1] if len(sys.argv) > 1 else os.getenv("HYPERV_HOST")
    vm_name = sys.argv[2] if len(sys.argv) > 2 else None

    creds = RemoteCreds(
        host=host,
        username=os.environ.get("HYPERV_USER"),
        password=os.environ.get("HYPERV_PASS"),
        transport=os.environ.get("HYPERV_TRANSPORT", "ntlm"),
        use_winrm=True,
    )

    ps_content = _load_ps_content()
    records = collect_hyperv_inventory_for_host(
        creds,
        ps_content=ps_content,
        level="detail",
        vm_name=vm_name,
        use_cache=False,
    )

    payload = [r.model_dump() if hasattr(r, "model_dump") else dict(r) for r in records]
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
