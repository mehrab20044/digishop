import { createAuthClient } from "./authClient";

const customer = createAuthClient({
  storageKey: "digishop.customer.session",
});

const BASE = "/api/v1/auth/";

export const hasSession = customer.hasSession;
export const customerFetch = customer.fetch;
export const requestOTP = customer.requestOTP;
export const verifyOTP = customer.verifyOTP;
export const getProfile = customer.getProfile;
export const logout = customer.logout;
export const logoutAll = customer.logoutAll;

export function updateProfile(data) {
  const multipart = data instanceof FormData;

  return customer.json(BASE + "me/", {
    method: "PATCH",
    headers: multipart
      ? undefined
      : { "Content-Type": "application/json" },
    body: multipart ? data : JSON.stringify(data),
  });
}

export function createAddress(data) {
  return customer.json(BASE + "addresses/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export function updateAddress(id, data) {
  return customer.json(BASE + `addresses/${id}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export function deleteAddress(id) {
  return customer.json(BASE + `addresses/${id}/`, {
    method: "DELETE",
  });
}