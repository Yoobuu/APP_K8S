import logging
from typing import Dict, Optional, Tuple

from pyVmomi import vim


class InventoryResolver:
    def __init__(self, service_instance, logger: Optional[logging.Logger] = None) -> None:
        self.content = service_instance.RetrieveContent()
        self.logger = logger or logging.getLogger("rvtools_exporter")
        self._host_name: Dict[str, str] = {}
        self._cluster_name: Dict[str, str] = {}
        self._datacenter_name: Dict[str, str] = {}
        self._folder_name: Dict[str, str] = {}
        self._rp_name: Dict[str, str] = {}
        self._dvportgroup_map: Optional[Dict[str, str]] = None
        self._dvportgroup_switch: Optional[Dict[str, str]] = None
        self._dvs_by_uuid: Optional[Dict[str, str]] = None
        self._vswitch_by_host_pg: Dict[str, Dict[str, str]] = {}

    def resolve_host_name(self, host_ref) -> str:
        return self._resolve_cached(host_ref, self._host_name, "host")

    def resolve_folder_name(self, folder_ref) -> str:
        # Simplistic: just name. Full path would require walking up.
        return self._resolve_cached(folder_ref, self._folder_name, "folder")

    def resolve_resource_pool_name(self, rp_ref) -> str:
        return self._resolve_cached(rp_ref, self._rp_name, "resource pool")

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
        self._ensure_dvportgroup_maps()
        return self._dvportgroup_map.get(portgroup_key, portgroup_key)  # type: ignore[arg-type]

    def resolve_dvs_name_for_portgroup(self, portgroup_key: str) -> str:
        if not portgroup_key:
            return ""
        self._ensure_dvportgroup_maps()
        if self._dvportgroup_switch:
            return self._dvportgroup_switch.get(portgroup_key, "")
        return ""

    def resolve_dvs_name_by_uuid(self, switch_uuid: str) -> str:
        if not switch_uuid:
            return ""
        if self._dvs_by_uuid is None:
            self._dvs_by_uuid = self._load_dvswitches()
        return self._dvs_by_uuid.get(switch_uuid, "")

    def resolve_vswitch_for_portgroup(
        self, host_ref, portgroup_identifier: str, network_moid: str = ""
    ) -> str:
        if not host_ref or (not portgroup_identifier and not network_moid):
            return ""
        host_moid = host_ref._GetMoId()
        if host_moid not in self._vswitch_by_host_pg:
            self._vswitch_by_host_pg[host_moid] = self._load_host_portgroup_switch_map(
                host_ref
            )
        mapping = self._vswitch_by_host_pg.get(host_moid, {})
        if portgroup_identifier in mapping:
            return mapping[portgroup_identifier]
        if network_moid and network_moid in mapping:
            return mapping[network_moid]
        return ""

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

    def _ensure_dvportgroup_maps(self) -> None:
        if self._dvportgroup_map is None or self._dvportgroup_switch is None:
            names, switches = self._load_dvportgroups()
            self._dvportgroup_map = names
            self._dvportgroup_switch = switches

    def _load_dvportgroups(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        mapping: Dict[str, str] = {}
        switch_map: Dict[str, str] = {}
        view = self.content.viewManager.CreateContainerView(
            self.content.rootFolder, [vim.DistributedVirtualPortgroup], True
        )
        try:
            for portgroup in view.view:
                try:
                    key = portgroup.key
                    name = portgroup.name
                    dvs_name = ""
                    dvs_ref = None
                    try:
                        config = getattr(portgroup, "config", None)
                        if config is not None:
                            dvs_ref = getattr(config, "distributedVirtualSwitch", None)
                    except Exception:
                        dvs_ref = None
                    if dvs_ref:
                        try:
                            dvs_name = dvs_ref.name
                            dvs_uuid = getattr(dvs_ref, "uuid", "")
                            if dvs_uuid:
                                if self._dvs_by_uuid is None:
                                    self._dvs_by_uuid = {}
                                self._dvs_by_uuid[dvs_uuid] = dvs_name
                        except Exception as exc:
                            self.logger.debug("No se pudo leer dvSwitch para dvPortgroup: %s", exc)
                    if key:
                        mapping[key] = name
                        switch_map[key] = dvs_name
                except Exception as exc:
                    self.logger.debug("No se pudo leer dvPortgroup: %s", exc)
        finally:
            try:
                view.Destroy()
            except Exception:
                self.logger.debug("No se pudo destruir dvPortgroup view", exc_info=True)
        return mapping, switch_map

    def _load_dvswitches(self) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        view = self.content.viewManager.CreateContainerView(
            self.content.rootFolder, [vim.DistributedVirtualSwitch], True
        )
        try:
            for dvs in view.view:
                try:
                    uuid = getattr(dvs, "uuid", "") or ""
                    name = getattr(dvs, "name", "") or ""
                    if uuid:
                        mapping[uuid] = name
                except Exception as exc:
                    self.logger.debug("No se pudo leer dvSwitch: %s", exc)
        finally:
            try:
                view.Destroy()
            except Exception:
                self.logger.debug("No se pudo destruir dvSwitch view", exc_info=True)
        return mapping

    def _load_host_portgroup_switch_map(self, host_ref) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        if not host_ref:
            return mapping
        try:
            config = getattr(host_ref, "config", None)
            network = getattr(config, "network", None) if config else None
            portgroups = getattr(network, "portgroup", None) if network else None
            if not portgroups:
                return mapping
            for pg in portgroups:
                try:
                    spec = getattr(pg, "spec", None)
                    pg_name = getattr(spec, "name", "") if spec else ""
                    vswitch_name = getattr(spec, "vswitchName", "") if spec else ""
                    pg_key = getattr(pg, "key", "") or ""
                    if pg_name:
                        mapping[pg_name] = vswitch_name
                    if pg_key:
                        mapping[pg_key] = vswitch_name
                except Exception as exc:
                    self.logger.debug("No se pudo leer portgroup en host %s: %s", host_ref, exc)
        except Exception as exc:
            self.logger.debug("No se pudo resolver portgroup->vSwitch: %s", exc)
        return mapping
