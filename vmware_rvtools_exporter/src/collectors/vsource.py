from .context import CollectorContext


def collect(context: CollectorContext):
    content = context.content
    about = content.about if content else None

    server_time = ""
    if context.service_instance is not None:
        try:
            server_time = context.service_instance.CurrentTime().isoformat()
        except Exception:
            server_time = ""

    row = {
        "SourceName": context.config.server,
        "SourceType": getattr(about, "apiType", ""),
        "ApiVersion": getattr(about, "apiVersion", ""),
        "ApiBuild": getattr(about, "build", ""),
        "InstanceUuid": getattr(about, "instanceUuid", ""),
        "ServerTime": server_time,
        "User": context.config.user,
        "Client": "vmware_rvtools_exporter",
        "ConnectedAt": context.connected_at,
    }

    return [row]
