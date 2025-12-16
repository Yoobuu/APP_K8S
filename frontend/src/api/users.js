import api from "./axios";

export function listUsers() {
  return api.get("/users/");
}

export function createUser(payload) {
  return api.post("/users/", payload);
}

export function resetUserPassword(userId, newPassword) {
  return api.post(`/users/${userId}/reset-password`, { new_password: newPassword });
}

export function deleteUser(userId) {
  return api.delete(`/users/${userId}`);
}
