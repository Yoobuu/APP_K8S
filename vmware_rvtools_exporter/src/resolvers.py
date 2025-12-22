import logging
from typing import Dict, Optional

from pyVmomi import vim


class InventoryResolver:
    def __init__(self, service_instance, logger: Optional[logging.Logger] = None) -> None:
        self.content = service_instance.RetrieveContent()
        self.logger = logger or logging.getLogger("rvtools_exporter")
        self._host_name: Dict[str, str] = {}
        self._cluster_name: Dict[str, str] = {}
        self._datacenter_name: Dict[str, str] = {}
        self._dvportgroup_map: Optional[Dict[str, str]] = None

    def resolve_host_name(self, host_ref) -> str:
        return self._resolve_cached(host_ref, self._host_name, "host")

    def resolve_cluster_name(self, host_ref) -> str:
        if not host_ref:
            return ""
        host_moid = host_ref._GetMoId()
        if host_moid in self._cluster_name:
            return self._cluster_name[host_moid]
        name = ""
        try:
            parent = host_ref.parent
            name = parent.name if parent else ""
        except Exception as exc:
            self.logger.debug("No se pudo resolver cluster: %s", exc)
        self._cluster_name[host_moid] = name
        return name

    def resolve_datacenter_name(self, host_ref) -> str:
        if not host_ref:
            return ""
        host_moid = host_ref._GetMoId()
        if host_moid in self._datacenter_name:
            return self._datacenter_name[host_moid]
        name = ""
        try:
            current = host_ref
            while current:
                parent = getattr(current, "parent", None)
                if parent is None:
                    break
                if isinstance(parent, vim.Datacenter):
                    name = parent.name
                    break
                current = parent
        except Exception as exc:
            self.logger.debug("No se pudo resolver datacenter: %s", exc)
        self._datacenter_name[host_moid] = name
        return name

    def resolve_dvportgroup_name(self, portgroup_key: str) -> str:
        if not portgroup_key:
            return ""
        if self._dvportgroup_map is None:
            self._dvportgroup_map = self._load_dvportgroups()
        return self._dvportgroup_map.get(portgroup_key, portgroup_key)

    def _resolve_cached(self, host_ref, cache: Dict[str, str], label: str) -> str:
        if not host_ref:
            return ""
        host_moid = host_ref._GetMoId()
        if host_moid in cache:
            return cache[host_moid]
        name = ""
        try:
            name = host_ref.name
        except Exception as exc:
            self.logger.debug("No se pudo resolver %s: %s", label, exc)
        cache[host_moid] = name
        return name

    def _load_dvportgroups(self) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        view = self.content.viewManager.CreateContainerView(
            self.content.rootFolder, [vim.DistributedVirtualPortgroup], True
        )
        try:
            for portgroup in view.view:
                try:
                    key = portgroup.key
                    name = portgroup.name
                    if key:
                        mapping[key] = name
                except Exception as exc:
                    self.logger.debug("No se pudo leer dvPortgroup: %s", exc)
        finally:
            try:
                view.Destroy()
            except Exception:
                self.logger.debug("No se pudo destruir dvPortgroup view", exc_info=True)
        return mapping
