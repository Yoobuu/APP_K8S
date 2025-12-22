from .context import CollectorContext
from ..property_fetch import fetch_vms


VM_PROPERTIES = [
    "name",
    "runtime.powerState",
    "config.template",
    "config.hardware.numCPU",
    "config.hardware.numCoresPerSocket",
    "config.cpuAllocation",
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
        diagnostics.add_error("vCPU", "property_fetch", exc)
        logger.error("Error PropertyCollector vCPU: %s", exc)
        return []

    rows = []
    for item in vm_items:
        props = item.get("props", {})
        name = props.get("name") or ""
        power_state = props.get("runtime.powerState")
        template = props.get("config.template", "")
        cpu = props.get("config.hardware.numCPU", "")
        cores = props.get("config.hardware.numCoresPerSocket", "")
        alloc = props.get("config.cpuAllocation")

        diagnostics.add_attempt("vCPU")
        if name:
            diagnostics.add_success("vCPU")
        else:
            diagnostics.add_error("vCPU", "<unknown>", ValueError("Missing name"))

        row = {
            "VM": name,
            "Powerstate": str(power_state) if power_state is not None else "",
            "Template": template,
            "CPUs": cpu,
            "CoresPerSocket": cores,
            "vCPU_Reservation": getattr(alloc, "reservation", "") if alloc else "",
            "vCPU_Limit": getattr(alloc, "limit", "") if alloc else "",
            "vCPU_Shares": _shares_value(getattr(alloc, "shares", None)) if alloc else "",
        }
        rows.append(row)

    return rows
