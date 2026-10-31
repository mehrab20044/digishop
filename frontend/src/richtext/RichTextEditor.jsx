import DashboardSelect from "../components/DashboardSelect";
import { useEffect, useRef, useState } from "react";
import "./richtext.css";
function textHTML(text) {
  const escape = (value) =>
    value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return text
    ? text
        .split(/\r?\n/)
        .map((line) => `<p>${escape(line)}</p>`)
        .join("")
    : "";
}
function RichTextEditor({
  name,
  html = "",
  plainText = "",
  disabled = false,
  label = "\u062A\u0648\u0636\u06CC\u062D\u0627\u062A \u0645\u062D\u0635\u0648\u0644",
}) {
  const selectionRef = useRef(null);
  const element = useRef(null);
  const editor = useRef(null);
  const hidden = useRef(null);
  const [value, setValue] = useState(html || textHTML(plainText));
  const [, redraw] = useState(0);
  const [error, setError] = useState("");
  const [linkOpen, setLinkOpen] = useState(false);
  const [link, setLink] = useState("");
  const [ready, setReady] = useState(false);
  const [api, setApi] = useState(null);
  const disabledRef = useRef(disabled);
  useEffect(() => {
    let active2 = true;
    let instance;
    import("./editor-vendor.js")
      .then(({ createEditor }) => {
        if (!active2) return;
        instance = createEditor({
          element: element.current,
          content: html || textHTML(plainText),
          editable: !disabledRef.current,
          label,
          onUpdate: ({ editor: current }) => {
            const next = current.isEmpty ? "" : current.getHTML();
            setValue(next);
            if (hidden.current) hidden.current.value = next;
          },
          onSelectionUpdate: ({ editor: current }) => {
            selectionRef.current = {
              from: current.state.selection.from,
              to: current.state.selection.to,
            };
          },
          onTransaction: () => {
            if (active2) redraw((n) => n + 1);
          },
        });
        editor.current = instance;
        setApi(instance);
        setReady(true);
      })
      .catch(() => {
        if (active2)
          setError(
            "\u0648\u06CC\u0631\u0627\u06CC\u0634\u06AF\u0631 \u0628\u0627\u0631\u06AF\u0630\u0627\u0631\u06CC \u0646\u0634\u062F. \u0635\u0641\u062D\u0647 \u0631\u0627 \u062A\u0627\u0632\u0647\u200C\u0633\u0627\u0632\u06CC \u06A9\u0646\u06CC\u062F\u061B \u0645\u062A\u0646 \u0642\u0628\u0644\u06CC \u062D\u0641\u0638 \u0634\u062F\u0647 \u0627\u0633\u062A.",
          );
      });
    return () => {
      active2 = false;
      instance?.destroy();
      editor.current = null;
    };
  }, [name, html, plainText, label]);
  useEffect(() => {
    disabledRef.current = disabled;
    editor.current?.setEditable(!disabled);
  }, [disabled, ready]);
  function rememberSelection() {
    const current = editor.current;
    if (current && !current.isDestroyed)
      selectionRef.current = {
        from: current.state.selection.from,
        to: current.state.selection.to,
      };
  }
  function command(method, ...args) {
    const current = editor.current;
    if (!current || current.isDestroyed || disabled) return;
    try {
      let chain = current.chain().focus();
      const selected = selectionRef.current;
      if (selected && method !== "undo" && method !== "redo")
        chain = chain.setTextSelection(selected);
      if (typeof chain[method] !== "function")
        throw new Error("Unsupported command");
      const applied = chain[method](...args).run();
      if (!applied) {
        setError(
          "\u0627\u06CC\u0646 \u0627\u0628\u0632\u0627\u0631 \u062F\u0631 \u0645\u062D\u0644 \u0641\u0639\u0644\u06CC \u0645\u062A\u0646 \u0642\u0627\u0628\u0644 \u0627\u0633\u062A\u0641\u0627\u062F\u0647 \u0646\u06CC\u0633\u062A.",
        );
        return;
      }
      const next = current.isEmpty ? "" : current.getHTML();
      setValue(next);
      if (hidden.current) hidden.current.value = next;
      rememberSelection();
      setError("");
      redraw((n) => n + 1);
    } catch {
      setError(
        "\u0627\u0639\u0645\u0627\u0644 \u0642\u0627\u0644\u0628\u200C\u0628\u0646\u062F\u06CC \u0627\u0646\u062C\u0627\u0645 \u0646\u0634\u062F\u061B \u0645\u062A\u0646 \u0631\u0627 \u0627\u0646\u062A\u062E\u0627\u0628 \u0648 \u062F\u0648\u0628\u0627\u0631\u0647 \u062A\u0644\u0627\u0634 \u06A9\u0646\u06CC\u062F.",
      );
    }
  }
  const active = (mark) => Boolean(api?.isActive(mark));
  function button(text, method, args = [], mark) {
    const paths = {
      setTextAlign: {
        right: "M3 5h18M9 10h12M3 15h18M9 20h12",
        center: "M3 5h18M7 10h10M3 15h18M7 20h10",
        left: "M3 5h18M3 10h12M3 15h18M3 20h12",
        justify: "M3 5h18M3 10h18M3 15h18M3 20h18",
      },
      toggleBulletList: "M9 6h12M9 12h12M9 18h12M3 6h.01M3 12h.01M3 18h.01",
      toggleOrderedList:
        "M10 6h11M10 12h11M10 18h11M3 4h1v5M3 9h3M3 13h3v2l-3 3h3",
      toggleBlockquote:
        "M10 7H4v6h6V7ZM20 7h-6v6h6V7ZM10 13c0 4-2 5-5 5M20 13c0 4-2 5-5 5",
      undo: "M9 5 4 10l5 5M4 10h10a6 6 0 0 1 6 6",
      redo: "m15 5 5 5-5 5M20 10H10a6 6 0 0 0-6 6",
      unsetLink:
        "m9 15 6-6M7 17l-1 1a4 4 0 0 1-6-6l4-4M17 7l1-1a4 4 0 0 1 6 6l-4 4M3 3l18 18",
    };

    const symbols = {
      selectAll: <span className="rt-symbol-all">همه</span>,
      toggleBold: <b>B</b>,
      toggleItalic: <i>I</i>,
      toggleUnderline: <span style={{ textDecoration: "underline" }}>U</span>,
      toggleStrike: <span style={{ textDecoration: "line-through" }}>S</span>,
      unsetAllMarks: <span className="rt-symbol-clear">Tx</span>,
    };

    const path =
      method === "setTextAlign" ? paths.setTextAlign[args[0]] : paths[method];

    const icon = path ? (
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        focusable="false"
      >
        <path d={path} />
      </svg>
    ) : (
      symbols[method] || text
    );

    return (
      <button
        key={method + JSON.stringify(args)}
        type="button"
        title={text}
        aria-label={text}
        aria-pressed={mark ? active(mark) : undefined}
        className={mark && active(mark) ? "is-active" : ""}
        disabled={disabled || !ready}
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => command(method, ...args)}
      >
        <span className="rt-tool-icon" aria-hidden="true">
          {icon}
        </span>
      </button>
    );
  }
  function addLink() {
    const href = link.trim();
    if (!/^(https?:\/\/[^\s\\]+|\/(?!\/)[^\s\\]*|#[\w-]+)$/i.test(href)) {
      setError(
        "\u0644\u06CC\u0646\u06A9 \u0628\u0627\u06CC\u062F /products \u06CC\u0627 \u0622\u062F\u0631\u0633 \u06A9\u0627\u0645\u0644 http/https \u0628\u0627\u0634\u062F.",
      );
      return;
    }
    command("setLink", { href });
    setLinkOpen(false);
    setError("");
  }
  return (
    <div className="rt-editor" role="group" aria-label={label}>
      <input ref={hidden} type="hidden" name={name} value={value} readOnly />
      <div
        onPointerDownCapture={rememberSelection}
        onFocusCapture={rememberSelection}
        className="rt-toolbar"
        role="toolbar"
        aria-label="ابزارهای ویرایش متن"
      >
        <DashboardSelect
          aria-label="نوع متن"
          disabled={disabled || !ready}
          value={
            api?.isActive("heading")
              ? String(api.getAttributes("heading").level)
              : "p"
          }
          onChange={(event) =>
            event.target.value === "p"
              ? command("setParagraph")
              : command("setHeading", { level: Number(event.target.value) })
          }
        >
          <option value="p">متن عادی</option>
          <option value="2">تیتر ۲</option>
          <option value="3">تیتر ۳</option>
          <option value="4">تیتر ۴</option>
        </DashboardSelect>
        {button(
          "\u0627\u0646\u062A\u062E\u0627\u0628 \u0647\u0645\u0647",
          "selectAll",
        )}
        {button("\u0628\u0648\u0644\u062F", "toggleBold", [], "bold")}
        {button(
          "\u0627\u06CC\u062A\u0627\u0644\u06CC\u06A9",
          "toggleItalic",
          [],
          "italic",
        )}
        {button(
          "\u0632\u06CC\u0631\u062E\u0637",
          "toggleUnderline",
          [],
          "underline",
        )}
        {button(
          "\u062E\u0637\u200C\u062E\u0648\u0631\u062F\u0647",
          "toggleStrike",
          [],
          "strike",
        )}
        <DashboardSelect
          aria-label="فونت متن"
          disabled={disabled || !ready}
          value={api?.getAttributes("textStyle").fontFamily || ""}
          onChange={(event) =>
            event.target.value
              ? command("setFontFamily", event.target.value)
              : command("unsetFontFamily")
          }
        >
          <option value="">فونت قالب</option>
          <option value="tahoma">Tahoma</option>
          <option value="arial">Arial</option>
          <option value="georgia">Georgia</option>
          <option value="times new roman">Times New Roman</option>
        </DashboardSelect>
        <DashboardSelect
          aria-label="اندازهٔ متن"
          disabled={disabled || !ready}
          value={api?.getAttributes("textStyle").fontSize || ""}
          onChange={(event) =>
            event.target.value
              ? command("setFontSize", event.target.value)
              : command("unsetFontSize")
          }
        >
          <option value="">اندازهٔ قالب</option>
          {[12, 14, 16, 18, 20, 24, 28, 32].map((size) => (
            <option key={size} value={`${size}px`}>
              {size}
            </option>
          ))}
        </DashboardSelect>
        <label className="rt-color" title="رنگ متن">
          رنگ
          <input
            aria-label="رنگ متن"
            type="color"
            disabled={disabled || !ready}
            onChange={(event) => command("setColor", event.target.value)}
          />
        </label>
        {button(
          "\u0631\u0627\u0633\u062A\u200C\u0686\u06CC\u0646",
          "setTextAlign",
          ["right"],
        )}
        {button("\u0648\u0633\u0637\u200C\u0686\u06CC\u0646", "setTextAlign", [
          "center",
        ])}
        {button("\u0686\u067E\u200C\u0686\u06CC\u0646", "setTextAlign", [
          "left",
        ])}
        {button(
          "\u062A\u0631\u0627\u0632 \u062F\u0648\u0637\u0631\u0641\u0647",
          "setTextAlign",
          ["justify"],
        )}
        {button(
          "\u0641\u0647\u0631\u0633\u062A \u0646\u0642\u0637\u0647\u200C\u0627\u06CC",
          "toggleBulletList",
          [],
          "bulletList",
        )}
        {button(
          "\u0641\u0647\u0631\u0633\u062A \u0634\u0645\u0627\u0631\u0647\u200C\u0627\u06CC",
          "toggleOrderedList",
          [],
          "orderedList",
        )}
        {button(
          "\u0646\u0642\u0644\u200C\u0642\u0648\u0644",
          "toggleBlockquote",
          [],
          "blockquote",
        )}
        <button
          type="button"
          disabled={disabled || !ready}
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => {
            setLink(editor.current?.getAttributes("link").href || "");
            setLinkOpen(!linkOpen);
          }}
        >
          لینک
        </button>
        {button("\u062D\u0630\u0641 \u0644\u06CC\u0646\u06A9", "unsetLink")}
        {button(
          "\u067E\u0627\u06A9 \u06A9\u0631\u062F\u0646 \u0642\u0627\u0644\u0628\u200C\u0628\u0646\u062F\u06CC",
          "unsetAllMarks",
        )}
        {button("\u0648\u0627\u06AF\u0631\u062F", "undo")}
        {button("\u0628\u0627\u0632\u0627\u0646\u062C\u0627\u0645", "redo")}
      </div>
      {linkOpen && (
        <div className="rt-link">
          <label>
            آدرس لینک
            <input
              dir="ltr"
              value={link}
              onChange={(event) => setLink(event.target.value)}
              placeholder="/products یا https://example.com"
            />
          </label>

          <button type="button" disabled={disabled} onClick={addLink}>
            ثبت لینک
          </button>

          <button type="button" onClick={() => setLinkOpen(false)}>
            بستن
          </button>
        </div>
      )}{" "}
      {error && (
        <p className="rt-error" role="alert">
          {error}
        </p>
      )}
      {!ready && !error && (
        <p role="status" className="rt-loading">
          در حال بارگذاری ویرایشگر…
        </p>
      )}
      <div className="rt-editor-surface" ref={element} />
      <small className="rt-help">
        برای تغییر نوشتهٔ موجود، اول آن را انتخاب کنید. بدون انتخاب، قالب روی
        نوشتهٔ بعدی اعمال می‌شود. Ctrl+B بولد · Ctrl+I ایتالیک · Ctrl+Z واگرد.
        فونت‌ها از گزینه‌های آماده هستند؛ فایل فونت جدید بارگذاری نمی‌شود.
      </small>
    </div>
  );
}
export { RichTextEditor as default };
