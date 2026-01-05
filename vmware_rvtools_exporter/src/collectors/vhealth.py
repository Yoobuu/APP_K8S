from pyVmomi import vim

from .context import CollectorContext
from ..property_fetch import fetch_objects
from ..utils.vm_meta import apply_vm_meta, get_vi_sdk_meta


def collect(context: CollectorContext):
    diagnostics = context.diagnostics
    logger = context.logger
    config = context.config
    vi_meta = context.shared_data.get("vi_sdk")
    if not vi_meta:
        vi_meta = get_vi_sdk_meta(context.service_instance, context.config.server)
        context.shared_data["vi_sdk"] = vi_meta

    # Properties to fetch
    props = ["name", "overallStatus", "triggeredAlarmState"]
    if config.health_events_enabled:
        # We can't easily fetch healthSystemRuntime via simple property list if it's deep/complex
        # but we can try.
        props.append("runtime.healthSystemRuntime")

    try:
        host_items = fetch_objects(
            context.service_instance, vim.HostSystem, props
        )
    except Exception as exc:
        diagnostics.add_error("vHealth", "property_fetch", exc)
        return []

    rows = []
    
    # Event Manager for events
    event_manager = None
    if config.health_events_enabled:
        try:
            event_manager = context.service_instance.content.eventManager
        except:
            pass

    for item in host_items:
        diagnostics.add_attempt("vHealth")
        try:
            props_dict = item.get("props", {})
            name = props_dict.get("name")
            status = str(props_dict.get("overallStatus", "unknown"))
            host_ref = item.get("ref") # ManagedObject reference
            
            # Base row: Host Status
            rows.append({
                "Entity": name,
                "Type": "Host",
                "Status": status,
                "Summary": f"Host status is {status}",
                "Details": "",
                "Sensor": "overallStatus",
                "Reading": "",
                "Unit": ""
            })
            apply_vm_meta(rows[-1], None, vi_meta)
            
            if config.health_events_enabled:
                # 1. Alarms
                alarms = props_dict.get("triggeredAlarmState", []) or []
                for alarm in alarms:
                    # Resolve alarm name if possible, otherwise use ID
                    # alarm.alarm is a MoRef.
                    # This would require caching alarms. For now use key.
                    rows.append({
                        "Entity": name,
                        "Type": "Alarm",
                        "Status": str(alarm.overallStatus),
                        "Summary": f"Triggered Alarm: {alarm.key}", # Improving this requires AlarmManager fetch
                        "Details": str(alarm.time),
                        "Sensor": "Alarm",
                        "Reading": "",
                        "Unit": ""
                    })
                    apply_vm_meta(rows[-1], None, vi_meta)

                # 2. Events
                if event_manager and host_ref:
                    try:
                        event_filter = vim.event.EventFilterSpec()
                        event_filter.entity = vim.event.EventFilterSpec.EntityDefaultSpec()
                        event_filter.entity.entity = host_ref
                        # recursion? self only
                        event_filter.entity.recursion = vim.event.EventFilterSpec.RecursionOption.self
                        
                        # We want warnings/errors?
                        # event_filter.type = ["VmPoweredOffEvent", "VmSuspendedEvent"] # Example
                        
                        # Limit count
                        collector = event_manager.CreateCollectorForEvents(event_filter)
                        if collector:
                            # Set page size
                            events = collector.ReadNextEvents(config.health_events_max_per_host)
                            for evt in events:
                                # Simple mapping
                                msg = evt.fullFormattedMessage if hasattr(evt, "fullFormattedMessage") else evt.userName
                                rows.append({
                                    "Entity": name,
                                    "Type": "Event",
                                    "Status": evt.key, # Event ID
                                    "Summary": msg,
                                    "Details": str(evt.createdTime),
                                    "Sensor": "Event",
                                    "Reading": "",
                                    "Unit": ""
                                })
                                apply_vm_meta(rows[-1], None, vi_meta)
                            collector.DestroyCollector()
                    except Exception as evt_exc:
                        logger.debug(f"Failed to fetch events for {name}: {evt_exc}")

                # 3. Health System Runtime (Sensors)
                hs_runtime = props_dict.get("runtime.healthSystemRuntime")
                if hs_runtime and hasattr(hs_runtime, "systemHealthInfo") and hs_runtime.systemHealthInfo:
                    if hasattr(hs_runtime.systemHealthInfo, "numericSensorInfo"):
                        for sensor in hs_runtime.systemHealthInfo.numericSensorInfo:
                            rows.append({
                                "Entity": name,
                                "Type": "Sensor",
                                "Status": sensor.healthState.label if sensor.healthState else "unknown",
                                "Summary": sensor.name,
                                "Details": f"Base Units: {sensor.baseUnits}",
                                "Sensor": sensor.sensorType,
                                "Reading": str(sensor.currentReading),
                                "Unit": sensor.unitModifier
                            })
                            apply_vm_meta(rows[-1], None, vi_meta)

            diagnostics.add_success("vHealth")
        except Exception as exc:
            diagnostics.add_error("vHealth", name, exc)

    return rows
