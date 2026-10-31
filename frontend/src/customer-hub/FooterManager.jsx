import { useEffect, useRef, useState } from "react";
import { api } from "../catalog/api";
import { useUnsaved } from "../catalog/shared";
import DashboardSelect from "../components/DashboardSelect";
import "../catalog/workspace.css";
import "./owner-hub.css";

const icons = [
  ["shield", "ضمانت / خدمات"],
  ["truck", "ارسال"],
  ["return", "بازگشت"],
  ["payment", "پرداخت"],
];
const blankLink = () => ({ title: "", url: "/" });
function Field({ label, children }) {
  return (
    <label className="oh-field">
      <span>{label}</span>
      {children}
    </label>
  );
}
export default function FooterManager({ resource }) {
  const [record, setRecord] = useState(null);
  const [draft, setDraft] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [attempt, setAttempt] = useState(0);
  const dirty = Boolean(
    record && draft && JSON.stringify(record.config) !== JSON.stringify(draft),
  );
  useUnsaved(dirty);
  useEffect(() => {
    const controller = new AbortController();
    api("footer-settings/", undefined, "GET", controller.signal)
      .then((data) => {
        setRecord(data);
        setDraft(structuredClone(data.config));
        setError("");
      })
      .catch((error) => {
        if (!controller.signal.aborted) setError(error.message);
      });
    return () => controller.abort();
  }, [attempt]);
  function patch(values) {
    setDraft((previous) => ({ ...previous, ...values }));
    setNotice("");
  }
  function collection(key, index, values) {
    patch({
      [key]: draft[key].map((row, i) =>
        i === index ? { ...row, ...values } : row,
      ),
    });
  }
  function reorder(key, index, delta) {
    const rows = [...draft[key]];
    [rows[index], rows[index + delta]] = [rows[index + delta], rows[index]];
    patch({ [key]: rows });
  }
  function links(key, rows, change) {
    return (
      <div className="oh-links">
        {rows.map((row, index) => (
          <div className="oh-link-row" key={index}>
            <Field label="عنوان">
              <input
                value={row.title}
                maxLength={80}
                required
                onChange={(event) =>
                  change(
                    rows.map((item, i) =>
                      i === index
                        ? { ...item, title: event.target.value }
                        : item,
                    ),
                  )
                }
              />
            </Field>
            <Field label="آدرس مقصد">
              <input
                dir="ltr"
                value={row.url}
                required
                maxLength={1000}
                placeholder="/pages/about یا https://..."
                onChange={(event) =>
                  change(
                    rows.map((item, i) =>
                      i === index ? { ...item, url: event.target.value } : item,
                    ),
                  )
                }
              />
            </Field>
            <button
              type="button"
              className="oh-remove"
              onClick={() => change(rows.filter((_, i) => i !== index))}
            >
              حذف
            </button>
          </div>
        ))}
        {rows.length < 8 && (
          <button
            className="cw-soft"
            type="button"
            onClick={() => change([...rows, blankLink()])}
          >
            + افزودن {key}
          </button>
        )}
      </div>
    );
  }
  async function save(event) {
    event.preventDefault();
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      const data = await api(
        "footer-settings/",
        { revision: record.revision, config: draft },
        "PATCH",
      );
      setRecord(data);
      setDraft(structuredClone(data.config));
      setNotice("فوتر فروشگاه ذخیره و منتشر شد.");
    } catch (error) {
      setError(error.message);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  if (!draft)
    return (
      <section className="cw">
        <h1>فوتر فروشگاه</h1>
        <p role={error ? "alert" : "status"}>
          {error || "در حال دریافت تنظیمات…"}
        </p>
        {error && (
          <button type="button" onClick={() => setAttempt((v) => v + 1)}>
            تلاش دوباره
          </button>
        )}
      </section>
    );
  return (
    <section className="cw oh-editor">
      <header>
        <h1>فوتر فروشگاه</h1>
        <p>
          تغییرها پس از ذخیره در تمام صفحه‌های فروشگاه نمایش داده می‌شوند. فقط
          خدمات و اطلاعات واقعی کسب‌وکار را وارد کنید.
        </p>
      </header>
      {error && (
        <p className="cw-error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="cw-notice" role="status">
          {notice}
        </p>
      )}
      <form onSubmit={save}>
        <fieldset disabled={busy || !resource.capabilities.change}>
          <section className="cw-panel">
            <h2>معرفی و اطلاعات تماس</h2>
            <div className="oh-grid">
              {[
                ["name", "نام فروشگاه", 100],
                ["phone", "شماره تماس", 32],
                ["email", "ایمیل", 254],
                ["hours", "ساعت پاسخ‌گویی", 200],
                ["address", "نشانی", 500],
                ["copyright", "متن حقوق محتوا؛ اختیاری", 300],
              ].map(([key, label, max]) => (
                <Field label={label} key={key}>
                  <input
                    value={draft[key]}
                    required={key === "name"}
                    maxLength={max}
                    type={key === "email" ? "email" : "text"}
                    onChange={(event) => patch({ [key]: event.target.value })}
                  />
                </Field>
              ))}
            </div>
            <Field label="توضیح کوتاه فروشگاه">
              <textarea
                rows={3}
                maxLength={2000}
                value={draft.description}
                onChange={(event) => patch({ description: event.target.value })}
              />
            </Field>
          </section>
          <section className="cw-panel">
            <h2>ردیف خدمات بالای فوتر</h2>
            <p>
              تا چهار مورد. عنوان و توضیح دلخواه؛ وعده‌های ارسال، ضمانت و
              بازپرداخت را فقط در صورت اجرای واقعی بنویسید.
            </p>
            {draft.services.map((row, index) => (
              <div className="oh-block" key={index}>
                <div className="oh-grid">
                  <Field label="عنوان">
                    <input
                      value={row.title}
                      required
                      maxLength={80}
                      onChange={(event) =>
                        collection("services", index, {
                          title: event.target.value,
                        })
                      }
                    />
                  </Field>
                  <Field label="توضیح">
                    <input
                      value={row.text}
                      maxLength={160}
                      onChange={(event) =>
                        collection("services", index, {
                          text: event.target.value,
                        })
                      }
                    />
                  </Field>
                  <Field label="نماد">
                    <DashboardSelect
                      value={row.icon}
                      onChange={(event) =>
                        collection("services", index, {
                          icon: event.target.value,
                        })
                      }
                    >
                      {icons.map(([value, label]) => (
                        <option value={value} key={value}>
                          {label}
                        </option>
                      ))}
                    </DashboardSelect>
                  </Field>
                </div>
                <div className="oh-row-actions">
                  <button
                    type="button"
                    disabled={index === 0}
                    onClick={() => reorder("services", index, -1)}
                  >
                    بالاتر
                  </button>
                  <button
                    type="button"
                    disabled={index === draft.services.length - 1}
                    onClick={() => reorder("services", index, 1)}
                  >
                    پایین‌تر
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      patch({
                        services: draft.services.filter((_, i) => i !== index),
                      })
                    }
                  >
                    حذف
                  </button>
                </div>
              </div>
            ))}
            {draft.services.length < 4 && (
              <button
                type="button"
                className="cw-soft"
                onClick={() =>
                  patch({
                    services: [
                      ...draft.services,
                      { title: "", text: "", icon: "shield" },
                    ],
                  })
                }
              >
                + افزودن خدمت
              </button>
            )}
          </section>
          <section className="cw-panel">
            <h2>ستون‌های لینک</h2>
            {draft.columns.map((column, index) => (
              <div className="oh-block" key={index}>
                <Field label="عنوان ستون">
                  <input
                    value={column.title}
                    maxLength={80}
                    required
                    onChange={(event) =>
                      collection("columns", index, {
                        title: event.target.value,
                      })
                    }
                  />
                </Field>
                {links("لینک", column.links, (rows) =>
                  collection("columns", index, { links: rows }),
                )}
                <div className="oh-row-actions">
                  <button
                    type="button"
                    disabled={index === 0}
                    onClick={() => reorder("columns", index, -1)}
                  >
                    بالاتر
                  </button>
                  <button
                    type="button"
                    disabled={index === draft.columns.length - 1}
                    onClick={() => reorder("columns", index, 1)}
                  >
                    پایین‌تر
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      patch({
                        columns: draft.columns.filter((_, i) => i !== index),
                      })
                    }
                  >
                    حذف ستون
                  </button>
                </div>
              </div>
            ))}
            {draft.columns.length < 4 && (
              <button
                className="cw-soft"
                type="button"
                onClick={() =>
                  patch({
                    columns: [...draft.columns, { title: "", links: [] }],
                  })
                }
              >
                + ستون جدید
              </button>
            )}
            <p>
              صفحه‌هایی که در صفحه‌ساز برای نمایش در فوتر فعال کرده‌اید، خودکار
              در یک ستون جدا نمایش داده می‌شوند.
            </p>
          </section>
          <section className="cw-panel">
            <h2>شبکه‌های اجتماعی</h2>
            {links("شبکه اجتماعی", draft.socials, (rows) =>
              patch({ socials: rows }),
            )}
          </section>
          <button className="cw-primary" type="submit" disabled={!dirty}>
            {busy ? "در حال ذخیره…" : "ذخیره و انتشار فوتر"}
          </button>
        </fieldset>
      </form>
    </section>
  );
}
