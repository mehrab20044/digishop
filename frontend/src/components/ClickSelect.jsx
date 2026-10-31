import {
  useEffect,
  useId,
  useRef,
  useState,
} from "react";

import "./click-select.css";

function normalize(value) {
  return String(value || "")
    .replace(/ي/g, "ی")
    .replace(/ك/g, "ک")
    .replace(/\u200c/g, " ")
    .toLowerCase()
    .trim();
}

export default function ClickSelect({
  name,
  label,
  options = [],
  value,
  defaultValue = "",
  onChange,
  searchable = false,
  disabled = false,
}) {
  const controlled = value !== undefined;

  const [internalValue, setInternalValue] = useState(
    String(defaultValue),
  );
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const host = useRef(null);
  const trigger = useRef(null);
  const searchInput = useRef(null);
  const popup = useRef(null);
  const id = useId();

  const selectedValue = String(
    controlled ? value ?? "" : internalValue,
  );

  const selected = options.find(
    (option) => String(option.value) === selectedValue,
  );

  const filtered = options.filter((option) =>
    normalize(option.searchText || option.label).includes(
      normalize(query),
    ),
  );

  function close(restoreFocus = false) {
    setOpen(false);
    setQuery("");

    if (restoreFocus) trigger.current?.focus();
  }

  function choose(option) {
    if (option.disabled) return;

    const next = String(option.value);

    if (!controlled) setInternalValue(next);

    onChange?.(next);
    close(true);
  }

  useEffect(() => {
    if (!open) return;

    function outside(event) {
      if (!host.current?.contains(event.target)) {
        setOpen(false);
        setQuery("");
      }
    }

    document.addEventListener("pointerdown", outside);

    const frame = requestAnimationFrame(() => {
      if (searchable) {
        searchInput.current?.focus();
      } else {
        popup.current
          ?.querySelector('[data-choice][aria-pressed="true"]')
          ?.focus();
      }
    });

    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("pointerdown", outside);
    };
  }, [open, searchable]);

  useEffect(() => {
    const form = host.current?.closest("form");
    if (!form) return;

    function reset() {
      if (!controlled) {
        setInternalValue(String(defaultValue));
      }

      setOpen(false);
      setQuery("");
    }

    form.addEventListener("reset", reset);
    return () => form.removeEventListener("reset", reset);
  }, [controlled, defaultValue]);

  function onKeyDown(event) {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      close(true);
      return;
    }

    if (
      event.key !== "ArrowDown" &&
      event.key !== "ArrowUp"
    ) {
      return;
    }

    event.preventDefault();

    const buttons = [
      ...(popup.current?.querySelectorAll(
        "[data-choice]:not(:disabled)",
      ) || []),
    ];

    if (!buttons.length) return;

    const current = buttons.indexOf(document.activeElement);
    const step = event.key === "ArrowDown" ? 1 : -1;

    const next =
      current === -1
        ? step === 1 ? 0 : buttons.length - 1
        : (current + step + buttons.length) % buttons.length;

    buttons[next].focus();
  }

  return (
    <div
      className="ux-select"
      ref={host}
      onBlur={(event) => {
        if (
          event.relatedTarget &&
          !event.currentTarget.contains(event.relatedTarget)
        ) {
          close();
        }
      }}
    >
      {name && (
        <input
          type="hidden"
          name={name}
          value={selectedValue}
          disabled={disabled}
        />
      )}

      <button
        ref={trigger}
        className="ux-select-trigger"
        type="button"
        disabled={disabled}
        aria-label={`${label}: ${selected?.label || "انتخاب نشده"}`}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => {
          setQuery("");
          setOpen((previous) => !previous);
        }}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            setOpen(true);
          }
        }}
      >
        <span>{selected?.label || "انتخاب کنید"}</span>
        <span aria-hidden="true">⌄</span>
      </button>

      {open && !disabled && (
        <div
          id={id}
          ref={popup}
          className="ux-select-popup"
          role="group"
          aria-label={label}
          onKeyDown={onKeyDown}
        >
          {searchable && (
            <div className="ux-select-search">
              <input
                ref={searchInput}
                type="search"
                value={query}
                placeholder="جست‌وجو…"
                aria-label={`جست‌وجو در ${label}`}
                onChange={(event) => setQuery(event.target.value)}
              />
            </div>
          )}

          <div className="ux-select-options">
            {filtered.map((option) => {
              const active =
                String(option.value) === selectedValue;

              return (
                <button
                  key={String(option.value)}
                  data-choice
                  type="button"
                  className={active ? "is-selected" : ""}
                  aria-pressed={active}
                  disabled={option.disabled}
                  onClick={() => choose(option)}
                >
                  <span>
                    <strong>{option.label}</strong>

                    {option.description && (
                      <small>{option.description}</small>
                    )}
                  </span>

                  <span className="ux-select-check" aria-hidden="true">
                    {active ? "✓" : ""}
                  </span>
                </button>
              );
            })}

            {!filtered.length && (
              <p className="ux-select-empty">
                موردی پیدا نشد.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}