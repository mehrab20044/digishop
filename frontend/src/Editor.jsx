import DashboardSelect from "./components/DashboardSelect";
import RichTextEditor from "./richtext/RichTextEditor";
import { useEffect, useRef, useState } from "react";

import { managementFetch } from "./managementAuth";

export const EDITABLE = ["products", "categories", "brands", "attributes"];

export const CREATABLE = ["categories", "brands", "attributes"];

const SLUG_REGEX = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

const commonFields = [
  { name: "name", label: "نام", required: true },
  { name: "slug", label: "نامک", required: true },
];

const productFields = [
  ...commonFields,
  {
    name: "price",
    label: "قیمت پایه",
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
    name: "long_description_html",
    label: "توضیحات کامل",
    type: "richtext",
  },
  {
    name: "gallery_description_html",
    label: "توضیحات گالری",
    type: "richtext",
  },
];

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

async function save(path, payload, method = "POST") {
  const csrf = await read(await managementFetch("/api/v1/owner/csrf/"));

  return read(
    await managementFetch(`/api/v1/owner/${path}`, {
      method,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-CSRFToken": csrf.csrfToken,
      },
      body: JSON.stringify(payload),
    }),
  );
}

async function loadCategories(signal) {
  const rows = [];

  for (let page = 1; ; page += 1) {
    const data = await read(
      await managementFetch(`/api/v1/owner/categories/?page=${page}`, {
        signal,
      }),
    );

    if (!Array.isArray(data.results)) {
      throw new Error("فهرست دسته‌بندی‌ها معتبر نیست.");
    }

    rows.push(...data.results);

    if (!data.next) return rows;
  }
}

function pathLabel(item, byId) {
  const parts = [];
  const seen = new Set();
  let current = item;

  while (current && !seen.has(current.id)) {
    seen.add(current.id);
    parts.unshift(current.name);
    current = byId.get(current.parent_id);
  }

  return parts.join(" / ");
}

function invalidParents(items, id) {
  const blocked = new Set(id ? [id] : []);
  let changed = true;

  while (changed) {
    changed = false;

    for (const item of items) {
      if (blocked.has(item.parent_id) && !blocked.has(item.id)) {
        blocked.add(item.id);
        changed = true;
      }
    }
  }

  return blocked;
}

function CategoryEditor({ initial, onClose, onSaved }) {
  const id = initial?.id;

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [parentId, setParentId] = useState("");
  const [description, setDescription] = useState("");
  const [sortOrder, setSortOrder] = useState(0);
  const [relatedIds, setRelatedIds] = useState([]);
  const [categories, setCategories] = useState([]);

  const [showNewParent, setShowNewParent] = useState(false);
  const [parentName, setParentName] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);

  const lock = useRef(false);
  const generatedSlug = useRef("");
  const generatedParentSlug = useRef("");

  useEffect(() => {
    let active = true;
    const controller = new AbortController();

    setLoading(true);
    setError("");

    async function load() {
      try {
        const [items, record] = await Promise.all([
          loadCategories(controller.signal),
          id
            ? managementFetch(`/api/v1/owner/categories/${id}/`, {
                signal: controller.signal,
              }).then(read)
            : Promise.resolve(null),
        ]);

        if (!active) return;

        setCategories(items);
        setName(record?.name || "");
        setSlug(record?.slug || "");
        setParentId(record?.parent_id == null ? "" : String(record.parent_id));
        setDescription(record?.description || "");
        setSortOrder(record?.sort_order ?? 0);
        setRelatedIds(record?.related_category_ids || []);
        setNotice("");
        setShowNewParent(false);
      } catch (err) {
        if (active && err.name !== "AbortError") {
          setError(err.message);
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    load();

    return () => {
      active = false;
      controller.abort();
    };
  }, [id, loadAttempt]);

  const byId = new Map(categories.map((item) => [item.id, item]));
  const blocked = invalidParents(categories, id);

  const options = categories
    .map((item) => ({
      ...item,
      label: pathLabel(item, byId),
    }))
    .sort((a, b) => a.label.localeCompare(b.label, "fa"));

  async function createParent() {
    if (lock.current) return;

    if (!parentName.trim()) {
      setError("نام دستهٔ بالاتر را بنویس.");
      return;
    }

    lock.current = true;
    setBusy(true);
    setError("");

    try {
      if (!generatedParentSlug.current) {
        generatedParentSlug.current = `category-${crypto.randomUUID()}`;
      }

      const created = await save("categories/create/", {
        name: parentName.trim(),
        slug: generatedParentSlug.current,
        parent_id: null,
      });

      setCategories((items) => [...items, created]);
      setParentId(String(created.id));
      setShowNewParent(false);
      setParentName("");
      generatedParentSlug.current = "";

      setNotice(
        `«${created.name}» ساخته و انتخاب شد. حالا دستهٔ اصلی را ذخیره کن.`,
      );
    } catch (err) {
      setError(
        `${err.message} اگر ارتباط قطع شده، قبل از تلاش مجدد وجود دسته را بررسی کن.`,
      );
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  async function submit(event) {
    event.preventDefault();

    if (lock.current) return;

    if (!name.trim()) {
      setError("نام دسته را بنویس.");
      return;
    }

    const manualSlug = slug.trim();

    if (manualSlug && !SLUG_REGEX.test(manualSlug)) {
      setError("نامک فقط حروف کوچک انگلیسی، عدد و خط تیره می‌پذیرد.");
      return;
    }

    const order = Number(sortOrder);

    if (!Number.isSafeInteger(order) || order < 0) {
      setError("ترتیب نمایش باید عدد صحیح صفر یا بیشتر باشد.");
      return;
    }

    lock.current = true;
    setBusy(true);
    setError("");

    try {
      if (!manualSlug && !generatedSlug.current) {
        generatedSlug.current = `category-${crypto.randomUUID()}`;
      }

      await save(
        id ? `categories/${id}/edit/` : "categories/create/",
        {
          name: name.trim(),
          slug: manualSlug || generatedSlug.current,
          parent_id: parentId ? Number(parentId) : null,
          description,
          sort_order: order,
          related_category_ids: relatedIds,
        },
        id ? "PATCH" : "POST",
      );
    } catch (err) {
      setError(err.message);
      lock.current = false;
      setBusy(false);
      return;
    }

    onSaved();
  }

  return (
    <section className="card editor" style={{ marginBottom: 22 }}>
      <div className="section-heading">
        <h2>{id ? "ویرایش دسته‌بندی" : "دسته‌بندی جدید"}</h2>
        <button
          className="button ghost"
          type="button"
          disabled={busy}
          onClick={onClose}
        >
          بستن
        </button>
      </div>

      {loading && <p role="status">در حال دریافت دسته‌ها…</p>}

      {error && (
        <p
          role="alert"
          style={{
            padding: 12,
            borderRadius: 10,
            background: "#fff0f0",
            color: "#9c3030",
          }}
        >
          {error}
        </p>
      )}

      {notice && (
        <p role="status" style={{ color: "#26734f", padding: 12 }}>
          {notice}
        </p>
      )}

      {!loading && categories.length === 0 && error && (
        <button
          className="button ghost"
          type="button"
          onClick={() => setLoadAttempt((value) => value + 1)}
        >
          دریافت دوبارهٔ دسته‌ها
        </button>
      )}

      {!loading && (
        <form onSubmit={submit}>
          <fieldset
            disabled={busy}
            style={{ border: 0, padding: 0, margin: 0 }}
          >
            <label className="field">
              <span>نام دسته</span>
              <input
                value={name}
                maxLength={100}
                required
                placeholder="مثلاً گوشی هوشمند"
                onChange={(event) => setName(event.target.value)}
              />
            </label>

            <label className="field">
              <span>دستهٔ بالاتر</span>
              <DashboardSelect
                value={parentId}
                onChange={(event) => setParentId(event.target.value)}
              >
                <option value="">ندارد — دستهٔ مستقل</option>
                {options
                  .filter((item) => !blocked.has(item.id))
                  .map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
              </DashboardSelect>
              <small className="muted">
                مثال: برای «گوشی هوشمند»، دستهٔ بالاتر «موبایل» است.
              </small>
            </label>

            {!showNewParent ? (
              <button
                className="button ghost"
                type="button"
                onClick={() => setShowNewParent(true)}
              >
                + دستهٔ بالاتر را پیدا نکردم؛ بساز
              </button>
            ) : (
              <div
                style={{
                  margin: "12px 0",
                  padding: 16,
                  background: "#f5f8ff",
                  border: "1px solid #dce5fa",
                  borderRadius: 12,
                }}
              >
                <label className="field">
                  <span>نام دستهٔ بالاتر جدید</span>
                  <input
                    value={parentName}
                    maxLength={100}
                    placeholder="مثلاً موبایل"
                    onChange={(event) => setParentName(event.target.value)}
                  />
                </label>

                <div className="form-actions">
                  <button
                    className="button primary"
                    type="button"
                    onClick={createParent}
                  >
                    ساخت و انتخاب
                  </button>
                  <button
                    className="button ghost"
                    type="button"
                    onClick={() => setShowNewParent(false)}
                  >
                    انصراف
                  </button>
                </div>

                <small className="muted">
                  دستهٔ بالاتر جداگانه ذخیره می‌شود؛ سپس دستهٔ اصلی را با دکمهٔ
                  پایین ذخیره کن.
                </small>
              </div>
            )}

            <details style={{ margin: "20px 0" }}>
              <summary style={{ cursor: "pointer" }}>
                تنظیمات بیشتر، اختیاری
              </summary>

              <div style={{ paddingTop: 16 }}>
                <label className="field">
                  <span>نامک انگلیسی</span>
                  <input
                    value={slug}
                    dir="ltr"
                    maxLength={120}
                    pattern="[a-z0-9]+(-[a-z0-9]+)*"
                    title="فقط حروف کوچک انگلیسی، عدد و خط تیره"
                    placeholder="مثلاً samsung"
                    autoCapitalize="none"
                    spellCheck={false}
                    onChange={(event) => setSlug(event.target.value)}
                  />
                  <small className="muted">
                    اگر خالی بگذاری، یک نامک انگلیسی یکتا ساخته می‌شود. برای
                    آدرس خوانا خودت وارد کن.
                  </small>
                </label>

                <label className="field">
                  <span>توضیح</span>
                  <textarea
                    rows={3}
                    value={description}
                    onChange={(event) => setDescription(event.target.value)}
                  />
                </label>

                <label className="field">
                  <span>ترتیب نمایش</span>
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={sortOrder}
                    onChange={(event) => setSortOrder(event.target.value)}
                  />
                </label>

                <p>دسته‌های مرتبط</p>
                <small className="muted">
                  ارتباط پیشنهادی است؛ دستهٔ بالاتر محسوب نمی‌شود.
                </small>

                <div style={{ maxHeight: 220, overflowY: "auto" }}>
                  {options
                    .filter((item) => item.id !== id)
                    .map((item) => (
                      <label
                        className="checkbox"
                        key={item.id}
                        style={{ display: "flex", margin: "10px 0" }}
                      >
                        <input
                          type="checkbox"
                          checked={relatedIds.includes(item.id)}
                          onChange={(event) => {
                            const checked = event.target.checked;

                            setRelatedIds((previous) =>
                              checked
                                ? [...new Set([...previous, item.id])]
                                : previous.filter((value) => value !== item.id),
                            );
                          }}
                        />
                        {item.label}
                      </label>
                    ))}
                </div>
              </div>
            </details>

            <div className="form-actions">
              <button className="button primary" type="submit" disabled={busy}>
                {busy ? "در حال ذخیره…" : "ذخیرهٔ دسته‌بندی"}
              </button>
            </div>
          </fieldset>
        </form>
      )}
    </section>
  );
}

function RecordEditor({ resource, initial, onClose, onSaved }) {
  const product = resource.key === "products";
  const fields = product ? productFields : commonFields;

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const lock = useRef(false);

  const initialStatus =
    initial?.status === "draft" || initial?.status === "پیش‌نویس"
      ? "draft"
      : "published";

  async function submit(event) {
    event.preventDefault();

    if (lock.current) return;

    const formData = new FormData(event.currentTarget);
    const payload = Object.fromEntries(
      fields.map((field) => [field.name, formData.get(field.name)]),
    );

    if (product) {
      payload.status = formData.get("status");
      payload.is_active = formData.get("is_active") === "on";
    }

    lock.current = true;
    setBusy(true);
    setError("");

    try {
      await save(
        initial
          ? `${resource.key}/${initial.id}/edit/`
          : `${resource.key}/create/`,
        payload,
        initial ? "PATCH" : "POST",
      );
    } catch (err) {
      setError(err.message);
      lock.current = false;
      setBusy(false);
      return;
    }

    onSaved();
  }

  return (
    <section className="card editor" style={{ marginBottom: 22 }}>
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

      {error && <p role="alert">{error}</p>}

      <form onSubmit={submit}>
        <fieldset
          disabled={busy}
          className="form-grid"
          style={{ border: 0, padding: 0, margin: 0 }}
        >
          {fields.map((field) =>
            field.type === "richtext" ? (
              <div className="field full-width" key={field.name}>
                <span>{field.label}</span>
                <RichTextEditor
                  name={field.name}
                  label={field.label}
                  html={initial?.[field.name] || ""}
                  plainText={initial?.[field.name.replace("_html", "")] || ""}
                  disabled={busy}
                />
              </div>
            ) : (
              <label className="field" key={field.name}>
                <span>{field.label}</span>
                {field.type === "textarea" ? (
                  <textarea
                    name={field.name}
                    rows={4}
                    maxLength={field.maxLength}
                    defaultValue={initial?.[field.name] ?? ""}
                  />
                ) : (
                  <input
                    name={field.name}
                    type={field.type || "text"}
                    min={field.min}
                    step={field.type === "number" ? "1" : undefined}
                    maxLength={field.maxLength}
                    required={field.required}
                    defaultValue={initial?.[field.name] ?? ""}
                  />
                )}
              </label>
            ),
          )}

          {product && (
            <>
              <label className="field">
                <span>وضعیت انتشار</span>
                <DashboardSelect name="status" defaultValue={initialStatus}>
                  <option value="draft">پیش‌نویس</option>
                  <option value="published">منتشرشده</option>
                </DashboardSelect>
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
                این قیمت و موجودی مربوط به محصول پایه‌اند؛ تنوع‌ها و گالری با
                این فرم تغییر نمی‌کنند.
              </p>
            </>
          )}

          <div className="form-actions">
            <button className="button primary" type="submit" disabled={busy}>
              {busy ? "در حال ذخیره…" : "ذخیره"}
            </button>
          </div>
        </fieldset>
      </form>
    </section>
  );
}

export default function Editor(props) {
  const key = `${props.resource.key}:${props.initial?.id || "new"}`;

  return props.resource.key === "categories" ? (
    <CategoryEditor key={key} {...props} />
  ) : (
    <RecordEditor key={key} {...props} />
  );
}
