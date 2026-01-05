import api from "./axios";

export async function getHypervHosts(params = {}) {
  const { data } = await api.get("/hyperv/hosts", { params });
  return data;
}

export async function getHypervHostDetail(host, params = {}) {
  const { data } = await api.get(`/hyperv/hosts/${host}`, { params });
  return data;
}

export async function getHypervSnapshot(scope, hosts, level = "summary") {
  const params = { scope, hosts: hosts.join(","), level };
  const { data } = await api.get("/hyperv/snapshot", { params });
  return data;
}

export async function postHypervRefresh(body) {
  const { data } = await api.post("/hyperv/refresh", body);
  return data;
}

export async function getHypervConfig() {
  const { data } = await api.get("/hyperv/config");
  return data;
}
