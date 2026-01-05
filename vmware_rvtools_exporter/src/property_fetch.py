import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from pyVmomi import vim, vmodl


def _is_invalid_property(exc: Exception) -> bool:
    invalid_cls = getattr(vim.fault, "InvalidProperty", None)
    if invalid_cls and isinstance(exc, invalid_cls):
        return True
    message = str(exc).lower()
    return "invalidproperty" in message or "invalid property" in message


def _extract_invalid_property(exc: Exception) -> Optional[str]:
    for attr in ("name", "propertyName", "property"):
        if hasattr(exc, attr):
            value = getattr(exc, attr)
            if value:
                return str(value)
    message = str(exc)
    match = re.search(
        r"(?:InvalidProperty|property(?:Name)?)[:= ]+['\"]?([A-Za-z0-9_.-]+)",
        message,
    )
    if match:
        return match.group(1)
    return None


def _remove_property(properties: List[str], prop_name: str) -> Tuple[List[str], bool]:
    if not prop_name:
        return list(properties), False
    if prop_name in properties:
        return [prop for prop in properties if prop != prop_name], True
    lowered = prop_name.lower()
    new_props = [prop for prop in properties if prop.lower() != lowered]
    if len(new_props) != len(properties):
        return new_props, True
    return list(properties), False


def _probe_properties(
    service_instance, properties: List[str]
) -> Tuple[bool, Optional[str], Optional[Exception]]:
    try:
        fetch_objects(service_instance, vim.VirtualMachine, properties)
        return True, None, None
    except Exception as exc:
        if not _is_invalid_property(exc):
            raise
        prop = getattr(exc, "_invalid_property_name", None) or _extract_invalid_property(exc)
        return False, prop, exc


def _isolate_invalid_property(
    service_instance, properties: List[str]
) -> Tuple[Optional[str], Optional[Exception]]:
    if not properties:
        return None, None
    if len(properties) == 1:
        return properties[0], None

    mid = len(properties) // 2
    left = properties[:mid]
    right = properties[mid:]

    left_ok, left_prop, left_exc = _probe_properties(service_instance, left)
    if not left_ok:
        if left_prop:
            return left_prop, left_exc
        return _isolate_invalid_property(service_instance, left)

    right_ok, right_prop, right_exc = _probe_properties(service_instance, right)
    if not right_ok:
        if right_prop:
            return right_prop, right_exc
        return _isolate_invalid_property(service_instance, right)

    return None, None


def fetch_objects(
    service_instance, obj_type: Any, properties: List[str]
) -> List[Dict[str, object]]:
    content = service_instance.RetrieveContent()
    view = content.viewManager.CreateContainerView(
        content.rootFolder, [obj_type], True
    )

    try:
        collector = content.propertyCollector
        traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
            name="traverseView",
            path="view",
            skip=False,
            type=vim.view.ContainerView,
        )
        obj_spec = vmodl.query.PropertyCollector.ObjectSpec(
            obj=view,
            skip=True,
            selectSet=[traversal_spec],
        )
        prop_spec = vmodl.query.PropertyCollector.PropertySpec(
            type=obj_type,
            pathSet=properties,
            all=False,
        )
        filter_spec = vmodl.query.PropertyCollector.FilterSpec(
            objectSet=[obj_spec],
            propSet=[prop_spec],
        )
        options = vmodl.query.PropertyCollector.RetrieveOptions(maxObjects=1000)

        results: List[Dict[str, object]] = []
        try:
            retrieved = collector.RetrievePropertiesEx([filter_spec], options)
        except Exception as exc:
            if _is_invalid_property(exc):
                prop = _extract_invalid_property(exc)
                if prop:
                    try:
                        setattr(exc, "_invalid_property_name", prop)
                    except Exception:
                        pass
            raise

        while retrieved:
            for obj in retrieved.objects:
                prop_dict = {prop.name: prop.val for prop in obj.propSet}
                results.append(
                    {
                        "moid": obj.obj._GetMoId(),
                        "ref": obj.obj,
                        "props": prop_dict,
                    }
                )
            if retrieved.token:
                retrieved = collector.ContinueRetrievePropertiesEx(retrieved.token)
            else:
                break

        return results
    finally:
        try:
            view.Destroy()
        except Exception:
            pass


def fetch_vms(service_instance, properties: List[str]) -> List[Dict[str, object]]:
    return fetch_objects(service_instance, vim.VirtualMachine, properties)


def safe_fetch_vms(
    service_instance,
    properties: List[str],
    max_retries: int = 8,
    logger: Optional[logging.Logger] = None,
    diagnostics: Optional[object] = None,
    sheet_name: str = "vInfo",
) -> List[Dict[str, object]]:
    logger = logger or logging.getLogger("rvtools_exporter")
    working = list(properties)
    properties[:] = working
    retries = 0

    while retries < max_retries:
        try:
            return fetch_objects(service_instance, vim.VirtualMachine, working)
        except Exception as exc:
            if not _is_invalid_property(exc):
                raise
            prop = getattr(exc, "_invalid_property_name", None) or _extract_invalid_property(exc)
            if not prop:
                try:
                    prop, prop_exc = _isolate_invalid_property(service_instance, working)
                except Exception:
                    prop = None
                    prop_exc = None
                if prop_exc:
                    exc = prop_exc
            if not prop:
                logger.warning("InvalidProperty en fetch_vms: nombre desconocido")
                if diagnostics:
                    diagnostics.add_error(
                        sheet_name, "fetch_vms", Exception("invalid property (name unknown)")
                    )
                return []

            logger.warning("InvalidProperty en fetch_vms: %s", prop)
            if diagnostics:
                diagnostics.add_error(sheet_name, prop, exc)
            new_working, removed = _remove_property(working, prop)
            if not removed:
                logger.warning("InvalidProperty en fetch_vms: no se pudo remover %s", prop)
                return []
            working = new_working
            properties[:] = working
            retries += 1
            if not working:
                return []
        except Exception:
            raise

    return []
