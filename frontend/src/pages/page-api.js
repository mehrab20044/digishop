import { managementFetch } from "../managementAuth";
const BASE = "/api/v1/owner/pages/";
function messages(value) {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(messages);
  return value && typeof value === "object" ? Object.values(value).flatMap(messages) : [];
}
async function read(response) {
  const data = await response.json().catch(() => null);
  if (!response.ok || data === null) {
    const error = new Error(messages(data?.error?.details).join("، ") || data?.error?.message || messages(data).join("، ") || `خطای ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return data;
}
export async function pageRequest(path = "", options = {}) {
  let headers = { Accept: "application/json", ...options.headers };
  if (options.method && options.method !== "GET") {
    const csrf = await read(await managementFetch("/api/v1/owner/csrf/"));
    headers["X-CSRFToken"] = csrf.csrfToken;
  }
  return read(await managementFetch(BASE + path, { ...options, headers }));
}
export function writePage(path, data, method = "POST") {
  return pageRequest(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
}
