import { customerFetch } from "../customerAuth";

const BASE = "/api/v1/orders/";

function messages(value) {
  if (typeof value === "string") return [value];

  if (Array.isArray(value)) {
    return value.flatMap(messages);
  }

  if (value && typeof value === "object") {
    return Object.values(value).flatMap(messages);
  }

  return [];
}

async function request(path, { method = "GET", data, signal } = {}) {
  const headers = {
    Accept: "application/json",
  };

  if (data !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const response = await customerFetch(BASE + path, {
    method,
    headers,
    signal,
    body: data === undefined ? undefined : JSON.stringify(data),
  });

  const result = await response.json().catch(() => null);

  if (!response.ok) {
    const error = new Error(
      messages(result?.error?.details).join("، ") ||
        result?.error?.message ||
        messages(result?.detail).join("، ") ||
        `خطای ${response.status}`,
    );

    error.status = response.status;
    error.code = result?.error?.code || "request_failed";
    error.details = result?.error?.details;
    error.retryAfter =
      Number(response.headers.get("Retry-After")) || 0;

    throw error;
  }

  if (result === null) {
    throw new Error("پاسخ سرور معتبر نیست.");
  }

  return result;
}

function orderPath(orderId) {
  const value = String(orderId);

  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
      value,
    )
  ) {
    throw new Error("شناسهٔ سفارش معتبر نیست.");
  }

  return `${value}/`;
}

export function previewOrder(addressId, { signal } = {}) {
  return request("preview/", {
    method: "POST",
    data: {
      address_id: addressId,
    },
    signal,
  });
}

export function createOrder({
  addressId,
  requestId,
  expectedTotal,
  customerNote = "",
}) {
  return request("", {
    method: "POST",
    data: {
      address_id: addressId,
      request_id: requestId,
      expected_total: expectedTotal,
      customer_note: customerNote,
    },
  });
}

export function loadOrders({ page = 1, signal } = {}) {
  if (!Number.isSafeInteger(page) || page < 1) {
    throw new Error("شمارهٔ صفحه معتبر نیست.");
  }

  return request(`?page=${page}`, { signal });
}

export function loadOrder(orderId, { signal } = {}) {
  return request(orderPath(orderId), { signal });
}

export function cancelOrder(orderId) {
  return request(`${orderPath(orderId)}cancel/`, {
    method: "POST",
  });
}