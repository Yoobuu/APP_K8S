from pyVmomi import vim

from .context import CollectorContext
from ..resolvers import InventoryResolver


def collect(context: CollectorContext):
    diagnostics = context.diagnostics
    logger = context.logger

    host_items = context.shared_data.get("hosts", [])
    if not host_items:
        logger.warning("No hosts found in shared_data for vNIC. Did vHost collector run?")
        return []

    resolver = InventoryResolver(context.service_instance, logger=logger)
    rows = []

    for item in host_items:
        host_name = item.get("props", {}).get("name", "")
        host_ref = item.get("ref")
        
        # Resolve once per host
        cluster = resolver.resolve_cluster_name(host_ref)
        datacenter = resolver.resolve_datacenter_name(host_ref)

        pnics = item.get("props", {}).get("config.network.pnic")
        if not pnics:
            continue

        for pnic in pnics:
            diagnostics.add_attempt("vNIC")
            try:
                device = pnic.device
                mac = pnic.mac
                driver = getattr(pnic, "driver", "")
                pci = getattr(pnic, "pci", "")
                
                link_speed = getattr(pnic, "linkSpeed", None)
                speed_mb = link_speed.speedMb if link_speed else 0
                duplex = link_speed.duplex if link_speed else False
                
                speed_str = f"{speed_mb} {'Full' if duplex else 'Half'}" if link_speed else ""

                rows.append({
                    "Host": host_name,
                    "vNIC": device,
                    "PortGroup": "", # Physical NIC doesn't belong to portgroup directly usually, connected to vSwitch
                    "MAC": mac,
                    "IP": "", # pNIC usually has no IP
                    "Subnet": "",
                    "DHCP": "",
                    "vSwitch": "", # Could find which vSwitch it belongs to, but requires cross-ref.
                    "MTU": "", # MTU is on vSwitch or vmk usually. pNIC has MTU?
                    "Speed": speed_str,
                    "Driver": driver,
                    "PCI": pci,
                })
                diagnostics.add_success("vNIC")
            except Exception as exc:
                diagnostics.add_error("vNIC", f"{host_name}:{pnic.device}", exc)

    return rows