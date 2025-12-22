from dataclasses import dataclass
from typing import Any


@dataclass
class CollectorContext:
    service_instance: Any
    content: Any
    config: Any
    logger: Any
    connected_at: str
    diagnostics: Any
