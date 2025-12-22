from pyVmomi import vim

from .context import CollectorContext
from ..property_fetch import fetch_vms
from ..resolvers import InventoryResolver


VM_PROPERTIES = [
    "name",
    "runtime.powerState",
    "runtime.host",
    "config.template",
    "config.uuid",
    "config.instanceUuid",
    "config.guestId",
    "config.hardware.numCPU",
    "config.hardware.memoryMB",
    "guest.guestFullName",
    "guest.ipAddress",
    "guest.toolsStatus",
    "guest.toolsRunningStatus",
    "guest.toolsVersionStatus2",
]


def collect_vm_smoke(
    service_instance, diagnostics=None, logger=None, sheet_name: str = "vInfo"
):
    if diagnostics is None:
        class _NullDiagnostics:
            def add_attempt(self, *_args, **_kwargs):
                pass

            def add_success(self, *_args, **_kwargs):
                pass

            def add_error(self, *_args, **_kwargs):
                pass

        diagnostics = _NullDiagnostics()

    if logger is None:
        import logging

        logger = logging.getLogger("rvtools_exporter")

    content = service_instance.RetrieveContent()
    rows = []

    try:
        view = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.VirtualMachine], True
        )
    except Exception as exc:
        diagnostics.add_error(sheet_name, "container_view", exc)
        logger.debug("No se pudo crear el container view: %s", exc)
        return []

    try:
        for vm in view.view:
            diagnostics.add_attempt(sheet_name)
            entity_name = "<unknown>"
            try:
                entity_name = vm.name
                power_state = vm.runtime.powerState
                if entity_name is None or power_state is None:
                    raise ValueError("Missing name or powerState")

                rows.append({"VM": entity_name, "Powerstate": str(power_state)})
                diagnostics.add_success(sheet_name)
            except Exception as exc:
                diagnostics.add_error(sheet_name, entity_name, exc)
                logger.debug("Error leyendo VM %s: %s", entity_name, exc)
    finally:
        try:
            view.Destroy()
        except Exception:
            logger.debug("No se pudo destruir el container view", exc_info=True)

    return rows


def collect(context: CollectorContext):
    diagnostics = context.diagnostics
    logger = context.logger

    try:
        vm_items = fetch_vms(context.service_instance, VM_PROPERTIES)
    except Exception as exc:
        diagnostics.add_error("vInfo", "property_fetch", exc)
        logger.debug("Fallo PropertyCollector, usando smoke test: %s", exc)
        return collect_vm_smoke(
            service_instance=context.service_instance,
            diagnostics=diagnostics,
            logger=logger,
        )

    resolver = InventoryResolver(context.service_instance, logger=logger)
    rows = []

    for item in vm_items:
        props = item.get("props", {})
        name = props.get("name") or ""
        power_state = props.get("runtime.powerState")
        host_ref = props.get("runtime.host")

        diagnostics.add_attempt("vInfo")
        if name and power_state is not None:
            diagnostics.add_success("vInfo")
        else:
            diagnostics.add_error("vInfo", name or "<unknown>", ValueError("Missing data"))

        row = {
            "VM": name,
            "Powerstate": str(power_state) if power_state is not None else "",
            "Template": props.get("config.template", ""),
            "Host": resolver.resolve_host_name(host_ref),
            "Cluster": resolver.resolve_cluster_name(host_ref),
            "Datacenter": resolver.resolve_datacenter_name(host_ref),
            "VMUUID": props.get("config.uuid", ""),
            "InstanceUUID": props.get("config.instanceUuid", ""),
            "OS": props.get("guest.guestFullName")
            or props.get("config.guestId", ""),
            "vCPU": props.get("config.hardware.numCPU", ""),
            "MemoryMB": props.get("config.hardware.memoryMB", ""),
            "ToolsStatus": props.get("guest.toolsStatus", ""),
            "ToolsRunningStatus": props.get("guest.toolsRunningStatus", ""),
            "ToolsVersionStatus2": props.get("guest.toolsVersionStatus2", ""),
            "Primary IP": props.get("guest.ipAddress", ""),
        }

        optional_fields = [
            "Host",
            "Cluster",
            "Datacenter",
            "OS",
            "ToolsStatus",
            "Primary IP",
        ]
        if any(not row.get(field) for field in optional_fields):
            diagnostics.add_empty("vInfo")

        rows.append(row)

    return rows
