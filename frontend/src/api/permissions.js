import api from "./axios";

export function listPermissionCatalog() {
  return api.get("/permissions/");
}

export function getUserPermissions(userId) {
  return api.get(`/permissions/users/${userId}`);
}

export function updateUserPermissions(userId, overrides) {
  return api.put(`/permissions/users/${userId}`, { overrides });
}
