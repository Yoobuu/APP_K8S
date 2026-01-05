from pyVmomi import vim

from .context import CollectorContext
from ..resolvers import InventoryResolver


def collect(context: CollectorContext):
    diagnostics = context.diagnostics
    logger = context.logger

    host_items = context.shared_data.get("hosts", [])
    if not host_items:
        logger.warning("No hosts found in shared_data for vMultiPath. Did vHost collector run?")
        return []

    resolver = InventoryResolver(context.service_instance, logger=logger)
    rows = []

    for item in host_items:
        host_name = item.get("props", {}).get("name", "")
        host_ref = item.get("ref")
        
        cluster = resolver.resolve_cluster_name(host_ref)
        datacenter = resolver.resolve_datacenter_name(host_ref)

        storage_device = item.get("props", {}).get("config.storageDevice")
        if not storage_device or not storage_device.multipathInfo or not storage_device.multipathInfo.lun:
            continue

        for mp_lun in storage_device.multipathInfo.lun:
            diagnostics.add_attempt("vMultiPath")
            try:
                lun_id = mp_lun.lun # usually string key
                policy = mp_lun.policy
                policy_name = policy.policy if policy else ""
                
                paths = mp_lun.path
                path_strings = []
                active_count = 0
                
                # We can store up to N paths. RVTools usually has columns "Path 1", "Path 1 state", etc.
                # We will collect list of dicts {name, state}
                
                collected_paths = []
                
                for p in paths:
                    state = p.pathState
                    name = p.name
                    path_str = f"{name} ({state})"
                    path_strings.append(path_str)
                    
                    collected_paths.append({
                        "name": name,
                        "state": state
                    })
                    
                    if state == "active":
                        active_count += 1
                
                row = {
                    "Host": host_name,
                    "Cluster": cluster,
                    "Datacenter": datacenter,
                    "Device": mp_lun.id, # Canonical name or ID
                    "Policy": policy_name,
                    "ActivePaths": active_count,
                    "Paths": ", ".join(path_strings), # Summary column
                    # "State": "", # Overall state?
                }
                
                # Fill individual Path columns 1..8 (RVTools typically has 8 pairs)
                for i in range(8):
                    idx = i # 0-based
                    p_name_key = f"Path {i+1}"
                    p_state_key = f"Path {i+1} state"
                    
                    if idx < len(collected_paths):
                        row[p_name_key] = collected_paths[idx]["name"]
                        row[p_state_key] = collected_paths[idx]["state"]
                    else:
                        row[p_name_key] = ""
                        row[p_state_key] = ""

                rows.append(row)
                diagnostics.add_success("vMultiPath")
            except Exception as exc:
                diagnostics.add_error("vMultiPath", f"{host_name}:{mp_lun.lun}", exc)

    return rows