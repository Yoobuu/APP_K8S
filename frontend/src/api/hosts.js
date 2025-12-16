import api from "./axios";

export async function getHosts(params = {}) {
  const { data } = await api.get("/hosts/", { params });
  return data;
}

export async function getHostDetail(id, params = {}) {
  const { data } = await api.get(`/hosts/${id}`, { params });
  return data;
}

export async function getHostDeep(id, params = {}) {
  const { data } = await api.get(`/hosts/${id}/deep`, { params });
  return data;
}
