from pyVmomi import vim

from .context import CollectorContext
from ..property_fetch import fetch_objects
from ..resolvers import InventoryResolver

DATASTORE_PROPERTIES = [
    "name",
    "summary.type",
    "summary.capacity",
    "summary.freeSpace",
    "summary.accessible",
    "summary.url",
    "browser",
]


def collect(context: CollectorContext):
    diagnostics = context.diagnostics
    logger = context.logger

    try:
        ds_items = fetch_objects(
            context.service_instance, vim.Datastore, DATASTORE_PROPERTIES
        )
    except Exception as exc:
        diagnostics.add_error("vDatastore", "property_fetch", exc)
        logger.error("Fallo fetching vDatastore: %s", exc)
        return []

    context.shared_data["datastores"] = ds_items

    resolver = InventoryResolver(context.service_instance, logger=logger)
    rows = []

    for item in ds_items:
        diagnostics.add_attempt("vDatastore")
        props = item.get("props", {})
        ref = item.get("ref")
        name = props.get("name") or ""

        if not name:
            diagnostics.add_error("vDatastore", "<unknown>", ValueError("Missing name"))
            continue

        diagnostics.add_success("vDatastore")

        datacenter = resolver.resolve_datacenter_name(ref)
        
        capacity_bytes = props.get("summary.capacity") or 0
        free_bytes = props.get("summary.freeSpace") or 0
        
        capacity_gb = round(capacity_bytes / (1024**3), 2)
        free_gb = round(free_bytes / (1024**3), 2)
        used_gb = round((capacity_bytes - free_bytes) / (1024**3), 2)
        provisioned_gb = 0 # Difficult to get accurately without browsing
        
        ds_type = props.get("summary.type", "")
        accessible = props.get("summary.accessible", False)
        url = props.get("summary.url", "")

        rows.append({
            "Datastore": name,
            "Type": ds_type,
            "CapacityGB": capacity_gb,
            "FreeGB": free_gb,
            "UsedGB": used_gb,
            "ProvisionedGB": provisioned_gb,
            "NumVMs": "", # Would require cross-reference
            "Datacenter": datacenter,
            "Cluster": "", # Many-to-many relationship, skipping for simple row
            "Accessible": str(accessible),
            "URL": url,
        })

    return rows