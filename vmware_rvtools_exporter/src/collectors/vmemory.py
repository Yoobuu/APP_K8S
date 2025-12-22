from .context import CollectorContext
from ..property_fetch import fetch_vms


VM_PROPERTIES = [
    "name",
    "runtime.powerState",
    "config.template",
    "config.hardware.memoryMB",
    "config.memoryAllocation",
]


def _shares_value(shares) -> str:
    if shares is None:
        return ""
    if getattr(shares, "shares", None) is not None:
        return str(shares.shares)
    return str(getattr(shares, "level", ""))


def collect(context: CollectorContext):
    diagnostics = context.diagnostics
    logger = context.logger

    try:
        vm_items = fetch_vms(context.service_instance, VM_PROPERTIES)
    except Exception as exc:
        diagnostics.add_error("vMemory", "property_fetch", exc)
        logger.error("Error PropertyCollector vMemory: %s", exc)
        return []

    rows = []
    for item in vm_items:
        props = item.get("props", {})
        name = props.get("name") or ""
        power_state = props.get("runtime.powerState")
        template = props.get("config.template", "")
        memory_mb = props.get("config.hardware.memoryMB", "")
        alloc = props.get("config.memoryAllocation")

        diagnostics.add_attempt("vMemory")
        if name:
            diagnostics.add_success("vMemory")
        else:
            diagnostics.add_error("vMemory", "<unknown>", ValueError("Missing name"))

        row = {
            "VM": name,
            "Powerstate": str(power_state) if power_state is not None else "",
            "Template": template,
            "MemoryMB": memory_mb,
            "Memory_Reservation": getattr(alloc, "reservation", "") if alloc else "",
            "Memory_Limit": getattr(alloc, "limit", "") if alloc else "",
            "Memory_Shares": _shares_value(getattr(alloc, "shares", None)) if alloc else "",
        }
        rows.append(row)

    return rows
