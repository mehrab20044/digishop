import DashboardSelect from "./components/DashboardSelect";
import { managementFetch } from "./managementAuth";
import { useState } from "react";

function initialMode(product) {
  if (product.status === "draft" || product.status === "پیش‌نویس") {
    return "draft";
  }

  return product.is_active ? "published" : "inactive";
}

function messageFrom(data) {
  if (data?.error?.message) {
    return data.error.message;
  }

  if (typeof data?.detail === "string") {
    return data.detail;
  }

  return data ? JSON.stringify(data) : "پاسخ سرور معتبر نیست.";
}

export default function ProductPublication({ product, onSaved }) {
  const [mode, setMode] = useState(() => initialMode(product));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function save(event) {
    event.preventDefault();
    if (busy) return;

    setBusy(true);
    setError("");

    const payload = {
      status: mode === "draft" ? "draft" : "published",
      is_active: mode === "published",
    };

    try {
      const csrfResponse = await managementFetch("/api/v1/owner/csrf/", {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
        cache: "no-store",
      });

      const csrf = await csrfResponse.json().catch(() => null);

      if (!csrfResponse.ok || !csrf?.csrfToken) {
        throw new Error(messageFrom(csrf));
      }

      const response = await managementFetch(
        `/api/v1/owner/products/${product.id}/edit/`,
        {
          method: "PATCH",
          credentials: "same-origin",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
            "X-CSRFToken": csrf.csrfToken,
          },
          body: JSON.stringify(payload),
        },
      );

      const data = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(messageFrom(data));
      }
    } catch (err) {
      setError(err.message);
      setBusy(false);
      return;
    }

    setBusy(false);
    onSaved();
  }

  return (
    <section
      style={{
        marginTop: 24,
        padding: 20,
        background: "#f4f7ff",
        border: "1px solid #dce6fa",
        borderRadius: 16,
      }}
    >
      <div className="section-heading">
        <h2>مدیریت انتشار</h2>
        <span className="counter">
          {initialMode(product) === "published"
            ? "منتشرشده و فعال"
            : initialMode(product) === "draft"
              ? "پیش‌نویس"
              : "غیرفعال"}
        </span>
      </div>

      <form onSubmit={save}>
        <label className="field">
          <span>وضعیت جدید محصول</span>

          <DashboardSelect
            value={mode}
            disabled={busy}
            onChange={(event) => setMode(event.target.value)}
          >
            <option value="draft">پیش‌نویس</option>
            <option value="published">منتشرشده و فعال</option>
            <option value="inactive">غیرفعال</option>
          </DashboardSelect>
        </label>

        <p className="muted" style={{ margin: "14px 0" }}>
          انتشار نیازمند تصویر اصلی و قیمت معتبر مطابق قوانین Backend است.
          غیرفعال‌کردن، محصول را حذف نمی‌کند.
        </p>

        {error && (
          <p
            role="alert"
            style={{
              color: "#a33030",
              overflowWrap: "anywhere",
            }}
          >
            {error}
          </p>
        )}

        <button
          className="button primary"
          type="submit"
          disabled={busy || mode === initialMode(product)}
        >
          {busy ? "در حال ذخیره…" : "ذخیرهٔ وضعیت انتشار"}
        </button>
      </form>
    </section>
  );
}
