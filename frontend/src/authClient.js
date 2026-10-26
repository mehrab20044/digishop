const BASE = "/api/v1/auth/";

function messages(value) {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(messages);

  if (value && typeof value === "object") {
    return Object.values(value).flatMap(messages);
  }

  return [];
}

async function wire(url, options) {
  try {
    return await fetch(url, options);
  } catch (cause) {
    if (cause.name === "AbortError") throw cause;

    const error = new Error(
      "ارتباط با سرور برقرار نشد. دوباره تلاش کنید.",
    );

    error.code = "network_error";
    error.status = 0;
    throw error;
  }
}

function apiError(data, response) {
  const error = new Error(
    messages(data?.error?.details).join("، ") ||
      data?.error?.message ||
      data?.detail ||
      `خطای ${response.status}`,
  );

  error.status = response.status;
  error.code = data?.error?.code || "request_failed";
  error.details = data?.error?.details;
  error.retryAfter =
    Number(response.headers.get("Retry-After")) || 0;

  return error;
}

export function createAuthClient({
  storageKey,
  prefix = "",
}) {
  let session = null;
  let revision = 0;
  let epoch = 0;
  let refreshing = null;

  try {
    const stored = JSON.parse(
      sessionStorage.getItem(storageKey),
    );

    if (
      typeof stored?.access === "string" &&
      typeof stored?.refresh === "string"
    ) {
      session = stored;
    }
  } catch {
    // Storage is optional.
  }

  function save(value, rotation = false) {
    session = value;
    revision += 1;

    if (!rotation) epoch += 1;

    try {
      if (value) {
        sessionStorage.setItem(
          storageKey,
          JSON.stringify(value),
        );
      } else {
        sessionStorage.removeItem(storageKey);
      }
    } catch {
      // Authentication still works in memory.
    }
  }

  function expired() {
    save(null);

    if (typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent("auth-expired", {
          detail: { storageKey },
        }),
      );
    }
  }

  async function read(response) {
    if (response.status === 204) return null;

    const data = await response.json().catch(() => null);

    if (!response.ok) {
      throw apiError(data, response);
    }

    if (data === null) {
      throw new Error("پاسخ سرور معتبر نیست.");
    }

    return data;
  }

  async function publicRequest(path, body) {
    return read(
      await wire(BASE + path, {
        method: "POST",
        credentials: "omit",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      }),
    );
  }

  async function renew() {
    if (refreshing) return refreshing;

    if (!session) {
      const error = new Error("ابتدا وارد حساب شوید.");
      error.status = 401;
      throw error;
    }

    const version = revision;
    const current = session;

    const pending = (async () => {
      try {
        const data = await publicRequest(
          prefix + "token/refresh/",
          { refresh: current.refresh },
        );

        if (revision !== version) {
          const error = new Error("نشست تغییر کرده است.");
          error.status = 401;
          throw error;
        }

        if (
          typeof data?.access !== "string" ||
          typeof data?.refresh !== "string"
        ) {
          throw new Error("پاسخ تمدید نشست معتبر نیست.");
        }

        save(
          {
            access: data.access,
            refresh: data.refresh,
          },
          true,
        );
      } catch (error) {
        if (
          revision === version &&
          [400, 401].includes(error.status)
        ) {
          expired();
        }

        throw error;
      }
    })();

    refreshing = pending;

    try {
      return await pending;
    } finally {
      if (refreshing === pending) refreshing = null;
    }
  }

  async function authorizedFetch(input, options = {}) {
    const url = new URL(input, window.location.origin);

    if (
      url.origin !== window.location.origin ||
      !url.pathname.startsWith("/api/v1/")
    ) {
      throw new Error("آدرس API مجاز نیست.");
    }

    if (!session) {
      expired();

      const error = new Error("ابتدا وارد حساب شوید.");
      error.status = 401;
      throw error;
    }

    const failedAccess = session.access;
    const requestEpoch = epoch;

    const run = () => {
      if (!session || epoch !== requestEpoch) {
        const error = new Error("نشست پایان یافته است.");
        error.status = 401;
        throw error;
      }

      const headers = new Headers(options.headers);
      headers.set(
        "Authorization",
        `Bearer ${session.access}`,
      );
      headers.set("Accept", "application/json");

      return wire(url.href, {
        ...options,
        body:
          typeof options.body === "function"
            ? options.body()
            : options.body,
        headers,
        credentials: "omit",
        cache: "no-store",
      });
    };

    let response = await run();

    if (response.status !== 401) return response;

    if (epoch !== requestEpoch) {
      const error = new Error("نشست درخواست تغییر کرده است.");
      error.status = 401;
      throw error;
    }

    if (!session) return response;

    if (session.access === failedAccess) {
      await renew();
    }

    response = await run();

    if (response.status === 401) expired();

    return response;
  }

  async function json(input, options = {}) {
    return read(await authorizedFetch(input, options));
  }

  return {
    storageKey,

    hasSession: () => Boolean(session),

    fetch: authorizedFetch,

    json,

    requestOTP: (phone) =>
      publicRequest(prefix + "otp/request/", { phone }),

    async verifyOTP(phone, code) {
      const version = revision;

      const data = await publicRequest(
        prefix + "otp/verify/",
        { phone, code },
      );

      if (revision !== version) {
        throw new Error("درخواست ورود تغییر کرده است.");
      }

      if (
        typeof data?.access !== "string" ||
        typeof data?.refresh !== "string"
      ) {
        throw new Error("پاسخ ورود معتبر نیست.");
      }

      save({
        access: data.access,
        refresh: data.refresh,
      });

      return data.user;
    },

    getProfile: () => json(BASE + "me/"),

    async logout() {
      if (!session) return;

      const logoutEpoch = epoch;

      try {
        await json(BASE + "logout/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: () =>
            JSON.stringify({
              refresh: session.refresh,
            }),
        });
      } catch (error) {
        if (session) throw error;
      }

      if (epoch === logoutEpoch) save(null);
    },
  };
}