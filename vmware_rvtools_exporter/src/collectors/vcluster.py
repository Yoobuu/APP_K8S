from collections import defaultdict
from pyVmomi import vim

from .context import CollectorContext
from ..property_fetch import fetch_objects
from ..resolvers import InventoryResolver

CLUSTER_PROPERTIES = [
    "name",
    "configurationEx",
    "summary.totalCpu",
    "summary.totalMemory",
    "summary.numHosts",
]


def collect(context: CollectorContext):
    diagnostics = context.diagnostics
    logger = context.logger

    try:
        cluster_items = fetch_objects(
            context.service_instance, vim.ClusterComputeResource, CLUSTER_PROPERTIES
        )
    except Exception as exc:
        diagnostics.add_error("vCluster", "property_fetch", exc)
        logger.error("Fallo fetching vCluster: %s", exc)
        return []

    # Calculate VM counts if vInfo data is available
    vm_counts = defaultdict(int)
    if "vInfo" in context.shared_data:
        for vm_row in context.shared_data["vInfo"]:
            c_name = vm_row.get("Cluster")
            if c_name:
                vm_counts[c_name] += 1

    resolver = InventoryResolver(context.service_instance, logger=logger)
    rows = []

    for item in cluster_items:
        diagnostics.add_attempt("vCluster")
        props = item.get("props", {})
        ref = item.get("ref")
        name = props.get("name") or ""

        if not name:
            diagnostics.add_error("vCluster", "<unknown>", ValueError("Missing name"))
            continue

        diagnostics.add_success("vCluster")

        datacenter = resolver.resolve_datacenter_name(ref)

        # Config
        config_ex = props.get("configurationEx")
        drs_config = config_ex.drsConfig if config_ex else None
        das_config = config_ex.dasConfig if config_ex else None
        
        drs_enabled = drs_config.enabled if drs_config else False
        ha_enabled = das_config.enabled if das_config else False

        # Summary
        total_cpu_mhz = props.get("summary.totalCpu") or 0
        total_mem_bytes = props.get("summary.totalMemory") or 0
        total_mem_gb = round(total_mem_bytes / (1024**3), 2)
        num_hosts = props.get("summary.numHosts") or 0

        rows.append({
            "Cluster": name,
            "Datacenter": datacenter,
            "HA_Enabled": str(ha_enabled),
            "DRS_Enabled": str(drs_enabled),
            "TotalCPU_MHz": total_cpu_mhz,
            "TotalMemory_GB": total_mem_gb,
            "NumHosts": num_hosts,
            "NumVMs": vm_counts.get(name, 0),
            # Fields not easily available or not prioritized:
            "EVC_Mode": "",
            "AdmissionControl": "",
            "Created": "",
        })

    return rows