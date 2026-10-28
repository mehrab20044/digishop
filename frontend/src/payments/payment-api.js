import { customerFetch } from "../customerAuth";

const BASE = "/api/v1/payments/";

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

function validId(value) {
  const id = String(value);

  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
      id,
    )
  ) {
    throw new Error("شناسهٔ پرداخت یا سفارش معتبر نیست.");
  }

  return id;
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
    error.code = result?.error?.code || "payment_request_failed";
    error.details = result?.error?.details;

    throw error;
  }

  if (result === null) {
    throw new Error("پاسخ سرویس پرداخت معتبر نیست.");
  }

  return result;
}

export function startPayment({ orderId, requestId }) {
  return request("start/", {
    method: "POST",
    data: {
      order_id: validId(orderId),
      request_id: validId(requestId),
    },
  });
}

export function loadPayment(paymentId, { signal } = {}) {
  return request(`${validId(paymentId)}/`, { signal });
}

export function loadFakePayment(paymentId, { signal } = {}) {
  return request(`fake/${validId(paymentId)}/`, { signal });
}

export function decideFakePayment(paymentId, outcome) {
  if (!["success", "cancel"].includes(outcome)) {
    throw new Error("نتیجهٔ آزمایشی معتبر نیست.");
  }

  return request(`fake/${validId(paymentId)}/decision/`, {
    method: "POST",
    data: { outcome },
  });
}

export function verifyFakePayment(paymentId) {
  return request(`fake/${validId(paymentId)}/verify/`, {
    method: "POST",
  });
}

export function fakePaymentHref(paymentId) {
  return `/payments/fake/${validId(paymentId)}`;
}