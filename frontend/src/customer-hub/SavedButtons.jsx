import { useEffect, useRef, useState } from "react";
import { hasSession } from "../customerAuth";
import { customerRequest } from "./api";
import HubIcon from "./Icons";
import "./customer-hub.css";

export default function SavedButtons({ productId }) {
  const [state, setState] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const lock = useRef(false);
  useEffect(() => {
    if (!hasSession()) return;
    const controller = new AbortController();
    setState(null);
    setError("");
    customerRequest(`saved/${productId}/`, undefined, "GET", controller.signal)
      .then(setState)
      .catch((error) => {
        if (!controller.signal.aborted) setError(error.message);
      });
    return () => controller.abort();
  }, [productId, attempt]);
  async function toggle(kind) {
    if (!hasSession()) {
      window.location.assign(
        `/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`,
      );
      return;
    }
    if (lock.current || state === null) return;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      const next = !state[kind];
      await customerRequest(
        "saved/",
        { product_id: productId, kind, enabled: next },
        "POST",
      );
      setState((previous) => ({ ...previous, [kind]: next }));
    } catch (error) {
      setError(error.message);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return (
    <div className="ch-save-actions">
      {[
        ["favorite", "heart", "علاقه‌مندی"],
        ["later", "later", "خرید بعدی"],
      ].map(([kind, icon, label]) => (
        <button
          type="button"
          key={kind}
          aria-pressed={Boolean(state?.[kind])}
          disabled={busy || (hasSession() && state === null)}
          onClick={() => toggle(kind)}
        >
          <HubIcon name={icon} size={17} />
          {state?.[kind] ? "ذخیره‌شده در " : "ذخیره در "}
          {label}
        </button>
      ))}
      {error && (
        <p role="alert">
          {error}{" "}
          <button type="button" onClick={() => setAttempt((v) => v + 1)}>
            تلاش دوباره
          </button>
        </p>
      )}
    </div>
  );
}
