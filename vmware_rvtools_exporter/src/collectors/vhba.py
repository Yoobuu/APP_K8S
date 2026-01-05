from pyVmomi import vim

from .context import CollectorContext
from ..resolvers import InventoryResolver


def collect(context: CollectorContext):
    diagnostics = context.diagnostics
    logger = context.logger

    host_items = context.shared_data.get("hosts", [])
    if not host_items:
        logger.warning("No hosts found in shared_data for vHBA. Did vHost collector run?")
        return []

    resolver = InventoryResolver(context.service_instance, logger=logger)
    rows = []

    for item in host_items:
        host_name = item.get("props", {}).get("name", "")
        host_ref = item.get("ref")
        
        cluster = resolver.resolve_cluster_name(host_ref)
        datacenter = resolver.resolve_datacenter_name(host_ref)

        storage_device = item.get("props", {}).get("config.storageDevice")
        if not storage_device or not storage_device.hostBusAdapter:
            continue

        for hba in storage_device.hostBusAdapter:
            diagnostics.add_attempt("vHBA")
            try:
                device = hba.device
                key = hba.key
                model = hba.model
                driver = hba.driver
                status = hba.status
                bus = hba.bus
                pci = hba.pci
                
                hba_type = hba.__class__.__name__
                if hba_type.startswith("Host"):
                    hba_type = hba_type[4:] # Strip "Host" prefix e.g. HostFibreChannelHba -> FibreChannelHba
                
                wwn = ""
                if isinstance(hba, vim.host.FibreChannelHba):
                    # Format WWN as hex string
                    try:
                        node_wwn = "{:x}".format(hba.nodeWorldWideName)
                        port_wwn = "{:x}".format(hba.portWorldWideName)
                        wwn = f"{node_wwn}/{port_wwn}"
                    except Exception:
                        pass
                elif isinstance(hba, vim.host.InternetScsiHba):
                    wwn = hba.iScsiName # Use iqn as identifier similar to WWN
                
                rows.append({
                    "Host": host_name,
                    "Cluster": cluster,
                    "Datacenter": datacenter,
                    "Device": device,
                    "Type": hba_type,
                    "Model": model,
                    "Driver": driver,
                    "Status": status,
                    "Bus": str(bus),
                    "Pci": pci,
                    "WWN": wwn,
                })
                diagnostics.add_success("vHBA")
            except Exception as exc:
                diagnostics.add_error("vHBA", f"{host_name}:{hba.device}", exc)

    return rows