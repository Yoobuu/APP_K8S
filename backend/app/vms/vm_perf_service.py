
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Tuple

from fastapi import HTTPException
from pyVim.connect import Disconnect
from pyVmomi import vim

from app.vms import vm_service

logger = logging.getLogger(__name__)

_COUNTER_CACHE = vm_service.ThreadSafeTTLCache(maxsize=128, ttl=3600)
_RESULT_CACHE = vm_service.ThreadSafeTTLCache(maxsize=512, ttl=30)

_REALTIME_INTERVAL = 20  # seconds
_ROLLUP_INTERVAL = 300  # seconds (5 minutes)


@dataclass(frozen=True)
class MetricConfig:
    group: str
    name: str
    rollup: str
    transform: Callable[[float, int], float]
    aggregate: Callable[[List[float]], Optional[float]]
    quickstat: Optional[Callable[[vim.VirtualMachine], Optional[float]]] = None
    zero_when_idle: bool = False


def _identity(value: float, _interval: int) -> float:
    return float(value)


def _avg(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _sum(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values)


def _quickstat_cpu(vm_ref: vim.VirtualMachine) -> Optional[float]:
    try:
        usage = getattr(vm_ref.summary.quickStats, "overallCpuUsage", None)
        max_mhz = getattr(vm_ref.summary.runtime, "maxCpuUsage", None)
        if usage is None or not max_mhz:
            return None
        return (usage / max_mhz) * 100.0
    except Exception:  # pragma: no cover - defensive
        return None


def _quickstat_mem(vm_ref: vim.VirtualMachine) -> Optional[float]:
    try:
        guest_mb = getattr(vm_ref.summary.quickStats, "guestMemoryUsage", None)
        total_mb = getattr(vm_ref.summary.config, "memorySizeMB", None)
        if guest_mb is None or not total_mb:
            return None
        return (guest_mb / total_mb) * 100.0
    except Exception:  # pragma: no cover - defensive
        return None


METRICS: Dict[str, MetricConfig] = {
    "cpu_usage_pct": MetricConfig("cpu", "usage", "average", lambda v, _i: v / 100.0, _avg, _quickstat_cpu),
    "mem_usage_pct": MetricConfig("mem", "usage", "average", lambda v, _i: v / 100.0, _avg, _quickstat_mem),
    "mem_active_mib": MetricConfig("mem", "active", "average", lambda v, _i: v / 1024.0, _avg),
    "mem_consumed_mib": MetricConfig("mem", "consumed", "average", lambda v, _i: v / 1024.0, _avg),
    "balloon_kb": MetricConfig("mem", "vmmemctl", "average", _identity, _avg, zero_when_idle=True),
    "disk_read_kbps": MetricConfig("disk", "read", "average", _identity, _sum, zero_when_idle=True),
    "disk_write_kbps": MetricConfig("disk", "write", "average", _identity, _sum, zero_when_idle=True),
    "disk_used_kb": MetricConfig("disk", "used", "latest", _identity, _sum, zero_when_idle=True),
    "iops_read": MetricConfig("disk", "numberReadAveraged", "average", _identity, _sum, zero_when_idle=True),
    "iops_write": MetricConfig("disk", "numberWriteAveraged", "average", _identity, _sum, zero_when_idle=True),
    "lat_read_ms": MetricConfig("disk", "totalReadLatency", "average", _identity, _avg, zero_when_idle=True),
    "lat_write_ms": MetricConfig("disk", "totalWriteLatency", "average", _identity, _avg, zero_when_idle=True),
}

PERCENT_METRICS: set[str] = {"cpu_usage_pct", "mem_usage_pct"}


def _get_counter_id(perf_manager: vim.PerformanceManager, config: MetricConfig) -> Optional[int]:
    cache_key = f"{config.group}:{config.name}:{config.rollup}"
    cached = _COUNTER_CACHE.get(cache_key)
    if cached is not None:
        return cached

    for counter in perf_manager.perfCounter:
        if (
            counter.groupInfo.key == config.group
            and counter.nameInfo.key == config.name
            and counter.rollupType == config.rollup
        ):
            _COUNTER_CACHE[cache_key] = counter.key
            return counter.key

    logger.warning("Metric %s.%s (%s) not found in vCenter counters", config.group, config.name, config.rollup)
    _COUNTER_CACHE[cache_key] = None
    return None


def _find_vm(content: vim.ServiceInstanceContent, vm_id: str) -> Optional[vim.VirtualMachine]:
    view = None
    try:
        view = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
        for vm in view.view:
            if vm._moId == vm_id:
                return vm
    finally:
        if view is not None:
            try:
                view.Destroy()
            except Exception:  # pragma: no cover - defensive
                logger.debug("Error destroying VM container view while searching for %s", vm_id)
    return None


def _process_results(
    results: List[vim.PerformanceManager.EntityMetricBase],
    counter_to_key: Dict[Tuple[int, str], str],
    collected_values: Dict[str, List[float]],
    default_interval: int,
    source_set: set[str],
    allowed_keys: Optional[set[str]] = None,
    instance_collector: Optional[Dict[str, Dict[str, List[float]]]] = None,
) -> Optional[datetime]:
    latest_ts: Optional[datetime] = None

    if not results:
        return latest_ts

    for entity_metric in results:
        sample_interval = default_interval
        sample_info = getattr(entity_metric, "sampleInfo", None)
        if sample_info:
            sample_interval = getattr(sample_info[0], "interval", default_interval) or default_interval
            timestamp = getattr(sample_info[-1], "sampleTime", None) or getattr(sample_info[-1], "time", None)
            if isinstance(timestamp, datetime):
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                if latest_ts is None or timestamp > latest_ts:
                    latest_ts = timestamp

        for metric_series in getattr(entity_metric, "value", []):
            counter_id = metric_series.id.counterId
            instance = metric_series.id.instance or ""
            key = counter_to_key.get((counter_id, instance))
            if not key or (allowed_keys is not None and key not in allowed_keys):
                continue
            if not metric_series.value:
                continue
            try:
                raw_value = float(metric_series.value[-1])
            except (TypeError, ValueError):
                continue

            transform = METRICS[key].transform
            try:
                value = transform(raw_value, sample_interval)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("No se pudo transformar el valor de %s: %s", key, exc)
                continue

            collected_values[key].append(value)
            if instance_collector is not None and key in ("disk_read_kbps", "disk_write_kbps", "disk_used_kb", "iops_read", "iops_write", "lat_read_ms", "lat_write_ms"):
                bucket = instance_collector.setdefault(instance, {})
                bucket.setdefault(key, []).append(value)
            source_set.add(key)

    return latest_ts




def _build_lun_uuid_map(host_ref: Optional[vim.HostSystem]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    if host_ref is None:
        return mapping
    try:
        config_manager = getattr(host_ref, "configManager", None)
        storage_system = getattr(config_manager, "storageSystem", None)
        if storage_system is None:
            return mapping

        device_info = getattr(storage_system, "storageDeviceInfo", None)
        if device_info is None:
            return mapping

        for lun in getattr(device_info, "scsiLun", []) or []:
            uuid = getattr(lun, "uuid", None)
            canonical = getattr(lun, "canonicalName", None)
            if not uuid or not canonical:
                continue
            uuid_str = str(uuid).strip()
            canonical_str = str(canonical).strip()
            if uuid_str and canonical_str:
                mapping[uuid_str] = canonical_str
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("No se pudo construir el mapa uuid->canonical: %s", exc)
    return mapping


def _build_disk_capacity_map(
    vm_ref: vim.VirtualMachine,
    uuid_to_canonical: Dict[str, str],
) -> Dict[str, Dict[str, Optional[float]]]:
    mapping: Dict[str, Dict[str, Optional[float]]] = {}
    hardware = getattr(getattr(vm_ref, "config", None), "hardware", None)
    if not hardware:
        return mapping

    controllers: Dict[int, int] = {}
    for device in getattr(hardware, "device", []):
        if isinstance(device, vim.vm.device.VirtualSCSIController):
            controllers[device.key] = getattr(device, "busNumber", None)

    def _add_alias(target: set[str], raw: Optional[object]) -> None:
        if raw is None:
            return
        value = str(raw).strip()
        if not value:
            return
        target.add(value)
        if "/" in value:
            target.add(value.rsplit("/", 1)[-1])
        if value.upper().startswith("NAA."):
            target.add(value.lower())
        target.add(value.upper())

    for device in getattr(hardware, "device", []):
        if isinstance(device, vim.vm.device.VirtualDisk):
            bus = controllers.get(getattr(device, "controllerKey", None))
            unit = getattr(device, "unitNumber", None)
            scsi_alias: Optional[str] = f"scsi{bus}:{unit}" if bus is not None and unit is not None else None
            capacity = getattr(device, "capacityInKB", None)
            device_info = getattr(device, "deviceInfo", None)
            label = getattr(device_info, "label", None)
            backing = getattr(device, "backing", None)

            aliases: set[str] = set()
            _add_alias(aliases, scsi_alias)

            preferred_instance: Optional[str] = None
            if backing is not None:
                for attr in ("canonicalName", "deviceName", "lunUuid", "uuid", "backingObjectId", "fileName"):
                    candidate = getattr(backing, attr, None)
                    if candidate:
                        if preferred_instance is None:
                            candidate_str = str(candidate).strip()
                            if candidate_str:
                                preferred_instance = candidate_str
                        _add_alias(aliases, candidate)

                uuid_candidates = []
                for attr in ("uuid", "lunUuid"):
                    candidate = getattr(backing, attr, None)
                    if candidate:
                        candidate_str = str(candidate).strip()
                        if candidate_str:
                            uuid_candidates.append(candidate_str)
                for uuid_value in uuid_candidates:
                    canonical = uuid_to_canonical.get(uuid_value)
                    if canonical:
                        _add_alias(aliases, canonical)

            if preferred_instance is None:
                preferred_instance = scsi_alias

            disk_key = getattr(device, "key", scsi_alias or label or "unknown")
            info: Dict[str, Optional[float]] = {
                "label": label or (scsi_alias or f"disk-{disk_key}"),
                "capacity_kb": float(capacity) if capacity is not None else None,
                "preferred_instance": preferred_instance,
                "scsi": scsi_alias,
                "_key": f"disk-{disk_key}",
            }

            if not aliases:
                aliases.add(str(info["_key"]))

            info["aliases"] = sorted(alias for alias in aliases if alias)

            for alias in aliases:
                mapping[alias] = info
    return mapping


def _summarize_disk_capacity_map(mapping: Dict[str, Dict[str, Optional[float]]]) -> List[Dict[str, object]]:
    grouped: Dict[str, Dict[str, object]] = {}
    for alias, info in mapping.items():
        group_key = str(info.get("_key") or info.get("preferred_instance") or info.get("scsi") or alias)
        entry = grouped.setdefault(
            group_key,
            {
                "key": group_key,
                "label": info.get("label"),
                "capacity_kb": info.get("capacity_kb"),
                "preferred_instance": info.get("preferred_instance"),
                "scsi": info.get("scsi"),
                "aliases": set(),
            },
        )
        entry["aliases"].add(alias)

    for entry in grouped.values():
        entry["aliases"] = sorted(entry["aliases"])  # type: ignore[assignment]
    return sorted(grouped.values(), key=lambda x: x["key"])

def get_vm_perf_summary(
    vm_id: str,
    *,
    window_seconds: int = 60,
    idle_to_zero: bool = False,
    by_disk: bool = False,
) -> Dict[str, Optional[float]]:
    if window_seconds < _REALTIME_INTERVAL:
        window_seconds = _REALTIME_INTERVAL
    if window_seconds > 1800:
        window_seconds = 1800

    cache_key = f"{vm_id}:{window_seconds}:{int(idle_to_zero)}:{int(by_disk)}"
    cached_summary = _RESULT_CACHE.get(cache_key)
    if cached_summary is not None:
        return cached_summary

    si = None
    missing_metrics: List[str] = []
    last_timestamp: Optional[datetime] = None
    disk_instance_values: Optional[Dict[str, Dict[str, List[float]]]] = {} if by_disk else None
    disk_capacity_map: Dict[str, Dict[str, Optional[float]]] = {}
    metrics_unavailable = False

    try:
        si, content = vm_service._soap_connect()
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Unable to connect to vCenter SOAP API: %s", exc)
        raise HTTPException(status_code=503, detail="no se pudo conectar al vCenter para metricas") from exc

    try:
        vm_ref = _find_vm(content, vm_id)
        if vm_ref is None:
            raise HTTPException(status_code=404, detail=f"VM {vm_id} no encontrada en vCenter")

        uuid_to_canonical = _build_lun_uuid_map(getattr(vm_ref.runtime, "host", None))
        disk_capacity_map = _build_disk_capacity_map(vm_ref, uuid_to_canonical)

        perf_manager: vim.PerformanceManager = content.perfManager
        available = perf_manager.QueryAvailablePerfMetric(entity=vm_ref, intervalId=_REALTIME_INTERVAL)

        metric_ids: List[vim.PerformanceManager.MetricId] = []
        counter_to_key: Dict[Tuple[int, str], str] = {}

        for key, config in METRICS.items():
            counter_id = _get_counter_id(perf_manager, config)
            if counter_id is None:
                missing_metrics.append(key)
                continue

            instances = [metric.instance or "" for metric in available if metric.counterId == counter_id]
            if not instances:
                missing_metrics.append(key)
                continue

            selected_instances = [""] if "" in instances else instances
            for instance in selected_instances:
                metric_ids.append(vim.PerformanceManager.MetricId(counterId=counter_id, instance=instance))
                counter_to_key[(counter_id, instance)] = key

        if not metric_ids:
            metrics_unavailable = True
            logger.warning(
                "No hay contadores disponibles para recopilar metricas de %s (faltan: %s)",
                vm_id,
                ", ".join(missing_metrics) or "desconocidos",
            )

        if missing_metrics:
            logger.warning(
                "Metricas no disponibles en vCenter para VM %s: %s",
                vm_id,
                ", ".join(missing_metrics),
            )

        collected_values: Dict[str, List[float]] = {key: [] for key in METRICS}
        realtime_sources: set[str] = set()
        rollup_sources: set[str] = set()

        start_time = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)

        if not metrics_unavailable:
            realtime_query = vim.PerformanceManager.QuerySpec(
                entity=vm_ref,
                intervalId=_REALTIME_INTERVAL,
                startTime=start_time,
                metricId=metric_ids,
            )
            realtime_results = perf_manager.QueryPerf(querySpec=[realtime_query])
            last_timestamp = _process_results(
                realtime_results,
                counter_to_key,
                collected_values,
                _REALTIME_INTERVAL,
                realtime_sources,
                None,
                disk_instance_values,
            )

            pending_keys = {key for key, values in collected_values.items() if not values}

            if pending_keys:
                try:
                    rollup_query = vim.PerformanceManager.QuerySpec(
                        entity=vm_ref,
                        intervalId=_ROLLUP_INTERVAL,
                        maxSample=1,
                        metricId=metric_ids,
                    )
                    rollup_results = perf_manager.QueryPerf(querySpec=[rollup_query])
                    rollup_timestamp = _process_results(
                        rollup_results,
                        counter_to_key,
                        collected_values,
                        _ROLLUP_INTERVAL,
                        rollup_sources,
                        pending_keys,
                        disk_instance_values if by_disk else None,
                    )
                    if rollup_timestamp and (last_timestamp is None or rollup_timestamp > last_timestamp):
                        last_timestamp = rollup_timestamp
                except Exception as exc:  # pragma: no cover - defensive
                    logger.debug("No se pudo obtener metrics rollup para VM %s: %s", vm_id, exc)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error consultando metricas de VM %s: %s", vm_id, exc)
        raise HTTPException(status_code=502, detail="error consultando metricas en vCenter") from exc
    finally:
        if si is not None:
            try:
                Disconnect(si)
            except Exception:  # pragma: no cover - defensive
                pass

    summary: Dict[str, Optional[float]] = {key: None for key in METRICS}
    summary["_interval_seconds"] = _REALTIME_INTERVAL
    summary["_collected_at"] = (last_timestamp or datetime.now(timezone.utc)).isoformat()
    summary["missing_metrics"] = sorted(set(missing_metrics))
    summary["_sources"] = {key: "none" for key in METRICS}
    summary["_metrics_available"] = not metrics_unavailable

    for key, values in collected_values.items():
        aggregated = METRICS[key].aggregate(values)
        if aggregated is not None:
            if key in PERCENT_METRICS:
                aggregated = round(aggregated, 2)
            summary[key] = aggregated
            if key in realtime_sources:
                summary["_sources"][key] = "realtime"
            elif key in rollup_sources:
                summary["_sources"][key] = "rollup"

    for key, config in METRICS.items():
        if summary[key] is None and config.quickstat is not None:
            quick_value = config.quickstat(vm_ref)
            if quick_value is not None:
                if key in PERCENT_METRICS:
                    quick_value = round(quick_value, 2)
                summary[key] = quick_value
                summary["_sources"][key] = "quickstats"

    if idle_to_zero:
        for key, config in METRICS.items():
            if summary[key] is None and key not in summary["missing_metrics"] and config.zero_when_idle:
                summary[key] = 0.0
                summary["_sources"][key] = "idle_zero"

    for key in summary["missing_metrics"]:
        summary["_sources"][key] = "missing_metric"

    if disk_capacity_map:
        capacities = [info.get("capacity_kb") for info in disk_capacity_map.values() if info.get("capacity_kb") is not None]
        summary["disk_capacity_kb_total"] = sum(capacities) if capacities else None
    else:
        summary["disk_capacity_kb_total"] = None

    if by_disk and isinstance(disk_instance_values, dict):
        metric_instances_debug: Dict[str, Dict[str, int]] = {}
        for inst, metrics in disk_instance_values.items():
            metric_instances_debug[inst] = {
                metric_name: len(values or [])
                for metric_name, values in metrics.items()
                if values
            }
        metric_field_map = [
            ("read_kbps", "disk_read_kbps"),
            ("write_kbps", "disk_write_kbps"),
            ("used_kb", "disk_used_kb"),
            ("iops_read", "iops_read"),
            ("iops_write", "iops_write"),
            ("lat_read_ms", "lat_read_ms"),
            ("lat_write_ms", "lat_write_ms"),
        ]
        entries: Dict[str, Dict[str, object]] = {}
        instances = set(disk_instance_values.keys())
        instances.update(disk_capacity_map.keys())
        for inst in sorted(instances):
            if not inst:
                continue
            kv = disk_instance_values.get(inst, {})
            info = disk_capacity_map.get(inst)
            if info:
                candidate_key = info.get("_key") or info.get("preferred_instance") or info.get("scsi") or inst
                entry_key = str(candidate_key) if candidate_key is not None else inst
            else:
                entry_key = inst
            entry = entries.get(entry_key)
            if entry is None:
                entry = {
                    "instance": None,
                    "label": None,
                    "capacity_kb": None,
                    "read_kbps": None,
                    "write_kbps": None,
                    "used_kb": None,
                    "iops_read": None,
                    "iops_write": None,
                    "lat_read_ms": None,
                    "lat_write_ms": None,
                    "_aliases": set(),
                    "_scsi": None,
                }
                entries[entry_key] = entry

            entry["_aliases"].add(inst)

            if info:
                if info.get("label"):
                    entry["label"] = info["label"]
                if info.get("capacity_kb") is not None:
                    entry["capacity_kb"] = info["capacity_kb"]
                preferred_instance = info.get("preferred_instance")
                if preferred_instance:
                    entry["instance"] = preferred_instance
                if info.get("scsi"):
                    entry["_scsi"] = info["scsi"]
                for alias in info.get("aliases", []):
                    if alias:
                        entry["_aliases"].add(alias)

            has_metric_values = False
            for field, metric_key in metric_field_map:
                values = kv.get(metric_key)
                if values:
                    aggregated = METRICS[metric_key].aggregate(values)
                    if aggregated is not None:
                        entry[field] = aggregated
                        has_metric_values = True

            if has_metric_values:
                entry["instance"] = inst

        disks: List[Dict[str, Optional[float]]] = []
        debug_entries: List[Dict[str, object]] = []
        for entry in entries.values():
            if entry["label"] is None:
                alias = next(iter(entry["_aliases"]), None)
                entry["label"] = alias or entry["_scsi"] or entry["instance"] or "Disco"
            if entry["instance"] is None:
                entry["instance"] = entry["_scsi"] or next(iter(entry["_aliases"]), None)

            if idle_to_zero:
                for field, metric_key in metric_field_map:
                    if entry[field] is None and metric_key not in summary["missing_metrics"]:
                        entry[field] = 0.0

            disk_entry = {
                "instance": entry["instance"],
                "label": entry["label"],
                "capacity_kb": entry["capacity_kb"],
                "used_kb": entry["used_kb"],
                "read_kbps": entry["read_kbps"],
                "write_kbps": entry["write_kbps"],
                "iops_read": entry["iops_read"],
                "iops_write": entry["iops_write"],
                "lat_read_ms": entry["lat_read_ms"],
                "lat_write_ms": entry["lat_write_ms"],
            }
            disks.append(disk_entry)
            debug_entries.append(
                {
                    "instance": entry["instance"],
                    "label": entry["label"],
                    "aliases": sorted(entry["_aliases"]),
                    "scsi": entry["_scsi"],
                    "capacity_kb": entry["capacity_kb"],
                    "has_metrics": any(
                        disk_entry[field] is not None
                        for field in ("read_kbps", "write_kbps", "used_kb", "iops_read", "iops_write", "lat_read_ms", "lat_write_ms")
                    ),
                }
            )

        disks.sort(key=lambda d: (d["label"] or d["instance"] or ""))
        summary["disks"] = disks
        summary["_debug_disk_mapping"] = {
            "capacity_groups": _summarize_disk_capacity_map(disk_capacity_map),
            "metric_instances": metric_instances_debug,
            "merged_entries": debug_entries,
        }

    _RESULT_CACHE[cache_key] = summary
    return summary
