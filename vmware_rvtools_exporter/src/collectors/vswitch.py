from pyVmomi import vim

from .context import CollectorContext
from ..resolvers import InventoryResolver


def collect(context: CollectorContext):
    diagnostics = context.diagnostics
    logger = context.logger

    host_items = context.shared_data.get("hosts", [])
    if not host_items:
        logger.warning("No hosts found in shared_data for vSwitch. Did vHost collector run?")
        return []

    resolver = InventoryResolver(context.service_instance, logger=logger)
    rows = []

    for item in host_items:
        host_name = item.get("props", {}).get("name", "")
        host_ref = item.get("ref")
        
        cluster = resolver.resolve_cluster_name(host_ref)
        datacenter = resolver.resolve_datacenter_name(host_ref)

        vswitches = item.get("props", {}).get("config.network.vswitch")
        if not vswitches:
            continue

        for vsw in vswitches:
            diagnostics.add_attempt("vSwitch")
            try:
                name = vsw.name
                num_ports = vsw.numPorts
                mtu = vsw.mtu
                pnic_keys = vsw.pnic if vsw.pnic else []
                # pnic keys are like 'key-vim.host.PhysicalNic-vmnic0' usually? 
                # actually vsw.pnic is a list of strings (keys).
                # We need to map keys to device names if possible, but the key usually contains the name like 'key-vim.host.PhysicalNic-vmnic0'
                # Or we can look at spec.bridge.
                # For simplicity, let's join the keys or try to extract 'vmnicX' if it's in the key.
                
                uplinks = []
                for key in pnic_keys:
                    # simplistic extraction: usually ends with vmnicX
                    if "-" in key:
                        uplinks.append(key.split("-")[-1])
                    else:
                        uplinks.append(key)
                uplinks_str = ", ".join(uplinks)

                spec = vsw.spec
                policy = spec.policy if spec else None
                
                promiscuous = ""
                mac_changes = ""
                forged_transmits = ""
                
                if policy and policy.security:
                    promiscuous = str(policy.security.allowPromiscuous)
                    mac_changes = str(policy.security.macChanges)
                    forged_transmits = str(policy.security.forgedTransmits)

                # Teaming
                teaming = ""
                if policy and policy.nicTeaming:
                    teaming = policy.nicTeaming.policy if policy.nicTeaming.policy else ""

                rows.append({
                    "Host": host_name,
                    "Cluster": cluster,
                    "Datacenter": datacenter,
                    "vSwitch": name,
                    "NumPorts": num_ports,
                    "MTU": mtu,
                    "Uplinks": uplinks_str,
                    "Promiscuous": promiscuous,
                    "MACChanges": mac_changes,
                    "ForgedTransmits": forged_transmits,
                    "TeamingPolicy": teaming,
                    # "Beacon": "", # Not easily available in simple struct
                })
                diagnostics.add_success("vSwitch")
            except Exception as exc:
                diagnostics.add_error("vSwitch", f"{host_name}:{vsw.name}", exc)

    return rows