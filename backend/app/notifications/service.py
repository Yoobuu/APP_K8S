from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Optional, TypedDict

from sqlmodel import Session

from app.notifications.models import (
    Notification,
    NotificationMetric,
    NotificationProvider,
    NotificationStatus,
)
from .repository import (
    compute_dedupe_key,
    create_if_new,
    mark_cleared_if_recovered,
)
from .utils import ensure_utc, norm_enum


class DiskUsageSample(TypedDict, total=False):
    used_pct: float
    size_gib: float


class VmSample(TypedDict, total=False):
    provider: str
    vm_name: str
    at: datetime
    cpu_pct: float
    ram_pct: float
    disks: List[DiskUsageSample]
    env: str
    vm_id: str


def _provider_enum(value: str | NotificationProvider) -> NotificationProvider:
    if isinstance(value, NotificationProvider):
        return value
    return NotificationProvider(norm_enum(value))


def _sanitize_disks(disks: Optional[Iterable[DiskUsageSample]]) -> Optional[List[dict]]:
    if not disks:
        return None
    sanitized: List[dict] = []
    for disk in disks:
        used = disk.get("used_pct")
        size = disk.get("size_gib")
        entry: dict = {}
        if used is not None:
            entry["used_pct"] = float(used)
        if size is not None:
            entry["size_gib"] = float(size)
        if entry:
            sanitized.append(entry)
    return sanitized or None


def evaluate_vm_sample(sample: VmSample, threshold: float = 85.0) -> List[Notification]:
    """Evaluate a single VM sample and return notifications (not persisted)."""
    provider_enum = _provider_enum(sample["provider"])
    vm_name = sample["vm_name"]
    at = ensure_utc(sample["at"])
    env = sample.get("env")
    vm_id = sample.get("vm_id")

    notifications: List[Notification] = []

    cpu_value = sample.get("cpu_pct")
    if cpu_value is not None and cpu_value >= threshold:
        metric = NotificationMetric.CPU
        dedupe_key = compute_dedupe_key(provider_enum.value, vm_name, metric.value, at)
        notifications.append(
            Notification(
                provider=provider_enum,
                vm_id=vm_id,
                vm_name=vm_name,
                metric=metric,
                value_pct=float(cpu_value),
                threshold_pct=threshold,
                env=env,
                at=at,
                status=NotificationStatus.OPEN,
                dedupe_key=dedupe_key,
            )
        )

    ram_value = sample.get("ram_pct")
    if ram_value is not None and ram_value >= threshold:
        metric = NotificationMetric.RAM
        dedupe_key = compute_dedupe_key(provider_enum.value, vm_name, metric.value, at)
        notifications.append(
            Notification(
                provider=provider_enum,
                vm_id=vm_id,
                vm_name=vm_name,
                metric=metric,
                value_pct=float(ram_value),
                threshold_pct=threshold,
                env=env,
                at=at,
                status=NotificationStatus.OPEN,
                dedupe_key=dedupe_key,
            )
        )

    disks = sample.get("disks") or []
    if provider_enum == NotificationProvider.HYPERV and disks:
        used_values = [disk["used_pct"] for disk in disks if disk.get("used_pct") is not None]
        if used_values and min(used_values) >= threshold:
            metric = NotificationMetric.DISK
            dedupe_key = compute_dedupe_key(provider_enum.value, vm_name, metric.value, at)
            notifications.append(
                Notification(
                    provider=provider_enum,
                    vm_id=vm_id,
                    vm_name=vm_name,
                    metric=metric,
                    value_pct=float(min(used_values)),
                    threshold_pct=threshold,
                    env=env,
                    at=at,
                    status=NotificationStatus.OPEN,
                    disks_json=_sanitize_disks(disks),
                    dedupe_key=dedupe_key,
                )
            )

    return notifications


def evaluate_batch(samples: Iterable[VmSample], threshold: float = 85.0) -> List[Notification]:
    notifications: List[Notification] = []
    for sample in samples:
        notifications.extend(evaluate_vm_sample(sample, threshold=threshold))
    return notifications


def persist_notifications(session: Session, notifications: Iterable[Notification]) -> dict:
    created = 0
    skipped = 0
    for notif in notifications:
        _, is_new = create_if_new(session, notif)
        if is_new:
            created += 1
        else:
            skipped += 1
    return {"created": created, "skipped": skipped}


def clear_recovered(session: Session, samples: Iterable[VmSample], threshold: float = 85.0) -> int:
    cleared = 0
    for sample in samples:
        provider_enum = _provider_enum(sample["provider"])
        vm_name = sample["vm_name"]
        at = ensure_utc(sample["at"])

        cpu_value = sample.get("cpu_pct")
        if cpu_value is not None and cpu_value < threshold:
            cleared += mark_cleared_if_recovered(
                session,
                provider_enum,
                vm_name,
                NotificationMetric.CPU,
                at,
                threshold=threshold,
            )

        ram_value = sample.get("ram_pct")
        if ram_value is not None and ram_value < threshold:
            cleared += mark_cleared_if_recovered(
                session,
                provider_enum,
                vm_name,
                NotificationMetric.RAM,
                at,
                threshold=threshold,
            )

        disks = sample.get("disks") or []
        if provider_enum == NotificationProvider.HYPERV and disks:
            used_values = [disk["used_pct"] for disk in disks if disk.get("used_pct") is not None]
            if used_values and min(used_values) < threshold:
                cleared += mark_cleared_if_recovered(
                    session,
                    provider_enum,
                    vm_name,
                    NotificationMetric.DISK,
                    at,
                    threshold=threshold,
                )

    return cleared
