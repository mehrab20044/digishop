import { useEffect, useRef, useState } from "react";
import DashboardSelect from "../components/DashboardSelect";
import { managementFetch } from "../managementAuth";
import "./page-robots.css";
import "./index-manager.css";

const BASE = "/api/v1/owner/seo/page-rules/";
const kinds = {
  product: "محصولات",
  category: "دسته‌بندی‌ها",
  page: "صفحات ساخته‌شده",
  system: "صفحات اصلی",
};
const statuses = {
  inherit: "پیش‌فرض صفحه",
  index: "ایندکس مجاز",
  noindex: "عدم ایندکس",
};
const keyOf = (row) => `${row.kind}:${row.object_id}`;
const messages = (value) =>
  typeof value === "string"
    ? [value]
    : value && typeof value === "object"
      ? Object.values(value).flatMap(messages)
      : [];
async function api(query = "", payload, csrf, signal) {
  const response = await managementFetch(BASE + query, {
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
      messages(data).join("، ") || "ارتباط با سرور انجام نشد.",
    );
    error.status = response.status;
    throw error;
  }
  return data;
}
function IndexSelect({ value, onChange, disabled, label }) {
  return (
    <DashboardSelect
      aria-label={label}
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
    >
      {Object.entries(statuses).map(([id, title]) => (
        <option key={id} value={id}>
          {title}
        </option>
      ))}
    </DashboardSelect>
  );
}
function CategoryOptions({ rows }) {
  const byId = new Map(rows.map((row) => [row.id, row]));
  function label(row) {
    const parts = [row.name],
      seen = new Set([row.id]);
    let parent = byId.get(row.parent_id);
    while (parent && !seen.has(parent.id)) {
      seen.add(parent.id);
      parts.unshift(parent.name);
      parent = byId.get(parent.parent_id);
    }
    return parts.join(" / ");
  }
  return rows.map((row) => (
    <option value={row.id} key={row.id}>
      {label(row)}
    </option>
  ));
}
export default function PageRobotsManager() {
  const [kind, setKind] = useState("product"),
    [search, setSearch] = useState(""),
    [query, setQuery] = useState("");
  const [status, setStatus] = useState("all"),
    [category, setCategory] = useState(""),
    [page, setPage] = useState(1),
    [pageSize, setPageSize] = useState(20),
    [reload, setReload] = useState(0);
  const [state, setState] = useState({ data: null, error: "", loading: true });
  const [selected, setSelected] = useState([]),
    [changes, setChanges] = useState({}),
    [bulk, setBulk] = useState("noindex"),
    [confirm, setConfirm] = useState(null);
  const [busy, setBusy] = useState(false),
    [notice, setNotice] = useState(""),
    [error, setError] = useState("");
  const lock = useRef(false),
    generation = useRef(0);
  const filterKey = JSON.stringify({
    kind,
    query,
    status,
    category,
    page,
    pageSize,
  });
  const current = state.key === filterKey ? state.data : null;
  const rows = current?.results || [];
  const canChange = Boolean(current?.can_change) && !busy && !state.loading;
  const selectedRows = rows.filter((row) => selected.includes(keyOf(row)));
  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    const controller = new AbortController();
    const requestId = ++generation.current;
    setState((previous) => ({ ...previous, loading: true, error: "" }));
    setSelected([]);
    setChanges({});
    setConfirm(null);
    setError("");
    const params = new URLSearchParams({
      kind,
      search: query,
      indexing: status,
      page,
      page_size: pageSize,
    });
    if (kind === "product" && category) params.set("category", category);
    api("?" + params, undefined, undefined, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted && requestId === generation.current)
          setState({ data, error: "", loading: false, key: filterKey });
      })
      .catch((err) => {
        if (!controller.signal.aborted)
          setState({
            data: null,
            error: err.message,
            loading: false,
            key: filterKey,
          });
      });
    return () => controller.abort();
  }, [filterKey, reload]);
  useEffect(() => {
    if (!Object.keys(changes).length) return;
    const warn = (e) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [changes]);
  useEffect(() => {
    if (!confirm) return;
    const previous = document.activeElement;
    const dialog = document.querySelector(".ix-modal");
    const trap = (event) => {
      if (event.key !== "Tab") return;
      const nodes = [...dialog.querySelectorAll("button:not(:disabled)")];
      if (!nodes.length) {
        event.preventDefault();
        return;
      }
      if (event.shiftKey && document.activeElement === nodes[0]) {
        event.preventDefault();
        nodes.at(-1).focus();
      } else if (!event.shiftKey && document.activeElement === nodes.at(-1)) {
        event.preventDefault();
        nodes[0].focus();
      }
    };
    dialog?.addEventListener("keydown", trap);
    return () => {
      dialog?.removeEventListener("keydown", trap);
      previous?.focus?.();
    };
  }, [confirm]);
  function navigate(action) {
    if (
      Object.keys(changes).length &&
      !window.confirm("ویرایش‌های ذخیره‌نشده کنار گذاشته شوند؟")
    )
      return;
    setChanges({});
    setSelected([]);
    setConfirm(null);
    action();
    setNotice("");
  }
  function select(row, checked) {
    const key = keyOf(row);
    setSelected((old) =>
      checked ? [...new Set([...old, key])] : old.filter((id) => id !== key),
    );
  }
  async function submit(items, indexing) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await api(
        "",
        {
          action: "bulk_index",
          indexing,
          items: items.map((row) => ({
            kind: row.kind,
            object_id: row.object_id,
            expected_version: row.version,
            ...(row.nextIndexing ? { indexing: row.nextIndexing } : {}),
          })),
        },
        current.csrfToken,
      );
      setNotice(
        `تنظیم ${result.updated.toLocaleString("fa-IR")} صفحه ذخیره شد؛ اعمال در گوگل پس از بازخوانی است.`,
      );
      setChanges({});
      setSelected([]);
      setConfirm(null);
      setReload((v) => v + 1);
    } catch (err) {
      setError(
        err.status === 409
          ? "یکی از صفحات هم‌زمان تغییر کرده؛ هیچ‌کدام ذخیره نشدند. فهرست را تازه‌سازی کن."
          : err.message,
      );
      setConfirm(null);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return (
    <section className="ix-manager" dir="rtl">
      <header className="ix-heading">
        <div>
          <span className="ix-eyebrow">مدیریت سئو / ایندکس</span>
          <h2>صفحات فروشگاه، مرتب و قابل کنترل</h2>
          <p>
            اجازهٔ حضور در نتایج گوگل را تنظیم کن. قوانین خزش در تب robots.txt
            مدیریت می‌شوند.
          </p>
        </div>
        <button
          type="button"
          disabled={busy}
          onClick={() => navigate(() => setReload((v) => v + 1))}
        >
          تازه‌سازی
        </button>
      </header>
      <nav className="ix-tabs" aria-label="نوع صفحه">
        {Object.entries(kinds).map(([id, title]) => (
          <button
            type="button"
            key={id}
            disabled={busy}
            aria-pressed={kind === id}
            onClick={() =>
              navigate(() => {
                setKind(id);
                setCategory("");
                setPage(1);
              })
            }
          >
            {title}
          </button>
        ))}
      </nav>
      <div className="ix-filters">
        <label className="ix-search">
          جست‌وجو
          <input
            type="search"
            value={search}
            disabled={busy}
            placeholder="نام، نامک یا شناسهٔ صفحه…"
            onChange={(e) => {
              const next = e.target.value;
              navigate(() => setSearch(next));
            }}
          />
        </label>
        <label>
          وضعیت ایندکس
          <DashboardSelect
            value={status}
            disabled={busy}
            onChange={(e) =>
              navigate(() => {
                setStatus(e.target.value);
                setPage(1);
              })
            }
          >
            <option value="all">همهٔ وضعیت‌ها</option>
            {Object.entries(statuses).map(([id, title]) => (
              <option key={id} value={id}>
                {title}
              </option>
            ))}
          </DashboardSelect>
        </label>
        {kind === "product" && (
          <label>
            دسته و زیرشاخه‌ها
            <DashboardSelect
              searchable
              value={category}
              disabled={busy || state.loading}
              onChange={(e) =>
                navigate(() => {
                  setCategory(e.target.value);
                  setPage(1);
                })
              }
            >
              <option value="">همهٔ دسته‌ها</option>
              <CategoryOptions rows={state.data?.categories || []} />
            </DashboardSelect>
          </label>
        )}
        <label>
          تعداد در صفحه
          <DashboardSelect
            value={pageSize}
            disabled={busy}
            onChange={(e) =>
              navigate(() => {
                setPageSize(Number(e.target.value));
                setPage(1);
              })
            }
          >
            {[20, 50, 100].map((value) => (
              <option key={value} value={value}>
                {value.toLocaleString("fa-IR")} ردیف
              </option>
            ))}
          </DashboardSelect>
        </label>
      </div>
      <div className="ix-help">
        <strong>پیش‌فرض صفحه</strong> از سیاست فعلی سایت استفاده می‌کند. «عدم
        ایندکس» برای حذف از نتایج است؛ جای بستن خزش را نمی‌گیرد. صفحات خصوصی با
        این بخش قابل ایندکس نمی‌شوند.
      </div>
      {notice && (
        <p role="status" className="ix-notice">
          {notice}
        </p>
      )}
      {(error || state.error) && (
        <p role="alert" className="ix-error">
          {error || state.error}
        </p>
      )}
      <div className="ix-bulk">
        <span>
          {selectedRows.length.toLocaleString("fa-IR")} صفحه انتخاب شده
        </span>
        <IndexSelect
          label="وضعیت گروهی"
          value={bulk}
          onChange={setBulk}
          disabled={!canChange || !selectedRows.length}
        />
        <button
          type="button"
          className="ix-primary"
          disabled={!canChange || !selectedRows.length}
          onClick={() => {
            if (
              Object.keys(changes).length &&
              !window.confirm(
                "تغییر گروهی جای ویرایش‌های ذخیره‌نشدهٔ این صفحه را بگیرد؟",
              )
            )
              return;
            setConfirm({ rows: selectedRows, indexing: bulk });
          }}
        >
          اعمال روی انتخاب‌ها
        </button>
        <small>انتخاب فقط برای ردیف‌های همین صفحه است.</small>
      </div>
      {Object.keys(changes).length > 0 && (
        <div className="ix-edits">
          <span>
            {Object.keys(changes).length.toLocaleString("fa-IR")} ویرایش
            ذخیره‌نشده
          </span>
          <button
            type="button"
            className="ix-primary"
            disabled={!canChange}
            onClick={() =>
              submit(
                rows
                  .filter((row) => changes[keyOf(row)] !== undefined)
                  .map((row) => ({
                    ...row,
                    nextIndexing: changes[keyOf(row)],
                  })),
                "inherit",
              )
            }
          >
            ذخیرهٔ همهٔ ویرایش‌ها
          </button>
          <button type="button" disabled={busy} onClick={() => setChanges({})}>
            کنارگذاشتن ویرایش‌ها
          </button>
        </div>
      )}
      <div className="ix-table-scroll">
        <table className="ix-table">
          <thead>
            <tr>
              <th>
                <input
                  type="checkbox"
                  aria-label="انتخاب همهٔ ردیف‌های همین صفحه"
                  disabled={!canChange || !rows.length}
                  checked={
                    rows.length > 0 && selectedRows.length === rows.length
                  }
                  onChange={(e) =>
                    setSelected(e.target.checked ? rows.map(keyOf) : [])
                  }
                />
              </th>
              <th>صفحه / آدرس</th>
              <th>شناسه</th>
              {kind === "product" && <th>دسته‌بندی</th>}
              <th>وضعیت ذخیره‌شده</th>
              <th>تنظیم جدید</th>
              <th>عملیات</th>
            </tr>
          </thead>
          <tbody>
            {state.loading ? (
              <tr>
                <td colSpan={7} className="ix-empty" role="status">
                  در حال دریافت صفحات…
                </td>
              </tr>
            ) : rows.length ? (
              rows.map((row) => {
                const key = keyOf(row);
                const value = changes[key] ?? row.indexing;
                return (
                  <tr
                    key={key}
                    className={selected.includes(key) ? "is-selected" : ""}
                  >
                    <td>
                      <input
                        type="checkbox"
                        aria-label={`انتخاب ${row.name}`}
                        disabled={!canChange}
                        checked={selected.includes(key)}
                        onChange={(e) => select(row, e.target.checked)}
                      />
                    </td>
                    <td>
                      <strong>{row.name}</strong>
                      <a
                        href={row.url}
                        target="_blank"
                        rel="noreferrer"
                        dir="ltr"
                      >
                        {row.url}
                      </a>
                    </td>
                    <td>
                      <bdi>{row.object_id || "—"}</bdi>
                    </td>
                    {kind === "product" && <td>{row.category_name || "—"}</td>}
                    <td>
                      <span className={`ix-status ix-${row.indexing}`}>
                        {statuses[row.indexing]}
                      </span>
                    </td>
                    <td>
                      <IndexSelect
                        label={`ایندکس ${row.name}`}
                        value={value}
                        disabled={!canChange}
                        onChange={(next) =>
                          setChanges((old) => {
                            const copy = { ...old };
                            if (next === row.indexing) delete copy[key];
                            else copy[key] = next;
                            return copy;
                          })
                        }
                      />
                    </td>
                    <td>
                      <button
                        type="button"
                        disabled={
                          !canChange ||
                          value === row.indexing ||
                          Object.keys(changes).length > 1
                        }
                        onClick={() => submit([row], value)}
                      >
                        {busy ? "…" : "ذخیره"}
                      </button>
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={7} className="ix-empty">
                  صفحه‌ای با این فیلترها پیدا نشد.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <footer className="ix-pagination">
        <span>
          {(current?.count || 0).toLocaleString("fa-IR")} نتیجه · صفحهٔ{" "}
          {page.toLocaleString("fa-IR")}
        </span>
        <div>
          <button
            type="button"
            disabled={page === 1 || busy || state.loading}
            onClick={() => navigate(() => setPage((v) => v - 1))}
          >
            قبلی
          </button>
          <button
            type="button"
            disabled={!current?.has_next || busy || state.loading}
            onClick={() => navigate(() => setPage((v) => v + 1))}
          >
            بعدی
          </button>
        </div>
      </footer>
      {confirm && (
        <div
          className="ix-modal-backdrop"
          onKeyDown={(e) => {
            if (e.key === "Escape" && !busy) setConfirm(null);
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="ix-confirm-title"
            className="ix-modal"
          >
            <h3 id="ix-confirm-title">تأیید تغییر گروهی</h3>
            <p>
              وضعیت {confirm.rows.length.toLocaleString("fa-IR")} صفحهٔ
              انتخاب‌شده به «{statuses[confirm.indexing]}» تغییر می‌کند.
            </p>
            <p>
              فایل robots.txt تغییر نمی‌کند. عملیات شامل تمام نتایج جست‌وجو
              نیست.
            </p>
            <div>
              <button
                autoFocus
                type="button"
                disabled={busy}
                onClick={() => setConfirm(null)}
              >
                انصراف
              </button>
              <button
                type="button"
                className="ix-primary"
                disabled={busy}
                onClick={() => submit(confirm.rows, confirm.indexing)}
              >
                {busy ? "در حال ذخیره…" : "تأیید و ذخیره"}
              </button>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
