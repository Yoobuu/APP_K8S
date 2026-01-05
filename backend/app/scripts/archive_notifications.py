from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.db import get_engine
from app.notifications.models import Notification, NotificationStatus
from app.settings import settings


def archive_notifications(retention_days: int) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    engine = get_engine()
    with Session(engine) as session:
        candidates = session.exec(
            select(Notification).where(
                Notification.status == NotificationStatus.CLEARED,
                Notification.archived.is_(False),
                Notification.created_at < cutoff,
            )
        ).all()

        for notif in candidates:
            notif.archived = True
            session.add(notif)

        session.commit()

    return len(candidates)


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive cleared notifications older than retention window.")
    parser.add_argument(
        "--days",
        type=int,
        default=settings.notifs_retention_days,
        help="Retention window in days (defaults to env NOTIFS_RETENTION_DAYS or 180).",
    )
    args = parser.parse_args()

    archived = archive_notifications(args.days)
    print(f"Archived {archived} notifications older than {args.days} days.")


if __name__ == "__main__":
    main()
