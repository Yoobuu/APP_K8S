from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.audit.models import AuditLog
from app.db import set_engine
from app.notifications.models import (
    Notification,
    NotificationMetric,
    NotificationProvider,
    NotificationStatus,
)
from app.notifications.reconciler import ReconciliationReport, reconcile_notifications
from app.notifications.repository import compute_dedupe_key
from app.notifications.utils import ensure_utc


def _now() -> datetime:
    return datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)


def _make_notification(
    provider: NotificationProvider,
    vm_name: str,
    metric: NotificationMetric,
    status: NotificationStatus,
    *,
    value: float = 92.0,
    threshold: float = 85.0,
    env: str | None = "PROD",
    vm_id: str | None = None,
) -> Notification:
    observed_at = _now()
    dedupe = compute_dedupe_key(provider.value, vm_name, metric.value, observed_at)
    return Notification(
        provider=provider,
        vm_name=vm_name,
        vm_id=vm_id,
        metric=metric,
        value_pct=value,
        threshold_pct=threshold,
        env=env,
        at=observed_at,
        status=status,
        dedupe_key=dedupe,
        created_at=observed_at,
    )


def test_clears_when_missing_in_current(test_engine):
    set_engine(test_engine)

    with Session(test_engine) as session:
        notif = _make_notification(
            NotificationProvider.VMWARE,
            "vm-01",
            NotificationMetric.CPU,
            NotificationStatus.OPEN,
        )
        session.add(notif)
        session.commit()
        notif_id = notif.id

    report = reconcile_notifications([], _now())
    assert isinstance(report, ReconciliationReport)
    assert report.created == 0
    assert report.cleared == 1
    assert report.updated == 0
    assert report.preserved == 0
    assert report.cleared_ids == [notif_id]

    with Session(test_engine) as session:
        persisted = session.get(Notification, notif_id)
        assert persisted.status == NotificationStatus.CLEARED
        assert persisted.cleared_at is not None
        assert ensure_utc(persisted.cleared_at) == ensure_utc(_now())
        audit = session.exec(select(AuditLog).where(AuditLog.action == "NOTIFICATION_CLEARED")).all()
        assert len(audit) == 1


def test_preserves_when_still_anomalous(test_engine):
    set_engine(test_engine)

    with Session(test_engine) as session:
        notif = _make_notification(
            NotificationProvider.VMWARE,
            "vm-02",
            NotificationMetric.RAM,
            NotificationStatus.OPEN,
            value=91.0,
        )
        session.add(notif)
        session.commit()
        notif_id = notif.id

    anomalies = [
        {
            "provider": NotificationProvider.VMWARE.value,
            "vm_name": "vm-02",
            "metric": NotificationMetric.RAM.value,
            "value_pct": 92.5,
            "threshold_pct": 85.0,
            "env": "PROD",
            "vm_id": None,
            "at": _now(),
        }
    ]

    report = reconcile_notifications(anomalies, _now())
    assert report.created == 0
    assert report.cleared == 0
    assert report.updated == 1
    assert report.updated_ids == [notif_id]

    with Session(test_engine) as session:
        persisted = session.get(Notification, notif_id)
        assert persisted.value_pct == 92.5
        assert persisted.status == NotificationStatus.OPEN
        audit_entries = session.exec(select(AuditLog).where(AuditLog.action == "NOTIFICATION_UPDATED")).all()
        assert len(audit_entries) == 1


def test_creates_when_new(test_engine):
    set_engine(test_engine)
    anomalies = [
        {
            "provider": NotificationProvider.HYPERV.value,
            "vm_name": "hv-01",
            "metric": NotificationMetric.CPU.value,
            "value_pct": 95.0,
            "threshold_pct": 85.0,
            "env": "LAB",
            "vm_id": "hv-01-id",
            "at": _now(),
            "disks_json": [{"used_pct": 95.0, "size_gib": 120}],
        }
    ]

    report = reconcile_notifications(anomalies, _now())
    assert report.created == 1
    assert report.created_ids

    created_id = report.created_ids[0]
    with Session(test_engine) as session:
        persisted = session.get(Notification, created_id)
        assert persisted is not None
        assert persisted.status == NotificationStatus.OPEN
        assert persisted.provider == NotificationProvider.HYPERV
        assert persisted.disks_json == [{"used_pct": 95.0, "size_gib": 120}]
        audit_entries = session.exec(select(AuditLog).where(AuditLog.action == "NOTIFICATION_CREATED")).all()
        assert len(audit_entries) == 1


def test_idempotent_double_run(test_engine):
    set_engine(test_engine)
    anomalies = [
        {
            "provider": NotificationProvider.VMWARE.value,
            "vm_name": "vm-03",
            "metric": NotificationMetric.CPU.value,
            "value_pct": 90.0,
            "threshold_pct": 85.0,
            "env": "QA",
            "vm_id": "vm-03-id",
            "at": _now(),
        }
    ]

    first = reconcile_notifications(anomalies, _now())
    assert first.created == 1

    second = reconcile_notifications(anomalies, _now())
    assert second.created == 0
    assert second.updated + second.preserved == 1


def test_ack_persists_until_cleared(test_engine):
    set_engine(test_engine)
    with Session(test_engine) as session:
        notif = _make_notification(
            NotificationProvider.VMWARE,
            "vm-04",
            NotificationMetric.CPU,
            NotificationStatus.ACK,
            value=88.0,
        )
        notif.ack_by = "superadmin"
        notif.ack_at = _now()
        session.add(notif)
        session.commit()
        notif_id = notif.id

    anomalies = [
        {
            "provider": NotificationProvider.VMWARE.value,
            "vm_name": "vm-04",
            "metric": NotificationMetric.CPU.value,
            "value_pct": 88.0,
            "threshold_pct": 85.0,
            "env": "PROD",
            "vm_id": None,
            "at": _now(),
        }
    ]

    preserve_report = reconcile_notifications(anomalies, _now())
    assert preserve_report.updated + preserve_report.preserved == 1

    clear_report = reconcile_notifications([], _now())
    assert clear_report.cleared == 1

    with Session(test_engine) as session:
        persisted = session.get(Notification, notif_id)
        assert persisted.status == NotificationStatus.CLEARED
        assert persisted.ack_by == "superadmin"
        assert persisted.ack_at is not None
        assert ensure_utc(persisted.ack_at) == ensure_utc(_now())
        assert persisted.cleared_at is not None
        assert ensure_utc(persisted.cleared_at) == ensure_utc(_now())
