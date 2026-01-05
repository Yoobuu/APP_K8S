from .context import CollectorContext
from ..property_fetch import fetch_vms
from ..resolvers import InventoryResolver


VM_PROPERTIES = [
    "name",
    "runtime.powerState",
    "runtime.host",
    "config.template",
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

    resolver = InventoryResolver(context.service_instance, logger=logger)
    rows = []
    for item in vm_items:
        props = item.get("props", {})
        name = props.get("name") or ""
        power_state = props.get("runtime.powerState")
        host_ref = props.get("runtime.host")
        template = props.get("config.template", "")
        
        host_name = resolver.resolve_host_name(host_ref)
        cluster = resolver.resolve_cluster_name(host_ref)
        datacenter = resolver.resolve_datacenter_name(host_ref)

        diagnostics.add_attempt("vTools")
        if name:
            diagnostics.add_success("vTools")
        else:
            diagnostics.add_error("vTools", "<unknown>", ValueError("Missing name"))

        row = {
            "VM": name,
            "Powerstate": str(power_state) if power_state is not None else "",
            "Template": template,
            "ToolsStatus": props.get("guest.toolsStatus", ""),
            "ToolsRunning": props.get("guest.toolsRunningStatus", ""),
            "ToolsVersionStatus2": props.get("guest.toolsVersionStatus2", ""),
            "Host": host_name,
            "Cluster": cluster,
            "Datacenter": datacenter,
        }
        rows.append(row)

    return rows
