from pyVmomi import vim

from .context import CollectorContext
from ..property_fetch import fetch_vms
from ..resolvers import InventoryResolver


VM_PROPERTIES = [
    "name",
    "runtime.powerState",
    "config.template",
    "config.hardware.device",
]


def _resolve_network_name(device, resolver: InventoryResolver) -> str:
    backing = getattr(device, "backing", None)
    if backing is None:
        return ""

    if isinstance(backing, vim.vm.device.VirtualEthernetCard.NetworkBackingInfo):
        if getattr(backing, "deviceName", None):
            return backing.deviceName
        network = getattr(backing, "network", None)
        return network.name if network else ""

    if isinstance(
        backing, vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo
    ):
        port = getattr(backing, "port", None)
        portgroup_key = getattr(port, "portgroupKey", "") if port else ""
        return resolver.resolve_dvportgroup_name(portgroup_key)

    if hasattr(backing, "opaqueNetworkName"):
        return getattr(backing, "opaqueNetworkName", "")

    return ""


def collect(context: CollectorContext):
    diagnostics = context.diagnostics
    logger = context.logger

    try:
        vm_items = fetch_vms(context.service_instance, VM_PROPERTIES)
    except Exception as exc:
        diagnostics.add_error("vNetwork", "property_fetch", exc)
        logger.error("Error PropertyCollector vNetwork: %s", exc)
        return []

    resolver = InventoryResolver(context.service_instance, logger=logger)
    rows = []

    for item in vm_items:
        props = item.get("props", {})
        name = props.get("name") or ""
        power_state = props.get("runtime.powerState")
        template = props.get("config.template", "")
        devices = props.get("config.hardware.device") or []

        for device in devices:
            if not isinstance(device, vim.vm.device.VirtualEthernetCard):
                continue

            diagnostics.add_attempt("vNetwork")
            try:
                network_name = _resolve_network_name(device, resolver)
                connectable = getattr(device, "connectable", None)
                connected = getattr(connectable, "connected", "") if connectable else ""
                row = {
                    "VM": name,
                    "Powerstate": str(power_state) if power_state is not None else "",
                    "Template": template,
                    "Network": network_name,
                    "PortGroup": network_name,
                    "Adapter": getattr(device.deviceInfo, "label", "")
                    if device.deviceInfo
                    else "",
                    "MAC": getattr(device, "macAddress", ""),
                    "Connected": connected,
                    "Type": device.__class__.__name__,
                }
                rows.append(row)
                diagnostics.add_success("vNetwork")
            except Exception as exc:
                diagnostics.add_error("vNetwork", name or "<unknown>", exc)

    return rows
