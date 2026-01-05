from pyVmomi import vim

from .context import CollectorContext
from ..resolvers import InventoryResolver


def collect(context: CollectorContext):
    diagnostics = context.diagnostics
    logger = context.logger

    host_items = context.shared_data.get("hosts", [])
    if not host_items:
        # If vHost failed or didn't run, we can't do this efficiently without re-fetching.
        # For now, we assume vHost ran.
        logger.warning("No hosts found in shared_data for vSC_VMK. Did vHost collector run?")
        return []

    resolver = InventoryResolver(context.service_instance, logger=logger)
    rows = []

    for item in host_items:
        host_name = item.get("props", {}).get("name", "")
        host_ref = item.get("ref")
        
        # Resolve once per host
        cluster = resolver.resolve_cluster_name(host_ref)
        datacenter = resolver.resolve_datacenter_name(host_ref)

        vnics = item.get("props", {}).get("config.network.vnic")
        if not vnics:
            continue

        for vnic in vnics:
            diagnostics.add_attempt("vSC_VMK")
            try:
                device = vnic.device
                portgroup = vnic.portgroup
                spec = vnic.spec
                ip_settings = spec.ip if spec else None
                
                ip = ip_settings.ipAddress if ip_settings else ""
                subnet = ip_settings.subnetMask if ip_settings else ""
                mtu = spec.mtu if spec else 0
                mac = spec.mac if spec else ""

                rows.append({
                    "Host": host_name,
                    "VMkernel": device,
                    "PortGroup": portgroup,
                    "IP": ip,
                    "Subnet": subnet,
                    "Management": "", # Requires parsing portgroup roles or specific flags
                    "vMotion": "",
                    "FaultTolerance": "",
                    "Provisioning": "",
                    "Storage": "",
                    "MTU": mtu,
                    "MAC": mac, # Not in original schema? Let's check schema.
                    # Wait, schema has: Host, VMkernel, PortGroup, IP, Subnet, Management...
                    # It doesn't have MTU or MAC?
                    # Let's check schema in schemas.py
                })
                diagnostics.add_success("vSC_VMK")
            except Exception as exc:
                diagnostics.add_error("vSC_VMK", f"{host_name}:{vnic.device}", exc)

    return rows