import { useEffect, useState } from "react";
import { getProfile, hasSession } from "./customerAuth";
import { safeImage } from "./storefront/store-api";

function UserIcon() {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="8" r="4" />
      <path d="M4 22v-3a8 8 0 0 1 16 0v3" />
    </svg>
  );
}

function Avatar({ image }) {
  const [failed, setFailed] = useState(false);

  return (
    <span className="sf-customer-avatar">
      {image && !failed ? (
        <img src={image} alt="" onError={() => setFailed(true)} />
      ) : (
        <UserIcon />
      )}
    </span>
  );
}

export default function StoreCustomerLink() {
  const [state, setState] = useState(() => ({
    status: hasSession() ? "loading" : "guest",
    user: null,
  }));

  useEffect(() => {
    let active = true;

    function onExpired(event) {
      if (event.detail?.storageKey !== "digishop.customer.session") {
        return;
      }

      active = false;
      setState({ status: "guest", user: null });
    }

    function onProfile(event) {
      if (hasSession() && event.detail?.id)
        setState({ status: "ready", user: event.detail });
    }
    window.addEventListener("customer-profile-updated", onProfile);
    window.addEventListener("auth-expired", onExpired);

    if (hasSession()) {
      getProfile()
        .then((user) => {
          if (active) {
            setState({ status: "ready", user });
          }
        })
        .catch(() => {
          if (active) {
            setState({
              status: hasSession() ? "error" : "guest",
              user: null,
            });
          }
        });
    }

    return () => {
      active = false;
      window.removeEventListener("customer-profile-updated", onProfile);
      window.removeEventListener("auth-expired", onExpired);
    };
  }, []);

  if (state.status === "loading") {
    return (
      <span className="sf-customer-loading" role="status">
        در حال بررسی حساب…
      </span>
    );
  }

  if (state.status === "guest") {
    return (
      <a className="sf-account" href="/login">
        <UserIcon />
        <span>ورود / ثبت‌نام</span>
      </a>
    );
  }

  const name =
    [state.user?.first_name, state.user?.last_name]
      .map((part) => part?.trim())
      .filter(Boolean)
      .join(" ") || "کاربر دیجی‌شاپ";

  const image = safeImage(state.user?.image);

  return (
    <a
      className="sf-account sf-customer"
      href="/account"
      aria-label={state.user ? `حساب ${name}` : "بازکردن حساب من"}
    >
      <Avatar key={image || "default"} image={image} />

      <span className="sf-customer-name">{state.user ? name : "حساب من"}</span>
    </a>
  );
}
