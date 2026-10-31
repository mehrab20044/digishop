import DashboardSelect from "../components/DashboardSelect";
import { useEffect, useRef, useState } from "react";
import { StoreLayout } from "../Storefront";
import PageContent from "../pages/PageContent";
import { pageRequest, writePage } from "../pages/page-api";
import PreviewFrame from "./PreviewFrame";
import { Promotions } from "../banners/Promotions";
import "../pages/page-builder.css";
import "./store-theme.css";
const PRESETS = [
  {
    name: "سبز",
    primary: "#176b61",
    background: "#ffffff",
    surface: "#f0f7f5",
    text: "#17212d",
  },
  {
    name: "آبی",
    primary: "#315bea",
    background: "#ffffff",
    surface: "#eef3ff",
    text: "#17212d",
  },
  {
    name: "گرم",
    primary: "#bd4b16",
    background: "#fffdf8",
    surface: "#fff0df",
    text: "#30251c",
  },
  {
    name: "تیره",
    primary: "#75d6b5",
    background: "#17212d",
    surface: "#243445",
    text: "#f5f7fa",
  },
];
function Field({ label, children }) {
  return (
    <label className="pbe-field">
      <span>{label}</span>
      {children}
    </label>
  );
}
const sample = {
  title: "صفحه‌های فروشگاه",
  layout: "simple",
  blocks: [
    {
      id: "sample-text",
      type: "text",
      enabled: true,
      data: {
        heading: "همهٔ صفحه‌ها، یک ظاهر مشترک",
        body: "هدر، فوتر، فونت، رنگ‌ها و دکمه‌ها از همین تنظیمات پیروی می‌کنند.",
        align: "right",
      },
    },
    {
      id: "sample-button",
      type: "buttons",
      enabled: true,
      data: {
        items: [{ label: "دیدن محصولات", href: "/products", style: "primary" }],
      },
    },
  ],
};
export default function AppearanceManager({ resource }) {
  const [record, setRecord] = useState(null);
  const [draft, setDraft] = useState(null);
  const [saved, setSaved] = useState("");
  const [images, setImages] = useState({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const lock = useRef(false);
  const mounted = useRef(false);
  const dirty = draft !== null && JSON.stringify(draft) !== saved;
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  function accept(data) {
    setRecord(data);
    setDraft(data.draft);
    setSaved(JSON.stringify(data.draft));
    if (data.preview.banner.image_id)
      setImages((previous) => ({
        ...previous,
        [data.preview.banner.image_id]: data.preview.banner.image_url,
      }));
  }
  useEffect(() => {
    const controller = new AbortController();
    pageRequest("theme/", { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) accept(data);
      })
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      });
    return () => controller.abort();
  }, [attempt]);
  useEffect(() => {
    if (!dirty) return undefined;
    function warn(event) {
      event.preventDefault();
      event.returnValue = "";
    }
    function protect(event) {
      if (
        event.target.closest?.("a[href]") &&
        !window.confirm("تغییرات ذخیره نشده‌اند. خارج می‌شوید؟")
      ) {
        event.preventDefault();
        event.stopPropagation();
      }
    }
    window.addEventListener("beforeunload", warn);
    document.addEventListener("click", protect, true);
    return () => {
      window.removeEventListener("beforeunload", warn);
      document.removeEventListener("click", protect, true);
    };
  }, [dirty]);
  async function perform(action) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (err) {
      if (mounted.current)
        setError(
          err.status === 409
            ? "نسخهٔ جدیدتری ذخیره شده است. تنظیمات فعلی حفظ شدند؛ قبل از دریافت نسخهٔ تازه، تغییرات لازم را یادداشت کنید."
            : err.message,
        );
    } finally {
      lock.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  function patch(values) {
    setDraft((current) => ({ ...current, ...values }));
  }
  function banner(values) {
    setDraft((current) => ({
      ...current,
      banner: { ...current.banner, ...values },
    }));
  }
  async function saveDraft() {
    if (!resource.capabilities?.change)
      throw new Error("مجوز تغییر ظاهر ندارید.");
    const data = await writePage(
      "theme/",
      { revision: record.revision, config: draft },
      "PATCH",
    );
    if (mounted.current) accept(data);
    return data;
  }
  function save() {
    return perform(async () => {
      await saveDraft();
      if (mounted.current)
        setNotice("پیش‌نویس ظاهر ذخیره شد؛ هنوز روی سایت اعمال نشده است.");
    });
  }
  function publish() {
    return perform(async () => {
      const current = dirty ? await saveDraft() : record;
      const data = await writePage("theme/", { revision: current.revision });
      if (mounted.current) {
        accept(data);
        setNotice("ظاهر منتشر شد؛ فروشگاه را تازه‌سازی کنید.");
      }
    });
  }
  function upload(file) {
    if (file.size > 5 * 1024 * 1024) {
      setError("تصویر باید حداکثر ۵ مگابایت باشد.");
      return;
    }
    return perform(async () => {
      const body = new FormData();
      body.set("image", file);
      const image = await pageRequest("images/", { method: "POST", body });
      if (mounted.current) {
        setImages((previous) => ({ ...previous, [image.id]: image.url }));
        banner({ image_id: image.id });
      }
    });
  }
  if (!draft)
    return (
      <section className="card">
        <h2>ظاهر فروشگاه</h2>
        {error ? (
          <p role="alert">
            {error}
            <button onClick={() => setAttempt((v) => v + 1)}>
              تلاش دوباره
            </button>
          </p>
        ) : (
          <p role="status">در حال دریافت تنظیمات…</p>
        )}
      </section>
    );
  const preview = {
    ...draft,
    banner: {
      ...draft.banner,
      image_url: images[draft.banner.image_id] || null,
    },
  };
  return (
    <section className="pbe-manager" dir="rtl">
      <div className="pbe-intro">
        <div>
          <span className="pbe-eyebrow">یک ظاهر برای همهٔ صفحه‌ها</span>
          <h2>ظاهر فروشگاه</h2>
          <p>رنگ‌ها، قالب عمومی و بنر صفحهٔ اول را تنظیم کنید.</p>
        </div>
        <div className="pbe-editor-actions">
          {resource.capabilities?.change && (
            <button
              className="pbe-soft"
              disabled={busy || !dirty}
              onClick={save}
            >
              ذخیرهٔ پیش‌نویس
            </button>
          )}
          {resource.capabilities?.publish && (
            <button
              className="pbe-primary"
              disabled={busy || (dirty && !resource.capabilities?.change)}
              onClick={publish}
            >
              انتشار ظاهر
            </button>
          )}
        </div>
      </div>
      {error && (
        <p role="alert" className="pbe-error">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="pbe-notice">
          {notice}
        </p>
      )}
      <p className="pbe-hint">
        {dirty ? "تغییرات ذخیره نشده‌اند." : "نسخهٔ ذخیره‌شده"} تغییرات فقط با
        «انتشار ظاهر» روی سایت اعمال می‌شوند.
      </p>
      <div className="st-editor">
        <div>
          <fieldset disabled={busy || !resource.capabilities?.change}>
            <section>
              <h3>رنگ قالب</h3>
              <div className="st-presets">
                {PRESETS.map(({ name, ...colors }) => (
                  <button
                    key={name}
                    type="button"
                    onClick={() => patch(colors)}
                  >
                    <i style={{ background: colors.primary }} />
                    {name}
                  </button>
                ))}
              </div>
              <div className="st-colors">
                {[
                  ["primary", "رنگ اصلی و دکمه‌ها"],
                  ["background", "پس‌زمینهٔ سایت"],
                  ["surface", "پس‌زمینهٔ بخش‌ها"],
                  ["text", "رنگ متن"],
                ].map(([key, label]) => (
                  <label className="pbe-field st-color" key={key}>
                    <span>{label}</span>
                    <input
                      type="color"
                      value={draft[key]}
                      onChange={(event) => patch({ [key]: event.target.value })}
                    />
                    <small dir="ltr">{draft[key]}</small>
                  </label>
                ))}
              </div>
              <small>
                رنگ نوشتهٔ دکمه خودکار انتخاب می‌شود. ترکیب ناخوانای متن و
                پس‌زمینه ذخیره نمی‌شود.
              </small>
            </section>
            <section>
              <h3>قالب عمومی صفحه‌ها</h3>
              <Field label="عرض محتوا">
                <DashboardSelect
                  value={draft.page_width}
                  onChange={(event) =>
                    patch({ page_width: event.target.value })
                  }
                >
                  <option value="compact">جمع‌وجور</option>
                  <option value="standard">استاندارد</option>
                  <option value="wide">عریض</option>
                </DashboardSelect>
              </Field>
              <Field label="فونت">
                <DashboardSelect
                  value={draft.font}
                  onChange={(event) => patch({ font: event.target.value })}
                >
                  <option value="tahoma">تاهوما؛ مناسب فارسی</option>
                  <option value="system">فونت سیستم</option>
                </DashboardSelect>
              </Field>
              <p className="pbe-hint">
                هدر و فوتر، همان اجزای اصلی فروشگاه‌اند؛ صفحه‌های ساخته‌شده داخل
                همین قالب قرار می‌گیرند.
              </p>
            </section>
            <section>
              <h3>بنرهای فروشگاه</h3>
              <p>مدیریت چند بنر، اسلایدر و زمان‌بندی به بخش مستقل منتقل شد.</p>
              <a href="/dashboard/banners">مدیریت بنرها ←</a>
            </section>
            <button
              type="button"
              className="pbe-soft"
              onClick={() => {
                if (
                  window.confirm(
                    "پیش‌نویس به ظاهر پیش‌فرض برگردد؟ برای اعمال روی سایت، انتشار لازم است.",
                  )
                )
                  setDraft(structuredClone(record.defaults));
              }}
            >
              بازگشت به ظاهر پیش‌فرض
            </button>
          </fieldset>
          <button
            className="pbe-link"
            disabled={busy}
            onClick={() => {
              if (
                !dirty ||
                window.confirm("تغییرات ذخیره‌نشده کنار گذاشته شوند؟")
              ) {
                setError("");
                setAttempt((value) => value + 1);
              }
            }}
          >
            دریافت نسخهٔ ذخیره‌شده
          </button>
        </div>
        <div>
          <div className="pbe-editor-actions" style={{ marginBottom: 12 }}>
            <button
              className="pbe-soft"
              aria-pressed={!mobile}
              onClick={() => setMobile(false)}
            >
              دسکتاپ
            </button>
            <button
              className="pbe-soft"
              aria-pressed={mobile}
              onClick={() => setMobile(true)}
            >
              موبایل
            </button>
          </div>
          <div className="st-preview-pane">
            <PreviewFrame mobile={mobile}>
              <StoreLayout preview themeOverride={preview}>
                <main id="sf-main" className="sf-container">
                  <Promotions placement="hero" />
                  <PageContent page={sample} />
                </main>
              </StoreLayout>
            </PreviewFrame>
          </div>
        </div>
      </div>
    </section>
  );
}
