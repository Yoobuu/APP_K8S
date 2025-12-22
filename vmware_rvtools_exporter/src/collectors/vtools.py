from .context import CollectorContext
from ..property_fetch import fetch_vms


VM_PROPERTIES = [
    "name",
    "guest.toolsStatus",
    "guest.toolsRunningStatus",
    "guest.toolsVersionStatus2",
]


def collect(context: CollectorContext):
    diagnostics = context.diagnostics
    logger = context.logger

    try:
        vm_items = fetch_vms(context.service_instance, VM_PROPERTIES)
    except Exception as exc:
        diagnostics.add_error("vTools", "property_fetch", exc)
        logger.error("Error PropertyCollector vTools: %s", exc)
        return []

    rows = []
    for item in vm_items:
        props = item.get("props", {})
        name = props.get("name") or ""

        diagnostics.add_attempt("vTools")
        if name:
            diagnostics.add_success("vTools")
        else:
            diagnostics.add_error("vTools", "<unknown>", ValueError("Missing name"))

        row = {
            "VM": name,
            "ToolsStatus": props.get("guest.toolsStatus", ""),
            "ToolsRunning": props.get("guest.toolsRunningStatus", ""),
            "ToolsVersionStatus2": props.get("guest.toolsVersionStatus2", ""),
        }
        rows.append(row)

    return rows
