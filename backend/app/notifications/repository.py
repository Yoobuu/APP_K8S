from __future__ import annotations

from datetime import datetime
from typing import Tuple

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.notifications.models import (
    Notification,
    NotificationMetric,
    NotificationProvider,
    NotificationStatus,
)
from .utils import ensure_utc, floor_to_hour, norm_enum


def compute_dedupe_key(provider: str, vm_name: str, metric: str, at: datetime) -> str:
    at_utc = floor_to_hour(ensure_utc(at))
    provider_norm = norm_enum(provider)
    metric_norm = norm_enum(metric)
    return f"{provider_norm}:{vm_name}:{metric_norm}:{at_utc.strftime('%Y-%m-%dT%H')}"


def _resolve_provider(provider: str | NotificationProvider) -> NotificationProvider:
    if isinstance(provider, NotificationProvider):
        return provider
    return NotificationProvider(norm_enum(provider))


def _resolve_metric(metric: str | NotificationMetric) -> NotificationMetric:
    if isinstance(metric, NotificationMetric):
        return metric
    return NotificationMetric(norm_enum(metric))


def create_if_new(session: Session, notif: Notification) -> Tuple[Notification, bool]:
    """
    Insert notification if dedupe key is new. Returns (notification, created_flag).
    """
    if not notif.dedupe_key:
        if not notif.provider or not notif.vm_name or not notif.metric or not notif.at:
            raise ValueError("Notification missing fields required to compute dedupe key")
        notif.dedupe_key = compute_dedupe_key(
            notif.provider.value if isinstance(notif.provider, NotificationProvider) else notif.provider,
            notif.vm_name,
            notif.metric.value if isinstance(notif.metric, NotificationMetric) else notif.metric,
            notif.at,
        )

    session.add(notif)
    try:
        session.commit()
        session.refresh(notif)
        return notif, True
    except IntegrityError:
        session.rollback()
        existing = session.exec(
            select(Notification).where(Notification.dedupe_key == notif.dedupe_key)
        ).one()
        return existing, False


def mark_cleared_if_recovered(
    session: Session,
    provider: str | NotificationProvider,
    vm_name: str,
    metric: str | NotificationMetric,
    now_at: datetime,
    threshold: float = 85.0,
) -> int:
    """
    Mark open notifications as cleared for the given VM/metric when metrics recover.
    """
    _ = threshold  # reserved for future logic that may depend on threshold
    provider_enum = _resolve_provider(provider)
    metric_enum = _resolve_metric(metric)
    normalized_at = ensure_utc(now_at)

    notifications = session.exec(
        select(Notification).where(
            Notification.provider == provider_enum,
            Notification.vm_name == vm_name,
            Notification.metric == metric_enum,
            Notification.status == NotificationStatus.OPEN,
        )
    ).all()

    if not notifications:
        return 0

    for notif in notifications:
        notif.status = NotificationStatus.CLEARED
        notif.cleared_at = normalized_at
        session.add(notif)

    session.commit()
    return len(notifications)
