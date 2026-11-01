import { useEffect, useRef, useState } from "react";
import DashboardSelect from "../components/DashboardSelect";
import { managementFetch } from "../managementAuth";
import "./robots-studio.css";

const BASE = "/api/v1/owner/seo/robots-studio/";
const uid = () =>
  globalThis.crypto?.randomUUID?.() ||
  `r-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
const scopes = {
  exact: "فقط همین صفحه",
  prefix: "مسیر و زیرشاخه‌ها",
  pattern: "الگوی پیشرفته",
};
const emptyRule = () => ({
  id: uid(),
  action: "disallow",
  scope: "prefix",
  path: "/account/",
  enabled: true,
});
const messages = (value) =>
  typeof value === "string"
    ? [value]
    : value && typeof value === "object"
      ? Object.values(value).flatMap(messages)
      : [];

async function request(payload, csrf, signal) {
  const response = await managementFetch(BASE, {
    signal,
    cache: "no-store",
    ...(payload
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
          body: JSON.stringify(payload),
        }
      : {}),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok || !data) {
    const error = new Error(
      messages(data?.error?.details || data?.error?.message || data).join(
        "، ",
      ) || "ارتباط با سرور کامل نشد.",
    );
    error.status = response.status;
    error.line = data?.line;
    throw error;
  }
  return data;
}

function Icon({ name }) {
  const paths = {
    bot: "M6 8h12v12H6ZM12 3v5M3 12h3M18 12h3M9 12v2M15 12v2M9 17h6",
    trash: "M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7",
    edit: "m4 16-1 5 5-1L21 7l-6-6L4 16ZM13 3l6 6",
    upload: "M12 16V3m-5 5 5-5 5 5M4 14v7h16v-7",
    save: "M4 3h13l4 4v14H3V3ZM7 3v6h10V3M7 21v-8h10v8",
    file: "M6 2h8l5 5v15H5V2ZM14 2v6h5M8 13h8M8 17h8",
    search: "M21 21l-6-6M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0Z",
  };
  return (
    <svg
      width="19"
      height="19"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name] || paths.file} />
    </svg>
  );
}

export default function RobotsStudio() {
  const [server, setServer] = useState(null),
    [doc, setDoc] = useState(null);
  const [active, setActive] = useState(null),
    [form, setForm] = useState(emptyRule),
    [editing, setEditing] = useState(null);
  const [rawText, setRawText] = useState(null);
  const [rawError, setRawError] = useState("");
  const [rawBusy, setRawBusy] = useState(false);
  const [rawLine, setRawLine] = useState(null);
  const rawInput = useRef(null);
  const [preview, setPreview] = useState({ key: "", text: "", error: "" });
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [attempt, setAttempt] = useState(0);
  const [newAgent, setNewAgent] = useState(null),
    [agentError, setAgentError] = useState("");
  const [testPath, setTestPath] = useState("/cart/"),
    [testAgent, setTestAgent] = useState("Googlebot"),
    [testSource, setTestSource] = useState("draft"),
    [test, setTest] = useState(null),
    [testing, setTesting] = useState(false);
  const lock = useRef(false),
    testLock = useRef(false),
    testGeneration = useRef(0),
    pathInput = useRef(null),
    modalInput = useRef(null);
  const rawEditing = rawText !== null;
  useEffect(() => {
    if (rawEditing) rawInput.current?.focus();
  }, [rawEditing]);
  const docKey = doc ? JSON.stringify(doc) : "";
  const valid = rawText === null && preview.key === docKey && !preview.error;
  const canChange = Boolean(server?.can_change) && !busy && rawText === null;
  const unpublished =
    rawEditing ||
    (doc && server && JSON.stringify(doc) !== JSON.stringify(server.published));
  const localChanges =
    rawText !== null ||
    (doc && server && JSON.stringify(doc) !== JSON.stringify(server.draft));
  const group =
    doc?.groups.find((item) => item.id === active) || doc?.groups[0];

  function accept(data) {
    setRawText(null);
    setRawError("");
    setRawLine(null);
    setServer(data);
    setDoc(data.draft);
    setPreview({
      key: JSON.stringify(data.draft),
      text: data.draft_text,
      error: "",
    });
    setActive((current) =>
      data.draft.groups.some((item) => item.id === current)
        ? current
        : data.draft.groups[0]?.id,
    );
    setTest(null);
    setError("");
  }
  useEffect(() => {
    const controller = new AbortController();
    request(null, null, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) accept(data);
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(err.message);
      });
    return () => controller.abort();
  }, [attempt]);
  useEffect(() => {
    if (!doc || !server || preview.key === docKey) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      request(
        { action: "preview", document: doc },
        server.csrfToken,
        controller.signal,
      )
        .then((data) => {
          if (!controller.signal.aborted)
            setPreview({ key: docKey, text: data.text, error: "" });
        })
        .catch((err) => {
          if (!controller.signal.aborted)
            setPreview({ key: docKey, text: "", error: err.message });
        });
    }, 300);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [docKey, server?.csrfToken]);
  useEffect(() => {
    testGeneration.current += 1;
    setTest(null);
  }, [docKey, testPath, testAgent, testSource]);
  useEffect(() => {
    if (localChanges) setNotice("");
  }, [docKey, localChanges]);
  useEffect(() => {
    if (!localChanges) return;
    const warn = (event) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [localChanges]);
  useEffect(() => {
    if (newAgent === null) return;
    modalInput.current?.focus();
    function keys(event) {
      if (event.key === "Escape") setNewAgent(null);
      if (event.key === "Tab") {
        const nodes = [
          ...document.querySelectorAll(".rb-modal input,.rb-modal button"),
        ].filter((node) => !node.disabled);
        if (event.shiftKey && document.activeElement === nodes[0]) {
          event.preventDefault();
          nodes.at(-1)?.focus();
        }
        if (!event.shiftKey && document.activeElement === nodes.at(-1)) {
          event.preventDefault();
          nodes[0]?.focus();
        }
      }
    }
    document.addEventListener("keydown", keys);
    return () => document.removeEventListener("keydown", keys);
  }, [newAgent === null]);

  function updateGroup(patch) {
    setDoc((current) => ({
      ...current,
      groups: current.groups.map((item) =>
        item.id === group.id ? { ...item, ...patch } : item,
      ),
    }));
  }
  function updateRule(id, patch) {
    updateGroup({
      rules: group.rules.map((rule) =>
        rule.id === id ? { ...rule, ...patch } : rule,
      ),
    });
  }
  function addRule(event) {
    event.preventDefault();
    if (!form.path.startsWith("/")) {
      setError("مسیر باید با / شروع شود؛ دامنه وارد نکن.");
      pathInput.current?.focus();
      return;
    }
    updateGroup({
      rules: editing
        ? group.rules.map((rule) =>
            rule.id === editing ? { ...form, id: editing } : rule,
          )
        : [...group.rules, form],
    });
    setForm(emptyRule());
    setEditing(null);
    setError("");
  }
  function addAgent(event) {
    event.preventDefault();
    const agent = newAgent.trim();
    if (!(agent === "*" || /^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(agent))) {
      setAgentError(
        "مانند Googlebot یا Bingbot وارد کن؛ * برای همهٔ ربات‌هاست.",
      );
      return;
    }
    if (
      doc.groups.some(
        (item) => item.agent.toLowerCase() === agent.toLowerCase(),
      )
    ) {
      setAgentError("این ربات از قبل گروه دارد.");
      return;
    }
    const item = { id: uid(), agent, enabled: true, rules: [] };
    setDoc((current) => ({ ...current, groups: [...current.groups, item] }));
    setActive(item.id);
    setNewAgent(null);
    setEditing(null);
    setForm(emptyRule());
  }
  async function save(action) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const data = await request(
        { action, document: doc, expected_revision: server.revision },
        server.csrfToken,
      );
      accept(data);
      setNotice(
        action === "publish"
          ? "نسخهٔ جدید منتشر شد؛ robots.txt عمومی به‌روز است."
          : action === "reset"
            ? "پیش‌نویس به نسخهٔ منتشرشده برگشت."
            : "پیش‌نویس ذخیره شد؛ فایل عمومی تغییر نکرد.",
      );
    } catch (err) {
      setError(
        err.status === 409
          ? "مدیر دیگری تنظیمات را تغییر داده است. ویرایش تو حفظ شده؛ قبل از ادامه نسخهٔ تازه را دریافت کن."
          : err.message,
      );
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  async function runTest() {
    if (testLock.current) return;
    testLock.current = true;
    const generation = ++testGeneration.current;
    setTesting(true);
    setTest(null);
    try {
      const data = await request(
        {
          action: "test",
          source: testSource,
          document: doc,
          path: testPath,
          agent: testAgent,
        },
        server.csrfToken,
      );
      if (generation === testGeneration.current) setTest(data);
    } catch (err) {
      if (generation === testGeneration.current)
        setTest({ error: err.message });
    } finally {
      testLock.current = false;
      setTesting(false);
    }
  }
  async function applyText() {
    if (rawBusy || rawText === null) return;
    setRawBusy(true);
    setRawError("");
    setRawLine(null);
    try {
      const data = await request(
        { action: "parse", text: rawText, document: doc },
        server.csrfToken,
      );
      setDoc(data.document);
      setPreview({
        key: JSON.stringify(data.document),
        text: data.text,
        error: "",
      });
      setActive(data.document.groups[0]?.id);
      setEditing(null);
      setForm(emptyRule());
      setRawText(null);
      setNotice(
        [
          "متن در فرم اعمال شد؛ برای تغییر فایل سایت، انتشار را بزن.",
          ...(data.warnings || []),
        ].join(" "),
      );
    } catch (err) {
      setRawError(err.message);
      setRawLine(err.line || null);
      rawInput.current?.focus();
      if (err.line) {
        const start =
          rawText
            .split("\n")
            .slice(0, err.line - 1)
            .join("\n").length + (err.line > 1 ? 1 : 0);
        rawInput.current?.setSelectionRange(
          start,
          rawText.indexOf("\n", start) < 0
            ? rawText.length
            : rawText.indexOf("\n", start),
        );
      }
    } finally {
      setRawBusy(false);
    }
  }
  function download() {
    const url = URL.createObjectURL(
      new Blob([preview.text], { type: "text/plain;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "robots.txt";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  if (!doc)
    return (
      <section className="rb-status card">
        <p role={error ? "alert" : "status"}>
          {error || "در حال دریافت ویرایشگر robots.txt…"}
        </p>
        {error && (
          <button type="button" onClick={() => setAttempt((v) => v + 1)}>
            تلاش دوباره
          </button>
        )}
      </section>
    );
  return (
    <section className="rb-studio" dir="rtl">
      <header className="rb-top">
        <div>
          <h1>
            مدیریت <bdi>robots.txt</bdi>
          </h1>
          <p>قوانین خزش را بساز، بررسی کن و منتشر کن.</p>
        </div>
        <div className="rb-top-actions">
          <span className={`rb-badge ${unpublished ? "is-draft" : "is-live"}`}>
            {unpublished ? "تغییرات منتشرنشده" : "نسخهٔ منتشرشده"}
          </span>
          <button
            type="button"
            className="rb-outline"
            disabled={!canChange || !valid}
            onClick={() => save("save")}
          >
            <Icon name="save" />
            ذخیرهٔ پیش‌نویس
          </button>
          <button
            type="button"
            className="rb-primary"
            disabled={!canChange || !valid}
            onClick={() => save("publish")}
          >
            <Icon name="upload" />
            {busy ? "در حال ذخیره…" : "انتشار تغییرات"}
          </button>
        </div>
      </header>
      {error && (
        <div role="alert" className="rb-error">
          {error}
          <button
            type="button"
            className="rb-link"
            onClick={() => {
              if (
                !localChanges ||
                window.confirm(
                  "نسخهٔ سرور جای ویرایش ذخیره‌نشده را می‌گیرد. ادامه می‌دهی؟",
                )
              )
                setAttempt((v) => v + 1);
            }}
          >
            دریافت نسخهٔ تازه
          </button>
        </div>
      )}
      {notice && (
        <div role="status" className="rb-success">
          {notice}
        </div>
      )}
      <div className="rb-layout">
        <div className="rb-editor">
          {rawText !== null && (
            <p className="rb-text-notice">
              در حال ویرایش متنی؛ ابتدا «بررسی و اعمال متن» یا «انصراف» را بزن.
            </p>
          )}
          <fieldset
            className="rb-visual-fields"
            disabled={rawText !== null || busy}
          >
            <section className="rb-card">
              <div className="rb-card-heading">
                <h2>قوانین ربات‌ها</h2>
                <Icon name="bot" />
              </div>
              <p className="rb-muted">
                هر گروه برای یک ربات یا همهٔ ربات‌هاست.
              </p>
              <div className="rb-agents" aria-label="گروه‌های ربات">
                {doc.groups.map((item) => (
                  <button
                    type="button"
                    key={item.id}
                    className={item.id === group.id ? "is-active" : ""}
                    aria-pressed={item.id === group.id}
                    onClick={() => {
                      setActive(item.id);
                      setEditing(null);
                      setForm(emptyRule());
                    }}
                  >
                    {item.agent === "*" ? "همهٔ ربات‌ها (*)" : item.agent}
                    {!item.enabled && <small> · غیرفعال</small>}
                  </button>
                ))}
                <button
                  type="button"
                  className="rb-dashed"
                  disabled={!canChange}
                  onClick={() => {
                    setNewAgent("");
                    setAgentError("");
                  }}
                >
                  ＋ افزودن ربات
                </button>
              </div>
              <div className="rb-group">
                <header>
                  <div>
                    <strong>
                      {group.agent === "*" ? "همهٔ ربات‌ها" : group.agent}
                    </strong>
                    <bdi>User-agent: {group.agent}</bdi>
                  </div>
                  <div className="rb-group-tools">
                    <label>
                      <input
                        type="checkbox"
                        checked={group.enabled}
                        disabled={!canChange}
                        onChange={(e) =>
                          updateGroup({ enabled: e.target.checked })
                        }
                      />
                      فعال
                    </label>
                    <button
                      type="button"
                      className="rb-icon rb-danger"
                      aria-label="حذف گروه ربات"
                      disabled={!canChange || doc.groups.length === 1}
                      onClick={() => {
                        setDoc((current) => ({
                          ...current,
                          groups: current.groups.filter(
                            (item) => item.id !== group.id,
                          ),
                        }));
                        setEditing(null);
                      }}
                    >
                      {" "}
                      <Icon name="trash" />
                    </button>
                  </div>
                </header>
                <p className="rb-group-note">
                  گروه اختصاصی، قوانین گروه * را به ارث نمی‌برد. گروهِ خالی یعنی
                  خزش مجاز.
                </p>
                <div className="rb-rule-list">
                  {group.rules.map((rule) => (
                    <div
                      className={`rb-rule ${rule.enabled ? "" : "is-disabled"}`}
                      key={rule.id}
                    >
                      <div className={`rb-action rb-action-${rule.action}`}>
                        <DashboardSelect
                          aria-label="نوع قانون"
                          value={rule.action}
                          disabled={!canChange}
                          onChange={(e) =>
                            updateRule(rule.id, { action: e.target.value })
                          }
                        >
                          <option value="allow">مجاز</option>
                          <option value="disallow">مسدود</option>
                        </DashboardSelect>
                      </div>
                      <input
                        dir="ltr"
                        className="rb-path"
                        aria-label="مسیر قانون"
                        value={rule.path}
                        disabled={!canChange}
                        onChange={(e) =>
                          updateRule(rule.id, { path: e.target.value })
                        }
                      />
                      <DashboardSelect
                        aria-label="نوع تطبیق قانون"
                        value={rule.scope}
                        disabled={!canChange}
                        onChange={(e) =>
                          updateRule(rule.id, { scope: e.target.value })
                        }
                      >
                        {Object.entries(scopes).map(([key, label]) => (
                          <option key={key} value={key}>
                            {label}
                          </option>
                        ))}
                      </DashboardSelect>
                      <div className="rb-row-tools">
                        <button
                          type="button"
                          className="rb-icon"
                          aria-label="ویرایش قانون"
                          disabled={!canChange}
                          onClick={() => {
                            setForm({ ...rule });
                            setEditing(rule.id);
                            pathInput.current?.focus();
                            pathInput.current?.scrollIntoView({
                              block: "nearest",
                            });
                          }}
                        >
                          <Icon name="edit" />
                        </button>
                        <button
                          type="button"
                          className="rb-icon rb-danger"
                          aria-label="حذف قانون"
                          disabled={!canChange}
                          onClick={() => {
                            updateGroup({
                              rules: group.rules.filter(
                                (item) => item.id !== rule.id,
                              ),
                            });
                            if (editing === rule.id) {
                              setEditing(null);
                              setForm(emptyRule());
                            }
                          }}
                        >
                          <Icon name="trash" />
                        </button>
                        <label className="rb-enable" title="فعال‌بودن قانون">
                          <input
                            type="checkbox"
                            aria-label="فعال‌بودن قانون"
                            checked={rule.enabled}
                            disabled={!canChange}
                            onChange={(e) =>
                              updateRule(rule.id, { enabled: e.target.checked })
                            }
                          />
                        </label>
                      </div>
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  className="rb-add-rule rb-dashed"
                  disabled={!canChange}
                  onClick={() => {
                    setEditing(null);
                    setForm(emptyRule());
                    pathInput.current?.focus();
                    pathInput.current?.scrollIntoView({ block: "nearest" });
                  }}
                >
                  ＋ افزودن قانون جدید
                </button>
                <form className="rb-rule-form" onSubmit={addRule}>
                  <h3>＋ {editing ? "ویرایش قانون" : "قانون جدید"}</h3>
                  <fieldset disabled={!canChange}>
                    <div className="rb-form-grid">
                      <label>
                        اجازهٔ خزش
                        <span className="rb-segments">
                          <button
                            type="button"
                            className={
                              form.action === "allow" ? "allow-active" : ""
                            }
                            aria-pressed={form.action === "allow"}
                            onClick={() =>
                              setForm((value) => ({
                                ...value,
                                action: "allow",
                              }))
                            }
                          >
                            مجاز
                          </button>
                          <button
                            type="button"
                            className={
                              form.action === "disallow" ? "block-active" : ""
                            }
                            aria-pressed={form.action === "disallow"}
                            onClick={() =>
                              setForm((value) => ({
                                ...value,
                                action: "disallow",
                              }))
                            }
                          >
                            مسدود
                          </button>
                        </span>
                      </label>
                      <label>
                        مسیر (URL)
                        <input
                          ref={pathInput}
                          dir="ltr"
                          required
                          maxLength={2048}
                          value={form.path}
                          onChange={(e) =>
                            setForm((value) => ({
                              ...value,
                              path: e.target.value,
                            }))
                          }
                          placeholder="/account/"
                        />
                      </label>
                      <label>
                        نوع تطبیق
                        <DashboardSelect
                          aria-label="نوع تطبیق قانون جدید"
                          value={form.scope}
                          onChange={(e) =>
                            setForm((value) => ({
                              ...value,
                              scope: e.target.value,
                            }))
                          }
                        >
                          {Object.entries(scopes).map(([key, label]) => (
                            <option key={key} value={key}>
                              {label}
                            </option>
                          ))}
                        </DashboardSelect>
                      </label>
                    </div>
                    <p className="rb-help">
                      {form.scope === "exact"
                        ? "فقط همین آدرس، بدون پارامتر اضافه؛ $ خودکار در خروجی قرار می‌گیرد."
                        : form.scope === "prefix"
                          ? "مسیر پوشه با / تمام می‌شود؛ فقط آدرس‌هایی که با همین مسیر شروع شوند."
                          : "الگوی robots.txt با * و $؛ نه عبارت منظم (Regex)."}
                    </p>
                    <div className="rb-form-actions">
                      <button className="rb-primary" type="submit">
                        {editing ? "اعمال ویرایش" : "افزودن به گروه"}
                      </button>
                      {editing && (
                        <button
                          type="button"
                          className="rb-link"
                          onClick={() => {
                            setEditing(null);
                            setForm(emptyRule());
                          }}
                        >
                          انصراف
                        </button>
                      )}
                    </div>
                  </fieldset>
                </form>
              </div>
            </section>
            <section className="rb-card rb-maps">
              <div className="rb-card-heading">
                <h2>نقشه‌های سایت</h2>
                <Icon name="file" />
              </div>
              {doc.sitemaps.map((item) => (
                <div className="rb-map-row" key={item.id}>
                  <input
                    dir="ltr"
                    type="url"
                    aria-label="آدرس نقشهٔ سایت"
                    value={item.url}
                    disabled={!canChange}
                    onChange={(e) =>
                      setDoc((current) => ({
                        ...current,
                        sitemaps: current.sitemaps.map((row) =>
                          row.id === item.id
                            ? { ...row, url: e.target.value }
                            : row,
                        ),
                      }))
                    }
                  />
                  <label>
                    <input
                      type="checkbox"
                      aria-label="فعال‌بودن نقشهٔ سایت"
                      checked={item.enabled}
                      disabled={!canChange}
                      onChange={(e) =>
                        setDoc((current) => ({
                          ...current,
                          sitemaps: current.sitemaps.map((row) =>
                            row.id === item.id
                              ? { ...row, enabled: e.target.checked }
                              : row,
                          ),
                        }))
                      }
                    />
                    فعال
                  </label>
                  <button
                    type="button"
                    className="rb-icon rb-danger"
                    aria-label="حذف نقشهٔ سایت"
                    disabled={!canChange}
                    onClick={() =>
                      setDoc((current) => ({
                        ...current,
                        sitemaps: current.sitemaps.filter(
                          (row) => row.id !== item.id,
                        ),
                      }))
                    }
                  >
                    <Icon name="trash" />
                  </button>
                </div>
              ))}
              <button
                type="button"
                className="rb-dashed rb-add-map"
                disabled={!canChange}
                onClick={() =>
                  setDoc((current) => ({
                    ...current,
                    sitemaps: [
                      ...current.sitemaps,
                      {
                        id: uid(),
                        url: current.sitemaps.length
                          ? ""
                          : `${server.site_origin}/sitemap.xml`,
                        enabled: true,
                      },
                    ],
                  }))
                }
              >
                ＋ افزودن نقشهٔ سایت
              </button>
            </section>
          </fieldset>
        </div>
        <aside className="rb-aside">
          <section className="rb-card rb-preview">
            <div className="rb-card-heading">
              <h2>
                {rawText === null ? "پیش‌نمایش فایل" : "ویرایش متنی robots.txt"}
              </h2>
              <Icon name="file" />
            </div>
            <div className="rb-mode-actions">
              {rawText === null ? (
                <button
                  type="button"
                  className="rb-outline"
                  disabled={!canChange || !valid}
                  onClick={() => {
                    setRawText(preview.text);
                    setRawError("");
                    setRawLine(null);
                  }}
                >
                  ویرایش با کیبورد
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    className="rb-primary"
                    disabled={rawBusy}
                    onClick={applyText}
                  >
                    {rawBusy ? "در حال بررسی…" : "بررسی و اعمال متن"}
                  </button>
                  <button
                    type="button"
                    className="rb-outline"
                    disabled={rawBusy}
                    onClick={() => {
                      setRawText(null);
                      setRawError("");
                    }}
                  >
                    انصراف
                  </button>
                </>
              )}
            </div>
            {rawText !== null ? (
              <>
                <p className="rb-muted">
                  متن فعال را ویرایش کن؛ قوانین خاموش حفظ می‌شوند. توضیحات # و
                  فاصله‌ها پس از اعمال استانداردسازی می‌شوند.
                </p>
                <div className="rb-text-editor" dir="ltr">
                  <div aria-hidden="true" className="rb-line-numbers">
                    {rawText.split("\n").map((_, i) => (
                      <span
                        className={rawLine === i + 1 ? "is-error" : ""}
                        key={i}
                      >
                        {i + 1}
                      </span>
                    ))}
                  </div>
                  <textarea
                    ref={rawInput}
                    aria-label="متن robots.txt"
                    value={rawText}
                    disabled={rawBusy}
                    spellCheck={false}
                    autoCapitalize="off"
                    autoCorrect="off"
                    wrap="off"
                    onScroll={(event) => {
                      const gutter = event.currentTarget.previousElementSibling;
                      if (gutter)
                        gutter.scrollTop = event.currentTarget.scrollTop;
                    }}
                    onChange={(event) => {
                      setRawText(event.target.value);
                      setRawError("");
                      setRawLine(null);
                    }}
                  />
                </div>
                <p className="rb-muted">
                  دستورهای قابل استفاده: User-agent، Allow، Disallow، Sitemap
                </p>
                {rawError && (
                  <p className="rb-error" role="alert">
                    {rawError}
                  </p>
                )}
              </>
            ) : (
              <div
                className="rb-code"
                role={canChange ? "button" : undefined}
                tabIndex={canChange ? 0 : undefined}
                aria-label={
                  canChange ? "برای ویرایش متن robots.txt کلیک کن" : undefined
                }
                onClick={() => {
                  if (canChange && valid) {
                    setRawText(preview.text);
                    setRawError("");
                    setRawLine(null);
                  }
                }}
                onKeyDown={(event) => {
                  if (
                    canChange &&
                    valid &&
                    (event.key === "Enter" || event.key === " ")
                  ) {
                    event.preventDefault();
                    setRawText(preview.text);
                    setRawError("");
                    setRawLine(null);
                  }
                }}
              >
                <ol>
                  {(valid
                    ? preview.text
                    : preview.key !== docKey
                      ? "در حال ساخت پیش‌نمایش…"
                      : "خروجی معتبر در دسترس نیست."
                  )
                    .trimEnd()
                    .split("\n")
                    .map((line, index) => (
                      <li key={index}>
                        <code>{line || " "}</code>
                      </li>
                    ))}
                </ol>
              </div>
            )}
            <div
              className={`rb-validation ${valid ? "is-valid" : "is-pending"}`}
              role="status"
            >
              {rawText !== null
                ? "متن هنوز اعمال نشده؛ انتشار تا پایان بررسی غیرفعال است."
                : valid
                  ? "✓ ساختار فایل معتبر است"
                  : preview.key !== docKey
                    ? "در حال بررسی با سرور…"
                    : preview.error}
            </div>
            <div className="rb-preview-tools">
              <button
                type="button"
                className="rb-link"
                disabled={!valid}
                onClick={download}
              >
                دانلود فایل
              </button>
              <span>نسخهٔ سند: {server.revision.toLocaleString("fa-IR")}</span>
            </div>
          </section>
          <section className="rb-card rb-tester">
            <div className="rb-card-heading">
              <h2>آزمایش یک آدرس</h2>
              <Icon name="search" />
            </div>
            <div className="rb-test-input">
              <input
                dir="ltr"
                aria-label="آدرس آزمایش"
                value={testPath}
                onChange={(e) => setTestPath(e.target.value)}
                placeholder="/cart/"
              />
              <button
                type="button"
                className="rb-primary"
                disabled={testing || (testSource === "draft" && !valid)}
                onClick={runTest}
              >
                {testing ? "بررسی…" : "بررسی"}
              </button>
            </div>
            <div className="rb-test-options">
              <label>
                ربات
                <input
                  dir="ltr"
                  aria-label="ربات آزمایش"
                  value={testAgent}
                  maxLength={256}
                  onChange={(e) => setTestAgent(e.target.value)}
                />
              </label>
              <label>
                نسخهٔ آزمایش
                <DashboardSelect
                  aria-label="نسخهٔ آزمایش"
                  value={testSource}
                  onChange={(e) => setTestSource(e.target.value)}
                >
                  <option value="draft">پیش‌نویس فعلی</option>
                  <option value="published">نسخهٔ منتشرشده</option>
                </DashboardSelect>
              </label>
            </div>
            {test && (
              <div
                className={`rb-test-result ${test.error ? "is-error" : test.allowed ? "is-allowed" : "is-blocked"}`}
                role="status"
              >
                <strong>
                  {test.error ||
                    (test.allowed
                      ? "✓ خزش این آدرس مجاز است"
                      : "△ خزش این آدرس مسدود است")}
                </strong>
                {!test.error && (
                  <>
                    <small>
                      گروه مؤثر:{" "}
                      {test.groups.join("، ") || "پیش‌فرضِ بدون گروه"}
                    </small>
                    {test.matched ? (
                      <code dir="ltr">
                        {test.matched.action === "allow" ? "Allow" : "Disallow"}
                        : {test.matched.pattern}
                      </code>
                    ) : (
                      <small>قانون مسدودکننده‌ای تطبیق نداشت.</small>
                    )}
                  </>
                )}
              </div>
            )}
            <p className="rb-help">
              نتیجه بر اساس قواعد پشتیبانی‌شدهٔ Google است؛ رفتار همهٔ ربات‌های
              اینترنت را تضمین نمی‌کند.
            </p>
          </section>
          <div className="rb-publish-meta">
            <p>
              آخرین انتشار:{" "}
              {server.published_at
                ? new Date(server.published_at).toLocaleString("fa-IR")
                : "هنوز منتشر نشده"}
            </p>
            <button
              type="button"
              className="rb-link"
              disabled={!canChange}
              onClick={() => {
                if (window.confirm("پیش‌نویس با نسخهٔ منتشرشده جایگزین شود؟"))
                  save("reset");
              }}
            >
              بازگشت پیش‌نویس به نسخهٔ منتشرشده
            </button>
            <p>بستن خزش به‌تنهایی، صفحه را از نتایج گوگل حذف نمی‌کند.</p>
          </div>
        </aside>
      </div>
      {newAgent !== null && (
        <div
          className="rb-modal-backdrop"
          onClick={(e) => {
            if (e.target === e.currentTarget) setNewAgent(null);
          }}
        >
          <section
            className="rb-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="rb-agent-title"
          >
            <h2 id="rb-agent-title">افزودن ربات</h2>
            <p>نام ربات مانند Googlebot یا Bingbot؛ * برای همهٔ ربات‌ها.</p>
            <form onSubmit={addAgent}>
              <label>
                نام ربات
                <input
                  ref={modalInput}
                  dir="ltr"
                  aria-label="نام ربات جدید"
                  value={newAgent}
                  maxLength={64}
                  required
                  onChange={(e) => setNewAgent(e.target.value)}
                  placeholder="Googlebot"
                />
              </label>
              {agentError && (
                <p role="alert" className="rb-error">
                  {agentError}
                </p>
              )}
              <div>
                <button type="submit" className="rb-primary">
                  ساخت گروه
                </button>
                <button
                  type="button"
                  className="rb-outline"
                  onClick={() => setNewAgent(null)}
                >
                  انصراف
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </section>
  );
}
