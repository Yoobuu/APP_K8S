"""Imprime información detallada de hosts ESXi usando pyVmomi."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from pyVim.connect import Disconnect
from pyVmomi import vim

# Asegura que el paquete app sea importable desde el script
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Carga variables de entorno (VCENTER_HOST, VCENTER_USER, VCENTER_PASS, etc.)
load_dotenv(BASE_DIR / ".env")

from app.vms.vm_service import _soap_connect  # noqa: E402


def _collect_datastores(host: vim.HostSystem) -> list[dict]:
    entries: list[dict] = []
    for ds in getattr(host, "datastore", []) or []:
        name = getattr(ds, "name", None)
        summary = getattr(ds, "summary", None)
        capacity = getattr(summary, "capacity", None) if summary else None
        free_space = getattr(summary, "freeSpace", None) if summary else None
        used = capacity - free_space if isinstance(capacity, (int, float)) and isinstance(free_space, (int, float)) else None
        entries.append(
            {
                "name": name,
                "capacity": capacity,
                "free_space": free_space,
                "used": used,
            }
        )
    return entries


def _collect_vms(host: vim.HostSystem) -> list[str]:
    result: list[str] = []
    for vm in getattr(host, "vm", []) or []:
        name = getattr(vm, "name", None)
        moid = getattr(vm, "_moId", None)
        result.append(name or moid or "<sin nombre>")
    return result


def main() -> int:
    si = None
    view = None
    try:
        si, content = _soap_connect()
        view = content.viewManager.CreateContainerView(content.rootFolder, [vim.HostSystem], True)

        hosts_payload: list[dict] = []
        for host in view.view:
            summary = getattr(host, "summary", None)
            hardware = getattr(summary, "hardware", None) if summary else None
            config = getattr(summary, "config", None) if summary else None
            quick = getattr(summary, "quickStats", None) if summary else None

            hosts_payload.append(
                {
                    "name": getattr(host, "name", None),
                    "hardware": {
                        "cpu_model": getattr(hardware, "cpuModel", None),
                        "cpu_cores": getattr(hardware, "numCpuCores", None),
                        "cpu_threads": getattr(hardware, "numCpuThreads", None),
                        "cpu_pkgs": getattr(hardware, "numCpuPkgs", None),
                        "memory_size": getattr(hardware, "memorySize", None),
                    },
                    "config": {
                        "product_name": getattr(config, "product", None) and getattr(config.product, "name", None),
                        "full_name": getattr(config, "product", None) and getattr(config.product, "fullName", None),
                        "version": getattr(config, "product", None) and getattr(config.product, "version", None),
                        "build": getattr(config, "product", None) and getattr(config.product, "build", None),
                        "vendor": getattr(config, "product", None) and getattr(config.product, "vendor", None),
                        "model": getattr(config, "product", None) and getattr(config.product, "osType", None),
                        "server_model": getattr(config, "product", None) and getattr(config.product, "productLineId", None),
                    },
                    "quick_stats": {
                        "overall_cpu_usage_mhz": getattr(quick, "overallCpuUsage", None),
                        "overall_memory_usage_mb": getattr(quick, "overallMemoryUsage", None),
                        "uptime_seconds": getattr(quick, "uptime", None),
                    },
                    "datastores": _collect_datastores(host),
                    "vms": _collect_vms(host),
                }
            )

        print(json.dumps(hosts_payload, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:  # pragma: no cover - script manual
        print(f"[ERROR] {exc}")
        return 1
    finally:
        if view is not None:
            try:
                view.Destroy()
            except Exception:
                pass
        if si is not None:
            try:
                Disconnect(si)
            except Exception:
                pass


if __name__ == "__main__":  # pragma: no cover - entrada script
    raise SystemExit(main())
