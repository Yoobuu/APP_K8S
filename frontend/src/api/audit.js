import api from "./axios";

export function listAudit({ limit = 25, offset = 0, action } = {}) {
  const params = { limit, offset };
  if (action) {
    params.action = action;
  }
  return api.get("/audit/", { params });
}
