import DashboardSelect from "../components/DashboardSelect";
import { StoreLayout } from "../Storefront";
import PreviewFrame from "../appearance/PreviewFrame";
import { useEffect, useRef, useState } from "react";
import PageContent from "./PageContent";
import { pageRequest, writePage } from "./page-api";
import "./page-builder.css";

const TYPES = [
  { type: "hero", name: "بنر معرفی", hint: "عنوان، تصویر و دکمه" },
  { type: "text", name: "متن", hint: "توضیحات و اطلاعات صفحه" },
  { type: "image", name: "تصویر", hint: "عکس همراه توضیح" },
  { type: "buttons", name: "دکمه‌ها", hint: "لینک به محصولات یا صفحات" },
  { type: "spacer", name: "فاصله", hint: "فضای خالی بین بخش‌ها" },
];
const labelFor = (type) =>
  TYPES.find((item) => item.type === type)?.name || type;
function makeBlock(type) {
  const defaults = {
    hero: {
      title: "به فروشگاه ما خوش آمدید",
      text: "اینجا دربارهٔ این صفحه بنویسید.",
      image_id: null,
      buttons: [{ label: "دیدن محصولات", href: "/products", style: "primary" }],
    },
    text: {
      heading: "عنوان بخش",
      body: "متن این بخش را بنویسید.",
      align: "right",
    },
    image: { image_id: null, alt: "", caption: "" },
    buttons: {
      items: [{ label: "دیدن محصولات", href: "/products", style: "primary" }],
    },
    spacer: { height: 32 },
  };
  return {
    id: crypto.randomUUID(),
    type,
    enabled: type !== "image",
    data: defaults[type],
  };
}
function newPage() {
  return {
    title: "",
    slug: "",
    seo_title: "",
    seo_description: "",
    layout: "simple",
    footer_visible: true,
    footer_label: "",
    footer_order: 0,
    blocks: [],
    images: {},
    is_published: false,
    slug_locked: false,
  };
}
function payload(page) {
  return {
    title: page.title,
    slug: page.slug,
    seo_title: page.seo_title,
    seo_description: page.seo_description,
    blocks: page.blocks,
    layout: page.layout || "simple",
    footer_visible: page.footer_visible ?? true,
    footer_label: page.footer_label || "",
    footer_order: page.footer_order || 0,
    ...(page.id ? { revision: page.revision } : {}),
  };
}
function move(items, from, to) {
  if (to < 0 || to >= items.length || from === to) return items;
  const next = [...items];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}
function Field({ label, children, hint }) {
  return (
    <label className="pbe-field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
function ButtonFields({ items, onChange }) {
  return (
    <div className="pbe-button-fields">
      {items.map((item, index) => (
        <div className="pbe-button-item" key={index}>
          <div className="pbe-button-item-title">
            <b>دکمهٔ {(index + 1).toLocaleString("fa-IR")}</b>
            <div>
              <button
                type="button"
                disabled={index === 0}
                aria-label="دکمه بالاتر"
                onClick={() => onChange(move(items, index, index - 1))}
              >
                ↑
              </button>
              <button
                type="button"
                disabled={index === items.length - 1}
                aria-label="دکمه پایین‌تر"
                onClick={() => onChange(move(items, index, index + 1))}
              >
                ↓
              </button>
              <button
                type="button"
                onClick={() => onChange(items.filter((_, i) => i !== index))}
              >
                حذف
              </button>
            </div>
          </div>
          <div className="pbe-two">
            <Field label="متن دکمه">
              <input
                value={item.label}
                maxLength={80}
                onChange={(event) =>
                  onChange(
                    items.map((row, i) =>
                      i === index ? { ...row, label: event.target.value } : row,
                    ),
                  )
                }
              />
            </Field>
            <Field label="آدرس مقصد">
              <input
                dir="ltr"
                value={item.href}
                placeholder="/products"
                maxLength={1000}
                onChange={(event) =>
                  onChange(
                    items.map((row, i) =>
                      i === index ? { ...row, href: event.target.value } : row,
                    ),
                  )
                }
              />
            </Field>
          </div>
          <Field label="ظاهر">
            <DashboardSelect
              value={item.style}
              onChange={(event) =>
                onChange(
                  items.map((row, i) =>
                    i === index ? { ...row, style: event.target.value } : row,
                  ),
                )
              }
            >
              <option value="primary">رنگی</option>
              <option value="outline">خط دور</option>
            </DashboardSelect>
          </Field>
        </div>
      ))}
      {items.length < 4 && (
        <button
          className="pbe-soft"
          type="button"
          onClick={() =>
            onChange([
              ...items,
              { label: "دکمهٔ جدید", href: "/products", style: "primary" },
            ])
          }
        >
          + افزودن دکمه
        </button>
      )}
    </div>
  );
}
function ImageField({ id, images, onUpload, busy, onRemove }) {
  return (
    <div className="pbe-image-field">
      {id && images[id] && (
        <img src={images[id]} alt="پیش‌نمایش تصویر انتخابی" />
      )}
      <label className="pbe-upload">
        {busy ? "در حال بارگذاری…" : id ? "تغییر تصویر" : "انتخاب تصویر"}
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          disabled={busy}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) onUpload(file);
            event.target.value = "";
          }}
        />
      </label>
      <small>JPG، PNG یا WebP؛ حداکثر ۵ مگابایت</small>
      {id && (
        <button type="button" className="pbe-link" onClick={onRemove}>
          حذف تصویر از این بخش
        </button>
      )}
    </div>
  );
}
function BlockFields({ block, images, update, upload, busy }) {
  const d = block.data;
  return (
    <div className="pbe-block-fields">
      {block.type === "hero" && (
        <>
          <Field label="عنوان بنر">
            <input
              value={d.title}
              maxLength={160}
              onChange={(event) => update({ title: event.target.value })}
            />
          </Field>
          <Field label="توضیح">
            <textarea
              rows={3}
              value={d.text}
              maxLength={2000}
              onChange={(event) => update({ text: event.target.value })}
            />
          </Field>
          <ImageField
            id={d.image_id}
            images={images}
            busy={busy}
            onUpload={upload}
            onRemove={() => update({ image_id: null })}
          />
          <ButtonFields
            items={d.buttons}
            onChange={(buttons) => update({ buttons })}
          />
        </>
      )}
      {block.type === "text" && (
        <>
          <Field label="عنوان بخش، اختیاری">
            <input
              value={d.heading}
              maxLength={160}
              onChange={(event) => update({ heading: event.target.value })}
            />
          </Field>
          <Field label="متن">
            <textarea
              rows={7}
              value={d.body}
              maxLength={15000}
              onChange={(event) => update({ body: event.target.value })}
            />
          </Field>
          <Field label="چیدمان">
            <DashboardSelect
              value={d.align}
              onChange={(event) => update({ align: event.target.value })}
            >
              <option value="right">راست‌چین</option>
              <option value="center">وسط‌چین</option>
            </DashboardSelect>
          </Field>
        </>
      )}
      {block.type === "image" && (
        <>
          <ImageField
            id={d.image_id}
            images={images}
            busy={busy}
            onUpload={upload}
            onRemove={() => update({ image_id: null })}
          />
          <Field
            label="توضیح تصویر برای دسترس‌پذیری"
            hint="مثلاً: نمای ورودی فروشگاه"
          >
            <input
              value={d.alt}
              maxLength={250}
              onChange={(event) => update({ alt: event.target.value })}
            />
          </Field>
          <Field label="زیرنویس، اختیاری">
            <input
              value={d.caption}
              maxLength={500}
              onChange={(event) => update({ caption: event.target.value })}
            />
          </Field>
          {!block.enabled && (
            <p className="pbe-hint">
              بعد از انتخاب تصویر و نوشتن توضیح، بخش را روشن کنید.
            </p>
          )}
        </>
      )}
      {block.type === "buttons" && (
        <ButtonFields items={d.items} onChange={(items) => update({ items })} />
      )}
      {block.type === "spacer" && (
        <Field label="ارتفاع فاصله">
          <DashboardSelect
            value={d.height}
            onChange={(event) => update({ height: Number(event.target.value) })}
          >
            {[8, 16, 24, 32, 48, 64, 96, 120].map((height) => (
              <option key={height} value={height}>
                {height.toLocaleString("fa-IR")} پیکسل
              </option>
            ))}
          </DashboardSelect>
        </Field>
      )}
    </div>
  );
}
function Preview({ page, onClose }) {
  const [mobile, setMobile] = useState(false);
  const close = useRef(null);
  const dialog = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    close.current?.focus();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    function keys(event) {
      if (event.key === "Escape") onClose();
      if (event.key === "Tab") {
        const focusable = [
          ...dialog.current.querySelectorAll(
            'button,a[href],input,select,textarea,[tabindex="0"]',
          ),
        ].filter((el) => !el.disabled);
        if (!focusable.length) return;
        if (event.shiftKey && document.activeElement === focusable[0]) {
          event.preventDefault();
          focusable.at(-1).focus();
        } else if (
          !event.shiftKey &&
          document.activeElement === focusable.at(-1)
        ) {
          event.preventDefault();
          focusable[0].focus();
        }
      }
    }
    document.addEventListener("keydown", keys);
    return () => {
      document.body.style.overflow = overflow;
      document.removeEventListener("keydown", keys);
      previous?.focus();
    };
  }, [onClose]);
  return (
    <div className="pbe-preview-backdrop">
      <section
        ref={dialog}
        className="pbe-preview-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="پیش‌نمایش صفحه"
      >
        <header>
          <div>
            <strong>پیش‌نمایش</strong>
            <small>
              پیش‌نمایش در قالب اصلی فروشگاه؛ این نسخه هنوز منتشر نشده است.
            </small>
          </div>
          <div>
            <button
              type="button"
              aria-pressed={!mobile}
              onClick={() => setMobile(false)}
            >
              دسکتاپ
            </button>
            <button
              type="button"
              aria-pressed={mobile}
              onClick={() => setMobile(true)}
            >
              موبایل
            </button>
            <button type="button" ref={close} onClick={onClose}>
              بستن ×
            </button>
          </div>
        </header>
        <div className="pbe-preview-scroll">
          <div className={`pbe-preview-canvas ${mobile ? "is-mobile" : ""}`}>
            <PreviewFrame mobile={mobile}>
              <StoreLayout
                preview
                linksOverride={
                  page.footer_visible !== false
                    ? [
                        {
                          title:
                            page.footer_label || page.title || "صفحهٔ جدید",
                          url: "#page",
                        },
                      ]
                    : []
                }
              >
                <main id="sf-main" className="sf-container">
                  <PageContent page={page} images={page.images} preview />
                </main>
              </StoreLayout>
            </PreviewFrame>
          </div>
        </div>
      </section>
    </div>
  );
}

export default function PageManager({ resource, revision }) {
  const [rows, setRows] = useState([]);
  const [listPage, setListPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [page, setPage] = useState(null);
  const [baseline, setBaseline] = useState("");
  const [preview, setPreview] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const mounted = useRef(false);
  const lock = useRef(false);
  const drag = useRef(null);
  const uncertainCreate = useRef(false);
  const newBlock = useRef(null);
  const dirty = page !== null && JSON.stringify(payload(page)) !== baseline;
  const editable = page?.id
    ? Boolean(resource.capabilities?.change)
    : Boolean(resource.capabilities?.add);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    pageRequest(`?${new URLSearchParams({ page: listPage, search })}`, {
      signal: controller.signal,
    })
      .then((data) => {
        if (active) {
          setRows(data.results);
          setHasNext(Boolean(data.next));
        }
      })
      .catch((err) => {
        if (active && err.name !== "AbortError") setError(err.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [listPage, search, refresh, revision]);
  useEffect(() => {
    if (!dirty) return undefined;
    function leave(event) {
      event.preventDefault();
      event.returnValue = "";
    }
    window.addEventListener("beforeunload", leave);
    function protect(event) {
      const link = event.target.closest?.("a[href]");
      if (
        link &&
        !link.closest(".pbe-preview-dialog") &&
        !window.confirm("تغییرات ذخیره نشده‌اند. از صفحه خارج می‌شوید؟")
      ) {
        event.preventDefault();
        event.stopPropagation();
      }
    }
    document.addEventListener("click", protect, true);
    return () => {
      window.removeEventListener("beforeunload", leave);
      document.removeEventListener("click", protect, true);
    };
  }, [dirty]);
  useEffect(() => {
    if (expanded === newBlock.current) {
      document
        .getElementById(`pbe-${expanded}`)
        ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      newBlock.current = null;
    }
  }, [expanded]);
  function accept(saved) {
    setPage(saved);
    setBaseline(JSON.stringify(payload(saved)));
    setRefresh((value) => value + 1);
    uncertainCreate.current = false;
  }
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
            ? "نسخهٔ جدیدتری از صفحه ذخیره شده. نوشته‌های فعلی را کپی کنید و «دریافت نسخهٔ ذخیره‌شده» را بزنید؛ تغییرات شما خودکار بازنویسی نمی‌شوند."
            : err.message,
        );
    } finally {
      lock.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  function open(id) {
    return perform(async () => {
      const data = await pageRequest(`${id}/`);
      if (mounted.current) {
        accept(data);
        setExpanded(data.blocks[0]?.id || null);
      }
    });
  }
  function back() {
    if (
      busy ||
      (dirty && !window.confirm("تغییرات ذخیره نشده‌اند. به فهرست برگردیم؟"))
    )
      return;
    setPage(null);
    setError("");
    setNotice("");
    setRefresh((value) => value + 1);
  }
  async function saveCurrent() {
    if (!editable) throw new Error("مجوز ویرایش ندارید.");
    if (uncertainCreate.current)
      throw new Error(
        "نتیجهٔ ساخت قبلی نامشخص است؛ ابتدا به فهرست برگردید و وجود صفحه را بررسی کنید.",
      );
    if (!page.title.trim()) throw new Error("عنوان صفحه را بنویسید.");
    try {
      const saved = await writePage(
        page.id ? `${page.id}/` : "",
        payload(page),
        page.id ? "PATCH" : "POST",
      );
      if (mounted.current) accept(saved);
      return saved;
    } catch (err) {
      if (!page.id && !err.status) uncertainCreate.current = true;
      throw err;
    }
  }
  function save() {
    return perform(async () => {
      await saveCurrent();
      if (mounted.current)
        setNotice(
          "پیش‌نویس ذخیره شد. برای نمایش تغییرات در سایت، انتشار را بزنید.",
        );
    });
  }
  function publish() {
    return perform(async () => {
      const saved = dirty || !page.id ? await saveCurrent() : page;
      const published = await writePage(`${saved.id}/publish/`, {
        revision: saved.revision,
      });
      if (mounted.current) {
        accept(published);
        setNotice("صفحه منتشر شد و در پیوندهای پایین فروشگاه قرار گرفت.");
      }
    });
  }
  function hide() {
    if (
      !window.confirm(
        "صفحه از دسترس عمومی خارج شود؟ محتوای ذخیره‌شده باقی می‌ماند.",
      )
    )
      return;
    return perform(async () => {
      const saved = await writePage(`${page.id}/hide/`, {
        revision: page.revision,
      });
      if (mounted.current) {
        accept(saved);
        setNotice("صفحه غیرفعال شد؛ بازدیدکننده دیگر به آن دسترسی ندارد.");
      }
    });
  }
  function patch(values) {
    setPage((current) => ({ ...current, ...values }));
  }
  function patchBlock(id, data) {
    setPage((current) => ({
      ...current,
      blocks: current.blocks.map((block) =>
        block.id === id
          ? { ...block, data: { ...block.data, ...data } }
          : block,
      ),
    }));
  }
  function add(type) {
    const block = makeBlock(type);
    patch({ blocks: [...page.blocks, block] });
    newBlock.current = block.id;
    setExpanded(block.id);
  }
  async function upload(id, file) {
    if (file.size > 5 * 1024 * 1024) {
      setError("تصویر باید حداکثر ۵ مگابایت باشد.");
      return;
    }
    return perform(async () => {
      const body = new FormData();
      body.set("image", file);
      const image = await pageRequest("images/", { method: "POST", body });
      if (mounted.current)
        setPage((current) => ({
          ...current,
          images: { ...current.images, [image.id]: image.url },
          blocks: current.blocks.map((block) =>
            block.id === id
              ? { ...block, data: { ...block.data, image_id: image.id } }
              : block,
          ),
        }));
    });
  }
  const closePreview = useRef(() => setPreview(false)).current;
  if (!page)
    return (
      <section className="pbe-manager" dir="rtl">
        <div className="pbe-intro">
          <div>
            <span className="pbe-eyebrow">محتوای فروشگاه</span>
            <h2>صفحه‌های سایت</h2>
            <p>دربارهٔ ما، راهنمای خرید یا هر صفحهٔ محتوایی دیگر را بسازید.</p>
          </div>
          {resource.capabilities?.add && (
            <button
              className="pbe-primary"
              disabled={busy}
              onClick={() => {
                const draft = newPage();
                setPage(draft);
                setBaseline(JSON.stringify(payload(draft)));
                setError("");
                setNotice("");
                uncertainCreate.current = false;
              }}
            >
              + صفحهٔ جدید
            </button>
          )}
        </div>
        {error && (
          <p className="pbe-error" role="alert">
            {error}
            <button onClick={() => setRefresh((value) => value + 1)}>
              تلاش دوباره
            </button>
          </p>
        )}
        <form
          className="pbe-search"
          onSubmit={(event) => {
            event.preventDefault();
            setSearch(query.trim());
            setListPage(1);
          }}
        >
          <input
            type="search"
            aria-label="جست‌وجوی صفحه"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="نام صفحه را پیدا کنید…"
          />
          <button className="pbe-soft">جست‌وجو</button>
        </form>
        {loading ? (
          <p className="pbe-empty" role="status">
            در حال دریافت صفحه‌ها…
          </p>
        ) : rows.length ? (
          <div className="pbe-page-list">
            {rows.map((row) => (
              <article key={row.id}>
                <div>
                  <span
                    className={`pbe-status ${row.is_published ? "is-live" : ""}`}
                  >
                    {row.is_published ? "منتشرشده" : "غیرفعال / پیش‌نویس"}
                  </span>
                  <h3>{row.title}</h3>
                  <small dir="ltr">{decodeURIComponent(row.url)}</small>
                  {row.has_changes && (
                    <p className="pbe-hint">تغییرات منتشرنشده دارد</p>
                  )}
                </div>
                <div className="pbe-list-actions">
                  <button
                    className="pbe-soft"
                    disabled={busy}
                    onClick={() => open(row.id)}
                  >
                    {resource.capabilities?.change ? "ویرایش صفحه" : "مشاهده"}
                  </button>
                  {row.is_published && (
                    <a href={row.url} target="_blank" rel="noopener noreferrer">
                      دیدن در سایت ↗
                    </a>
                  )}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="pbe-empty">
            <h3>{search ? "صفحه‌ای پیدا نشد" : "اولین صفحه‌ات را بساز"}</h3>
            <p>با بخش‌های آماده، بدون نوشتن کد.</p>
          </div>
        )}
        <nav className="pbe-pagination" aria-label="صفحه‌بندی">
          <button
            disabled={loading || listPage === 1}
            onClick={() => setListPage((value) => value - 1)}
          >
            قبلی
          </button>
          <span>{listPage.toLocaleString("fa-IR")}</span>
          <button
            disabled={loading || !hasNext}
            onClick={() => setListPage((value) => value + 1)}
          >
            بعدی
          </button>
        </nav>
      </section>
    );
  return (
    <section className="pbe-manager" dir="rtl">
      <div className="pbe-editor-bar">
        <button className="pbe-link" disabled={busy} onClick={back}>
          → همهٔ صفحه‌ها
        </button>
        <div className="pbe-save-state" role="status">
          {busy
            ? "در حال انجام…"
            : dirty
              ? "تغییرات ذخیره نشده"
              : page.id
                ? "نسخهٔ ذخیره‌شده"
                : "صفحهٔ جدید"}
        </div>
        <div className="pbe-editor-actions">
          <button
            className="pbe-soft"
            disabled={busy}
            onClick={() => setPreview(true)}
          >
            پیش‌نمایش
          </button>
          {editable && (
            <button
              className="pbe-soft"
              disabled={busy || (Boolean(page.id) && !dirty)}
              onClick={save}
            >
              ذخیرهٔ پیش‌نویس
            </button>
          )}
          {resource.capabilities?.publish && (
            <button
              className="pbe-primary"
              disabled={busy || (!editable && dirty)}
              onClick={publish}
            >
              {page.is_published ? "انتشار تغییرات" : "انتشار صفحه"}
            </button>
          )}
        </div>
      </div>
      {error && (
        <p className="pbe-error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="pbe-notice" role="status">
          {notice}
        </p>
      )}
      <div className="pbe-editor-layout">
        <div className="pbe-main">
          <fieldset disabled={busy || !editable} className="pbe-title-box">
            <Field label="عنوان صفحه">
              <input
                className="pbe-title-input"
                value={page.title}
                maxLength={160}
                placeholder="مثلاً دربارهٔ ما"
                onChange={(event) => patch({ title: event.target.value })}
              />
            </Field>
          </fieldset>
          <section className="pbe-title-box">
            <h3>چیدمان آماده</h3>
            <div className="st-template-buttons">
              {[
                ["simple", "صفحهٔ ساده"],
                ["about", "دربارهٔ ما"],
                ["landing", "تبلیغاتی"],
              ].map(([layout, label]) => (
                <button
                  type="button"
                  key={layout}
                  disabled={busy || !editable}
                  className={
                    (page.layout || "simple") === layout ? "is-active" : ""
                  }
                  onClick={() => {
                    const types =
                      layout === "about"
                        ? ["hero", "text", "buttons"]
                        : layout === "landing"
                          ? ["hero", "image", "text", "buttons"]
                          : ["text"];
                    patch({
                      layout,
                      ...(!page.blocks.length
                        ? { blocks: types.map(makeBlock) }
                        : {}),
                    });
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
            <small>
              انتخاب چیدمان، محتوای فعلی را حذف نمی‌کند؛ برای صفحهٔ خالی بخش‌های
              آماده می‌سازد.
            </small>
          </section>
          <div className="pbe-blocks-heading">
            <h3>محتوای صفحه</h3>
            <p>
              بخش‌ها را اضافه کنید؛ با ↑ ↓ یا کشیدن دستگیره ترتیب را عوض کنید.
            </p>
          </div>
          {!page.blocks.length && (
            <div className="pbe-empty pbe-empty-blocks">
              <b>از یک بنر یا متن شروع کنید</b>
              <p>
                هر بخش تنظیمات خودش را دارد و می‌توانید جداگانه خاموشش کنید.
              </p>
            </div>
          )}
          <div className="pbe-block-list">
            {page.blocks.map((block, index) => (
              <article
                id={`pbe-${block.id}`}
                key={block.id}
                className={`pbe-block ${!block.enabled ? "is-off" : ""}`}
                onDragOver={(event) => {
                  if (editable && !busy) event.preventDefault();
                }}
                onDrop={(event) => {
                  event.preventDefault();
                  if (drag.current == null || busy || !editable) return;
                  const from = page.blocks.findIndex(
                    (item) => item.id === drag.current,
                  );
                  if (from >= 0)
                    patch({ blocks: move(page.blocks, from, index) });
                  drag.current = null;
                }}
              >
                <header>
                  <button
                    className="pbe-drag"
                    type="button"
                    draggable={editable && !busy}
                    disabled={!editable || busy}
                    aria-label="دستگیرهٔ جابه‌جایی؛ از دکمه‌های بالا و پایین هم می‌توانید استفاده کنید"
                    onDragStart={(event) => {
                      drag.current = block.id;
                      event.dataTransfer.setData("text/plain", block.id);
                      event.dataTransfer.effectAllowed = "move";
                    }}
                    onDragEnd={() => {
                      drag.current = null;
                    }}
                  >
                    ⠿
                  </button>
                  <button
                    className="pbe-block-toggle"
                    type="button"
                    aria-expanded={expanded === block.id}
                    aria-controls={`fields-${block.id}`}
                    onClick={() =>
                      setExpanded(expanded === block.id ? null : block.id)
                    }
                  >
                    <span>{labelFor(block.type)}</span>
                    <small>
                      {block.data.heading ||
                        block.data.title ||
                        block.data.caption ||
                        `بخش ${(index + 1).toLocaleString("fa-IR")}`}
                    </small>
                  </button>
                  <div className="pbe-block-actions">
                    <button
                      type="button"
                      disabled={!editable || busy || index === 0}
                      aria-label="بخش بالاتر"
                      onClick={() =>
                        patch({ blocks: move(page.blocks, index, index - 1) })
                      }
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      disabled={
                        !editable || busy || index === page.blocks.length - 1
                      }
                      aria-label="بخش پایین‌تر"
                      onClick={() =>
                        patch({ blocks: move(page.blocks, index, index + 1) })
                      }
                    >
                      ↓
                    </button>
                    <button
                      className={block.enabled ? "pbe-on" : ""}
                      type="button"
                      aria-pressed={block.enabled}
                      disabled={!editable || busy}
                      onClick={() =>
                        patch({
                          blocks: page.blocks.map((item) =>
                            item.id === block.id
                              ? { ...item, enabled: !item.enabled }
                              : item,
                          ),
                        })
                      }
                    >
                      {block.enabled ? "روشن" : "خاموش"}
                    </button>
                  </div>
                </header>
                {expanded === block.id && (
                  <div id={`fields-${block.id}`}>
                    <fieldset disabled={!editable || busy}>
                      <BlockFields
                        block={block}
                        images={page.images}
                        busy={busy}
                        update={(data) => patchBlock(block.id, data)}
                        upload={(file) => upload(block.id, file)}
                      />
                    </fieldset>
                    <div className="pbe-block-bottom">
                      <button
                        type="button"
                        disabled={!editable || busy || page.blocks.length >= 60}
                        onClick={() => {
                          const copy = {
                            ...structuredClone(block),
                            id: crypto.randomUUID(),
                          };
                          patch({
                            blocks: [
                              ...page.blocks.slice(0, index + 1),
                              copy,
                              ...page.blocks.slice(index + 1),
                            ],
                          });
                          setExpanded(copy.id);
                        }}
                      >
                        تکثیر بخش
                      </button>
                      <button
                        className="pbe-danger"
                        type="button"
                        disabled={!editable || busy}
                        onClick={() => {
                          if (window.confirm("این بخش حذف شود؟"))
                            patch({
                              blocks: page.blocks.filter(
                                (item) => item.id !== block.id,
                              ),
                            });
                        }}
                      >
                        حذف بخش
                      </button>
                    </div>
                  </div>
                )}
              </article>
            ))}
          </div>
          {editable && (
            <section className="pbe-add-block">
              <h3>+ افزودن بخش</h3>
              <div>
                {TYPES.map((item) => (
                  <button
                    key={item.type}
                    type="button"
                    disabled={busy || page.blocks.length >= 60}
                    onClick={() => add(item.type)}
                  >
                    <strong>{item.name}</strong>
                    <small>{item.hint}</small>
                  </button>
                ))}
              </div>
            </section>
          )}
        </div>
        <aside className="pbe-settings">
          <section>
            <h3>وضعیت صفحه</h3>
            <span
              className={`pbe-status ${page.is_published ? "is-live" : ""}`}
            >
              {page.is_published
                ? "در سایت نمایش داده می‌شود"
                : "در سایت نمایش داده نمی‌شود"}
            </span>
            <p>
              ذخیرهٔ پیش‌نویس، نسخهٔ عمومی را تغییر نمی‌دهد. برای نمایش تغییرات
              «انتشار» را بزنید.
            </p>
            {page.is_published && (
              <>
                <a href={page.url} target="_blank" rel="noopener noreferrer">
                  دیدن نسخهٔ عمومی ↗
                </a>
                {resource.capabilities?.publish && (
                  <button
                    className="pbe-danger pbe-hide"
                    disabled={busy || dirty}
                    onClick={hide}
                  >
                    غیرفعال کردن صفحه
                  </button>
                )}
                {dirty && (
                  <small>
                    برای غیرفعال‌سازی ابتدا تغییرات را ذخیره یا نسخهٔ ذخیره‌شده
                    را دریافت کنید.
                  </small>
                )}
              </>
            )}
          </section>
          <section>
            <h3>دکمهٔ بالای فوتر</h3>
            <fieldset disabled={busy || !editable}>
              <Field label="نمایش لینک این صفحه در بالای فوتر">
                <input
                  type="checkbox"
                  checked={page.footer_visible ?? true}
                  onChange={(event) =>
                    patch({ footer_visible: event.target.checked })
                  }
                />
              </Field>
              <Field label="متن دکمه، اختیاری">
                <input
                  value={page.footer_label || ""}
                  maxLength={80}
                  placeholder={page.title || "عنوان صفحه"}
                  onChange={(event) =>
                    patch({ footer_label: event.target.value })
                  }
                />
              </Field>
              <Field
                label="ترتیب نمایش"
                hint="عدد کمتر، زودتر نمایش داده می‌شود."
              >
                <input
                  type="number"
                  min="0"
                  max="9999"
                  value={page.footer_order || 0}
                  onChange={(event) =>
                    patch({ footer_order: Number(event.target.value) })
                  }
                />
              </Field>
            </fieldset>
            <small>این تنظیمات بعد از انتشار صفحه در سایت اعمال می‌شوند.</small>
          </section>
          <section>
            <h3>آدرس و جست‌وجو</h3>
            <fieldset disabled={busy || !editable}>
              <Field
                label="نامک صفحه"
                hint={
                  page.slug_locked
                    ? "پس از اولین انتشار، ثابت می‌ماند تا لینک خراب نشود."
                    : "اختیاری؛ خالی باشد از عنوان ساخته می‌شود."
                }
              >
                <input
                  value={page.slug}
                  maxLength={120}
                  disabled={page.slug_locked}
                  onChange={(event) => patch({ slug: event.target.value })}
                />
              </Field>
              {page.url && (
                <small className="pbe-url" dir="ltr">
                  {decodeURIComponent(page.url)}
                </small>
              )}
              <Field label="عنوان SEO، اختیاری">
                <input
                  value={page.seo_title}
                  maxLength={180}
                  onChange={(event) => patch({ seo_title: event.target.value })}
                />
              </Field>
              <Field label="توضیح SEO، اختیاری">
                <textarea
                  rows={4}
                  value={page.seo_description}
                  maxLength={320}
                  onChange={(event) =>
                    patch({ seo_description: event.target.value })
                  }
                />
              </Field>
            </fieldset>
          </section>
          {page.id && (
            <button
              className="pbe-soft"
              disabled={busy}
              onClick={() => {
                if (
                  !dirty ||
                  window.confirm("تغییرات ذخیره‌نشده کنار گذاشته شوند؟")
                )
                  open(page.id);
              }}
            >
              دریافت نسخهٔ ذخیره‌شده
            </button>
          )}
          <p className="pbe-hint">
            این بخش برای صفحه‌های محتوایی است؛ سبد خرید و پرداخت از اینجا تغییر
            نمی‌کنند.
          </p>
        </aside>
      </div>
      {preview && <Preview page={page} onClose={closePreview} />}
    </section>
  );
}
