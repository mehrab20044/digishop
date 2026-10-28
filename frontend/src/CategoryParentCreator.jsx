import { useRef, useState } from "react";

import { managementFetch } from "./managementAuth";

const SLUG_REGEX = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

function messages(value) {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(messages);

  if (value && typeof value === "object") {
    return Object.values(value).flatMap(messages);
  }

  return [];
}

async function read(response) {
  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      messages(data?.error?.details).join("، ") ||
        data?.error?.message ||
        messages(data).join("، ") ||
        `خطای ${response.status}`,
    );
  }

  if (!data) throw new Error("پاسخ سرور معتبر نیست.");

  return data;
}

export default function CategoryParentCreator({
  onCreated,
  onCancel,
}) {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const lock = useRef(false);

  async function submit(event) {
    event.preventDefault();

    if (lock.current) return;

    const cleanName = name.trim();
    const cleanSlug = slug.trim();

    if (!cleanName) {
      setError("نام والد را وارد کنید.");
      return;
    }

    if (!SLUG_REGEX.test(cleanSlug)) {
      setError(
        "نامک فقط باید حروف کوچک انگلیسی، عدد و خط تیره داشته باشد؛ "
        + "مثلاً mobile-phone.",
      );
      return;
    }

    lock.current = true;
    setBusy(true);
    setError("");

    try {
      const csrf = await read(
        await managementFetch("/api/v1/owner/csrf/"),
      );

      const created = await read(
        await managementFetch("/api/v1/owner/categories/create/", {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
            "X-CSRFToken": csrf.csrfToken,
          },
          body: JSON.stringify({
            name: cleanName,
            slug: cleanSlug,
            parent_id: null,
            description: "",
            sort_order: 0,
            related_category_ids: [],
          }),
        }),
      );

      onCreated(created);
    } catch (err) {
      setError(err.message);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  return (
    <section
      aria-labelledby="new-parent-heading"
      style={{
        margin: "20px 0",
        padding: 20,
        border: "1px solid #b9cafa",
        borderRadius: 12,
        background: "#f5f8ff",
      }}
    >
      <h3 id="new-parent-heading">ساخت دستهٔ والد جدید</h3>

      <p className="muted">
        اینجا یک دستهٔ مستقل می‌سازید که پس از ذخیره،
        به‌عنوان والدِ فرم اصلی انتخاب می‌شود.
      </p>

      <p className="muted">
        مثال: نام والد «موبایل»، نامک آن «mobile» و
        نام زیر‌دسته در فرم اصلی «گوشی هوشمند».
      </p>

      {error && (
        <div role="alert">
          <p>{error}</p>
          <p className="muted">
            اگر ارتباط قطع شده، پیش از ارسال دوباره،
            وجود والد را در فهرست دسته‌بندی‌ها بررسی کنید.
          </p>
        </div>
      )}

      <form onSubmit={submit}>
        <fieldset
          disabled={busy}
          className="form-grid"
          style={{ border: 0, padding: 0, margin: 0 }}
        >
          <label className="field">
            <span>نام والد جدید</span>
            <input
              value={name}
              maxLength={100}
              required
              placeholder="مثلاً موبایل"
              onChange={(event) => setName(event.target.value)}
            />
            <small className="muted">
              نامی که مشتری می‌بیند؛ می‌تواند فارسی باشد.
            </small>
          </label>

          <label className="field">
            <span>نامک انگلیسی والد</span>
            <input
              value={slug}
              dir="ltr"
              maxLength={120}
              required
              pattern="[a-z0-9]+(-[a-z0-9]+)*"
              title="فقط حروف کوچک انگلیسی، عدد و خط تیره"
              placeholder="mobile"
              autoCapitalize="none"
              spellCheck={false}
              onChange={(event) => setSlug(event.target.value)}
            />
            <small className="muted">
              فقط حروف کوچک انگلیسی، عدد و خط تیره.
              نامک فارسی، فاصله و زیرخط مجاز نیست.
              مثال: mobile-phone
            </small>
          </label>

          <p className="muted full-width">
            این دکمه فقط والد را ذخیره می‌کند. پس از ساخت والد،
            فرم دستهٔ اصلی را هم ذخیره کنید.
            بستن فرم اصلی، والد ساخته‌شده را حذف نمی‌کند.
          </p>

          <div className="form-actions">
            <button
              className="button primary"
              type="submit"
              disabled={busy}
            >
              {busy
                ? "در حال ساخت والد…"
                : "ساخت والد و انتخاب آن"}
            </button>

            <button
              className="button ghost"
              type="button"
              disabled={busy}
              onClick={onCancel}
            >
              انصراف از ساخت والد
            </button>
          </div>
        </fieldset>
      </form>
    </section>
  );
}