from pyVmomi import vim

from .context import CollectorContext
from ..property_fetch import fetch_objects

VCD_PROPERTIES = [
    "name",
    "config.hardware.device",
    "runtime.host",
]


def collect(context: CollectorContext):
    diagnostics = context.diagnostics
    logger = context.logger

    try:
        vm_items = fetch_objects(
            context.service_instance, vim.VirtualMachine, VCD_PROPERTIES
        )
    except Exception as exc:
        diagnostics.add_error("vCD", "property_fetch", exc)
        logger.error("Fallo fetching vCD: %s", exc)
        return []

    rows = []

    for item in vm_items:
        props = item.get("props", {})
        vm_name = props.get("name") or ""
        devices = props.get("config.hardware.device") or []

        for device in devices:
            if isinstance(device, vim.vm.device.VirtualCdrom):
                diagnostics.add_attempt("vCD")
                try:
                    connectable = device.connectable
                    connected = connectable.connected if connectable else False
                    start_connected = connectable.startConnected if connectable else False
                    allow_guest_control = connectable.allowGuestControl if connectable else False
                    
                    backing = device.backing
                    iso_path = ""
                    datastore = ""
                    client_device = False
                    
                    if isinstance(backing, vim.vm.device.VirtualCdrom.IsoBackingInfo):
                        iso_path = backing.fileName
                        if backing.datastore:
                            try:
                                # Try to resolve datastore name if object is present
                                # But backing.datastore is a ManagedObject reference usually
                                # We can cheat and parse [DatastoreName] from fileName
                                if iso_path.startswith("["):
                                    end = iso_path.find("]")
                                    if end != -1:
                                        datastore = iso_path[1:end]
                            except Exception:
                                pass
                    elif isinstance(backing, vim.vm.device.VirtualCdrom.RemotePassthroughBackingInfo):
                        client_device = True
                    elif isinstance(backing, vim.vm.device.VirtualCdrom.AtapiBackingInfo):
                        iso_path = f"Host Device: {backing.deviceName}"


                    rows.append({
                        "VM": vm_name,
                        "Device": device.deviceInfo.label,
                        "Connected": str(connected),
                        "StartConnected": str(start_connected),
                        "ISOPath": iso_path,
                        "ClientDevice": str(client_device),
                        "AllowGuestControl": str(allow_guest_control),
                        "Controller": f"{device.controllerKey}:{device.unitNumber}",
                        "Datastore": datastore
                    })
                    diagnostics.add_success("vCD")
                except Exception as exc:
                    diagnostics.add_error("vCD", vm_name, exc)

    return rows