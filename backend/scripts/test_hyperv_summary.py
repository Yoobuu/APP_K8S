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
    host = sys.argv[1] if len(sys.argv) > 1 else os.getenv("HYPERV_HOST")
    if not host:
        print("Define HYPERV_HOST o pasa el host como argumento")
        return 1

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
        level="summary",
        use_cache=False,
    )

    payload = [r.model_dump() if hasattr(r, "model_dump") else dict(r) for r in records]
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
