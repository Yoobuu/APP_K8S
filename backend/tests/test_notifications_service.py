from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.notifications.models import (
    Notification,
    NotificationMetric,
    NotificationProvider,
    NotificationStatus,
)
from app.notifications.sampler import collect_vmware_samples
from app.notifications.service import (
    clear_recovered,
    evaluate_batch,
    evaluate_vm_sample,
    persist_notifications,
)


def _now() -> datetime:
    return datetime(2024, 1, 1, 10, 30, tzinfo=timezone.utc)


def test_cpu_threshold_creates_notification(session: Session):
    sample = {
        "provider": "vmware",
        "vm_name": "VM-CPU-85",
        "cpu_pct": 85.0,
        "at": _now(),
    }
    notifications = evaluate_vm_sample(sample)
    assert len(notifications) == 1
    assert notifications[0].metric == NotificationMetric.CPU

    result = persist_notifications(session, notifications)
    assert result == {"created": 1, "skipped": 0}

    stored = session.exec(select(Notification)).all()
    assert len(stored) == 1
    assert stored[0].provider == NotificationProvider.VMWARE
    assert stored[0].status == NotificationStatus.OPEN


def test_cpu_below_threshold_does_not_create(session: Session):
    sample = {
        "provider": "vmware",
        "vm_name": "VM-CPU-LOW",
        "cpu_pct": 84.9,
        "at": _now(),
    }
    notifications = evaluate_vm_sample(sample)
    assert notifications == []


def test_ram_high_creates_notification(session: Session):
    sample = {
        "provider": "hyperv",
        "vm_name": "HV-RAM-ALERT",
        "ram_pct": 92.0,
        "at": _now(),
    }
    notifications = evaluate_vm_sample(sample)
    assert len(notifications) == 1
    assert notifications[0].metric == NotificationMetric.RAM

    result = persist_notifications(session, notifications)
    assert result == {"created": 1, "skipped": 0}


def test_dedupe_same_hour_skips_duplicates(session: Session):
    sample = {
        "provider": "vmware",
        "vm_name": "VM-DEDUPE",
        "cpu_pct": 90.0,
        "at": _now(),
    }
    notifications = evaluate_vm_sample(sample)
    first = persist_notifications(session, notifications)
    assert first == {"created": 1, "skipped": 0}

    # Same hour should reuse dedupe key
    notifications_dup = evaluate_vm_sample(sample)
    second = persist_notifications(session, notifications_dup)
    assert second["created"] == 0
    assert second["skipped"] == len(notifications_dup)


def test_disk_rules_for_hyperv(session: Session):
    base_sample = {
        "provider": "hyperv",
        "vm_name": "HV-DISK",
        "at": _now(),
    }

    sample_ok = {**base_sample, "disks": [{"used_pct": 100}, {"used_pct": 100}, {"used_pct": 100}, {"used_pct": 40}]}
    assert evaluate_vm_sample(sample_ok) == []

    sample_alert = {**base_sample, "disks": [{"used_pct": 90}, {"used_pct": 90}, {"used_pct": 90}, {"used_pct": 90}]}
    notifs = evaluate_vm_sample(sample_alert)
    assert len(notifs) == 1
    assert notifs[0].metric == NotificationMetric.DISK

    sample_alert_mixed = {**base_sample, "disks": [{"used_pct": 100}, {"used_pct": 100}, {"used_pct": 100}, {"used_pct": 90}]}
    assert len(evaluate_vm_sample(sample_alert_mixed)) == 1

    sample_no_alert = {**base_sample, "disks": [{"used_pct": 100}, {"used_pct": 100}, {"used_pct": 100}, {"used_pct": 70}]}
    assert evaluate_vm_sample(sample_no_alert) == []


def test_clear_recovered_updates_status(session: Session):
    alert_sample = {
        "provider": "vmware",
        "vm_name": "VM-CLEAR",
        "cpu_pct": 90.0,
        "at": _now(),
    }
    notifications = evaluate_vm_sample(alert_sample)
    persist_notifications(session, notifications)

    stored = session.exec(select(Notification)).one()
    assert stored.status == NotificationStatus.OPEN

    recovered_sample = {
        "provider": "vmware",
        "vm_name": "VM-CLEAR",
        "cpu_pct": 40.0,
        "at": _now() + timedelta(hours=1),
    }

    cleared = clear_recovered(session, [recovered_sample])
    assert cleared == 1

    refreshed = session.exec(select(Notification)).one()
    assert refreshed.status == NotificationStatus.CLEARED


def test_vmware_sampler_uses_snapshot(session: Session, monkeypatch):
    snap_at = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    snapshots = [
        {
            "vm_name": "VM-CPU",
            "vm_id": "vm-1",
            "cpu_pct": 90.0,
            "ram_pct": 40.0,
            "env": "PRODUCCION",
            "at": snap_at,
        },
        {
            "vm_name": "VM-RAM",
            "vm_id": "vm-2",
            "cpu_pct": 20.0,
            "ram_pct": 91.0,
            "env": "SANDBOX",
            "at": snap_at,
        },
        {
            "vm_name": "VM-NO-ALERT",
            "vm_id": "vm-3",
            "cpu_pct": 10.0,
            "ram_pct": 30.0,
            "env": "DEV",
            "at": snap_at,
        },
    ]

    monkeypatch.setattr(
        "app.notifications.sampler.fetch_vmware_snapshot",
        lambda refresh: snapshots,
    )

    samples = collect_vmware_samples(refresh=False)
    assert len(samples) == len(snapshots)

    notifications = evaluate_batch(samples)
    metrics = {notif.metric for notif in notifications}
    assert metrics == {NotificationMetric.CPU, NotificationMetric.RAM}

    result = persist_notifications(session, notifications)
    assert result == {"created": 2, "skipped": 0}

    stored = session.exec(select(Notification)).all()
    dedupe_keys = {notif.dedupe_key for notif in stored}
    assert "vmware:VM-CPU:cpu:2024-01-01T12" in dedupe_keys
    assert "vmware:VM-RAM:ram:2024-01-01T12" in dedupe_keys

    recovery_samples = [
        {
            "provider": "vmware",
            "vm_name": "VM-CPU",
            "cpu_pct": 10.0,
            "at": snap_at + timedelta(hours=1),
        },
        {
            "provider": "vmware",
            "vm_name": "VM-RAM",
            "ram_pct": 10.0,
            "at": snap_at + timedelta(hours=1),
        },
    ]

    cleared = clear_recovered(session, recovery_samples)
    assert cleared == 2

    refreshed = session.exec(select(Notification)).all()
    assert all(n.status == NotificationStatus.CLEARED for n in refreshed)
