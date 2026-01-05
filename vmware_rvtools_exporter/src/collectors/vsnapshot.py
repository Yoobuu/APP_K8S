from datetime import datetime
from pyVmomi import vim

from .context import CollectorContext
from ..property_fetch import fetch_objects
from ..resolvers import InventoryResolver
from ..utils.custom_fields import extract_backup_fields, load_custom_field_map
from ..utils.vm_meta import apply_vm_meta, get_vi_sdk_meta, get_vm_meta

SNAPSHOT_PROPERTIES = [
    "name",
    "snapshot.rootSnapshotList",
    "snapshot.currentSnapshot",
    "runtime.host",
    "runtime.powerState",
    "customValue",
    "layoutEx",
]


def _bytes_to_mib(value) -> object:
    try:
        if value is None:
            return ""
        return float(value) / (1024 * 1024)
    except Exception:
        return ""


def _build_layout_maps(layout_ex):
    if not layout_ex:
        return {}, {}
    file_by_key = {}
    for info in getattr(layout_ex, "file", None) or []:
        try:
            key = getattr(info, "key", None)
            if key is not None:
                file_by_key[key] = info
        except Exception:
            continue
    snapshot_by_moid = {}
    for snap_layout in getattr(layout_ex, "snapshot", None) or []:
        snap_ref = getattr(snap_layout, "key", None)
        try:
            moid = snap_ref._GetMoId() if snap_ref and hasattr(snap_ref, "_GetMoId") else None
        except Exception:
            moid = None
        if moid:
            snapshot_by_moid[moid] = snap_layout
    return file_by_key, snapshot_by_moid


def _compute_snapshot_sizes(layout_entry, file_by_key):
    if not layout_entry:
        return "", "", ""

    filename = ""
    vmsn_size = ""
    total_size = ""
    file_keys = set()

    for key_name in ("memoryKey", "dataKey"):
        key_val = getattr(layout_entry, key_name, None)
        if isinstance(key_val, int):
            file_keys.add(key_val)

    for disk_layout in getattr(layout_entry, "disk", None) or []:
        chain = getattr(disk_layout, "chain", None) or []
        for unit in chain:
            try:
                for key_val in getattr(unit, "fileKey", None) or []:
                    if isinstance(key_val, int):
                        file_keys.add(key_val)
            except Exception:
                continue

    for key_name in ("memoryKey", "dataKey"):
        key_val = getattr(layout_entry, key_name, None)
        info = file_by_key.get(key_val)
        if info:
            filename = getattr(info, "name", "") or filename
            vmsn_size = _bytes_to_mib(getattr(info, "size", None))
            if filename:
                break

    total_bytes = 0.0
    found_size = False
    for file_key in file_keys:
        info = file_by_key.get(file_key)
        if info is None:
            continue
        size_val = getattr(info, "size", None)
        if size_val is None:
            continue
        try:
            total_bytes += float(size_val)
            found_size = True
        except Exception:
            continue
    if found_size:
        total_size = _bytes_to_mib(total_bytes)

    return filename, vmsn_size, total_size


def _traverse_snapshots(
    snapshot_tree,
    parent_name,
    vm_name,
    results,
    vm_power_state,
    host_name,
    cluster_name,
    datacenter_name,
    vm_meta,
    vi_meta,
    backup_status,
    last_backup,
):
    for node in snapshot_tree:
        name = node.name
        desc = node.description
        create_time = node.createTime
        state = node.state
        quiesced = node.quiesced
        
        # Format date if possible
        created_str = ""
        if create_time:
            # pyVmomi usually returns datetime objects
            try:
                created_str = create_time.isoformat()
            except AttributeError:
                created_str = str(create_time)

        row = {
            "VM": vm_name,
            "SnapshotName": name,
            "Created": created_str,
            "Description": desc,
            "State": state,
            "Quiesced": str(quiesced),
            "Parent": parent_name,
            "SizeGB": "", # Difficult to get without browsing datastore
            "IsCurrent": False, # Will check later
            "SnapshotObj": node.snapshot, # Keep ref if needed
            "Powerstate": str(vm_power_state) if vm_power_state is not None else "",
            "Host": host_name,
            "Cluster": cluster_name,
            "Datacenter": datacenter_name,
            "Backup status": backup_status,
            "Last backup": last_backup,
        }
        apply_vm_meta(row, vm_meta, vi_meta, include_srm=True)
        results.append(row)
        
        # Recursively traverse children
        if hasattr(node, "childSnapshotList"):
            _traverse_snapshots(
                node.childSnapshotList,
                name,
                vm_name,
                results,
                vm_power_state,
                host_name,
                cluster_name,
                datacenter_name,
                vm_meta,
                vi_meta,
                backup_status,
                last_backup,
            )


def collect(context: CollectorContext):
    diagnostics = context.diagnostics
    logger = context.logger
    vi_meta = context.shared_data.get("vi_sdk")
    if not vi_meta:
        vi_meta = get_vi_sdk_meta(context.service_instance, context.config.server)
        context.shared_data["vi_sdk"] = vi_meta
    vm_meta_by_moid = context.shared_data.get("vm_meta_by_moid", {})
    field_map = context.shared_data.get("custom_field_map")
    if field_map is None:
        field_map = load_custom_field_map(context.content)
        context.shared_data["custom_field_map"] = field_map
    resolver = InventoryResolver(context.service_instance, logger=logger)

    try:
        vm_items = fetch_objects(
            context.service_instance, vim.VirtualMachine, SNAPSHOT_PROPERTIES
        )
    except Exception as exc:
        diagnostics.add_error("vSnapshot", "property_fetch", exc)
        logger.error("Fallo fetching vSnapshot: %s", exc)
        return []

    rows = []
    
    for item in vm_items:
        props = item.get("props", {})
        vm_name = props.get("name") or ""
        vm_ref = item.get("ref")
        moid = item.get("moid") or (vm_ref._GetMoId() if vm_ref and hasattr(vm_ref, "_GetMoId") else "")
        vm_meta = vm_meta_by_moid.get(moid)
        if not vm_meta:
            vm_meta = get_vm_meta(vm_ref, props, None)
        backup_status = ""
        last_backup = ""
        if field_map:
            backup_status, last_backup = extract_backup_fields(
                props.get("customValue"), field_map
            )
        
        # Check if VM has snapshots
        root_snapshot_list = props.get("snapshot.rootSnapshotList")
        if not root_snapshot_list:
            continue

        diagnostics.add_attempt("vSnapshot")
        
        current_snapshot_ref = props.get("snapshot.currentSnapshot")
        vm_power_state = props.get("runtime.powerState")
        host_ref = props.get("runtime.host")
        host_name = ""
        cluster_name = ""
        datacenter_name = ""
        if host_ref:
            host_name = resolver.resolve_host_name(host_ref)
            cluster_name = resolver.resolve_cluster_name(host_ref)
            datacenter_name = resolver.resolve_datacenter_name(host_ref)
        layout_ex = props.get("layoutEx")
        file_by_key, snapshot_layout_by_moid = _build_layout_maps(layout_ex)
        
        vm_snapshots = []
        try:
            _traverse_snapshots(
                root_snapshot_list,
                "",
                vm_name,
                vm_snapshots,
                vm_power_state,
                host_name,
                cluster_name,
                datacenter_name,
                vm_meta,
                vi_meta,
                backup_status,
                last_backup,
            )
            for snap in vm_snapshots:
                snap_obj = snap.get("SnapshotObj")
                snap_moid = snap_obj._GetMoId() if snap_obj else None
                layout_entry = snapshot_layout_by_moid.get(snap_moid)
                if layout_entry:
                    filename, size_vmsn, size_total = _compute_snapshot_sizes(
                        layout_entry, file_by_key
                    )
                    if filename:
                        snap["Filename"] = filename
                    if size_vmsn != "":
                        snap["Size MiB (vmsn)"] = size_vmsn
                    if size_total != "":
                        snap["Size MiB (total)"] = size_total

            current_moid = current_snapshot_ref._GetMoId() if current_snapshot_ref else None
            for snap in vm_snapshots:
                snap_obj = snap.pop("SnapshotObj", None)
                if snap_obj and current_moid and snap_obj._GetMoId() == current_moid:
                    snap["IsCurrent"] = True

            rows.extend(vm_snapshots)
            diagnostics.add_success("vSnapshot")
            
        except Exception as exc:
            diagnostics.add_error("vSnapshot", vm_name, exc)

    return rows
