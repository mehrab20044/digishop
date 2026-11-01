import { useEffect, useId, useRef, useState } from "react";
import "./category-card-dialog.css";

const normalize = (value) =>
  String(value || "")
    .replace(/ي/g, "ی")
    .replace(/ك/g, "ک")
    .replace(/\u200c/g, " ")
    .trim()
    .toLowerCase();
export function categoryCardPath(rows, value) {
  const seen = new Set(),
    path = [];
  let row = rows.find((item) => item.value === value);
  while (row && !seen.has(row.value)) {
    seen.add(row.value);
    path.unshift(row);
    row = rows.find((item) => item.value && item.value === row.parent);
  }
  return path;
}
export default function CategoryCardDialog({
  rows,
  label,
  onChoose,
  onClose,
  renderCreate,
  multiple,
  nested,
}) {
  const initial = rows.find((row) => row.selected && row.value);
  const [current, setCurrent] = useState(initial?.value || "");
  const [query, setQuery] = useState("");
  const shell = useRef(null),
    search = useRef(null),
    body = useRef(null);
  const id = useId();
  const categories = rows.filter((row) => row.value);
  const node = categories.find((row) => row.value === current);
  const path = categoryCardPath(categories, current);
  const roots = categories.filter(
    (row) => !categories.some((parent) => parent.value === row.parent),
  );
  const children = node
    ? categories.filter((row) => row.parent === node.value)
    : roots;
  const results = query.trim()
    ? categories.filter((row) =>
        normalize(
          categoryCardPath(categories, row.value)
            .map((part) => part.label)
            .join(" "),
        ).includes(normalize(query)),
      )
    : children;
  const empty = rows.find((row) => !row.value && !row.disabled);

  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    search.current?.focus();
    return () => {
      document.body.style.overflow = previous;
    };
  }, []);
  useEffect(() => {
    if (body.current) body.current.scrollTop = 0;
  }, [current, query]);
  function navigate(value) {
    setCurrent(value);
    setQuery("");
    search.current?.focus();
  }
  function key(event) {
    // Portal events bubble through the original select: the card dialog owns its keys.
    if (event.target.closest?.(".ccd-dialog")) return;
    event.stopPropagation();
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
    }
    if (event.key === "Tab") {
      const nodes = [
        ...shell.current.querySelectorAll(
          'button:not(:disabled),input:not(:disabled),[tabindex="0"]',
        ),
      ].filter((el) => el.getClientRects().length);
      const first = nodes[0],
        last = nodes.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
  }
  return (
    <div
      className="dcc-overlay"
      style={nested ? { zIndex: 2147472000 } : undefined}
      onKeyDown={key}
      onClick={(event) => {
        event.stopPropagation();
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="dcc-dialog"
        ref={shell}
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${id}-title`}
        aria-describedby={`${id}-hint`}
        dir="rtl"
      >
        <header className="dcc-head">
          <div>
            <h2 id={`${id}-title`}>{label || "انتخاب دسته‌بندی"}</h2>
            <p id={`${id}-hint`}>
              وارد شاخه شو؛ سپس «انتخاب همین دسته» را بزن.
            </p>
          </div>
          <button
            type="button"
            className="dcc-close"
            aria-label="بستن انتخاب دسته"
            onClick={onClose}
          >
            ×
          </button>
        </header>
        <div className="dcc-navigation">
          <nav aria-label="مسیر دسته‌بندی">
            <button type="button" onClick={() => navigate("")}>
              همهٔ دسته‌ها
            </button>
            {path.map((part) => (
              <span key={part.value}>
                <span aria-hidden="true">‹</span>
                <button
                  type="button"
                  aria-current={part.value === current ? "location" : undefined}
                  onClick={() => navigate(part.value)}
                >
                  {part.label}
                </button>
              </span>
            ))}
          </nav>
          <button
            className="dcc-back"
            type="button"
            disabled={!node}
            onClick={() => navigate(path.at(-2)?.value || "")}
          >
            بازگشت ←
          </button>
        </div>
        <div className="dcc-search">
          <svg
            viewBox="0 0 24 24"
            width="20"
            height="20"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.7"
            aria-hidden="true"
          >
            <circle cx="10" cy="10" r="6" />
            <path d="m15 15 5 5" />
          </svg>
          <input
            ref={search}
            type="search"
            value={query}
            aria-label="جست‌وجوی دسته‌بندی"
            placeholder="جست‌وجوی دسته‌بندی…"
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div className="dcc-body" ref={body}>
          <div className="dcc-heading">
            <h3>
              {query.trim()
                ? "نتیجهٔ جست‌وجو"
                : node
                  ? `زیر‌دسته‌های ${node.label}`
                  : "دسته‌های اصلی"}
            </h3>
            <span>{results.length.toLocaleString("fa-IR")} دسته</span>
          </div>
          <div className="dcc-grid">
            {results.map((row) => {
              const count = categories.filter(
                (item) => item.parent === row.value,
              ).length;
              const ancestry = categoryCardPath(categories, row.value).slice(
                0,
                -1,
              );
              return (
                <button
                  key={row.value}
                  type="button"
                  className={`dcc-card ${row.selected ? "is-selected" : ""}`}
                  onClick={() => navigate(row.value)}
                  aria-label={`بازکردن ${row.label}`}
                >
                  <span className="dcc-art">
                    {row.image && /^(https?:\/\/|\/)(?!\/)/.test(row.image) ? (
                      <img
                        src={row.image}
                        alt=""
                        onError={(e) => {
                          e.currentTarget.hidden = true;
                        }}
                      />
                    ) : (
                      <svg
                        width="38"
                        height="38"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.2"
                        aria-hidden="true"
                      >
                        <path d="M3 5h6l2 2h10v12H3Z" />
                        <path d="M8 12h8M8 15h5" />
                      </svg>
                    )}
                  </span>
                  <span className="dcc-card-copy">
                    <strong>{row.label}</strong>
                    <small>
                      {query.trim() && ancestry.length
                        ? ancestry.map((p) => p.label).join(" ← ")
                        : count
                          ? `${count.toLocaleString("fa-IR")} زیر‌دسته`
                          : "مشاهده و انتخاب"}
                    </small>
                  </span>
                  <span className="dcc-card-arrow" aria-hidden="true">
                    ‹
                  </span>
                  {row.selected && (
                    <span
                      className="dcc-selected-mark"
                      aria-label="انتخاب فعلی"
                    >
                      ✓
                    </span>
                  )}
                </button>
              );
            })}
            {!query.trim() && renderCreate && (
              <div className="dcc-create">{renderCreate(node, onClose)}</div>
            )}
          </div>
          {!results.length && (
            <p className="dcc-empty" role="status">
              {query.trim()
                ? "دسته‌ای با این نام پیدا نشد."
                : node
                  ? "این دسته زیر‌شاخه‌ای ندارد؛ می‌توانی همین دسته را انتخاب کنی."
                  : "هنوز دسته‌ای ساخته نشده است."}
            </p>
          )}
        </div>
        <footer className="dcc-footer">
          <div className="dcc-current">
            <small>دستهٔ فعلی</small>
            <strong>{node?.label || "هنوز دسته‌ای انتخاب نشده"}</strong>
          </div>
          <div className="dcc-actions">
            <button
              type="button"
              className="dcc-confirm"
              disabled={!node || node.disabled}
              onClick={() => onChoose(node)}
            >
              {multiple && node?.selected
                ? "برداشتن این دسته"
                : "انتخاب همین دسته"}
            </button>
            {!multiple && empty && (
              <button
                type="button"
                className="dcc-clear"
                onClick={() => onChoose(empty)}
              >
                بدون دسته
              </button>
            )}
            <button type="button" className="dcc-cancel" onClick={onClose}>
              {multiple ? "پایان انتخاب" : "انصراف"}
            </button>
          </div>
        </footer>
      </section>
    </div>
  );
}
