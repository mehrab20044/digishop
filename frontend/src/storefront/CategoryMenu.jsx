import { useEffect, useId, useRef, useState } from "react";

import {
  categoryLink,
  flattenCategoryTree,
  loadCategoryTree,
  normalizeCategory,
  useCategoryTree,
} from "./category-data";

import "./category-dropdown.css";

function GridIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      aria-hidden="true"
    >
      <rect x="3" y="3" width="7" height="7" rx="2" />
      <rect x="14" y="3" width="7" height="7" rx="2" />
      <rect x="3" y="14" width="7" height="7" rx="2" />
      <rect x="14" y="14" width="7" height="7" rx="2" />
    </svg>
  );
}

export default function CategoryMenu() {
  const { data, error, loading, retry } = useCategoryTree();

  const [open, setOpen] = useState(false);
  const [rootId, setRootId] = useState(null);
  const [mobilePath, setMobilePath] = useState([]);
  const [query, setQuery] = useState("");

  const host = useRef(null);
  const trigger = useRef(null);
  const panel = useRef(null);
  const focusSearch = useRef(false);
  const panelId = useId();

  const roots = data || [];
  const flat = flattenCategoryTree(roots);
  const byId = new Map(flat.map((row) => [row.id, row]));

  const desktopRoot =
    byId.get(rootId) || byId.get(roots[0]?.id);

  const mobileCurrent = byId.get(mobilePath.at(-1));
  const mobileRows = mobileCurrent?.children || roots;

  const normalizedQuery = normalizeCategory(query);

  const results = normalizedQuery
    ? flat.filter((row) =>
        normalizeCategory(
          row.path.map((part) => part.name).join(" "),
        ).includes(normalizedQuery),
      )
    : [];

  function close(restoreFocus = false) {
    setOpen(false);

    if (restoreFocus) trigger.current?.focus();
  }

  function show() {
    setOpen(true);
    loadCategoryTree().catch(() => {});
  }

  function drillInto(node) {
    setMobilePath(
      byId.get(node.id)?.path.map((part) => part.id) || [node.id],
    );
    setQuery("");

    panel.current
      ?.querySelector(".dg-mobile-body")
      ?.scrollTo?.({ top: 0 });
  }

  useEffect(() => {
    if (!open) return;

    function outside(event) {
      if (!host.current?.contains(event.target)) {
        setOpen(false);
      }
    }

    function onKeyDown(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        trigger.current?.focus();
      }
    }

    function updateHeight() {
      const element = panel.current;
      if (!element) return;

      const viewport = window.visualViewport;
      const bottom = viewport
        ? viewport.height + viewport.offsetTop
        : window.innerHeight;

      const available = Math.max(
        120,
        bottom - element.getBoundingClientRect().top - 12,
      );

      element.style.setProperty("--dg-space", `${available}px`);
    }

    const frame = requestAnimationFrame(() => {
      updateHeight();

      if (focusSearch.current) {
        panel.current?.querySelector("input")?.focus();
        focusSearch.current = false;
      }
    });

    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", onKeyDown);
    window.addEventListener("resize", updateHeight);
    window.visualViewport?.addEventListener("resize", updateHeight);

    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("resize", updateHeight);
      window.visualViewport?.removeEventListener(
        "resize",
        updateHeight,
      );
    };
  }, [open]);

  return (
    <div className="dg-category" ref={host}>
      <button
        ref={trigger}
        type="button"
        className={`dg-trigger ${open ? "is-open" : ""}`}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => (open ? close() : show())}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            focusSearch.current = true;
            show();
          }
        }}
      >
        <GridIcon />
        <span>دسته‌بندی کالاها</span>
        <span className="dg-trigger-arrow" aria-hidden="true">
          ⌄
        </span>
      </button>

      {open && (
        <section
          ref={panel}
          id={panelId}
          className="dg-panel"
          aria-label="دسته‌بندی کالاها"
          onClick={(event) => {
            if (event.target.closest?.("a[href]")) close();
          }}
        >
          <div className="dg-panel-heading">
            <strong>دسته‌بندی کالاها</strong>
            <button
              className="dg-close"
              type="button"
              aria-label="بستن دسته‌بندی‌ها"
              onClick={() => close(true)}
            >
              ×
            </button>
          </div>

          <div className="dg-search">
            <svg
              width="19"
              height="19"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              aria-hidden="true"
            >
              <circle cx="10.5" cy="10.5" r="6.5" />
              <path d="m16 16 4 4" />
            </svg>

            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="پیدا کردن دسته‌بندی…"
              aria-label="جست‌وجو در دسته‌بندی‌ها"
              maxLength={100}
            />

            {query && (
              <button
                type="button"
                aria-label="پاک کردن جست‌وجو"
                onClick={() => setQuery("")}
              >
                ×
              </button>
            )}
          </div>

          {error && (
            <div className="dg-status" role="alert">
              <span>{error}</span>
              <button type="button" onClick={retry}>
                تلاش دوباره
              </button>
            </div>
          )}

          {data === null ? (
            <div className="dg-status" role="status">
              {loading ? "در حال دریافت دسته‌ها…" : "دسته‌ها دریافت نشدند."}
            </div>
          ) : normalizedQuery ? (
            <div className="dg-results">
              <p className="dg-result-count">
                {results.length.toLocaleString("fa-IR")} دسته پیدا شد
              </p>

              {results.map((row) => (
                <a
                  className="dg-result"
                  href={categoryLink("", row)}
                  key={row.id}
                >
                  <strong>{row.name}</strong>
                  <small>
                    {row.path.map((part) => part.name).join(" / ")}
                  </small>
                  <span aria-hidden="true">←</span>
                </a>
              ))}

              {!results.length && (
                <p className="dg-status">دسته‌ای با این نام پیدا نشد.</p>
              )}
            </div>
          ) : (
            <>
              <div className="dg-desktop">
                <nav className="dg-roots" aria-label="دسته‌های اصلی">
                  {roots.map((root, index) => (
                    <button
                      type="button"
                      key={root.id}
                      className={
                        desktopRoot?.id === root.id ? "is-active" : ""
                      }
                      aria-pressed={desktopRoot?.id === root.id}
                      
                      onClick={() => setRootId(root.id)}
                    >
                      <span className="dg-root-icon" aria-hidden="true">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      <span>{root.name}</span>
                      <span className="dg-root-arrow" aria-hidden="true">
                        ‹
                      </span>
                    </button>
                  ))}
                </nav>

                <div className="dg-branches" key={desktopRoot?.id}>
                  {desktopRoot && (
                    <>
                      <a
                        className="dg-view-all"
                        href={categoryLink("", desktopRoot)}
                      >
                        همهٔ محصولات {desktopRoot.name}
                        <span aria-hidden="true">←</span>
                      </a>

                      <div className="dg-columns">
                        {(desktopRoot.children || []).map((child) => (
                          <section className="dg-group" key={child.id}>
                            <a
                              className="dg-group-title"
                              href={categoryLink("", child)}
                            >
                              {child.name}
                              <span aria-hidden="true">‹</span>
                            </a>

                            {(child.children || []).map((grandchild) => (
                              <div
                                className="dg-subgroup"
                                key={grandchild.id}
                              >
                                <a href={categoryLink("", grandchild)}>
                                  {grandchild.name}
                                </a>

                                {(grandchild.children || []).map((node) => (
                                  <div className="dg-deep" key={node.id}>
                                    <a href={categoryLink("", node)}>
                                      {node.name}
                                    </a>

                                    {(node.children || []).map((leaf) => (
                                      <a
                                        className="dg-leaf"
                                        key={leaf.id}
                                        href={categoryLink("", leaf)}
                                      >
                                        {leaf.name}
                                      </a>
                                    ))}
                                  </div>
                                ))}
                              </div>
                            ))}
                          </section>
                        ))}
                      </div>

                      {!desktopRoot.children?.length && (
                        <p className="dg-empty">
                          برای دیدن کالاها، «همهٔ محصولات این دسته» را انتخاب کن.
                        </p>
                      )}
                    </>
                  )}
                </div>
              </div>

              <div className="dg-mobile">
                {mobileCurrent && (
                  <div className="dg-mobile-path">
                    <button
                      type="button"
                      onClick={() =>
                        setMobilePath((previous) => previous.slice(0, -1))
                      }
                    >
                      → برگشت
                    </button>
                    <strong>{mobileCurrent.name}</strong>
                  </div>
                )}

                <div className="dg-mobile-body">
                  {mobileCurrent && (
                    <a
                      className="dg-view-all"
                      href={categoryLink("", mobileCurrent)}
                    >
                      همهٔ محصولات {mobileCurrent.name}
                      <span aria-hidden="true">←</span>
                    </a>
                  )}

                  {mobileRows.map((node) => (
                    <div className="dg-mobile-row" key={node.id}>
                      <a href={categoryLink("", node)}>
                        {node.name}
                      </a>

                      {node.children?.length > 0 && (
                        <button
                          type="button"
                          aria-label={`زیرشاخه‌های ${node.name}`}
                          onClick={() => drillInto(node)}
                        >
                          <span>
                            {node.children.length.toLocaleString("fa-IR")}
                          </span>
                          ‹
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {!roots.length && (
                <p className="dg-status">هنوز دسته‌بندی ثبت نشده است.</p>
              )}
            </>
          )}

          <div className="dg-panel-footer">
            <a href="/products">مشاهدهٔ همهٔ کالاها ←</a>
            <span>انتخاب دسته، پیدا کردن سریع‌تر کالا</span>
          </div>
        </section>
      )}
    </div>
  );
}