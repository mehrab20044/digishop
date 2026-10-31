import DashboardSelect from "../components/DashboardSelect";
import { useEffect, useState } from "react";
import { api, pathLabel } from "./api";
export function useUnsaved(dirty) {
  useEffect(() => {
    if (!dirty) return;
    const unload = (e) => {
      e.preventDefault();
      e.returnValue = "";
    };
    const click = (e) => {
      if (
        e.target.closest?.("a[href]") &&
        !window.confirm("تغییرات ذخیره نشده‌اند. از این صفحه خارج می‌شوید؟")
      ) {
        e.preventDefault();
        e.stopImmediatePropagation();
      }
    };
    const leave = (e) => {
      if (!window.confirm("تغییرات ذخیره نشده‌اند؛ خارج می‌شوید؟"))
        e.preventDefault();
    };
    window.addEventListener("catalog-before-leave", leave);
    window.addEventListener("beforeunload", unload);
    document.addEventListener("click", click, true);
    return () => {
      window.removeEventListener("catalog-before-leave", leave);
      window.removeEventListener("beforeunload", unload);
      document.removeEventListener("click", click, true);
    };
  }, [dirty]);
}
export function CategorySelect({ rows, value, onChange, exclude = [] }) {
  const choices = rows
    .filter((row) => !exclude.includes(row.id))
    .map((row) => ({ ...row, path: pathLabel(row.id, rows) }))
    .sort((a, b) => a.path.localeCompare(b.path, "fa"));
  return (
    <div className="cw-category-select">
      <DashboardSelect
        searchable
        aria-label="دسته‌بندی"
        value={value ?? ""}
        onChange={(event) =>
          onChange(event.target.value ? Number(event.target.value) : null)
        }
      >
        <option value="">انتخاب دسته</option>
        {choices.map((row) => (
          <option key={row.id} value={row.id} data-path={row.path}>
            {row.name}
          </option>
        ))}
      </DashboardSelect>
    </div>
  );
}
export function QuickCreate({ kind, choices, onSaved, parentId = null }) {
  const [open, setOpen] = useState(false),
    [name, setName] = useState(""),
    [parent, setParent] = useState(parentId),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const category = kind === "category";
  return (
    <div className="cw-quick">
      {!open ? (
        <button type="button" className="cw-text" onClick={() => setOpen(true)}>
          + ساخت {category ? "دسته" : "برند"} در همین صفحه
        </button>
      ) : (
        <div className="cw-inset">
          <strong>{category ? "دستهٔ جدید" : "برند جدید"}</strong>
          <label>
            نام
            <input
              autoFocus
              maxLength={category ? 100 : 150}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          {category && (
            <>
              <label>جایگاه دسته</label>
              <CategorySelect
                rows={choices.categories}
                value={parent}
                onChange={setParent}
              />
              <small>بدون انتخاب دستهٔ بالاتر، دستهٔ اصلی ساخته می‌شود.</small>
            </>
          )}
          {error && (
            <p role="alert" className="cw-error">
              {error}
            </p>
          )}
          <div className="cw-actions">
            <button
              type="button"
              disabled={busy || !name.trim()}
              onClick={async () => {
                setBusy(true);
                setError("");
                try {
                  const row = await api(
                    category ? "categories/create/" : "workspace/brands/",
                    category
                      ? { name: name.trim(), parent_id: parent }
                      : { name: name.trim() },
                  );
                  await onSaved(row);
                  setOpen(false);
                  setName("");
                } catch (err) {
                  setError(err.message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              {busy ? "در حال ساخت…" : "ساخت و انتخاب"}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => setOpen(false)}
            >
              انصراف
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
export function ValueField({ rule, value, onChange }) {
  return (
    <label>
      <span>
        {rule.name}
        {rule.required && <b className="cw-required"> الزامی</b>}
        {rule.unit && ` (${rule.unit})`}
      </span>
      {["boolean", "choice"].includes(rule.value_type) ? (
        <DashboardSelect
          value={value}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">انتخاب کنید</option>
          {(rule.value_type === "boolean" ? ["بله", "خیر"] : rule.choices).map(
            (v) => (
              <option key={v}>{v}</option>
            ),
          )}
        </DashboardSelect>
      ) : (
        <input
          maxLength={255}
          inputMode={rule.value_type === "number" ? "decimal" : "text"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
    </label>
  );
}
