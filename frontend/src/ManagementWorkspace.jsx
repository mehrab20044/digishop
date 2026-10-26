import { useEffect, useRef, useState } from "react";

import App from "./App";
import { managementAuth } from "./managementAuth";

function goToLogin() {
  const next =
    window.location.pathname + window.location.search;

  window.location.replace(
    `/management/login?next=${encodeURIComponent(next)}`,
  );
}

export default function ManagementWorkspace() {
  const [state, setState] = useState({
    ready: false,
    error: "",
  });
  const [logoutError, setLogoutError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const pendingLogout = useRef(false);

  useEffect(() => {
    const controller = new AbortController();

    function onExpired(event) {
      if (
        event.detail?.storageKey ===
        managementAuth.storageKey
      ) {
        goToLogin();
      }
    }

    window.addEventListener("auth-expired", onExpired);

    if (!managementAuth.hasSession()) {
      goToLogin();

      return () => {
        window.removeEventListener(
          "auth-expired",
          onExpired,
        );
      };
    }

    managementAuth
      .json("/api/v1/owner/", {
        signal: controller.signal,
      })
      .then(() => {
        if (!controller.signal.aborted) {
          setState({ ready: true, error: "" });
        }
      })
      .catch((error) => {
        if (controller.signal.aborted) return;

        if (error.status === 401) {
          goToLogin();
          return;
        }

        setState({
          ready: false,
          error: error.message,
        });
      });

    return () => {
      controller.abort();
      window.removeEventListener(
        "auth-expired",
        onExpired,
      );
    };
  }, [attempt]);

  async function signOut() {
    if (pendingLogout.current) return;

    pendingLogout.current = true;
    setLogoutError("");

    try {
      await managementAuth.logout();
      window.location.replace("/management/login");
    } catch (error) {
      setLogoutError(error.message);
    } finally {
      pendingLogout.current = false;
    }
  }

  if (!state.ready) {
    return (
      <main className="owner-auth-status" dir="rtl">
        <section className="card">
          <h1>پنل مدیریت</h1>

          {state.error ? (
            <>
              <p role="alert">{state.error}</p>

              <div className="owner-auth-actions">
                <button
                  className="button primary"
                  onClick={() => {
                    setState({ ready: false, error: "" });
                    setAttempt((value) => value + 1);
                  }}
                >
                  تلاش مجدد
                </button>

                <button
                  className="button ghost"
                  onClick={signOut}
                >
                  خروج از حساب مدیریت
                </button>
              </div>
            </>
          ) : (
            <p role="status">در حال بررسی دسترسی…</p>
          )}

          {logoutError && (
            <p role="alert">{logoutError}</p>
          )}
        </section>
      </main>
    );
  }

  return (
    <>
      {logoutError && (
        <p className="owner-auth-error" role="alert">
          {logoutError}
        </p>
      )}

      <App onLogout={signOut} />
    </>
  );
}