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
      await post(
        "access/",
        { user_id: user.id, ...flags },
        csrfToken,
      );
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
          {inherited.map((key) => permissionLabels[key]).join("، ")}
          . لغو آن باید از گروه مربوط در Django Admin انجام شود.
        </p>
      )}

      {error && <p role="alert">{error}</p>}

      <button
        className="button primary"
        disabled={busy}
        onClick={save}
      >
        {busy ? "در حال ذخیره…" : "ذخیرهٔ دسترسی مستقیم"}
      </button>
    </div>
  );
}

function AccessManager({ csrfToken }) {
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [notice, setNotice] = useState("");

  const state = useSEO(
    `access/?page=${page}&refresh=${revision}`,
  );

  return (
    <section className="card" style={{ marginTop: 22 }}>
      <div className="section-heading">
        <h2>دسترسی مسئولان SEO</h2>
      </div>

      <p className="muted" style={{ marginBottom: 20 }}>
        تیک‌ها مجوز مستقیم هستند. حساب مسئول باید قبلاً در
        بخش کاربران، فعال و عضو مدیریت (Staff) شده باشد.
        نیازی به Superuser کردن مسئول SEO نیست.
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
  const [revision, setRevision] = useState(0);
  const [desired, setDesired] = useState(null);
  const [confirmation, setConfirmation] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const state = useSEO(`?refresh=${revision}`);

  function refresh() {
    setDesired(null);
    setConfirmation(null);
    setError("");
    setRevision((value) => value + 1);
  }

  async function submit(action) {
    if (!state.data || busy) return;

    setBusy(true);
    setError("");
    setNotice("");

    try {
      if (action === "prepare") {
        const prepared = await post(
          "",
          {
            action: "prepare",
            expected_version: state.data.settings.version,
            allow_crawling:
              desired ?? state.data.settings.allow_crawling,
          },
          state.data.csrfToken,
        );

        if (prepared.unchanged) {
          setNotice("تغییری نسبت به تنظیمات فعلی نداده‌ای.");
        } else {
          setConfirmation(prepared);
        }
      } else {
        await post(
          "",
          {
            action: "confirm",
            confirmation: confirmation.confirmation,
          },
          state.data.csrfToken,
        );

        setNotice("تنظیم خزش ذخیره و تغییر آن ثبت شد.");
        refresh();
      }
    } catch (err) {
      setError(err.message);
      setConfirmation(null);
    } finally {
      setBusy(false);
    }
  }

  if (state.loading) {
    return <p role="status">در حال دریافت تنظیمات SEO…</p>;
  }

  if (state.error) {
    return (
      <section className="card">
        <p role="alert">{state.error}</p>
        <button className="button primary" onClick={refresh}>
          تلاش دوباره
        </button>
      </section>
    );
  }

  const { settings, capabilities, logs, csrfToken } = state.data;

  return (
    <>
      <section className="card">
        <div className="section-heading">
          <h2>تنظیمات خزش ربات‌ها</h2>

          <button
            className="button ghost"
            disabled={busy}
            onClick={refresh}
          >
            تازه‌سازی
          </button>
        </div>

        {notice && <div className="notice" role="status">{notice}</div>}
        {error && <p role="alert" style={{ color: "#a33030" }}>{error}</p>}

        {settings ? (
          <>
            <p>
              وضعیت فعلی:{" "}
              <strong>
                {settings.allow_crawling ? "خزش مجاز" : "خزش غیرمجاز"}
              </strong>
            </p>

            <p className="muted">
              نسخهٔ تنظیمات: {settings.version.toLocaleString("fa-IR")}
            </p>

            {capabilities.change && (
              <>
                <label
                  className="checkbox"
                  style={{ margin: "25px 0" }}
                >
                  <input
                    type="checkbox"
                    checked={desired ?? settings.allow_crawling}
                    disabled={busy || Boolean(confirmation)}
                    onChange={(event) => setDesired(event.target.checked)}
                  />
                  اجازهٔ خزش عمومی ربات‌ها
                </label>

                {!confirmation ? (
                  <button
                    className="button primary"
                    disabled={busy}
                    onClick={() => submit("prepare")}
                  >
                    {busy ? "در حال بررسی…" : "بررسی و تأیید تغییر"}
                  </button>
                ) : (
                  <div
                    style={{
                      padding: 20,
                      background: "#fff8e8",
                      border: "1px solid #eddcb4",
                      borderRadius: 14,
                    }}
                  >
                    <strong>تغییر اجازهٔ خزش را تأیید می‌کنی؟</strong>

                    <p>
                      از {confirmation.old_value ? "مجاز" : "غیرمجاز"}
                      {" به "}
                      {confirmation.new_value ? "مجاز" : "غیرمجاز"}
                    </p>

                    <div style={{ display: "flex", gap: 10 }}>
                      <button
                        className="button primary"
                        disabled={busy}
                        onClick={() => submit("confirm")}
                      >
                        {busy ? "در حال ذخیره…" : "تأیید و ذخیره"}
                      </button>

                      <button
                        className="button ghost"
                        disabled={busy}
                        onClick={() => setConfirmation(null)}
                      >
                        انصراف
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}

            <p className="muted" style={{ marginTop: 22 }}>
              این تنظیم محتوای robots.txt را تغییر می‌دهد؛
              مجوز دسترسی به صفحات یا تضمین حذف از موتور جست‌وجو نیست.
            </p>
          </>
        ) : (
          <p>مجوز مشاهدهٔ تنظیمات را نداری.</p>
        )}
      </section>

      {capabilities.history && (
        <section className="card" style={{ marginTop: 22 }}>
          <div className="section-heading">
            <h2>۲۰ تغییر اخیر SEO</h2>
          </div>

          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>تغییردهنده</th>
                  <th>قبلی</th>
                  <th>جدید</th>
                  <th>زمان</th>
                </tr>
              </thead>

              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td>{log.changed_by}</td>
                    <td>{log.old_value ? "مجاز" : "غیرمجاز"}</td>
                    <td>{log.new_value ? "مجاز" : "غیرمجاز"}</td>
                    <td>
                      {new Date(log.changed_at).toLocaleString("fa-IR")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {logs.length === 0 && <p>تغییری ثبت نشده است.</p>}
        </section>
      )}

      {capabilities.manage_access && (
        <AccessManager csrfToken={csrfToken} />
      )}
    </>
  );
}