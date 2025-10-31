from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(CURRENT_DIR)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from sqlmodel import Session

from app.db import get_engine
from app.notifications.sampler import collect_all_samples
from app.notifications.service import (
    clear_recovered,
    evaluate_batch,
    persist_notifications,
)


def main() -> None:
    samples = collect_all_samples(refresh=True)
    engine = get_engine()
    with Session(engine) as session:
        notifications = evaluate_batch(samples, threshold=85.0)
        stats = persist_notifications(session, notifications)
        cleared = clear_recovered(session, samples, threshold=85.0)
    summary = {
        "samples": len(samples),
        "created": stats.get("created", 0),
        "skipped": stats.get("skipped", 0),
        "cleared": cleared,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    print(summary)


if __name__ == "__main__":
    main()
