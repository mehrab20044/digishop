import { useEffect, useRef, useState } from "react";
import { managementFetch } from "../managementAuth";
import { useUnsaved } from "../catalog/shared";
import DashboardSelect from "../components/DashboardSelect";
import "./category-showcase.css";

const BASE = "/api/v1/owner/";
async function read(response) {
  const data = await response.json().catch(() => null);
  function text(value) {
    return typeof value === "string"
      ? value
      : Array.isArray(value)
        ? value.map(text).join("، ")
        : value && typeof value === "object"
          ? Object.values(value).map(text).join("، ")
          : "";
  }
  if (!response.ok)
    throw new Error(
      text(data?.error?.details) ||
        data?.error?.message ||
        text(data) ||
        "ذخیره انجام نشد.",
    );
  return data;
}
async function csrf() {
  return (await read(await managementFetch(BASE + "csrf/"))).csrfToken;
}
function pathName(row, rows) {
  const names = [],
    seen = new Set();
  while (row && !seen.has(row.id)) {
    seen.add(row.id);
    names.unshift(row.name);
    row = rows.find((c) => c.id === row.parent_id);
  }
  return names.join(" / ");
}
export function HomeCategoriesEditor({ rows, canChange, onEdit }) {
  const [ids, setIds] = useState(["", "", "", "", ""]);
  const [original, setOriginal] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const lock = useRef(false);
  useEffect(() => {
    const c = new AbortController();
    setOriginal(null);
    setError("");
    managementFetch(BASE + "category-showcase/", { signal: c.signal })
      .then(read)
      .then((data) => {
        if (!c.signal.aborted) {
          setOriginal(data.category_ids);
          setIds(
            Array.from({ length: 5 }, (_, i) =>
              String(data.category_ids[i] || ""),
            ),
          );
        }
      })
      .catch((err) => {
        if (!c.signal.aborted) setError(err.message);
      });
    return () => c.abort();
  }, [attempt]);
  useUnsaved(
    original !== null &&
      ids.some(Boolean) &&
      JSON.stringify(ids.map(Number)) !== JSON.stringify(original),
  );
  const selected = ids.map((id) => rows.find((row) => String(row.id) === id));
  const complete =
    selected.every((row) => row?.image_url) && new Set(ids).size === 5;
  async function save(event) {
    event.preventDefault();
    if (lock.current || !complete) return;
    lock.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const data = await read(
        await managementFetch(BASE + "category-showcase/", {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": await csrf(),
          },
          body: JSON.stringify({
            category_ids: ids.map(Number),
            expected_ids: original,
          }),
        }),
      );
      setOriginal(data.category_ids);
      setNotice("پنج دسته با همین ترتیب در صفحه اصلی نمایش داده می‌شوند.");
    } catch (err) {
      setError(err.message);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  function move(index, change) {
    setIds((previous) => {
      const next = [...previous];
      [next[index], next[index + change]] = [next[index + change], next[index]];
      return next;
    });
    setNotice("");
  }
  return (
    <details className="csh-home" open>
      <summary>
        پنج دستهٔ صفحهٔ اصلی <small>انتخاب و ترتیب نمایش</small>
      </summary>
      <p>
        جایگاه ۱ در سمت راست شروع می‌شود. هر دسته یا زیر‌دسته را می‌توانید
        انتخاب کنید؛ پنج انتخاب باید متفاوت و دارای عکس باشند.
      </p>
      {error && (
        <p role="alert" className="dc-error">
          {error}{" "}
          <button type="button" onClick={() => setAttempt((v) => v + 1)}>
            دریافت دوباره
          </button>
        </p>
      )}
      {notice && (
        <p role="status" className="dc-notice">
          {notice}
        </p>
      )}
      <form onSubmit={save}>
        <fieldset disabled={busy || original === null || !canChange}>
          <div className="csh-slots">
            {ids.map((id, index) => (
              <div className="csh-slot" key={index}>
                <span className="csh-position">
                  جایگاه {(index + 1).toLocaleString("fa-IR")}
                </span>
                {selected[index]?.image_url ? (
                  <img src={selected[index].image_url} alt="" />
                ) : (
                  <div className="csh-placeholder">عکس دسته</div>
                )}
                <DashboardSelect
                  tree
                  aria-label={`دسته جایگاه ${index + 1}`}
                  value={id}
                  onChange={(e) => {
                    setIds((old) =>
                      old.map((v, i) => (i === index ? e.target.value : v)),
                    );
                    setNotice("");
                  }}
                >
                  <option value="">انتخاب دسته</option>
                  {rows.map((row) => (
                    <option
                      key={row.id}
                      value={row.id}
                      data-path={pathName(row, rows)}
                      data-parent={row.parent_id ?? ""}
                      disabled={ids.some(
                        (v, i) => i !== index && v === String(row.id),
                      )}
                    >
                      {row.name}
                    </option>
                  ))}
                </DashboardSelect>
                {selected[index] && !selected[index].image_url && (
                  <button
                    type="button"
                    className="dc-link"
                    onClick={() => onEdit(selected[index])}
                  >
                    + بارگذاری عکس این دسته
                  </button>
                )}
                <div className="csh-move">
                  <button
                    type="button"
                    disabled={index === 0}
                    onClick={() => move(index, -1)}
                    aria-label={`جلو بردن جایگاه ${index + 1}`}
                  >
                    →
                  </button>
                  <button
                    type="button"
                    disabled={index === 4}
                    onClick={() => move(index, 1)}
                    aria-label={`عقب بردن جایگاه ${index + 1}`}
                  >
                    ←
                  </button>
                </div>
              </div>
            ))}
          </div>
          <div className="csh-actions">
            <button
              type="submit"
              className="button primary"
              disabled={!complete}
            >
              {busy ? "در حال ذخیره…" : "ذخیره پنج دسته"}
            </button>
            <a href="/categories" target="_blank" rel="noreferrer">
              دیدن صفحهٔ همهٔ دسته‌بندی‌ها ↗
            </a>
          </div>
        </fieldset>
      </form>
    </details>
  );
}
export function CategoryImageEditor({ category, onSaved }) {
  const [file, setFile] = useState(null),
    [preview, setPreview] = useState("");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const input = useRef(null),
    lock = useRef(false);
  useEffect(() => {
    if (!file) {
      setPreview("");
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  async function save(remove = false) {
    if (lock.current || (!remove && !file)) return;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      const body = new FormData();
      if (file) body.append("image", file);
      const saved = await read(
        await managementFetch(`${BASE}category-images/${category.id}/`, {
          method: remove ? "DELETE" : "PUT",
          headers: { "X-CSRFToken": await csrf() },
          ...(remove ? {} : { body }),
        }),
      );
      setFile(null);
      if (input.current) input.current.value = "";
      onSaved(saved);
    } catch (err) {
      setError(err.message);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return (
    <section className="csh-image" aria-label="عکس دسته‌بندی">
      <div>
        <h3>عکس «{category.name}»</h3>
        <p>
          یک عکس مربعی و واضح انتخاب کنید. JPG، PNG یا WebP تا ۵ مگابایت. تصویر
          برای نمایش بهینه می‌شود.
        </p>
      </div>
      <div className="csh-image-body">
        {preview || category.image_url ? (
          <img
            src={preview || category.image_url}
            alt={`پیش‌نمایش ${category.name}`}
          />
        ) : (
          <div className="csh-placeholder">هنوز عکسی ندارد</div>
        )}
        <div>
          <label className="dc-field">
            <span>انتخاب یا جایگزینی عکس</span>
            <input
              ref={input}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              disabled={busy}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f && f.size > 5 * 1024 * 1024) {
                  setError("حجم عکس بیش از ۵ مگابایت است.");
                  e.target.value = "";
                  return;
                }
                setError("");
                setFile(f || null);
              }}
            />
          </label>
          <div className="csh-actions">
            <button
              className="button primary"
              type="button"
              disabled={!file || busy}
              onClick={() => save()}
            >
              {busy ? "در حال ذخیره…" : "ذخیره عکس"}
            </button>
            {category.image_url && (
              <button
                type="button"
                className="button ghost"
                disabled={busy || category.is_home_featured}
                onClick={() => save(true)}
              >
                حذف عکس
              </button>
            )}
          </div>
          {category.is_home_featured && (
            <small>عکس دستهٔ صفحه اصلی را می‌توانید جایگزین کنید.</small>
          )}
        </div>
      </div>
      {error && (
        <p className="dc-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
