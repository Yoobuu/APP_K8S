from pyVmomi import vim

from .context import CollectorContext
from ..property_fetch import fetch_objects
from ..resolvers import InventoryResolver

RP_PROPERTIES = [
    "name",
    "parent",
    "config.cpuAllocation",
    "config.memoryAllocation",
    "summary",
    "runtime",
    "vm",
]


def collect(context: CollectorContext):
    diagnostics = context.diagnostics
    logger = context.logger

    try:
        rp_items = fetch_objects(
            context.service_instance, vim.ResourcePool, RP_PROPERTIES
        )
    except Exception as exc:
        diagnostics.add_error("vRP", "property_fetch", exc)
        logger.error("Fallo fetching vRP: %s", exc)
        return []

    resolver = InventoryResolver(context.service_instance, logger=logger)
    rows = []
    vm_rows = context.shared_data.get("vInfo") or []
    rp_stats = {}
    for vm_row in vm_rows:
        rp_name = vm_row.get("Resource pool")
        if not rp_name:
            continue
        stats = rp_stats.setdefault(rp_name, {"vm_count": 0, "vcpu_total": 0})
        stats["vm_count"] += 1
        cpu_val = vm_row.get("CPUs") or 0
        try:
            stats["vcpu_total"] += int(cpu_val)
        except (TypeError, ValueError):
            pass

    for item in rp_items:
        diagnostics.add_attempt("vRP")
        try:
            props = item.get("props", {})
            ref = item.get("ref")
            name = props.get("name") or ""
            
            # Resolve parent to build path or just name
            parent_ref = props.get("parent")
            parent_name = ""
            if parent_ref:
                try:
                    parent_name = parent_ref.name
                except:
                    pass
            
            cluster = resolver.resolve_cluster_name(ref) # Indirectly resolves cluster via owner
            datacenter = resolver.resolve_datacenter_name(ref)
            
            # VM count
            vms = props.get("vm", [])
            num_vms = len(vms) if vms else 0
            stats = rp_stats.get(name, {})
            vm_total = stats.get("vm_count", num_vms)
            vcpu_total = stats.get("vcpu_total", "")
            
            # CPU Config
            cpu_alloc = props.get("config.cpuAllocation")
            cpu_res = cpu_alloc.reservation if cpu_alloc else 0
            cpu_lim = cpu_alloc.limit if cpu_alloc else 0
            cpu_shares = cpu_alloc.shares.shares if cpu_alloc and cpu_alloc.shares else 0
            cpu_overhead = cpu_alloc.overheadLimit if cpu_alloc else ""
            cpu_level = cpu_alloc.shares.level if cpu_alloc and cpu_alloc.shares else ""
            cpu_expandable = cpu_alloc.expandableReservation if cpu_alloc else ""
            
            # Mem Config
            mem_alloc = props.get("config.memoryAllocation")
            mem_res = mem_alloc.reservation if mem_alloc else 0
            mem_lim = mem_alloc.limit if mem_alloc else 0
            mem_shares = mem_alloc.shares.shares if mem_alloc and mem_alloc.shares else 0
            mem_overhead = mem_alloc.overheadLimit if mem_alloc else ""

            summary = props.get("summary")
            mem_configured = ""
            if summary is not None:
                mem_configured = getattr(summary, "configuredMemoryMB", "")

            runtime = props.get("runtime")
            status = ""
            cpu_overall = ""
            cpu_max = ""
            if runtime is not None:
                status = getattr(runtime, "overallStatus", "")
                cpu_runtime = getattr(runtime, "cpu", None)
                if cpu_runtime is not None:
                    cpu_overall = getattr(cpu_runtime, "overallUsage", "")
                    cpu_max = getattr(cpu_runtime, "maxUsage", "")

            rows.append({
                "ResourcePool": name,
                "Parent": parent_name,
                "Cluster": cluster,
                "Datacenter": datacenter,
                "CPU_Reservation": cpu_res,
                "CPU_Limit": cpu_lim,
                "CPU_Shares": cpu_shares,
                "Memory_Reservation": mem_res,
                "Memory_Limit": mem_lim,
                "Memory_Shares": mem_shares,
                "# VMs": num_vms,
                "Status": status,
                "# VMs total": vm_total,
                "# vCPUs": vcpu_total,
                "CPU overheadLimit": cpu_overhead,
                "CPU level": cpu_level,
                "CPU expandableReservation": cpu_expandable,
                "CPU maxUsage": cpu_max,
                "CPU overallUsage": cpu_overall,
                "Mem Configured": mem_configured,
                "Mem overheadLimit": mem_overhead,
                # Other stats can be filled if needed
            })
            diagnostics.add_success("vRP")
        except Exception as exc:
            diagnostics.add_error("vRP", name, exc)

    return rows
