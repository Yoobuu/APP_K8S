from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class CollectorContext:
    service_instance: Any
    content: Any
    config: Any
    logger: Any
    connected_at: str
    diagnostics: Any
    shared_data: Dict[str, Any] = field(default_factory=dict)
