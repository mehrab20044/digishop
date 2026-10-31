import BasicStep from "./BasicStep";
import ContentStep from "./ContentStep";
import SpecificationsStep from "./SpecificationsStep";
import InventoryStep from "./InventoryStep";
import ReviewStep from "./ReviewStep";
import { useEffect, useRef, useState } from "react";
import { api, digits, combinationKey as keyOf } from "./api";
import { useUnsaved } from "./shared";
import "./workspace.css";
const steps = [
  "اطلاعات محصول",
  "عکس و توضیحات",
  "مشخصات",
  "قیمت و موجودی",
  "بررسی و انتشار",
];
const initial = {
  name: "",
  slug: "",
  category_id: null,
  brand_id: null,
  short_description: "",
  long_description_html: "",
  gallery_description_html: "",
};
const basicKeys = Object.keys(initial);
export default function ProductWorkspace({ productId, onClose }) {
  const [choices, setChoices] = useState(null),
    [saved, setSaved] = useState(null),
    [basic, setBasic] = useState(initial),
    [specs, setSpecs] = useState({}),
    [axes, setAxes] = useState([]),
    [rows, setRows] = useState([]),
    [step, setStep] = useState(0),
    [dirty, setDirty] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [attempt, setAttempt] = useState(0),
    [vary, setVary] = useState(false),
    [simple, setSimple] = useState({ price: "", stock: 0 }),
    [bulk, setBulk] = useState({ axis: "", value: "", price: "", stock: "" });
  const [pendingInline, setPendingInline] = useState(false);
  const id = useRef(productId),
    lock = useRef(false),
    form = useRef(null),
    current = useRef(true),
    creatingUncertain = useRef(false);
  useUnsaved(dirty || pendingInline);
  function accept(item) {
    id.current = item.id;
    if (!productId)
      window.history.replaceState(
        null,
        "",
        `/dashboard/products/${item.id}/edit`,
      );
    setSaved(item);
    setBasic(
      Object.fromEntries(basicKeys.map((k) => [k, item[k] ?? initial[k]])),
    );
    setSpecs(item.values);
    setAxes(item.axes);
    setRows(item.variants.map((v) => ({ ...v, expected_stock: v.stock })));
    setSimple({ price: item.price || "", stock: item.stock });
    setVary(Boolean(item.axes.length || item.variants.length));
    setDirty(false);
  }
  useEffect(() => {
    current.current = true;
    const controller = new AbortController();
    Promise.all([
      api("workspace/choices/", undefined, "GET", controller.signal),
      productId
        ? api(
            `workspace/products/${productId}/`,
            undefined,
            "GET",
            controller.signal,
          )
        : null,
    ])
      .then(([options, item]) => {
        if (!controller.signal.aborted) {
          setChoices(options);
          if (item) accept(item);
        }
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(err.message);
      });
    return () => {
      current.current = false;
      controller.abort();
    };
  }, [productId, attempt]);
  const canEdit = saved
    ? choices?.permissions.change_product
    : choices?.permissions.add_product;
  async function reload() {
    if (dirty && !window.confirm("تغییرات ذخیره‌نشده کنار گذاشته شوند؟"))
      return;
    setError("");
    if (id.current) {
      try {
        accept(await api(`workspace/products/${id.current}/`));
      } catch (err) {
        setError(err.message);
      }
    } else setAttempt((n) => n + 1);
  }
  async function operation(action, data) {
    return api(`workspace/products/${id.current}/`, {
      version: saved.version,
      action,
      data,
    });
  }
  async function save(next = false, mode = null) {
    if (lock.current) return;
    if (step === 2 && pendingInline) {
      setError("ابتدا مشخصهٔ باز را اعمال یا لغو کنید، سپس ادامه دهید.");
      return;
    }
    lock.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      let item;
      if (mode) item = await operation("publication", mode);
      else if (step === 0) {
        if (!basic.name.trim() || !basic.category_id)
          throw new Error("نام محصول و دسته‌بندی را مشخص کنید.");
        if (!id.current && creatingUncertain.current)
          throw new Error(
            "نتیجهٔ ساخت قبلی نامشخص است؛ ابتدا فهرست محصولات را بررسی کنید تا محصول تکراری ساخته نشود.",
          );
        if (id.current) item = await operation("basic", basic);
        else {
          creatingUncertain.current = true;
          item = await api("workspace/products/", { basic });
          creatingUncertain.current = false;
        }
      } else if (step === 1) {
        const data = new FormData(form.current);
        item = await operation("basic", {
          ...basic,
          long_description_html: String(
            data.get("long_description_html") || "",
          ),
          gallery_description_html: String(
            data.get("gallery_description_html") || "",
          ),
        });
      } else if (step === 2)
        item = await operation(
          "specs",
          saved.schema.map((rule) => ({
            attribute_id: rule.id,
            value: specs[rule.id] || "",
          })),
        );
      else if (step === 3) {
        if (vary) {
          if (!rows.length)
            throw new Error(
              "ابتدا پیش‌نمایش ترکیب‌ها را بسازید و قیمت و موجودی را وارد کنید.",
            );
          if (rows.length > 200)
            throw new Error("هر بار حداکثر ۲۰۰ ردیف ذخیره می‌شود.");
          const payload = rows
            .map((row) => ({
              ...row,
              ...(row.id
                ? { id: row.id, expected_stock: row.expected_stock }
                : {}),
              price: Number(digits(row.price)),
              stock: Number(digits(row.stock)),
            }))
            .map((row) =>
              Object.fromEntries(
                [
                  "id",
                  "expected_stock",
                  "sku",
                  "options",
                  "price",
                  "stock",
                  "is_active",
                ]
                  .filter((k) => row[k] !== undefined)
                  .map((k) => [k, row[k]]),
              ),
            );
          if (
            rows.some(
              (r) =>
                String(r.price).trim() === "" || String(r.stock).trim() === "",
            )
          )
            throw new Error("قیمت و موجودی تمام ردیف‌ها را وارد کنید.");
          item = await operation("combinations", { axes, rows: payload });
        } else {
          if (
            String(simple.price).trim() === "" ||
            String(simple.stock).trim() === ""
          )
            throw new Error(
              "قیمت و موجودی را وارد کنید؛ برای ناموجود بودن، موجودی را صفر بگذارید.",
            );
          item = await operation("simple", {
            price: Number(digits(simple.price)),
            stock: Number(digits(simple.stock)),
            expected_stock: saved.stock,
          });
        }
      } else return;
      if (current.current) {
        accept(item);
        setNotice(
          mode === "published" ? "محصول منتشر شد." : "تغییرات ذخیره شد.",
        );
        if (next) setStep((n) => Math.min(4, n + 1));
      }
    } catch (err) {
      if (err.status && err.status >= 400 && err.status < 500)
        creatingUncertain.current = false;
      if (current.current) setError(err.message);
    } finally {
      lock.current = false;
      if (current.current) setBusy(false);
    }
  }
  async function applySpecification(payload) {
    if (lock.current) return false;
    lock.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const item = await operation("inline-specification", {
        ...payload,
        values: saved.schema.map((rule) => ({
          attribute_id: rule.id,
          value: specs[rule.id] || "",
        })),
      });
      if (current.current) {
        accept(item);
        setNotice("مشخصه ساخته یا انتخاب شد و همراه مقدار محصول ذخیره شد.");
        setPendingInline(false);
      }
      return true;
    } catch (err) {
      if (current.current) setError(err.message);
      return false;
    } finally {
      lock.current = false;
      if (current.current) setBusy(false);
    }
  }
  function move(index) {
    if (busy || (index > 0 && !saved)) return;
    if (dirty || pendingInline) {
      setError(
        "ابتدا تغییرات این مرحله را ذخیره کنید یا «دریافت اطلاعات تازه» را بزنید.",
      );
      return;
    }
    setError("");
    setStep(index);
  }
  function change(key, value) {
    setBasic((b) => ({ ...b, [key]: value }));
    setDirty(true);
  }
  async function quick(kind, row) {
    setChoices((c) => ({ ...c, [kind]: [...c[kind], row] }));
    change(kind === "categories" ? "category_id" : "brand_id", row.id);
  }
  async function generate() {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await api("workspace/combinations/preview/", { axes });
      const map = new Map(rows.map((r) => [keyOf(r.options), r]));
      const generated = result.rows.map(
        (options) =>
          map.get(keyOf(options)) || {
            sku: "",
            options,
            price: "",
            stock: 0,
            is_active: true,
          },
      );
      const keys = new Set(generated.map((r) => keyOf(r.options)));
      const retained = rows.filter((r) => r.id && !keys.has(keyOf(r.options)));
      setRows([...retained, ...generated]);
      setDirty(true);
      setNotice("ترکیب‌ها هنوز ذخیره نشده‌اند؛ قیمت و موجودی را کامل کنید.");
    } catch (err) {
      setError(err.message);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  function updateRow(index, key, value) {
    setRows((previous) =>
      previous.map((r, i) => (i === index ? { ...r, [key]: value } : r)),
    );
    setDirty(true);
  }
  if (!choices || (productId && !saved))
    return (
      <section className="card cw">
        <h2>مدیریت محصول</h2>
        {error ? (
          <>
            <p role="alert">{error}</p>
            <button onClick={() => setAttempt((n) => n + 1)}>تلاش مجدد</button>
          </>
        ) : (
          <p role="status">در حال آماده‌سازی فرم…</p>
        )}
      </section>
    );
  return (
    <section className="cw" dir="rtl">
      <header className="cw-heading">
        <div>
          <span className="cw-eyebrow">کاتالوگ فروشگاه</span>
          <h2>{saved ? basic.name : "محصول جدید"}</h2>
          <p>
            هر مرحله را کامل کنید؛ پیش‌نویس شما برای ادامهٔ کار ذخیره می‌شود.
          </p>
        </div>
        <div className="cw-actions">
          <span className="cw-status">
            {dirty
              ? "تغییرات ذخیره نشده"
              : saved?.is_active
                ? "منتشرشده"
                : saved
                  ? "ذخیره‌شده"
                  : "هنوز ساخته نشده"}
          </span>
          <button disabled={busy} onClick={onClose}>
            بازگشت به محصولات
          </button>
        </div>
      </header>
      <nav className="cw-steps" aria-label="مراحل ساخت محصول">
        {steps.map((title, i) => (
          <button
            key={title}
            disabled={busy || (!saved && i > 0)}
            aria-current={i === step ? "step" : undefined}
            onClick={() => move(i)}
          >
            <b>{new Intl.NumberFormat("fa-IR").format(i + 1)}</b>
            <span>{title}</span>
          </button>
        ))}
      </nav>
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
      <form
        ref={form}
        onSubmit={(e) => {
          e.preventDefault();
          save(true);
        }}
        onInput={() => setDirty(true)}
      >
        <fieldset disabled={busy || !canEdit} className="cw-panel">
          <div className="cw-section-heading">
            <div>
              <h3>{steps[step]}</h3>
              <p>
                {
                  [
                    "نام و دسته را انتخاب کنید؛ برند و آدرس اختیاری‌اند.",
                    "تصویر محصول را اضافه کنید و توضیحات را بنویسید.",
                    "این فیلدها از دسته‌بندی انتخاب‌شده آمده‌اند.",
                    "محصول یک قیمت دارد یا مشتری سایز، رنگ و مانند آن را انتخاب می‌کند؟",
                    "قبل از انتشار، موارد ناقص را برطرف کنید.",
                  ][step]
                }
              </p>
            </div>
            {saved && (
              <button type="button" className="cw-text" onClick={reload}>
                دریافت اطلاعات تازه
              </button>
            )}
          </div>
          {step === 0 && (
            <BasicStep
              basic={basic}
              choices={choices}
              change={change}
              quick={quick}
            />
          )}
          {step === 1 && (
            <ContentStep saved={saved} basic={basic} change={change} />
          )}
          {step === 2 && (
            <SpecificationsStep
              saved={saved}
              specs={specs}
              setSpecs={setSpecs}
              setDirty={setDirty}
              choices={choices}
              applySpecification={applySpecification}
              onPending={setPendingInline}
            />
          )}
          {step === 3 && (
            <InventoryStep
              vary={vary}
              setVary={setVary}
              setDirty={setDirty}
              saved={saved}
              simple={simple}
              setSimple={setSimple}
              axes={axes}
              setAxes={setAxes}
              rows={rows}
              setRows={setRows}
              busy={busy}
              generate={generate}
              bulk={bulk}
              setBulk={setBulk}
              updateRow={updateRow}
            />
          )}
          {step === 4 && (
            <ReviewStep
              saved={saved}
              choices={choices}
              move={move}
              save={save}
            />
          )}
        </fieldset>
        <footer className="cw-footer">
          <button
            type="button"
            disabled={busy || step === 0}
            onClick={() => move(step - 1)}
          >
            مرحلهٔ قبل
          </button>
          <span>
            {busy
              ? "در حال ذخیره…"
              : dirty
                ? "پیش از خروج ذخیره کنید."
                : "اطلاعات ذخیره‌شده در سرور نگه‌داری می‌شود."}
          </span>
          {step < 4 && (
            <div className="cw-actions">
              <button
                type="button"
                disabled={busy || !canEdit}
                onClick={() => save(false)}
              >
                ذخیرهٔ این مرحله
              </button>
              <button
                className="cw-primary"
                type="submit"
                disabled={busy || !canEdit}
              >
                ذخیره و ادامه ←
              </button>
            </div>
          )}
        </footer>
      </form>
    </section>
  );
}
