from pyVmomi import vim

from .context import CollectorContext
from ..property_fetch import fetch_vms
from ..resolvers import InventoryResolver

VUSB_PROPERTIES = [
    "name",
    "runtime.powerState",
    "runtime.host",
    "config.template",
    "config.hardware.device",
]


def collect(context: CollectorContext):
    diagnostics = context.diagnostics
    logger = context.logger

    try:
        vm_items = fetch_vms(context.service_instance, VUSB_PROPERTIES)
    except Exception as exc:
        diagnostics.add_error("vUSB", "property_fetch", exc)
        return []

    resolver = InventoryResolver(context.service_instance, logger=logger)
    rows = []

    for item in vm_items:
        props = item.get("props", {})
        name = props.get("name")
        power_state = props.get("runtime.powerState")
        host_ref = props.get("runtime.host")
        template = props.get("config.template", "")
        devices = props.get("config.hardware.device") or []
        
        host_name = resolver.resolve_host_name(host_ref)
        cluster = resolver.resolve_cluster_name(host_ref)
        datacenter = resolver.resolve_datacenter_name(host_ref)

        for dev in devices:
            # Check for VirtualUSB
            if isinstance(dev, vim.vm.device.VirtualUSB):
                diagnostics.add_attempt("vUSB")
                try:
                    summary = dev.deviceInfo.summary if dev.deviceInfo else ""
                    label = dev.deviceInfo.label if dev.deviceInfo else "USB"
                    
                    connected = dev.connectable.connected if dev.connectable else False
                    
                    rows.append({
                        "VM": name,
                        "Powerstate": str(power_state),
                        "Template": template,
                        "Host": host_name,
                        "Cluster": cluster,
                        "Datacenter": datacenter,
                        "Device": label,
                        "Description": summary,
                        "Connected": str(connected),
                        "AutoConnect": str(dev.connectable.startConnected) if dev.connectable else "",
                        # "Family": "", 
                        # "Speed": "",
                    })
                    diagnostics.add_success("vUSB")
                except Exception as exc:
                    diagnostics.add_error("vUSB", name, exc)

    return rows