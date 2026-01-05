import api from "./axios";

export function cediaLogin() {
  return api.get("/cedia/login");
}

export function listCediaVms() {
  return api.get("/cedia/vms");
}

export async function getCediaSnapshot() {
  const response = await api.get("/cedia/snapshot");
  if (response.status === 204) {
    return { empty: true };
  }
  return response.data;
}

export function getCediaVm(vmId) {
  return api.get(`/cedia/vms/${vmId}`);
}

export function getCediaVmMetrics(vmId) {
  return api.get(`/cedia/vms/${vmId}/metrics`);
}
