import { customerFetch } from "../customerAuth";

function messages(value) {
  if (typeof value === "string") return value;
  if (value && typeof value === "object")
    return Object.values(value).map(messages).filter(Boolean).join("، ");
  return "";
}
export async function customerRequest(path, data, method = "GET", signal) {
  const response = await customerFetch(`/api/v1/customer/${path}`, {
    method,
    signal,
    headers: {
      Accept: "application/json",
      ...(data === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  const result = await response.json().catch(() => null);
  if (!response.ok || result === null) {
    const error = new Error(
      messages(
        result?.error?.details || result?.error?.message || result?.detail,
      ) || "دریافت اطلاعات انجام نشد.",
    );
    error.status = response.status;
    throw error;
  }
  return result;
}
