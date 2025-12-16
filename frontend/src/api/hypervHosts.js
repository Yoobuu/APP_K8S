import api from "./axios";

export async function getHypervHosts(params = {}) {
  const { data } = await api.get("/hyperv/hosts", { params });
  return data;
}

export async function getHypervHostDetail(host, params = {}) {
  const { data } = await api.get(`/hyperv/hosts/${host}`, { params });
  return data;
}
