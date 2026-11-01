import RobotsStudio from "./seo/RobotsStudio";
import PageRobotsManager from "./seo/PageRobotsManager";
import { managementFetch } from "./managementAuth";
import { useEffect, useState } from "react";

const BASE = "/api/v1/owner/seo/";

const permissionLabels = {
  view: "مشاهده",
  change: "تغییر",
  history: "تاریخچه",
};

async function request(path = "", options = {}) {
  const response = await managementFetch(`${BASE}${path}`, {
    credentials: "same-origin",
    cache: "no-store",
    ...options,
    headers: {
      Accept: "application/json",
      ...options.headers,
    },
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      typeof data?.detail === "string"
        ? data.detail
        : data
          ? JSON.stringify(data)
          : `خطای ${response.status}`,
    );
  }

  if (!data) {
    throw new Error("پاسخ سرور معتبر نیست.");
  }

  return data;
}

function useSEO(path) {
  const [result, setResult] = useState({
    path: null,
    data: null,
    error: "",
  });

  useEffect(() => {
    const controller = new AbortController();

    request(path, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) {
          setResult({ path, data, error: "" });
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setResult({ path, data: null, error: error.message });
        }
      });

    return () => controller.abort();
  }, [path]);

  const ready = result.path === path;

  return {
    data: ready ? result.data : null,
    error: ready ? result.error : "",
    loading: !ready,
  };
}

function post(path, payload, csrfToken) {
  return request(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken,
    },
    body: JSON.stringify(payload),
  });
}

function PermissionRow({ user, csrfToken, onSaved }) {
  const [flags, setFlags] = useState(user.direct);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function toggle(key, checked) {
    setFlags((current) => {
      const next = { ...current, [key]: checked };

      if (key === "change" && checked) next.view = true;
      if (key === "view" && !checked) next.change = false;

      return next;
    });
  }

  async function save() {
    setBusy(true);
    setError("");

    try {
      await post("access/", { user_id: user.id, ...flags }, csrfToken);
    } catch (err) {
      setError(err.message);
      setBusy(false);
      return;
    }

    onSaved();
  }

  const inherited = Object.keys(permissionLabels).filter(
    (key) => user.inherited[key],
  );

  return (
    <div
      style={{
        padding: 18,
        border: "1px solid #e3eaf4",
        borderRadius: 14,
        marginBottom: 12,
      }}
    >
      <strong>{user.full_name || user.username}</strong>
      <p className="muted">{user.username}</p>

      <div
        style={{
          display: "flex",
          gap: 20,
          flexWrap: "wrap",
          margin: "15px 0",
        }}
      >
        {Object.entries(permissionLabels).map(([key, label]) => (
          <label className="checkbox" key={key}>
            <input
              type="checkbox"
              checked={flags[key]}
              disabled={busy}
              onChange={(event) => toggle(key, event.target.checked)}
            />
            {label}
          </label>
        ))}
      </div>

      {inherited.length > 0 && (
        <p className="muted" style={{ marginBottom: 12 }}>
          دسترسی از گروه:{" "}
          {inherited.map((key) => permissionLabels[key]).join("، ")}. لغو آن
          باید از گروه مربوط در Django Admin انجام شود.
        </p>
      )}

      {error && <p role="alert">{error}</p>}

      <button className="button primary" disabled={busy} onClick={save}>
        {busy ? "در حال ذخیره…" : "ذخیرهٔ دسترسی مستقیم"}
      </button>
    </div>
  );
}

function AccessManager({ csrfToken }) {
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [notice, setNotice] = useState("");

  const state = useSEO(`access/?page=${page}&refresh=${revision}`);

  return (
    <section className="card" style={{ marginTop: 22 }}>
      <div className="section-heading">
        <h2>دسترسی مسئولان SEO</h2>
      </div>

      <p className="muted" style={{ marginBottom: 20 }}>
        تیک‌ها مجوز مستقیم هستند. حساب مسئول باید قبلاً در بخش کاربران، فعال و
        عضو مدیریت (Staff) شده باشد. نیازی به Superuser کردن مسئول SEO نیست.
      </p>

      {notice && <p role="status">{notice}</p>}
      {state.loading && <p role="status">در حال دریافت کاربران…</p>}
      {state.error && <p role="alert">{state.error}</p>}

      {state.data?.results.map((user) => (
        <PermissionRow
          key={`${user.id}:${revision}:${page}`}
          user={user}
          csrfToken={csrfToken}
          onSaved={() => {
            setNotice("دسترسی‌ها ذخیره شدند.");
            setRevision((value) => value + 1);
          }}
        />
      ))}

      {state.data?.results.length === 0 && (
        <p>حساب فعال Staff به‌جز مدیر اصلی پیدا نشد.</p>
      )}

      {state.data && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 15,
            marginTop: 20,
          }}
        >
          <button
            className="button ghost"
            disabled={!state.data.previous}
            onClick={() => setPage((value) => value - 1)}
          >
            قبلی
          </button>

          <span>{page.toLocaleString("fa-IR")}</span>

          <button
            className="button ghost"
            disabled={!state.data.next}
            onClick={() => setPage((value) => value + 1)}
          >
            بعدی
          </button>
        </div>
      )}
    </section>
  );
}

export default function SEOManager() {
  const state = useSEO("");
  const [tab, setTab] = useState("robots");
  if (state.loading) return <p role="status">در حال دریافت دسترسی سئو…</p>;
  if (state.error)
    return (
      <section className="card">
        <p role="alert">{state.error}</p>
      </section>
    );
  const { capabilities, csrfToken, logs } = state.data;
  return (
    <>
      {capabilities.view && (
        <>
          <nav className="rs-section-tabs" aria-label="بخش‌های سئو">
            <button
              type="button"
              aria-pressed={tab === "robots"}
              onClick={() => setTab("robots")}
            >
              robots.txt
            </button>
            <button
              type="button"
              aria-pressed={tab === "index"}
              onClick={() => setTab("index")}
            >
              ایندکس صفحات
            </button>
          </nav>
          {tab === "robots" ? (
            <RobotsStudio />
          ) : (
            <PageRobotsManager indexOnly />
          )}
        </>
      )}
      {!capabilities.view && (
        <section className="card">
          <p>برای مدیریت robots.txt به مجوز مشاهدهٔ سئو نیاز دارید.</p>
        </section>
      )}
      {capabilities.history && (
        <details className="rs-access">
          <summary>تاریخچهٔ تنظیمات قبلی سئو</summary>
          <ul>
            {logs.map((log) => (
              <li key={log.id}>
                {log.changed_by} ·{" "}
                {new Date(log.changed_at).toLocaleString("fa-IR")} ·{" "}
                {log.old_value ? "مجاز" : "مسدود"} ←{" "}
                {log.new_value ? "مجاز" : "مسدود"}
              </li>
            ))}
          </ul>
          {logs.length === 0 && <p>تغییری ثبت نشده است.</p>}
        </details>
      )}
      {capabilities.manage_access && (
        <details className="rs-access">
          <summary>مدیریت دسترسی مسئولان سئو</summary>
          <AccessManager csrfToken={csrfToken} />
        </details>
      )}
    </>
  );
}
