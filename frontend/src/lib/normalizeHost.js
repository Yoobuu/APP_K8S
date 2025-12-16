const pct = (num, den) => {
  if (num == null || den == null || !Number.isFinite(num) || !Number.isFinite(den) || den === 0) return null;
  return Math.round((num / den) * 10000) / 100;
};

const toNumber = (value) => {
  if (value == null) return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

const toList = (val) => (Array.isArray(val) ? val : []);

const humanUptime = (seconds) => {
  if (!Number.isFinite(seconds)) return "—";
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const parts = [];
  if (d) parts.push(`${d}d`);
  if (h || d) parts.push(`${h}h`);
  parts.push(`${m}m`);
  return parts.join(" ");
};

const toGB = (value) => {
  if (!Number.isFinite(value)) return null;
  return Math.round((value / 1024) * 100) / 100;
};

const formatBytes = (bytes) => {
  if (!Number.isFinite(bytes)) return "—";
  const tb = bytes / (1024 ** 4);
  if (tb >= 1) return `${tb.toFixed(2)} TB`;
  const gb = bytes / (1024 ** 3);
  return `${gb.toFixed(2)} GB`;
};

const translatePowerPolicy = (name) => {
  const map = {
    "PowerPolicy.dynamic.name": "Automático (dinámico)",
    "PowerPolicy.static.name": "Máximo rendimiento",
    "PowerPolicy.low.name": "Ahorro de energía",
  };
  if (!name) return null;
  return map[name] || name;
};

const translateState = (value) => {
  const map = {
    connected: "Conectado",
    disconnected: "Desconectado",
    poweredon: "Encendido",
    poweredoff: "Apagado",
  };
  const key = String(value || "").toLowerCase();
  return map[key] || value;
};

const classifyServerType = (model) => {
  const m = String(model || "").toUpperCase();
  if (m.includes("B200")) return "Blade";
  if (m.includes("R7") || m.includes("R6")) return "Rack";
  return "Servidor";
};

const computeHealth = (raw) => {
  const sensors = raw?.health_sensors || [];
  const hasCritical = sensors.some((s) => String(s.health || s.status || "").toLowerCase().includes("red"));
  const hasWarn = sensors.some((s) => String(s.health || s.status || "").toLowerCase().includes("yellow"));
  const conn = String(raw?.connection_state || raw?.runtime?.connection_state || "").toLowerCase();
  if (hasCritical || conn === "disconnected") return "critical";
  if (hasWarn) return "warning";
  return "healthy";
};

const formatSensors = (sensors = []) => {
  const buckets = { temperature: [], power: [], voltage: [], fan: [], other: [] };
  sensors.forEach((s) => {
    const name = String(s.name || "").toLowerCase();
    const entry = { ...s };
    if (name.includes("temp")) buckets.temperature.push(entry);
    else if (name.includes("power")) buckets.power.push(entry);
    else if (name.includes("volt") || name.includes("12v") || name.includes("5v") || name.includes("3.3")) buckets.voltage.push(entry);
    else if (name.includes("fan")) buckets.fan.push(entry);
    else buckets.other.push(entry);
  });
  return buckets;
};

export function normalizeHostSummary(raw) {
  if (!raw) return null;
  const memMb = toNumber(raw.memory_total_mb);
  const cpuUsageMhz = toNumber(raw.overall_cpu_usage_mhz);
  const cpuCapMhz = raw.cpu_cores ? toNumber(raw.cpu_cores) * 1000 : null;
  const health = computeHealth(raw);
  const type = classifyServerType(raw.model);
  return {
    id: raw.id,
    name: raw.name,
    cluster: raw.cluster,
    connection_state: translateState(raw.connection_state),
    power_state: translateState(raw.power_state),
    cpu_cores: toNumber(raw.cpu_cores),
    cpu_threads: toNumber(raw.cpu_threads),
    memory_total_mb: memMb,
    memory_total_gb: toGB(memMb),
    cpu_usage_mhz: cpuUsageMhz,
    cpu_usage_pct: pct(cpuUsageMhz, cpuCapMhz),
    cpu_free_pct: cpuCapMhz && cpuUsageMhz != null ? Math.max(0, Math.round((1 - cpuUsageMhz / cpuCapMhz) * 100)) : null,
    memory_usage_mb: toNumber(raw.overall_memory_usage_mb),
    memory_usage_pct: pct(toNumber(raw.overall_memory_usage_mb), memMb),
    memory_free_pct:
      memMb != null && raw.overall_memory_usage_mb != null
        ? Math.max(0, Math.round((1 - raw.overall_memory_usage_mb / memMb) * 100))
        : null,
    total_vms: toNumber(raw.total_vms),
    version: raw.version,
    build: raw.build,
    vendor: raw.vendor,
    model: raw.model,
    server_type: type,
    health,
    datastore_usage_pct: null,
  };
}

export function normalizeHostDetail(raw) {
  if (!raw) return null;
  const hardware = raw.hardware || {};
  const quick = raw.quick_stats || {};
  const memBytes = toNumber(hardware.memory_size_bytes);
  const memMbTotal = memBytes != null ? Math.round(memBytes / (1024 * 1024)) : null;
  const memMbUsed = toNumber(quick.overall_memory_usage_mb);
  const cpuUsageMhz = toNumber(quick.overall_cpu_usage_mhz);
  const cpuCapMhz = hardware.cpu_cores ? toNumber(hardware.cpu_cores) * 1000 : null;
  const health = computeHealth(raw);
  const type = classifyServerType(hardware.server_model);
  const datastores = (raw.datastores || []).map((ds) => {
    const cap = toNumber(ds.capacity);
    const free = toNumber(ds.free_space);
    const used = toNumber(ds.used);
    const usedVal = used != null ? used : cap != null && free != null ? cap - free : null;
    return {
      name: ds.name,
      capacity: cap,
      capacity_h: formatBytes(cap),
      free_space: free,
      free_space_h: formatBytes(free),
      used: usedVal,
      used_h: formatBytes(usedVal),
      type: ds.type,
      status: ds.status,
      used_pct: pct(usedVal, cap),
    };
  });

  const vmkGrouped = { management: [], vmotion: [], vsan: [], provisioning: [], otros: [] };
  (raw.networking?.vmkernel_nics || []).forEach((vmk) => {
    const name = String(vmk.portgroup || vmk.device || '').toLowerCase();
    const bucket = name.includes('motion') ? 'vmotion' : name.includes('san') ? 'vsan' : name.includes('prov') ? 'provisioning' : name.includes('manag') ? 'management' : 'otros';
    vmkGrouped[bucket].push(vmk);
  });

  const representativeSensors = (raw.sensors || []).reduce(
    (acc, sensor) => {
      const lname = String(sensor.name || '').toLowerCase();
      if (lname.includes('temp') && !acc.temperature) acc.temperature = sensor;
      else if ((lname.includes('volt') || lname.includes('12v') || lname.includes('5v') || lname.includes('3.3')) && !acc.voltage) acc.voltage = sensor;
      else if (lname.includes('power') && !acc.power) acc.power = sensor;
      else if (lname.includes('fan') && !acc.fan) acc.fan = sensor;
      return acc;
    },
    { temperature: null, voltage: null, power: null, fan: null }
  );

  return {
    id: raw.id,
    name: raw.name,
    cluster: raw.cluster,
    datacenter: raw.datacenter,
    server_type: type,
    health,
    hardware: {
      cpu_model: hardware.cpu_model,
      cpu_pkgs: toNumber(hardware.cpu_pkgs),
      cpu_cores: toNumber(hardware.cpu_cores),
      cpu_threads: toNumber(hardware.cpu_threads),
      memory_size_bytes: memBytes,
      memory_size_mb: memMbTotal,
      memory_size_gb: toGB(memMbTotal),
      server_model: hardware.server_model,
      vendor: hardware.vendor,
    },
    esxi: raw.esxi || {},
    quick_stats: {
      cpu_usage_mhz: cpuUsageMhz,
      cpu_usage_pct: pct(cpuUsageMhz, cpuCapMhz),
      cpu_total_mhz: cpuCapMhz,
      cpu_free_mhz: cpuCapMhz != null && cpuUsageMhz != null ? cpuCapMhz - cpuUsageMhz : null,
      memory_usage_mb: memMbUsed,
      memory_usage_pct: pct(memMbUsed, memMbTotal),
      memory_total_mb: memMbTotal,
      memory_free_mb: memMbTotal != null && memMbUsed != null ? memMbTotal - memMbUsed : null,
      memory_total_gb: toGB(memMbTotal),
      memory_free_gb: memMbTotal != null && memMbUsed != null ? toGB(memMbTotal - memMbUsed) : null,
      uptime_seconds: toNumber(quick.uptime_seconds),
      uptime_human: humanUptime(toNumber(quick.uptime_seconds)),
      power_policy: translatePowerPolicy(quick.power_policy?.name || quick.power_policy?.short_name || quick.power_policy),
    },
    networking: {
      pnics: raw.networking?.pnics || [],
      vmkernel_nics: raw.networking?.vmkernel_nics || [],
      vmk_grouped: vmkGrouped,
      vswitches: raw.networking?.vswitches || [],
      dvswitches: raw.networking?.dvswitches || [],
    },
    datastores,
    maintenance: raw.quick_stats?.in_maintenance ?? raw.maintenance ?? null,
    vms: toList(raw.vms).map((vm) => ({
      name: vm.name,
      moid: vm.moid,
      power_state: translateState(vm.power_state),
    })),
    sensor_samples: representativeSensors,
  };
}

const renameSensor = (name = "") => {
  const n = name.toLowerCase();
  if (n.includes("memory")) return "DIMM";
  if (n.includes("proc")) return "CPU Sensor";
  if (n.includes("board")) return "Board Sensor";
  return name;
};

export function normalizeHostDeep(raw) {
  if (!raw) return null;
  const sensors = formatSensors(raw.sensors || []);
  // rename entries
  Object.keys(sensors).forEach((k) => {
    sensors[k] = sensors[k].map((s) => ({ ...s, name: renameSensor(s.name || '') }));
  });
  return {
    id: raw.id,
    name: raw.name,
    sensors,
    networking: raw.networking || {},
    storage: raw.storage || {},
    security: raw.security || {},
    profiles: raw.profiles || {},
    hardware: raw.hardware || {},
    runtime: raw.runtime || {},
    datastores: raw.datastores || [],
    vms: raw.vms || [],
    raw,
  };
}
