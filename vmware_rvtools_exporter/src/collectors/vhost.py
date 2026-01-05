from pyVmomi import vim

from .context import CollectorContext
from ..property_fetch import fetch_objects
from ..resolvers import InventoryResolver

HOST_PROPERTIES = [
    "name",
    "parent",
    "summary.hardware",
    "summary.runtime",
    "summary.quickStats",
    "summary.config.product",
    "config.product",
    "config.dateTimeInfo",
    "capability",
    "hardware.systemInfo",
    "hardware.cpuPowerManagementInfo",
    "hardware.memoryTieringType",
    "config.network.vnic",
    "config.network.pnic",
    "config.network.vswitch",
    "config.network.portgroup",
    "config.storageDevice",
]


def collect(context: CollectorContext):
    diagnostics = context.diagnostics
    logger = context.logger

    try:
        host_items = fetch_objects(
            context.service_instance, vim.HostSystem, HOST_PROPERTIES
        )
        # Store for vNIC/vSC_VMK
        context.shared_data["hosts"] = host_items
    except Exception as exc:
        diagnostics.add_error("vHost", "property_fetch", exc)
        logger.error("Fallo fetching vHost: %s", exc)
        return []

    resolver = InventoryResolver(context.service_instance, logger=logger)
    rows = []
    vm_rows = context.shared_data.get("vInfo") or []
    vm_stats = {}
    for vm_row in vm_rows:
        host_name = vm_row.get("Host")
        if not host_name:
            continue
        stats = vm_stats.setdefault(
            host_name, {"vm_count": 0, "vcpu_total": 0, "vram_total": 0}
        )
        stats["vm_count"] += 1
        cpu_val = vm_row.get("CPUs") or 0
        mem_val = vm_row.get("Memory") or 0
        try:
            stats["vcpu_total"] += int(cpu_val)
        except (TypeError, ValueError):
            pass
        try:
            stats["vram_total"] += int(mem_val)
        except (TypeError, ValueError):
            pass

    for item in host_items:
        diagnostics.add_attempt("vHost")
        props = item.get("props", {})
        ref = item.get("ref")
        name = props.get("name") or ""
        
        if not name:
            diagnostics.add_error("vHost", "<unknown>", ValueError("Missing name"))
            continue

        diagnostics.add_success("vHost")

        # Resolve references
        cluster = resolver.resolve_cluster_name(ref)
        datacenter = resolver.resolve_datacenter_name(ref)

        # Extract Hardware Info
        hardware = props.get("summary.hardware")
        model = hardware.model if hardware else ""
        cpu_model = hardware.cpuModel if hardware else ""
        cpu_sockets = hardware.numCpuPkgs if hardware else 0
        cpu_cores = hardware.numCpuCores if hardware else 0
        memory_bytes = hardware.memorySize if hardware else 0
        memory_gb = round(memory_bytes / (1024**3), 2) if memory_bytes else 0
        vendor = getattr(hardware, "vendor", "") if hardware else ""
        host_uuid = getattr(hardware, "uuid", "") if hardware else ""
        cpu_mhz = getattr(hardware, "cpuMhz", 0) if hardware else 0
        cpu_threads = getattr(hardware, "numCpuThreads", 0) if hardware else 0
        memory_tiering_type = props.get("hardware.memoryTieringType") or ""

        system_info = props.get("hardware.systemInfo")
        serial_number = ""
        service_tag = ""
        oem_string = ""
        if system_info is not None:
            serial_number = getattr(system_info, "serialNumber", "") or ""
            other_ids = getattr(system_info, "otherIdentifyingInfo", None) or []
            for ident in other_ids:
                ident_type = getattr(ident, "identifierType", None)
                ident_key = ""
                ident_label = ""
                if ident_type is not None:
                    ident_key = getattr(ident_type, "key", "") or ""
                    ident_label = getattr(ident_type, "label", "") or ""
                ident_value = getattr(ident, "identifierValue", "") or ""
                ident_text = f"{ident_key} {ident_label}".lower()
                if not service_tag and ("service tag" in ident_text or "servicetag" in ident_text):
                    service_tag = ident_value
                if not oem_string and "oem" in ident_text:
                    oem_string = ident_value

        # Extract Runtime Info
        runtime = props.get("summary.runtime")
        connection_state = str(runtime.connectionState) if runtime else ""
        power_state = str(runtime.powerState) if runtime else ""
        in_maintenance = getattr(runtime, "inMaintenanceMode", "") if runtime else ""
        in_quarantine = getattr(runtime, "inQuarantineMode", "") if runtime else ""
        boot_time = getattr(runtime, "bootTime", "") if runtime else ""
        if hasattr(boot_time, "isoformat"):
            boot_time = boot_time.isoformat()

        quick_stats = props.get("summary.quickStats")
        cpu_usage_pct = ""
        mem_usage_pct = ""
        if quick_stats and cpu_mhz and cpu_cores:
            total_mhz = cpu_mhz * cpu_cores
            overall_cpu = getattr(quick_stats, "overallCpuUsage", 0) or 0
            if total_mhz:
                cpu_usage_pct = round((overall_cpu / total_mhz) * 100, 2)
        if quick_stats and memory_bytes:
            overall_mem = getattr(quick_stats, "overallMemoryUsage", 0) or 0
            total_mem_mb = memory_bytes / (1024 * 1024)
            if total_mem_mb:
                mem_usage_pct = round((overall_mem / total_mem_mb) * 100, 2)

        # Extract Product Info
        # Prefer config.product (HostProductInfo) over summary.config.product
        product_info = props.get("config.product") or props.get("summary.config.product")
        version = product_info.version if product_info else ""
        build = product_info.build if product_info else ""

        date_info = props.get("config.dateTimeInfo")
        time_zone = ""
        time_zone_name = ""
        ntp_servers = ""
        if date_info is not None:
            tz_val = getattr(date_info, "timeZone", "")
            if tz_val:
                if hasattr(tz_val, "name"):
                    time_zone_name = tz_val.name
                    time_zone = str(tz_val.name)
                else:
                    time_zone = str(tz_val)
                    time_zone_name = str(tz_val)
            ntp_config = getattr(date_info, "ntpConfig", None)
            if ntp_config is not None:
                servers = getattr(ntp_config, "server", None) or []
                if isinstance(servers, (list, tuple)):
                    ntp_servers = ",".join([str(s) for s in servers if s])
                else:
                    ntp_servers = str(servers)

        capability = props.get("capability")
        vmotion_support = ""
        storage_vmotion_support = ""
        if capability is not None:
            vmotion_support = getattr(capability, "vmotionSupported", "")
            storage_vmotion_support = getattr(capability, "storageVmotionSupported", "")

        pnics = props.get("config.network.pnic") or []
        num_nics = len(pnics)
        storage_device = props.get("config.storageDevice")
        hbas = getattr(storage_device, "hostBusAdapter", None) if storage_device else None
        num_hbas = len(hbas) if hbas else 0

        ht_available = ""
        if cpu_threads and cpu_cores:
            ht_available = str(cpu_threads > cpu_cores)

        cpu_power = props.get("hardware.cpuPowerManagementInfo")
        cpu_power_current = ""
        cpu_power_supported = ""
        if cpu_power is not None:
            cpu_power_current = getattr(cpu_power, "currentPolicy", "") or ""
            hw_support = getattr(cpu_power, "hardwareSupport", None)
            if isinstance(hw_support, (list, tuple)):
                cpu_power_supported = ",".join([str(v) for v in hw_support if v])
            elif hw_support is not None:
                cpu_power_supported = str(hw_support)

        stats = vm_stats.get(name, {})
        vm_count = stats.get("vm_count", "")
        vcpu_total = stats.get("vcpu_total", "")
        vram_total = stats.get("vram_total", "")
        vms_per_core = ""
        vcpus_per_core = ""
        if cpu_cores:
            try:
                vms_per_core = round(vm_count / cpu_cores, 2)
            except Exception:
                vms_per_core = ""
            try:
                vcpus_per_core = round(vcpu_total / cpu_cores, 2)
            except Exception:
                vcpus_per_core = ""

        rows.append({
            "Host": name,
            "Cluster": cluster,
            "Datacenter": datacenter,
            "ConnectionState": connection_state,
            "PowerState": power_state,
            "Model": model,
            "CPU_Model": cpu_model,
            "CPU_Sockets": cpu_sockets,
            "CPU_Cores": cpu_cores,
            "Memory_GB": memory_gb,
            "Version": version,
            "Build": build,
            "Vendor": vendor,
            "UUID": host_uuid,
            "Speed": cpu_mhz,
            "HT Available": ht_available,
            "# NICs": num_nics,
            "# HBAs": num_hbas,
            "CPU usage %": cpu_usage_pct,
            "Memory usage %": mem_usage_pct,
            "in Maintenance Mode": str(in_maintenance) if in_maintenance != "" else "",
            "Boot time": boot_time,
            "in Quarantine Mode": str(in_quarantine) if in_quarantine != "" else "",
            "Time Zone": time_zone,
            "Time Zone Name": time_zone_name,
            "VMotion support": str(vmotion_support) if vmotion_support != "" else "",
            "Storage VMotion support": str(storage_vmotion_support) if storage_vmotion_support != "" else "",
            "VI SDK Server": context.config.server,
            "VI SDK UUID": context.content.about.instanceUuid if context.content else "",
            "vRAM": vram_total if vram_total != "" else "",
            "VMs per Core": vms_per_core,
            "vCPUs per Core": vcpus_per_core,
            "Serial number": serial_number,
            "Service tag": service_tag,
            "OEM specific string": oem_string,
            "Object ID": ref._GetMoId() if ref and hasattr(ref, "_GetMoId") else "",
            "NTP Server(s)": ntp_servers,
            "Supported CPU power man.": cpu_power_supported,
            "Current CPU power man. policy": cpu_power_current,
            "Host Power Policy": cpu_power_current,
            "Memory Tiering Type": memory_tiering_type,
        })
        
    return rows
