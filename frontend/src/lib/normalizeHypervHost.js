const toNumber = (val) => {
  if (val == null) return null;
  const n = Number(val);
  return Number.isFinite(n) ? n : null;
};

const bytesToGb = (val) => {
  const n = toNumber(val);
  return n != null ? Math.round((n / (1024 ** 3)) * 100) / 100 : null;
};

export function normalizeHypervHostSummary(raw) {
  if (!raw) return null;
  const switches = Array.isArray(raw.switches) ? raw.switches : [];
  const nics = Array.isArray(raw.nics) ? raw.nics : [];
  return {
    id: raw.host,
    name: raw.host,
    cluster: raw.cluster,
    version: raw.version,
    logical_processors: toNumber(raw.logical_processors),
    memory_capacity_bytes: toNumber(raw.memory_capacity_bytes),
    memory_capacity_gb: bytesToGb(raw.memory_capacity_bytes),
    vmm_migration_enabled: Boolean(raw.virtual_machine_migration_enabled),
    total_vms: toNumber(raw.total_vms),
    switch_count: switches.length,
    switches,
    nics,
    nic_count: nics.length,
    storage: Array.isArray(raw.storage) ? raw.storage : [],
    uptime_seconds: toNumber(raw.uptime_seconds),
    cpu_usage_pct: toNumber(raw.cpu_usage_pct),
    memory_usage_pct: toNumber(raw.memory_usage_pct),
  };
}
