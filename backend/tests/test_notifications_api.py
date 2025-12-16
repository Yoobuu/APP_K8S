from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.audit.models import AuditLog
from app.auth.user_model import User, UserRole
from app.dependencies import get_current_user
from app.notifications.models import Notification, NotificationMetric, NotificationProvider, NotificationStatus


def _seed_notifications(session: Session):
    now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    session.add_all(
        [
            Notification(
                provider=NotificationProvider.VMWARE,
                vm_name="vm-prod-01",
                vm_id="vm-1",
                metric=NotificationMetric.CPU,
                value_pct=92.0,
                threshold_pct=85.0,
                env="PRODUCCION",
                at=now,
                status=NotificationStatus.OPEN,
                dedupe_key="vmware:vm-prod-01:cpu:2024-01-01T12",
                created_at=now,
                disks_json='[{"used_pct":95.0,"size_gib":120}]',
            ),
            Notification(
                provider=NotificationProvider.VMWARE,
                vm_name="vm-test-01",
                vm_id="vm-2",
                metric=NotificationMetric.RAM,
                value_pct=80.0,
                threshold_pct=85.0,
                env="TEST",
                at=now,
                status=NotificationStatus.CLEARED,
                dedupe_key="vmware:vm-test-01:ram:2024-01-01T12",
                created_at=now,
            ),
        ]
    )
    session.commit()


def test_list_notifications_filters(client, session):
    _seed_notifications(session)

    response = client.get("/api/notifications", params={"status": "OPEN", "limit": 10})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    first = payload["items"][0]
    assert first["vm_name"] == "vm-prod-01"
    assert first.get("disks_json") in (None, []) or isinstance(first["disks_json"], list)
    for field in ["id", "provider", "metric", "value_pct", "status", "created_at"]:
        assert field in first

    response = client.get("/api/notifications", params={"metric": "RAM"})
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_ack_notification_flow(client, session, test_engine):
    _seed_notifications(session)

    response = client.post("/api/notifications/1/ack/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ACK"
    assert body["ack_by"] == "superadmin"
    assert body["ack_at"] is not None

    # Ensure audit log created
    with Session(test_engine) as verify_session:
        audit_entries = verify_session.exec(select(AuditLog).where(AuditLog.action == "notification.ack")).all()
        assert len(audit_entries) == 1

    # Ack again should return conflict
    response = client.post("/api/notifications/1/ack")
    assert response.status_code == 409

    # Ack nonexistent -> 404
    response = client.post("/api/notifications/999/ack")
    assert response.status_code == 404


def test_ack_requires_permission(client, session):
    _seed_notifications(session)

    def override_get_current_user():
        return User(id=123, username="limited", hashed_password="x", role=UserRole.USER)

    client.app.dependency_overrides[get_current_user] = override_get_current_user
    response = client.post("/api/notifications/1/ack")
    assert response.status_code == 403
    client.app.dependency_overrides.pop(get_current_user, None)
