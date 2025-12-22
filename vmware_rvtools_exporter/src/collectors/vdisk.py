from pyVmomi import vim

from .context import CollectorContext
from ..property_fetch import fetch_vms


VM_PROPERTIES = [
    "name",
    "runtime.powerState",
    "config.template",
    "config.hardware.device",
]


def _capacity_gb_from_kb(capacity_kb):
    if capacity_kb is None:
        return ""
    try:
        return round(float(capacity_kb) / (1024 * 1024), 2)
    except (TypeError, ValueError):
        return ""


def _extract_datastore_name(backing, filename: str) -> str:
    if getattr(backing, "datastore", None) is not None:
        try:
            return backing.datastore.name
        except Exception:
            return ""
    if filename and filename.startswith("[") and "]" in filename:
        return filename.split("]", 1)[0].lstrip("[")
    return ""


def collect(context: CollectorContext):
    diagnostics = context.diagnostics
    logger = context.logger

    try:
        vm_items = fetch_vms(context.service_instance, VM_PROPERTIES)
    except Exception as exc:
        diagnostics.add_error("vDisk", "property_fetch", exc)
        logger.error("Error PropertyCollector vDisk: %s", exc)
        return []

    rows = []
    for item in vm_items:
        props = item.get("props", {})
        name = props.get("name") or ""
        power_state = props.get("runtime.powerState")
        template = props.get("config.template", "")
        devices = props.get("config.hardware.device") or []

        for device in devices:
            if not isinstance(device, vim.vm.device.VirtualDisk):
                continue

            diagnostics.add_attempt("vDisk")
            try:
                label = getattr(device.deviceInfo, "label", "") if device.deviceInfo else ""
                capacity_gb = _capacity_gb_from_kb(getattr(device, "capacityInKB", None))
                backing = getattr(device, "backing", None)
                filename = getattr(backing, "fileName", "") if backing else ""
                thin = getattr(backing, "thinProvisioned", "") if backing else ""
                datastore_name = _extract_datastore_name(backing, filename)

                row = {
                    "VM": name,
                    "Powerstate": str(power_state) if power_state is not None else "",
                    "Template": template,
                    "Disk": label,
                    "CapacityGB": capacity_gb,
                    "Datastore": datastore_name,
                    "File": filename,
                    "Thin": thin,
                    "Controller": getattr(device, "controllerKey", ""),
                    "UnitNumber": getattr(device, "unitNumber", ""),
                    "Type": device.__class__.__name__,
                }
                rows.append(row)
                diagnostics.add_success("vDisk")
            except Exception as exc:
                diagnostics.add_error("vDisk", name or "<unknown>", exc)

    return rows
