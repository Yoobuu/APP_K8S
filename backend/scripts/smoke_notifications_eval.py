from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

from sqlmodel import Session, select

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(CURRENT_DIR)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.db import get_engine
from app.notifications.models import Notification, NotificationStatus
from app.notifications.service import evaluate_batch, persist_notifications


def main() -> None:
    now = datetime.now(timezone.utc)
    samples = [
        {
            "provider": "vmware",
            "vm_name": "VMWARE-01",
            "cpu_pct": 87.5,
            "ram_pct": 68.0,
            "at": now,
            "env": "PROD",
        },
        {
            "provider": "hyperv",
            "vm_name": "HYPERV-APP-01",
            "cpu_pct": 61.0,
            "ram_pct": 92.1,
            "at": now,
            "env": "SANDBOX",
        },
        {
            "provider": "hyperv",
            "vm_name": "HYPERV-DB-01",
            "disks": [
                {"used_pct": 93.0, "size_gib": 120},
                {"used_pct": 91.0, "size_gib": 200},
            ],
            "at": now,
            "env": "PROD",
        },
    ]

    notifications = evaluate_batch(samples)

    engine = get_engine()
    with Session(engine) as session:
        summary = persist_notifications(session, notifications)
        open_notifications = session.exec(
            select(Notification).where(Notification.status == NotificationStatus.OPEN)
        ).all()

    print(summary)
    if open_notifications:
        print("Open notifications:")
        for notif in open_notifications:
            print(
                f"- id={notif.id} provider={notif.provider} vm={notif.vm_name} "
                f"metric={notif.metric} value_pct={notif.value_pct} at={notif.at.isoformat()}"
            )
    else:
        print("No open notifications.")


if __name__ == "__main__":
    main()
