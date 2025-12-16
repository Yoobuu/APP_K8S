import api from "./axios";

export function cediaLogin() {
  return api.get("/cedia/login");
}

export function listCediaVms() {
  return api.get("/cedia/vms");
}

export function getCediaVm(vmId) {
  return api.get(`/cedia/vms/${vmId}`);
}

export function getCediaVmMetrics(vmId) {
  return api.get(`/cedia/vms/${vmId}/metrics`);
}
