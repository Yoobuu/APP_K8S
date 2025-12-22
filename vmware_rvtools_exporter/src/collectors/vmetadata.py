from pathlib import Path

from .context import CollectorContext
from ..version import EXPORTER_VERSION


def collect(context: CollectorContext):
    content = context.content
    about = content.about if content else None

    row = {
        "ExporterVersion": EXPORTER_VERSION,
        "GeneratedAt": context.connected_at,
        "Server": context.config.server,
        "ApiType": getattr(about, "apiType", ""),
        "ApiVersion": getattr(about, "apiVersion", ""),
        "Workbook": Path(context.config.out_path).name,
        "Format": "xlsx",
        "Locale": "en_US",
    }

    return [row]
