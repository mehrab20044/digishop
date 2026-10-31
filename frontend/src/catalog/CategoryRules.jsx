import { useEffect, useState } from "react";
import { api } from "./api";
import { useUnsaved } from "./shared";
import { DefinitionForm } from "./LibraryManager";
import "./workspace.css";
export default function CategoryRules({ categoryId }) {
  const [doc, setDoc] = useState(null),
    [definitions, setDefinitions] = useState([]),
    [rules, setRules] = useState([]),
    [query, setQuery] = useState(""),
    [creating, setCreating] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [dirty, setDirty] = useState(false),
    [caps, setCaps] = useState({});
  useUnsaved(dirty);
  useEffect(() => {
    let active = true;
    Promise.all([
      api(`catalog/categories/${categoryId}/`),
      api("workspace/choices/"),
    ])
      .then(([data, choices]) => {
        if (active) {
          setDoc(data);
          setRules(data.own);
          setDefinitions(choices.attributes);
          setCaps(choices.permissions);
        }
      })
      .catch((err) => {
        if (active) setError(err.message);
      });
    return () => {
      active = false;
    };
  }, [categoryId]);
  const inherited =
    doc?.effective.filter((r) => r.category_id !== categoryId) || [];
  function toggle(id, on) {
    setRules((previous) =>
      on
        ? [
            ...previous,
            { attribute_id: id, required: false, sort_order: previous.length },
          ]
        : previous.filter((r) => r.attribute_id !== id),
    );
    setDirty(true);
  }
  return (
    <section className="cw" dir="rtl" style={{ marginTop: 24 }}>
      <div className="cw-panel">
        <h3>چه مشخصاتی برای محصولات این دسته لازم است؟</h3>
        <p>
          مثلاً برای پیراهن «جنس پارچه» را اضافه کنید. سایز و رنگِ قابل خرید را
          در بخش قیمت و موجودی خود محصول می‌سازید.
        </p>
        {error && (
          <p className="cw-error" role="alert">
            {error}
          </p>
        )}
        {!doc && !error && <p role="status">در حال دریافت…</p>}
        {inherited.length > 0 && (
          <div className="cw-inherited">
            <strong>از دستهٔ بالاتر دریافت شده:</strong>
            {inherited.map((r) => (
              <p key={r.id}>
                {r.name} — {r.required ? "الزامی" : "اختیاری"}
              </p>
            ))}
            <small>
              برای تغییر قانون والد فقط در این دسته، همان ویژگی را در فهرست زیر
              انتخاب کنید.
            </small>
          </div>
        )}
        {doc && (
          <>
            <input
              aria-label="جست‌وجوی ویژگی"
              placeholder="ویژگی را پیدا کنید؛ مثلاً جنس"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <div style={{ maxHeight: 350, overflow: "auto", margin: "16px 0" }}>
              {definitions
                .filter((d) => d.name.includes(query))
                .map((d) => {
                  const rule = rules.find((r) => r.attribute_id === d.id);
                  return (
                    <div className="cw-rule" key={d.id}>
                      <label>
                        <input
                          type="checkbox"
                          disabled={busy}
                          checked={Boolean(rule)}
                          onChange={(e) => toggle(d.id, e.target.checked)}
                        />{" "}
                        {d.name}
                        {d.unit ? ` (${d.unit})` : ""}
                      </label>
                      {rule && (
                        <label>
                          <input
                            type="checkbox"
                            disabled={busy}
                            checked={rule.required}
                            onChange={(e) => {
                              setRules((rs) =>
                                rs.map((r) =>
                                  r.attribute_id === d.id
                                    ? { ...r, required: e.target.checked }
                                    : r,
                                ),
                              );
                              setDirty(true);
                            }}
                          />{" "}
                          پاسخ الزامی
                        </label>
                      )}
                    </div>
                  );
                })}
            </div>
            {!definitions.length && <p>هنوز ویژگی‌ای تعریف نشده است.</p>}
            <div className="cw-actions">
              {caps.add_attribute && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => setCreating(true)}
                >
                  + تعریف ویژگی جدید
                </button>
              )}
              <button
                type="button"
                className="cw-primary"
                disabled={busy || !dirty}
                onClick={async () => {
                  setBusy(true);
                  setError("");
                  try {
                    const data = await api(
                      `catalog/categories/${categoryId}/`,
                      { revision: doc.revision, rules },
                      "PUT",
                    );
                    setDoc(data);
                    setRules(data.own);
                    setDirty(false);
                  } catch (err) {
                    setError(err.message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {busy ? "در حال ذخیره…" : "ذخیرهٔ مشخصات دسته"}
              </button>
            </div>
            <small>
              الزام جدید روی محصولات منتشرشده هم بررسی می‌شود؛ اگر ناقص باشند
              سرور ذخیره را رد می‌کند و داده‌ای حذف نمی‌شود.
            </small>
          </>
        )}
        {creating && (
          <DefinitionForm
            onCancel={() => setCreating(false)}
            onSaved={async (row) => {
              setDefinitions((ds) => [...ds, row]);
              setRules((rs) => [
                ...rs,
                {
                  attribute_id: row.id,
                  required: false,
                  sort_order: rs.length,
                },
              ]);
              setDirty(true);
              setCreating(false);
            }}
          />
        )}
      </div>
    </section>
  );
}
