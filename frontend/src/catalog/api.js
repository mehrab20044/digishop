import { managementFetch } from "../managementAuth";
export const ROOT = "/api/v1/owner/";
function messages(value) {
  if (typeof value === "string") return [value];
  return value && typeof value === "object"
    ? Object.values(value).flatMap(messages)
    : [];
}
export async function api(path, data, method = "POST", signal) {
  const response = await managementFetch(ROOT + path, {
    signal,
    cache: "no-store",
    ...(data === undefined
      ? {}
      : {
          method,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        }),
  });
  const result = await response.json().catch(() => null);
  if (!response.ok || !result) {
    const error = new Error(
      messages(result?.error?.details || result?.error?.message || result).join(
        "، ",
      ) || "ارتباط کامل نشد؛ پیش از تکرار، نتیجهٔ ذخیره را بررسی کنید.",
    );
    error.status = response.status;
    throw error;
  }
  return result;
}
export function pathLabel(id, rows) {
  const names = [],
    seen = new Set();
  let row = rows.find((r) => r.id === Number(id));
  while (row && !seen.has(row.id)) {
    seen.add(row.id);
    names.unshift(row.name);
    row = rows.find((r) => r.id === row.parent_id);
  }
  return names.join(" / ");
}
export const digits = (value) =>
  String(value)
    .replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d))
    .replace(/[٠-٩]/g, (d) => "٠١٢٣٤٥٦٧٨٩".indexOf(d));
export const splitValues = (text) =>
  text
    .split(/[,،\n]/)
    .map((s) => s.trim())
    .filter(Boolean);

export const combinationKey = (options) =>
  JSON.stringify(
    Object.entries(options).sort(([a], [b]) => a.localeCompare(b)),
  );
