import { createAuthClient } from "./authClient";

export const managementAuth = createAuthClient({
  storageKey: "digishop.management.session",
  prefix: "management/",
});

export const managementFetch = managementAuth.fetch;