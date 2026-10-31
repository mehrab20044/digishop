import { useEffect, useRef, useState } from "react";
import { api } from "../catalog/api";
import { money } from "../storefront/store-api";
import DashboardSelect from "../components/DashboardSelect";
import "../catalog/workspace.css";
import "./owner-hub.css";

export default function CustomerOperations({ resource }) {
  const [tab, setTab] = useState("orders");
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [data, setData] = useState(null);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [policy, setPolicy] = useState(null);
  const lock = useRef(false);
  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setPolicy(null);
    setError("");
    api(
      `customer-operations/?${new URLSearchParams({ kind: tab, page, status })}`,
      undefined,
      "GET",
      controller.signal,
    )
      .then((result) => {
        if (tab === "policy") setPolicy(result);
        else setData(result);
      })
      .catch((error) => {
        if (!controller.signal.aborted) setError(error.message);
      });
    return () => controller.abort();
  }, [tab, page, status, revision]);
  async function perform(payload, method) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api("customer-operations/", payload, method);
      setNotice("تغییر ذخیره شد.");
      setRevision((v) => v + 1);
    } catch (error) {
      setError(error.message);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return (
    <section className="cw oh-editor">
      <h1>سفارش‌ها و مرجوعی‌ها</h1>
      <div className="oh-tabs">
        {[
          ["orders", "سفارش‌ها"],
          ["returns", "مرجوعی‌ها"],
          ["policy", "سیاست مرجوعی"],
        ]
          .filter(
            ([key]) => key !== "returns" || resource.capabilities.view_returns,
          )
          .map(([key, label]) => (
            <button
              key={key}
              className={tab === key ? "is-active" : ""}
              type="button"
              disabled={busy}
              onClick={() => {
                setTab(key);
                setPage(1);
              }}
            >
              {label}
            </button>
          ))}
      </div>
      {error && (
        <p className="cw-error" role="alert">
          {error}
          <button type="button" onClick={() => setRevision((v) => v + 1)}>
            تازه‌سازی
          </button>
        </p>
      )}
      {notice && (
        <p className="cw-notice" role="status">
          {notice}
        </p>
      )}
      {tab === "orders" && (
        <label className="oh-field">
          <span>وضعیت</span>
          <DashboardSelect
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          >
            <option value="">همه</option>
            <option value="pending_payment">در انتظار پرداخت</option>
            <option value="paid">پرداخت‌شده؛ آماده ارسال</option>
            <option value="shipped">ارسال‌شده</option>
            <option value="delivered">تحویل‌شده</option>
            <option value="cancelled">لغوشده</option>
            <option value="expired">منقضی‌شده</option>
          </DashboardSelect>
        </label>
      )}
      {!data && !policy && !error && <p role="status">در حال دریافت…</p>}
      {data?.results.map((row) =>
        tab === "returns" ? (
          <article className="cw-panel" key={row.id}>
            <h2>
              مرجوعی سفارش <bdi>{row.order_id}</bdi>
            </h2>
            <p>{row.status_label}</p>
            <p>{row.reason}</p>
            <ul>
              {row.items.map((item) => (
                <li key={item.item_id}>
                  {row.item_details?.find(
                    (detail) => detail.item_id === item.item_id,
                  )?.name || `ردیف سفارش ${item.item_id}`}
                  ؛ تعداد {item.quantity}
                </li>
              ))}
            </ul>
            {row.manager_note && <p>پاسخ قبلی: {row.manager_note}</p>}
            {row.can_review &&
              ["requested", "approved"].includes(row.status) && (
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    const values = new FormData(event.currentTarget);
                    perform(
                      {
                        request_id: row.id,
                        expected_status: row.status,
                        status: values.get("status"),
                        note: values.get("note"),
                      },
                      "PATCH",
                    );
                  }}
                >
                  <fieldset disabled={busy}>
                    <label className="oh-field">
                      <span>نتیجه بررسی</span>
                      <DashboardSelect
                        name="status"
                        defaultValue={
                          row.status === "requested" ? "approved" : "received"
                        }
                      >
                        {row.status === "requested" ? (
                          <>
                            <option value="approved">
                              تأیید ارسال کالا توسط مشتری
                            </option>
                            <option value="rejected">رد درخواست</option>
                          </>
                        ) : (
                          <option value="received">
                            کالای مرجوعی دریافت شد
                          </option>
                        )}
                      </DashboardSelect>
                    </label>
                    <label className="oh-field">
                      <span>پاسخ قابل نمایش به مشتری</span>
                      <textarea
                        name="note"
                        required
                        maxLength={1000}
                        rows={3}
                      />
                    </label>
                    <button className="cw-primary" type="submit">
                      ثبت نتیجه بررسی
                    </button>
                  </fieldset>
                </form>
              )}
            <p>دریافت مرجوعی، به معنی بازپرداخت یا افزایش موجودی نیست.</p>
          </article>
        ) : (
          <article className="cw-panel" key={row.id}>
            <h2>
              <bdi>{row.id}</bdi>
            </h2>
            <p>
              {row.status_label} · {money(row.total)}
            </p>
            <p>
              {row.recipient_name} · <bdi>{row.recipient_phone}</bdi>
            </p>
            <p>
              {row.province}، {row.city}، {row.street_address}، پلاک{" "}
              {row.building_number}، واحد {row.unit || "—"}، کد پستی{" "}
              {row.postal_code}
            </p>
            <ul>
              {row.items.map((item) => (
                <li key={item.id}>
                  ردیف {item.id}: {item.product_name} — {item.variant_name} ×{" "}
                  {item.quantity}
                </li>
              ))}
            </ul>
            {row.shipment && (
              <p>
                رهگیری: {row.shipment.carrier} ·{" "}
                <bdi>{row.shipment.tracking_code}</bdi>
              </p>
            )}
            {row.can_change && row.status === "paid" && (
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  const values = new FormData(event.currentTarget);
                  perform(
                    {
                      order_id: row.id,
                      expected_status: row.status,
                      status: "shipped",
                      carrier: values.get("carrier"),
                      tracking_code: values.get("tracking_code"),
                      tracking_url: values.get("tracking_url"),
                      note: values.get("note"),
                    },
                    "POST",
                  );
                }}
              >
                <fieldset disabled={busy}>
                  <div className="oh-grid">
                    <label className="oh-field">
                      <span>روش / شرکت ارسال</span>
                      <input name="carrier" required maxLength={100} />
                    </label>
                    <label className="oh-field">
                      <span>کد رهگیری</span>
                      <input name="tracking_code" required maxLength={120} />
                    </label>
                    <label className="oh-field">
                      <span>آدرس رهگیری؛ اختیاری</span>
                      <input
                        name="tracking_url"
                        type="url"
                        placeholder="https://..."
                        maxLength={1000}
                      />
                    </label>
                    <label className="oh-field">
                      <span>توضیح قابل نمایش به مشتری</span>
                      <input name="note" maxLength={500} />
                    </label>
                  </div>
                  <button className="cw-primary" type="submit">
                    ثبت ارسال سفارش
                  </button>
                </fieldset>
              </form>
            )}
            {row.can_change && row.status === "shipped" && (
              <button
                className="cw-primary"
                type="button"
                disabled={busy}
                onClick={() => {
                  if (
                    window.confirm(
                      "تحویل واقعی این سفارش به مشتری تأیید می‌شود؟",
                    )
                  )
                    perform(
                      {
                        order_id: row.id,
                        expected_status: row.status,
                        status: "delivered",
                        note: "تحویل سفارش توسط فروشگاه تأیید شد.",
                      },
                      "POST",
                    );
                }}
              >
                تأیید تحویل به مشتری
              </button>
            )}
          </article>
        ),
      )}
      {data && data.results.length === 0 && (
        <p className="cw-panel">موردی وجود ندارد.</p>
      )}
      {data && (
        <div className="oh-pagination">
          <button
            type="button"
            disabled={busy || !data.previous}
            onClick={() => setPage((v) => v - 1)}
          >
            صفحه قبل
          </button>
          <span>{page.toLocaleString("fa-IR")}</span>
          <button
            type="button"
            disabled={busy || !data.next}
            onClick={() => setPage((v) => v + 1)}
          >
            صفحه بعد
          </button>
        </div>
      )}
      {policy && (
        <form
          className="cw-panel"
          onSubmit={(event) => {
            event.preventDefault();
            perform(
              { enabled: policy.enabled, days: Number(policy.days) },
              "PATCH",
            );
          }}
        >
          <h2>مهلت درخواست مرجوعی</h2>
          <p>
            این تنظیم، زمان مجاز ثبت درخواست پس از تحویل را تعیین می‌کند. پذیرش
            درخواست و بازپرداخت جداگانه بررسی می‌شوند.
          </p>
          <fieldset disabled={busy || !policy.editable}>
            <label>
              <input
                type="checkbox"
                checked={policy.enabled}
                onChange={(event) =>
                  setPolicy((previous) => ({
                    ...previous,
                    enabled: event.target.checked,
                  }))
                }
              />
              ثبت درخواست مرجوعی فعال باشد
            </label>
            <label className="oh-field">
              <span>تعداد روز پس از تحویل</span>
              <input
                type="number"
                required
                min={1}
                max={365}
                value={policy.days}
                onChange={(event) =>
                  setPolicy((previous) => ({
                    ...previous,
                    days: event.target.value,
                  }))
                }
              />
            </label>
            <button className="cw-primary" type="submit">
              ذخیره سیاست مرجوعی
            </button>
          </fieldset>
        </form>
      )}
    </section>
  );
}
