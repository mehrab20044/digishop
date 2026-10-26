import { createAuthClient } from "./authClient";

const customer = createAuthClient({
  storageKey: "digishop.customer.session",
});

export const hasSession = customer.hasSession;
export const requestOTP = customer.requestOTP;
export const verifyOTP = customer.verifyOTP;
export const getProfile = customer.getProfile;
export const logout = customer.logout;