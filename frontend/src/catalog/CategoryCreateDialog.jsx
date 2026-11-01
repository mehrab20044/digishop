import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "./api";
import "./category-create-dialog.css";

export default function CategoryCreateDialog({
  choices,
  onSaved,
  parentId,
  ParentSelect,
  fixedParentLabel,
  triggerLabel = "+ ساخت دستهٔ جدید",
  triggerClassName = "cw-text",
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [parent, setParent] = useState(parentId ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const dialog = useRef(null);
  const firstInput = useRef(null);
  const trigger = useRef(null);
  const lock = useRef(false);
  const id = useId();

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    firstInput.current?.focus();
    function keydown(event) {
      // The category picker owns Escape and navigation while its popup is open.
      if (document.querySelector(".ds-popup")) return;
      if (event.key === "Escape") {
        event.preventDefault();
        if (!lock.current) setOpen(false);
      }
      if (event.key !== "Tab") return;
      const nodes = [
        ...dialog.current.querySelectorAll(
          'button:not(:disabled), input:not(:disabled), [tabindex="0"]',
        ),
      ].filter(
        (node) =>
          node.getClientRects().length &&
          node.getAttribute("aria-hidden") !== "true",
      );
      const first = nodes[0],
        last = nodes.at(-1);
      if (
        event.shiftKey &&
        (document.activeElement === first ||
          !dialog.current.contains(document.activeElement))
      ) {
        event.preventDefault();
        last?.focus();
      } else if (
        !event.shiftKey &&
        (document.activeElement === last ||
          !dialog.current.contains(document.activeElement))
      ) {
        event.preventDefault();
        first?.focus();
      }
    }
    document.addEventListener("keydown", keydown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", keydown);
      trigger.current?.focus();
    };
  }, [open]);

  async function save(event) {
    event.preventDefault();
    if (lock.current) return;
    const cleanName = name.trim(),
      cleanSlug = slug.trim();
    if (!cleanName) {
      setError("نام دسته را وارد کنید.");
      firstInput.current?.focus();
      return;
    }
    if (cleanSlug && !/^[\p{L}\p{M}\p{N}_-]+$/u.test(cleanSlug)) {
      setError(
        "نامک نباید فاصله، اسلش یا علامت‌های آدرس داشته باشد؛ مثلاً mens-shirts.",
      );
      return;
    }
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      const row = await api("categories/create/", {
        name: cleanName,
        slug: cleanSlug,
        parent_id: parent,
      });
      await onSaved(row);
      setOpen(false);
      setName("");
      setSlug("");
    } catch (err) {
      setError(err.message || "ساخت دسته انجام نشد.");
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  return (
    <>
      <button
        ref={trigger}
        type="button"
        className={triggerClassName}
        onClick={() => {
          setError("");
          setParent(parentId ?? null);
          setOpen(true);
        }}
      >
        {triggerLabel}
      </button>
      {open &&
        createPortal(
          <div
            className="ccd-overlay"
            onClick={(event) => {
              if (event.target === event.currentTarget && !lock.current)
                setOpen(false);
            }}
          >
            <section
              ref={dialog}
              role="dialog"
              aria-modal="true"
              aria-labelledby={`${id}-title`}
              aria-describedby={`${id}-hint`}
              className="ccd-dialog"
              dir="rtl"
            >
              <header className="ccd-header">
                <div>
                  <span className="ccd-eyebrow">مدیریت دسته‌بندی</span>
                  <h2 id={`${id}-title`}>دستهٔ جدید</h2>
                </div>
                <button
                  type="button"
                  className="ccd-close"
                  aria-label="بستن پنجرهٔ ساخت دسته"
                  disabled={busy}
                  onClick={() => setOpen(false)}
                >
                  ×
                </button>
              </header>
              <p id={`${id}-hint`} className="ccd-hint">
                دسته را همین‌جا بساز؛ بعد از ذخیره، در فرم اصلی انتخاب می‌شود.
              </p>
              <form onSubmit={save}>
                <fieldset disabled={busy} className="ccd-fields">
                  <label htmlFor={`${id}-name`}>
                    نام دسته <span>الزامی</span>
                  </label>
                  <input
                    ref={firstInput}
                    id={`${id}-name`}
                    required
                    maxLength={100}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="مثلاً پیراهن مردانه"
                  />
                  <label>
                    دستهٔ والد <span>اختیاری</span>
                  </label>
                  {fixedParentLabel ? (
                    <div className="ccd-url">{fixedParentLabel}</div>
                  ) : (
                    <ParentSelect
                      rows={choices.categories}
                      value={parent}
                      onChange={setParent}
                    />
                  )}
                  <small>
                    {fixedParentLabel
                      ? "دستهٔ جدید در همین بخش ساخته می‌شود."
                      : "برای ساخت دستهٔ اصلی، والد را خالی بگذار."}
                  </small>
                  <label htmlFor={`${id}-slug`}>
                    نامک آدرس <span>اختیاری</span>
                  </label>
                  <input
                    id={`${id}-slug`}
                    maxLength={120}
                    dir="ltr"
                    value={slug}
                    autoCapitalize="none"
                    spellCheck={false}
                    onChange={(e) => setSlug(e.target.value)}
                    placeholder="mens-shirts"
                    aria-describedby={`${id}-slug-help`}
                  />
                  <small id={`${id}-slug-help`}>
                    خالی بگذاری، سرور نامک می‌سازد. برای جداکردن کلمات از خط
                    تیره استفاده کن.
                  </small>
                  {slug.trim() && (
                    <div className="ccd-url">
                      نامک انتخاب‌شده: <bdi>{slug.trim()}</bdi>
                    </div>
                  )}
                </fieldset>
                {error && (
                  <p role="alert" className="ccd-error">
                    {error}
                  </p>
                )}
                <footer className="ccd-actions">
                  <button
                    className="ccd-save"
                    type="submit"
                    disabled={busy || !name.trim()}
                  >
                    {busy ? "در حال ذخیره…" : "ساخت و انتخاب دسته"}
                  </button>
                  <button
                    className="ccd-cancel"
                    type="button"
                    disabled={busy}
                    onClick={() => setOpen(false)}
                  >
                    انصراف
                  </button>
                </footer>
              </form>
            </section>
          </div>,
          document.body,
        )}
    </>
  );
}
