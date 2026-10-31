import {
  forwardRef,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import "./dashboard-select.css";

const normalize = (value) =>
  String(value || "")
    .replace(/ي/g, "ی")
    .replace(/ك/g, "ک")
    .replace(/\u200c/g, " ")
    .trim()
    .toLowerCase();
const EMPTY = {
  rows: [],
  disabled: false,
  label: "انتخاب گزینه",
  signature: "",
};

// The real select retains browser validation, FormData and existing React handlers.
const DashboardSelect = forwardRef(function DashboardSelect(
  {
    children,
    onChange,
    onFocus,
    onInvalid,
    className = "",
    style,
    searchable,
    ...props
  },
  forwardedRef,
) {
  const id = useId();
  const native = useRef(null);
  const host = useRef(null);
  const trigger = useRef(null);
  const popup = useRef(null);
  const search = useRef(null);
  const [model, setModel] = useState(EMPTY);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(-1);
  const [position, setPosition] = useState(null);
  const [appearance, setAppearance] = useState({});

  const setNative = useCallback(
    (node) => {
      native.current = node;
      if (typeof forwardedRef === "function") forwardedRef(node);
      else if (forwardedRef) forwardedRef.current = node;
    },
    [forwardedRef],
  );

  const sync = useCallback(() => {
    const el = native.current;
    if (!el) return;
    const rows = Array.from(el.options).map((option, index) => ({
      index,
      value: option.value,
      label: option.label || option.textContent,
      selected: option.selected,
      description: option.dataset.path || "",
      disabled:
        option.disabled ||
        (option.parentElement.tagName === "OPTGROUP" &&
          option.parentElement.disabled),
      group:
        option.parentElement.tagName === "OPTGROUP"
          ? option.parentElement.label
          : "",
    }));
    const labelNode = el.labels?.[0]?.cloneNode(true);
    labelNode
      ?.querySelectorAll(".ds-control,select,button,input,small")
      .forEach((node) => node.remove());
    const label =
      props["aria-label"] || labelNode?.textContent?.trim() || "انتخاب گزینه";
    const disabled = el.matches(":disabled");
    const signature = JSON.stringify([rows, disabled, label]);
    setModel((previous) =>
      previous.signature === signature
        ? previous
        : { rows, disabled, label, signature },
    );
  }, [props["aria-label"]]);

  useLayoutEffect(() => {
    sync();
  });

  useEffect(() => {
    const el = native.current;
    const form = el?.form;
    let timer;
    const reset = () => {
      setOpen(false);
      timer = setTimeout(sync, 0);
    };
    const observer = new MutationObserver(sync);
    if (el)
      observer.observe(el, {
        childList: true,
        subtree: true,
        characterData: true,
        attributes: true,
      });
    form?.addEventListener("reset", reset);
    return () => {
      observer.disconnect();
      form?.removeEventListener("reset", reset);
      clearTimeout(timer);
    };
  }, [sync]);

  useEffect(() => {
    if (model.disabled) setOpen(false);
  }, [model.disabled]);

  const selected = model.rows.filter((row) => row.selected);
  const canSearch = searchable ?? model.rows.length > 7;
  const rows = model.rows.filter((row) =>
    normalize(`${row.group} ${row.label} ${row.description}`).includes(
      normalize(query),
    ),
  );

  function close(restore = false) {
    setOpen(false);
    setQuery("");
    if (restore) trigger.current?.focus({ preventScroll: true });
  }

  function show() {
    if (native.current?.matches(":disabled")) return;
    sync();
    setQuery("");
    setActive(-1);
    setPosition(null);
    setOpen(true);
    window.dispatchEvent(
      new CustomEvent("digishop:select-open", { detail: id }),
    );
  }

  function choose(row) {
    if (row.disabled || native.current?.matches(":disabled")) return;
    const el = native.current;
    if (!el.multiple && el.selectedIndex === row.index) {
      close(true);
      return;
    }
    if (el.multiple)
      el.options[row.index].selected = !el.options[row.index].selected;
    else el.selectedIndex = row.index;
    // Dispatch on the original node; callers receive the genuine select target,
    // including selectedOptions, options, name and validity APIs.
    el.dispatchEvent(new Event("change", { bubbles: true }));
    sync();
    if (!el.multiple) {
      setOpen(false);
      setQuery("");
      // Rich text commands may already have restored focus to their editor.
      if (popup.current?.contains(document.activeElement))
        trigger.current?.focus({ preventScroll: true });
    }
  }

  useEffect(() => {
    if (!open) return;
    function place() {
      const element = trigger.current;
      if (!element || element.matches(":disabled")) {
        setOpen(false);
        return;
      }
      const rect = element.getBoundingClientRect();
      const viewport = window.visualViewport;
      const viewLeft = viewport?.offsetLeft || 0;
      const viewTop = viewport?.offsetTop || 0;
      const width = viewport?.width || window.innerWidth;
      const height = viewport?.height || window.innerHeight;
      const bottom = viewTop + height;
      if (rect.bottom < viewTop || rect.top > bottom) {
        setOpen(false);
        return;
      }
      const below = bottom - rect.bottom - 14;
      const above = rect.top - viewTop - 14;
      const useAbove = below < 210 && above > below;
      const available = Math.max(80, Math.min(360, useAbove ? above : below));
      const panelWidth = Math.min(
        Math.max(rect.width, 260),
        Math.max(100, width - 20),
      );
      setPosition({
        position: "fixed",
        width: panelWidth,
        left: Math.max(
          viewLeft + 10,
          Math.min(rect.right - panelWidth, viewLeft + width - panelWidth - 10),
        ),
        top: useAbove ? undefined : rect.bottom + 6,
        bottom: useAbove ? window.innerHeight - rect.top + 6 : undefined,
        maxHeight: available,
      });
      const computed = getComputedStyle(element);
      const context = getComputedStyle(host.current);
      setAppearance({
        "--ds-accent":
          context.getPropertyValue("--cw-accent").trim() ||
          context.getPropertyValue("--blue").trim() ||
          context.getPropertyValue("--sf-blue").trim() ||
          "#145d52",
        fontFamily: computed.fontFamily,
        fontSize: computed.fontSize,
        direction: computed.direction,
      });
    }
    function outside(event) {
      if (
        !host.current?.contains(event.target) &&
        !popup.current?.contains(event.target)
      )
        setOpen(false);
    }
    function another(event) {
      if (event.detail !== id) setOpen(false);
    }
    place();
    const frame = requestAnimationFrame(() => {
      if (canSearch) search.current?.focus({ preventScroll: true });
    });
    document.addEventListener("pointerdown", outside);
    document.addEventListener("focusin", outside);
    window.addEventListener("digishop:select-open", another);
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    window.visualViewport?.addEventListener("resize", place);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("focusin", outside);
      window.removeEventListener("digishop:select-open", another);
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
      window.visualViewport?.removeEventListener("resize", place);
    };
  }, [open, canSearch, id]);

  function keys(event) {
    if (event.key === "Escape" && open) {
      event.preventDefault();
      event.stopPropagation();
      close(true);
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) {
        show();
        return;
      }
      const candidates = rows.filter((row) => !row.disabled);
      if (!candidates.length) return;
      const at = candidates.findIndex((row) => row.index === active);
      const next =
        at < 0
          ? event.key === "ArrowDown"
            ? 0
            : candidates.length - 1
          : (at + (event.key === "ArrowDown" ? 1 : -1) + candidates.length) %
            candidates.length;
      setActive(candidates[next].index);
      popup.current
        ?.querySelector(`[data-index="${candidates[next].index}"]`)
        ?.scrollIntoView?.({ block: "nearest" });
    } else if (open && event.key === "Enter") {
      event.preventDefault();
      const row = rows.find((item) => item.index === active);
      if (row) choose(row);
    } else if (open && event.key === "Tab") {
      const candidates = Array.from(
        document.querySelectorAll(
          "a[href],button,input,textarea,select,[tabindex]",
        ),
      ).filter(
        (node) =>
          node.tabIndex >= 0 &&
          !node.matches(":disabled") &&
          !popup.current?.contains(node) &&
          node.getClientRects().length > 0,
      );
      const at = candidates.indexOf(trigger.current);
      const next = candidates[at + (event.shiftKey ? -1 : 1)];
      if (next) {
        event.preventDefault();
        close();
        next.focus();
      } else close(true);
    }
  }

  return (
    <span
      className={`ds-control ${className}`}
      style={style}
      ref={host}
      onKeyDown={keys}
    >
      <select
        {...props}
        ref={setNative}
        className="ds-native"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(event) => {
          onChange?.(event);
          sync();
        }}
        onFocus={(event) => {
          onFocus?.(event);
          trigger.current?.focus({ preventScroll: true });
        }}
        onInvalid={(event) => {
          onInvalid?.(event);
          event.preventDefault();
          show();
          trigger.current?.focus();
        }}
      >
        {children}
      </select>
      <button
        ref={trigger}
        type="button"
        className="ds-trigger"
        disabled={model.disabled}
        role="combobox"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls={`${id}-list`}
        aria-label={model.label}
        aria-required={props.required || undefined}
        aria-describedby={props["aria-describedby"]}
        aria-invalid={props["aria-invalid"]}
        aria-activedescendant={
          open && active >= 0 ? `${id}-${active}` : undefined
        }
        onClick={() => (open ? close() : show())}
      >
        <span className="ds-value">
          {selected.map((row) => row.label).join("، ") || "انتخاب کنید"}
        </span>
        {props.multiple && selected.length > 0 && (
          <span className="ds-count">
            {selected.length.toLocaleString("fa-IR")}
          </span>
        )}
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          aria-hidden="true"
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>
      {open &&
        createPortal(
          <div
            ref={popup}
            className="ds-popup"
            style={{
              ...position,
              ...appearance,
              visibility: position ? "visible" : "hidden",
            }}
            onKeyDown={(event) => {
              event.stopPropagation();
              keys(event);
            }}
          >
            <div className="ds-popup-head">
              <strong>{model.label}</strong>
              <button
                type="button"
                aria-label="بستن فهرست"
                onClick={() => close(true)}
              >
                ×
              </button>
            </div>
            {canSearch && (
              <div className="ds-search">
                <input
                  ref={search}
                  type="search"
                  value={query}
                  placeholder="جست‌وجو در گزینه‌ها…"
                  aria-label={`جست‌وجو در ${model.label}`}
                  onChange={(event) => {
                    setQuery(event.target.value);
                    setActive(-1);
                  }}
                />
              </div>
            )}
            <div
              id={`${id}-list`}
              role="listbox"
              aria-label={model.label}
              aria-multiselectable={props.multiple || undefined}
              className="ds-options"
            >
              {rows.map((row) => (
                <button
                  key={row.index}
                  id={`${id}-${row.index}`}
                  type="button"
                  tabIndex={-1}
                  role="option"
                  data-index={row.index}
                  aria-selected={row.selected}
                  disabled={row.disabled}
                  className={`ds-option ${row.selected ? "is-selected" : ""} ${active === row.index ? "is-keyboard" : ""}`}
                  onClick={() => choose(row)}
                >
                  <span>
                    <span className="ds-option-label">{row.label}</span>
                    {(row.description || row.group) && (
                      <small>{row.description || row.group}</small>
                    )}
                  </span>
                  <span className="ds-tick" aria-hidden="true">
                    {row.selected ? "✓" : ""}
                  </span>
                </button>
              ))}
              {!rows.length && <p className="ds-empty">گزینه‌ای پیدا نشد.</p>}
            </div>
            {props.multiple && (
              <button
                type="button"
                className="ds-done"
                onClick={() => close(true)}
              >
                تأیید انتخاب‌ها
              </button>
            )}
          </div>,
          document.body,
        )}
    </span>
  );
});
export default DashboardSelect;
