import { useState } from "react";

export const EDITABLE = [
  "products",
  "categories",
  "brands",
  "attributes",
];

export const CREATABLE = [
  "categories",
  "brands",
  "attributes",
];

const commonFields = [
  { name: "name", label: "نام", required: true },
  { name: "slug", label: "نامک", required: true },
];

const productFields = [
  ...commonFields,
  {
    name: "price",
    label: "قیمت پایه — مطابق واحد مبلغ Backend",
    type: "number",
    min: 0,
    required: true,
  },
  {
    name: "stock",
    label: "موجودی پایه",
    type: "number",
    min: 0,
    required: true,
  },
  {
    name: "short_description",
    label: "توضیح کوتاه",
    maxLength: 500,
  },
  {
    name: "long_description",
    label: "توضیحات کامل",
    type: "textarea",
  },
  {
    name: "gallery_description",
    label: "توضیحات گالری",
    type: "textarea",
  },
];

async function readResponse(response) {
  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const error = new Error("ذخیره انجام نشد.");

    error.details = data ?? {
      detail: `خطای سرور: ${response.status}`,
    };

    throw error;
  }

  if (!data) {
    throw new Error("پاسخ سرور معتبر نیست.");
  }

  return data;
}

export default function Editor({
  resource,
  initial,
  onClose,
  onSaved,
}) {
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState(null);

  const product = resource.key === "products";
  const fields = product ? productFields : commonFields;

  // The current read API returns the Persian status label.
  const initialStatus =
    initial?.status === "draft" ||
    initial?.status === "پیش‌نویس"
      ? "draft"
      : "published";

  async function submit(event) {
    event.preventDefault();

    if (busy) return;

    const formData = new FormData(event.currentTarget);

    const payload = Object.fromEntries(
      fields.map((field) => [
        field.name,
        formData.get(field.name),
      ]),
    );

    if (product) {
      payload.status = formData.get("status");
      payload.is_active = formData.get("is_active") === "on";
    }

    setBusy(true);
    setErrors(null);

    try {
      const csrfResponse = await fetch(
        "/api/v1/owner/csrf/",
        {
          credentials: "same-origin",
          headers: { Accept: "application/json" },
          cache: "no-store",
        },
      );

      const csrf = await readResponse(csrfResponse);

      const path = initial
        ? `${resource.key}/${initial.id}/edit/`
        : `${resource.key}/create/`;

      const response = await fetch(
        `/api/v1/owner/${path}`,
        {
          method: initial ? "PATCH" : "POST",
          credentials: "same-origin",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
            "X-CSRFToken": csrf.csrfToken,
          },
          body: JSON.stringify(payload),
        },
      );

      await readResponse(response);
    } catch (error) {
      setErrors(
        error.details ?? { detail: error.message },
      );
      setBusy(false);
      return;
    }

    onSaved();
  }

  return (
    <section
      className="card editor"
      style={{ marginBottom: 22 }}
    >
      <div className="section-heading">
        <h2>
          {initial ? "ویرایش" : "افزودن"} — {resource.label}
        </h2>

        <button
          className="button ghost"
          type="button"
          disabled={busy}
          onClick={onClose}
        >
          بستن
        </button>
      </div>

      {errors && (
        <div
          role="alert"
          style={{
            padding: 15,
            marginBottom: 20,
            background: "#fff0f0",
            color: "#9c3030",
            borderRadius: 12,
          }}
        >
          <strong>ذخیره انجام نشد:</strong>

          <ul>
            {Object.entries(errors).map(([key, value]) => (
              <li key={key}>
                {fields.find((field) => field.name === key)
                  ?.label ?? key}
                :{" "}
                {Array.isArray(value)
                  ? value.join("، ")
                  : String(value)}
              </li>
            ))}
          </ul>
        </div>
      )}

      <form onSubmit={submit}>
        <fieldset
          disabled={busy}
          className="form-grid"
          style={{ border: 0, padding: 0, margin: 0 }}
        >
          {fields.map((field) => (
            <label className="field" key={field.name}>
              <span>{field.label}</span>

              {field.type === "textarea" ? (
                <textarea
                  name={field.name}
                  rows={4}
                  defaultValue={initial?.[field.name] ?? ""}
                />
              ) : (
                <input
                  name={field.name}
                  type={field.type ?? "text"}
                  min={field.min}
                  step={field.type === "number" ? "1" : undefined}
                  maxLength={field.maxLength}
                  required={field.required}
                  defaultValue={initial?.[field.name] ?? ""}
                />
              )}
            </label>
          ))}

          {product && (
            <>
              <label className="field">
                <span>وضعیت انتشار</span>
                <select name="status" defaultValue={initialStatus}>
                  <option value="draft">پیش‌نویس</option>
                  <option value="published">منتشرشده</option>
                </select>
              </label>

              <label className="checkbox">
                <input
                  name="is_active"
                  type="checkbox"
                  defaultChecked={initial?.is_active ?? false}
                />
                فعال و قابل انتشار
              </label>

              <p className="muted full-width">
                قیمت و موجودی این فرم مربوط به محصول پایه‌اند؛
                تنوع‌ها و گالری با این فرم تغییر نمی‌کنند.
              </p>
            </>
          )}

          <div className="form-actions">
            <button
              className="button primary"
              type="submit"
              disabled={busy}
            >
              {busy ? "در حال ذخیره…" : "ذخیره در دیتابیس"}
            </button>
          </div>
        </fieldset>
      </form>
    </section>
  );
}