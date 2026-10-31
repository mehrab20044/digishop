import DashboardSelect from "../components/DashboardSelect";
import { useEffect, useState } from "react";
import { api, splitValues } from "./api";
import { useUnsaved } from "./shared";
import "./workspace.css";
const types = {
  text: "متن آزاد",
  number: "عدد",
  boolean: "بله / خیر",
  choice: "انتخاب از فهرست",
};
export function DefinitionForm({ record, onSaved, onCancel, canSave = true }) {
  const [name, setName] = useState(record?.name || ""),
    [type, setType] = useState(record?.value_type || "text"),
    [unit, setUnit] = useState(record?.unit || ""),
    [values, setValues] = useState((record?.choices || []).join("، ")),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [dirty, setDirty] = useState(false);
  useUnsaved(dirty);
  return (
    <div className="cw-panel">
      <h3>{record ? "ویرایش ویژگی" : "ویژگی جدید"}</h3>
      <p>
        ویژگی‌هایی مانند جنس، وزن و کشور سازنده را یک بار تعریف کنید؛ در دسته‌ها
        قابل استفاده‌اند.
      </p>
      {error && (
        <p className="cw-error" role="alert">
          {error}
        </p>
      )}
      <fieldset
        disabled={busy || !canSave}
        style={{ border: 0, padding: 0 }}
        onChange={() => setDirty(true)}
      >
        <label>
          نام ویژگی
          <input
            maxLength={100}
            value={name}
            placeholder="مثلاً جنس پارچه"
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label>
          نوع پاسخ
          <DashboardSelect
            value={type}
            onChange={(e) => setType(e.target.value)}
          >
            {Object.entries(types).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </DashboardSelect>
        </label>
        {type === "number" && (
          <label>
            واحد، اختیاری
            <input
              maxLength={30}
              placeholder="مثلاً گرم یا سانتی‌متر"
              value={unit}
              onChange={(e) => setUnit(e.target.value)}
            />
          </label>
        )}
        {type === "choice" && (
          <label>
            گزینه‌های مجاز
            <textarea
              value={values}
              placeholder="پنبه، کتان، پلی‌استر"
              onChange={(e) => setValues(e.target.value)}
            />
            <small>با ویرگول یا خط جدید جدا کنید.</small>
          </label>
        )}
        <div className="cw-inherited">
          <strong>نمونهٔ چیزی که مدیر محصول می‌بیند:</strong>
          <p>
            {name || "نام ویژگی"}
            {type === "number" && unit ? ` (${unit})` : ""} —{" "}
            {type === "choice"
              ? splitValues(values).join(" / ") || "گزینه‌های شما"
              : types[type]}
          </p>
        </div>
        <div className="cw-actions">
          <button
            type="button"
            className="cw-primary"
            disabled={
              !name.trim() || (type === "choice" && !splitValues(values).length)
            }
            onClick={async () => {
              setBusy(true);
              setError("");
              try {
                const row = await api(
                  `catalog/attributes/${record ? record.id + "/" : ""}`,
                  {
                    name: name.trim(),
                    value_type: type,
                    unit: type === "number" ? unit.trim() : "",
                    choices: type === "choice" ? splitValues(values) : [],
                    ...(record ? { revision: record.revision } : {}),
                  },
                  record ? "PUT" : "POST",
                );
                setDirty(false);
                await onSaved(row);
              } catch (err) {
                setError(err.message);
              } finally {
                setBusy(false);
              }
            }}
          >
            ذخیرهٔ ویژگی
          </button>
          <button
            type="button"
            onClick={() => {
              if (!dirty || window.confirm("تغییرات کنار گذاشته شوند؟"))
                onCancel();
            }}
          >
            انصراف
          </button>
        </div>
      </fieldset>
    </div>
  );
}
export default function LibraryManager({
  kind,
  resource,
  initialId,
  initialCreate = false,
}) {
  const attributes = kind === "attributes";
  const [rows, setRows] = useState(null),
    [editing, setEditing] = useState(initialCreate ? null : undefined),
    [query, setQuery] = useState(""),
    [error, setError] = useState(""),
    [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    api(attributes ? "catalog/attributes/" : "workspace/choices/")
      .then((result) => {
        if (active) {
          const loaded = attributes ? result : result.brands;
          setRows(loaded);
          if (initialId) setEditing(loaded.find((row) => row.id === initialId));
        }
      })
      .catch((err) => {
        if (active) setError(err.message);
      });
    return () => {
      active = false;
    };
  }, [attributes, attempt]);
  async function saved(row) {
    setRows((previous) =>
      previous.some((r) => r.id === row.id)
        ? previous.map((r) => (r.id === row.id ? row : r))
        : [...previous, row],
    );
    setEditing(undefined);
  }
  return (
    <section className="cw" dir="rtl">
      <header className="cw-heading">
        <div>
          <span className="cw-eyebrow">اطلاعات مشترک کاتالوگ</span>
          <h2>{attributes ? "ویژگی‌ها" : "برندها"}</h2>
          <p>
            {attributes
              ? "ابتدا ویژگی را تعریف کنید؛ سپس در دسته مشخص کنید کدام ویژگی لازم است."
              : "برند اختیاری است؛ نام سازنده را ثبت کنید و هنگام ساخت محصول انتخاب کنید."}
          </p>
        </div>
        {resource.capabilities?.add && (
          <button
            className="cw-primary"
            onClick={() => {
              if (
                window.dispatchEvent(
                  new Event("catalog-before-leave", { cancelable: true }),
                )
              )
                setEditing(null);
            }}
          >
            + {attributes ? "ویژگی" : "برند"} جدید
          </button>
        )}
      </header>
      {error && (
        <p className="cw-error" role="alert">
          {error}
          <button onClick={() => setAttempt((n) => n + 1)}>تلاش مجدد</button>
        </p>
      )}
      <div className="cw-library-grid">
        <div className="cw-panel">
          <input
            className="cw-search"
            aria-label="جست‌وجو"
            placeholder="جست‌وجو در نام‌ها…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="cw-list">
            {rows
              ?.filter((r) => r.name.includes(query))
              .map((row) => (
                <button
                  key={row.id}
                  aria-pressed={editing?.id === row.id}
                  onClick={() => {
                    if (
                      window.dispatchEvent(
                        new Event("catalog-before-leave", { cancelable: true }),
                      )
                    )
                      setEditing(row);
                  }}
                >
                  <strong>{row.name}</strong>
                  <small>{attributes ? types[row.value_type] : row.slug}</small>
                </button>
              ))}
            {rows && !rows.length && (
              <p>هنوز موردی نساخته‌اید؛ از دکمهٔ بالا شروع کنید.</p>
            )}
            {!rows && !error && <p role="status">در حال دریافت…</p>}
          </div>
        </div>
        {editing !== undefined ? (
          attributes ? (
            <DefinitionForm
              key={editing?.id || "new"}
              record={editing}
              canSave={Boolean(
                editing
                  ? resource.capabilities?.change
                  : resource.capabilities?.add,
              )}
              onSaved={saved}
              onCancel={() => setEditing(undefined)}
            />
          ) : (
            <BrandForm
              key={editing?.id || "new"}
              record={editing}
              canSave={Boolean(
                editing
                  ? resource.capabilities?.change
                  : resource.capabilities?.add,
              )}
              onSaved={saved}
              onCancel={() => setEditing(undefined)}
            />
          )
        ) : (
          <div className="cw-panel cw-empty">
            <h3>
              {attributes
                ? "ویژگی‌ها، بدون فیلدهای فنی"
                : "برندها، ساده و اختیاری"}
            </h3>
            <p>
              برای ویرایش، نام را از فهرست انتخاب کنید. آدرس به‌صورت خودکار
              ساخته می‌شود.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
function BrandForm({ record, onSaved, onCancel, canSave }) {
  const [name, setName] = useState(record?.name || ""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useUnsaved(name !== (record?.name || ""));
  return (
    <div className="cw-panel">
      <h3>{record ? "ویرایش برند" : "برند جدید"}</h3>
      <label>
        نام برند
        <input
          maxLength={150}
          value={name}
          placeholder="مثلاً سامسونگ"
          onChange={(e) => setName(e.target.value)}
        />
      </label>
      <p className="cw-help">
        برند با دسته‌بندی فرق دارد و انتخاب آن برای محصول الزامی نیست.
      </p>
      {error && (
        <p className="cw-error" role="alert">
          {error}
        </p>
      )}
      <div className="cw-actions">
        <button
          disabled={busy || !name.trim() || !canSave}
          className="cw-primary"
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              await onSaved(
                await api(
                  `workspace/brands/${record ? record.id + "/" : ""}`,
                  { name: name.trim() },
                  record ? "PUT" : "POST",
                ),
              );
            } catch (err) {
              setError(err.message);
            } finally {
              setBusy(false);
            }
          }}
        >
          ذخیرهٔ برند
        </button>
        <button disabled={busy} onClick={onCancel}>
          انصراف
        </button>
      </div>
    </div>
  );
}
