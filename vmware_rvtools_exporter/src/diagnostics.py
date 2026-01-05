from dataclasses import dataclass, field
from typing import Dict, List, Optional

from pyVmomi import vim, vmodl


@dataclass
class SheetDiagnostics:
    attempted_count: int = 0
    success_count: int = 0
    empty_count: int = 0
    no_permission_count: int = 0
    invalid_property_count: int = 0
    not_found_count: int = 0
    other_error_count: int = 0
    examples: List[Dict[str, str]] = field(default_factory=list)

    @property
    def total_error_count(self) -> int:
        return (
            self.no_permission_count
            + self.invalid_property_count
            + self.not_found_count
            + self.other_error_count
        )


class Diagnostics:
    def __init__(self, sheet_names: Optional[List[str]] = None) -> None:
        self._stats: Dict[str, SheetDiagnostics] = {}
        self._runtime_config: Dict[str, object] = {}
        if sheet_names:
            for name in sheet_names:
                self._stats[name] = SheetDiagnostics()

    def _get_stats(self, sheet: str) -> SheetDiagnostics:
        if sheet not in self._stats:
            self._stats[sheet] = SheetDiagnostics()
        return self._stats[sheet]

    def get_sheet_stats(self, sheet: str) -> SheetDiagnostics:
        return self._get_stats(sheet)

    @staticmethod
    def classify_exception(exc: Exception) -> str:
        if isinstance(exc, vim.fault.NoPermission):
            return "no_permission"
        invalid_cls = getattr(vim.fault, "InvalidProperty", None)
        if invalid_cls and isinstance(exc, invalid_cls):
            return "invalid_property"
        message = str(exc).lower()
        if "invalidproperty" in message or "invalid property" in message:
            return "invalid_property"
        not_found = [vmodl.fault.ManagedObjectNotFound]
        if hasattr(vim.fault, "NotFound"):
            not_found.append(vim.fault.NotFound)
        if isinstance(exc, tuple(not_found)):
            return "not_found"
        return "other_error"

    def add_attempt(self, sheet: str) -> None:
        self._get_stats(sheet).attempted_count += 1

    def add_success(self, sheet: str) -> None:
        self._get_stats(sheet).success_count += 1

    def add_empty(self, sheet: str) -> None:
        self._get_stats(sheet).empty_count += 1

    def add_error(self, sheet: str, entity: str, exc: Exception) -> str:
        error_type = self.classify_exception(exc)
        stats = self._get_stats(sheet)

        if error_type == "no_permission":
            stats.no_permission_count += 1
        elif error_type == "invalid_property":
            stats.invalid_property_count += 1
        elif error_type == "not_found":
            stats.not_found_count += 1
        else:
            stats.other_error_count += 1

        if len(stats.examples) < 10:
            stats.examples.append(
                {
                    "entity": str(entity),
                    "error_type": error_type,
                    "message": str(exc),
                }
            )

        return error_type

    def set_runtime_config(self, runtime_config: Dict[str, object]) -> None:
        self._runtime_config = dict(runtime_config)

    def to_dict(self) -> Dict[str, object]:
        serialized: Dict[str, Dict[str, object]] = {}
        for sheet, stats in self._stats.items():
            serialized[sheet] = {
                "attempted_count": stats.attempted_count,
                "success_count": stats.success_count,
                "empty_count": stats.empty_count,
                "no_permission_count": stats.no_permission_count,
                "invalid_property_count": stats.invalid_property_count,
                "not_found_count": stats.not_found_count,
                "other_error_count": stats.other_error_count,
                "examples": list(stats.examples),
            }
        return {"runtime_config": dict(self._runtime_config), **serialized}
