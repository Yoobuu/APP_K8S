from typing import Dict, List

from pyVmomi import vim, vmodl


def fetch_vms(service_instance, properties: List[str]) -> List[Dict[str, object]]:
    content = service_instance.RetrieveContent()
    view = content.viewManager.CreateContainerView(
        content.rootFolder, [vim.VirtualMachine], True
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
            type=vim.VirtualMachine,
            pathSet=properties,
            all=False,
        )
        filter_spec = vmodl.query.PropertyCollector.FilterSpec(
            objectSet=[obj_spec],
            propSet=[prop_spec],
        )
        options = vmodl.query.PropertyCollector.RetrieveOptions(maxObjects=1000)

        results: List[Dict[str, object]] = []
        retrieved = collector.RetrievePropertiesEx([filter_spec], options)

        while retrieved:
            for obj in retrieved.objects:
                prop_dict = {prop.name: prop.val for prop in obj.propSet}
                results.append(
                    {
                        "moid": obj.obj._GetMoId(),
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
