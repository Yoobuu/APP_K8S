from __future__ import annotations

import logging
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.jobs.hourly_reconcile import run_hourly_reconcile

logger = logging.getLogger(__name__)


def create_scheduler() -> BackgroundScheduler:
    return BackgroundScheduler(timezone="UTC")


def scan_vm_metrics_job() -> None:
    try:
        run_hourly_reconcile(refresh=True)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Notification reconciliation job failed: %s", exc)


def schedule_scan_job(scheduler: BackgroundScheduler) -> None:
    dev_minutes = os.getenv("NOTIF_SCHED_DEV_MINUTES")
    if dev_minutes:
        minute_value = dev_minutes.strip() or "1"
        cron_args = {"minute": f"*/{minute_value}"}
    else:
        cron_args = {"minute": "0"}

    trigger = CronTrigger(timezone="UTC", **cron_args)
    scheduler.add_job(
        scan_vm_metrics_job,
        trigger=trigger,
        id="notifications_scan",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=180,
    )
