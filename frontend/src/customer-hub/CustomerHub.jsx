import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { getProfile, hasSession, logout, logoutAll } from "../customerAuth";
import CustomerAccount from "../CustomerAccount";
import PayOrderButton from "../payments/PayOrderButton";
import { cancelOrder } from "../orders/order-api";
import { money, number, safeImage } from "../storefront/store-api";
import { customerRequest } from "./api";
import HubIcon from "./Icons";
import "./customer-hub.css";

const MENU = [
  ["overview", "حساب کاربری", "user"],
  ["orders", "سفارش‌های من", "orders"],
  ["later", "خرید بعدی", "later"],
  ["returns", "درخواست‌های مرجوعی", "return"],
  ["addresses", "آدرس‌های من", "pin"],
  ["favorites", "علاقه‌مندی‌ها", "heart"],
  ["profile", "ویرایش اطلاعات", "user"],
  ["security", "امنیت حساب", "shield"],
];
const STATUSES = [
  ["pending_payment", "در انتظار پرداخت", "payment"],
  ["paid", "در حال آماده‌سازی", "box"],
  ["shipped", "ارسال‌شده", "truck"],
  ["delivered", "تحویل‌شده", "shield"],
];
const statusName = (value) =>
  [...STATUSES, ["cancelled", "لغوشده"], ["expired", "منقضی‌شده"]].find(
    (row) => row[0] === value,
  )?.[1] || value;
const date = (value) =>
  value ? new Date(value).toLocaleDateString("fa-IR") : "—";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
function snapshot() {
  return window.location.pathname + window.location.search;
}
function subscribe(listener) {
  window.addEventListener("customer-hub:navigate", listener);
  window.addEventListener("popstate", listener);
  return () => {
    window.removeEventListener("customer-hub:navigate", listener);
    window.removeEventListener("popstate", listener);
  };
}
function go(href) {
  window.history.pushState(null, "", href);
  window.dispatchEvent(new Event("customer-hub:navigate"));
  window.scrollTo({ top: 0, behavior: "instant" });
}
function HubLink({ href, children, ...props }) {
  return (
    <a
      {...props}
      href={href}
      onClick={(event) => {
        if (
          !event.defaultPrevented &&
          event.button === 0 &&
          !event.ctrlKey &&
          !event.metaKey &&
          !event.shiftKey &&
          !event.altKey
        ) {
          event.preventDefault();
          go(href);
        }
      }}
    >
      {children}
    </a>
  );
}
function useLoad(path, revision = 0) {
  const [result, setResult] = useState({});
  const [attempt, setAttempt] = useState(0);
  const key = `${path}:${revision}:${attempt}`;
  useEffect(() => {
    const controller = new AbortController();
    customerRequest(path, undefined, "GET", controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setResult({ key, data });
      })
      .catch((error) => {
        if (!controller.signal.aborted) setResult({ key, error });
      });
    return () => controller.abort();
  }, [path, key]);
  return {
    data: result.key === key ? result.data : null,
    error: result.key === key ? result.error : null,
    retry: () => setAttempt((v) => v + 1),
  };
}
function LoadState({ error, retry }) {
  return (
    <div className="ch-empty" role={error ? "alert" : "status"}>
      <HubIcon name="box" size={34} />
      <p>{error?.message || "در حال دریافت اطلاعات…"}</p>
      {error && (
        <button className="ch-button" type="button" onClick={retry}>
          تلاش دوباره
        </button>
      )}
    </div>
  );
}
function OrderCard({ order }) {
  return (
    <article className="ch-order-card">
      <header>
        <span className={`ch-status ch-status-${order.status}`}>
          {statusName(order.status)}
        </span>
        <HubLink href={`/account/orders/${order.id}`}>جزئیات سفارش ←</HubLink>
      </header>
      <div className="ch-order-meta">
        <span>
          کد سفارش <bdi>{order.id.slice(0, 8).toUpperCase()}</bdi>
        </span>
        <span>{date(order.created_at)}</span>
        <strong>{money(order.total)}</strong>
      </div>
      <div className="ch-order-items">
        {order.items.slice(0, 4).map((item) => (
          <span key={item.id}>
            <HubIcon name="box" size={19} />
            {item.product_name}
            {item.variant_name && <small>{item.variant_name}</small>}
          </span>
        ))}
      </div>
      <footer>
        <span>
          {number(order.items.reduce((sum, item) => sum + item.quantity, 0))}{" "}
          کالا
        </span>
        <HubLink className="ch-link" href={`/account/orders/${order.id}`}>
          {order.status === "pending_payment"
            ? "ادامه و پرداخت"
            : "مشاهده و پیگیری"}{" "}
          ←
        </HubLink>
      </footer>
    </article>
  );
}
function Overview() {
  const state = useLoad("summary/");
  if (!state.data) return <LoadState {...state} />;
  const data = state.data;
  return (
    <>
      <section className="ch-card">
        <div className="ch-card-title">
          <h1>سفارش‌های من</h1>
          <HubLink href="/account?tab=orders">مشاهدهٔ همه ←</HubLink>
        </div>
        <div className="ch-stats">
          {STATUSES.map(([status, title, icon]) => (
            <HubLink key={status} href={`/account?tab=orders&status=${status}`}>
              <span className="ch-stat-icon">
                <HubIcon name={icon} size={27} />
              </span>
              <span>
                <strong>{number(data.counts[status] || 0)} سفارش</strong>
                <small>{title}</small>
              </span>
            </HubLink>
          ))}
        </div>
      </section>
      <section className="ch-card">
        <div className="ch-card-title">
          <h2>سفارش‌های اخیر</h2>
          <HubLink href="/account?tab=orders">همهٔ سفارش‌ها ←</HubLink>
        </div>
        {data.recent_orders.length ? (
          data.recent_orders.map((order) => (
            <OrderCard key={order.id} order={order} />
          ))
        ) : (
          <div className="ch-empty">
            <HubIcon name="orders" size={38} />
            <h3>هنوز سفارشی ثبت نکرده‌ای</h3>
            <p>بعد از خرید، وضعیت سفارش‌ها اینجا نمایش داده می‌شود.</p>
            <a className="ch-button" href="/products">
              دیدن محصولات
            </a>
          </div>
        )}
      </section>
    </>
  );
}
function Pagination({ data, href }) {
  return (
    (data.previous || data.next) && (
      <nav className="ch-pagination" aria-label="صفحه‌بندی">
        {data.previous && <HubLink href={href(-1)}>صفحهٔ قبل</HubLink>}
        {data.next && <HubLink href={href(1)}>صفحهٔ بعد</HubLink>}
      </nav>
    )
  );
}
function Orders({ params }) {
  const page = Math.max(1, Number(params.get("page")) || 1);
  const status = params.get("status") || "";
  const state = useLoad(`orders/?${new URLSearchParams({ page, status })}`);
  return (
    <section className="ch-card">
      <div className="ch-card-title">
        <h1>سفارش‌های من</h1>
        <span>{state.data ? `${number(state.data.count)} سفارش` : ""}</span>
      </div>
      <nav className="ch-tabs" aria-label="وضعیت سفارش">
        {[
          ["", "همه"],
          ...STATUSES,
          ["cancelled", "لغوشده"],
          ["expired", "منقضی‌شده"],
        ].map(([value, label]) => (
          <HubLink
            key={value}
            className={value === status ? "is-active" : ""}
            href={`/account?tab=orders${value ? `&status=${value}` : ""}`}
          >
            {label}
          </HubLink>
        ))}
      </nav>
      {!state.data ? (
        <LoadState {...state} />
      ) : (
        <>
          {state.data.results.map((order) => (
            <OrderCard key={order.id} order={order} />
          ))}
          {!state.data.results.length && (
            <div className="ch-empty">سفارشی در این بخش وجود ندارد.</div>
          )}
          <Pagination
            data={state.data}
            href={(change) =>
              `/account?tab=orders&status=${status}&page=${page + change}`
            }
          />
        </>
      )}
    </section>
  );
}
function ReturnForm({ order, onSaved }) {
  const [quantities, setQuantities] = useState({});
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const lock = useRef(false);
  async function submit(event) {
    event.preventDefault();
    if (lock.current) return;
    const items = order.items
      .filter((item) => quantities[item.id] > 0)
      .map((item) => ({
        item_id: item.id,
        quantity: Number(quantities[item.id]),
      }));
    if (!items.length) {
      setError("حداقل یک کالا انتخاب کنید.");
      return;
    }
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      await customerRequest(
        "returns/",
        { order_id: order.id, reason, items },
        "POST",
      );
      onSaved();
    } catch (error) {
      setError(error.message);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return (
    <form className="ch-return-form" onSubmit={submit}>
      <h2>ثبت درخواست بررسی مرجوعی</h2>
      <p>
        کالا و تعداد را انتخاب کن. ثبت درخواست به معنی تأیید مرجوعی یا بازپرداخت
        نیست.
      </p>
      <fieldset disabled={busy}>
        {order.items.map((item) => (
          <label key={item.id} className="ch-return-item">
            <input
              type="checkbox"
              checked={Boolean(quantities[item.id])}
              onChange={(event) =>
                setQuantities((previous) => ({
                  ...previous,
                  [item.id]: event.target.checked ? 1 : 0,
                }))
              }
            />
            <span>
              {item.product_name}
              <small>{item.variant_name}</small>
            </span>
            {quantities[item.id] > 0 && (
              <input
                aria-label={`تعداد مرجوعی ${item.product_name}`}
                type="number"
                min="1"
                max={item.quantity}
                required
                value={quantities[item.id]}
                onChange={(event) =>
                  setQuantities((previous) => ({
                    ...previous,
                    [item.id]: event.target.value,
                  }))
                }
              />
            )}
          </label>
        ))}
        <label className="ch-field">
          دلیل درخواست
          <textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            required
            maxLength={1000}
            rows={4}
          />
        </label>
        <button className="ch-button" type="submit">
          {busy ? "در حال ثبت…" : "ثبت درخواست"}
        </button>
      </fieldset>
      {error && (
        <p className="ch-error" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}
function OrderDetails({ orderId }) {
  const state = useLoad(`orders/${orderId}/`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirm, setConfirm] = useState(false);
  const lock = useRef(false);
  if (!state.data) return <LoadState {...state} />;
  const order = state.data;
  async function cancel() {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      await cancelOrder(order.id);
      setConfirm(false);
      state.retry();
    } catch (error) {
      setError(error.message);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return (
    <section className="ch-card">
      <div className="ch-card-title">
        <h1>جزئیات سفارش</h1>
        <button type="button" className="ch-soft" onClick={state.retry}>
          تازه‌سازی وضعیت
        </button>
        <HubLink href="/account?tab=orders">همهٔ سفارش‌ها ←</HubLink>
      </div>
      <OrderCard order={order} />
      <div className="ch-progress">
        {STATUSES.map(([status, label, icon], index) => (
          <div
            className={
              STATUSES.findIndex((row) => row[0] === order.status) >= index
                ? "is-done"
                : ""
            }
            key={status}
          >
            <HubIcon name={icon} />
            <span>{label}</span>
          </div>
        ))}
      </div>
      <div className="ch-detail-grid">
        <div>
          <h2>نشانی تحویل</h2>
          <p>
            {order.recipient_name} · <bdi>{order.recipient_phone}</bdi>
          </p>
          <p>
            {order.province}، {order.city}، {order.street_address}، پلاک{" "}
            {order.building_number}
            {order.unit && `، واحد ${order.unit}`}
          </p>
          <p>
            کد پستی: <bdi>{order.postal_code}</bdi>
          </p>
        </div>
        <div>
          <h2>خلاصهٔ پرداخت</h2>
          <p>کالاها: {money(order.subtotal)}</p>
          <p>ارسال: {money(order.shipping_cost)}</p>
          <strong>مبلغ نهایی: {money(order.total)}</strong>
        </div>
      </div>
      <div className="ch-item-table">
        {order.items.map((item) => (
          <div key={item.id}>
            <span>
              {item.product_id ? (
                <a href={`/products/${item.product_id}`}>{item.product_name}</a>
              ) : (
                item.product_name
              )}
              <small>{item.variant_name}</small>
            </span>
            <span>{number(item.quantity)} عدد</span>
            <strong>{money(item.line_total)}</strong>
          </div>
        ))}
      </div>
      {order.shipment && (
        <div className="ch-shipment">
          <h2>اطلاعات ارسال</h2>
          <p>{order.shipment.carrier}</p>
          <p>
            کد رهگیری: <bdi>{order.shipment.tracking_code}</bdi>
          </p>
          {/^https:\/\//i.test(order.shipment.tracking_url) && (
            <a
              href={order.shipment.tracking_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              پیگیری مرسوله ←
            </a>
          )}
        </div>
      )}
      <div className="ch-actions">
        {order.status === "pending_payment" && (
          <>
            <PayOrderButton order={order} />
            <button
              className="ch-soft"
              type="button"
              disabled={busy}
              onClick={() => setConfirm((v) => !v)}
            >
              لغو سفارش
            </button>
            <small>
              مهلت پرداخت: {new Date(order.expires_at).toLocaleString("fa-IR")}
            </small>
          </>
        )}
        {confirm && (
          <div className="ch-confirm">
            <span>سفارش لغو شود؟</span>
            <button
              type="button"
              className="ch-danger"
              disabled={busy}
              onClick={cancel}
            >
              بله، لغو سفارش
            </button>
          </div>
        )}
      </div>
      {error && (
        <p className="ch-error" role="alert">
          {error}
        </p>
      )}
      {order.events.length > 0 && (
        <div className="ch-timeline">
          <h2>تاریخچهٔ پیگیری</h2>
          {order.events.map((event, index) => (
            <p key={index}>
              <strong>{statusName(event.status)}</strong> ·{" "}
              {date(event.created_at)}
              <small>{event.note}</small>
            </p>
          ))}
        </div>
      )}
      {order.return_request && <ReturnCard row={order.return_request} />}
      {order.status === "delivered" &&
        !order.return_request &&
        !order.can_request_return && (
          <p className="ch-muted">
            درخواست آنلاین مرجوعی برای این سفارش فعال نیست یا مهلت آن پایان
            یافته است.
          </p>
        )}
      {order.can_request_return && (
        <p className="ch-muted">
          مهلت ثبت درخواست: {number(order.return_policy?.days || 7)} روز پس از
          تحویل؛ مطابق سیاست فعلی فروشگاه.
        </p>
      )}
      {order.can_request_return && (
        <ReturnForm order={order} onSaved={state.retry} />
      )}
    </section>
  );
}
function ReturnCard({ row }) {
  return (
    <article className="ch-return-card">
      <header>
        <HubLink href={`/account/orders/${row.order_id}`}>
          سفارش {row.order_id.slice(0, 8).toUpperCase()}
        </HubLink>
        <span className="ch-status">{row.status_label}</span>
      </header>
      <p>{row.reason}</p>
      {row.item_details?.map((item) => (
        <p key={item.item_id}>
          {item.name} · {item.variant} · {number(item.quantity)} عدد
        </p>
      ))}
      {row.manager_note && (
        <p className="ch-manager-note">پاسخ فروشگاه: {row.manager_note}</p>
      )}
      <small>{date(row.created_at)}</small>
    </article>
  );
}
function Returns({ params }) {
  const page = Math.max(1, Number(params.get("page")) || 1);
  const state = useLoad(`returns/?page=${page}`);
  return (
    <section className="ch-card">
      <div className="ch-card-title">
        <h1>درخواست‌های مرجوعی</h1>
      </div>
      <p className="ch-muted">
        درخواست هر سفارش واجد شرایط، از صفحهٔ جزئیات همان سفارش ثبت می‌شود.
      </p>
      {!state.data ? (
        <LoadState {...state} />
      ) : (
        <>
          {state.data.results.map((row) => (
            <ReturnCard row={row} key={row.id} />
          ))}
          {!state.data.results.length && (
            <div className="ch-empty">درخواستی ثبت نشده است.</div>
          )}
          <Pagination
            data={state.data}
            href={(change) => `/account?tab=returns&page=${page + change}`}
          />
        </>
      )}
    </section>
  );
}
function SavedList({ kind, params }) {
  const page = Math.max(1, Number(params.get("page")) || 1);
  const state = useLoad(`saved/?kind=${kind}&page=${page}`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const lock = useRef(false);
  async function remove(row) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      await customerRequest(
        "saved/",
        { product_id: row.product_id, kind, enabled: false },
        "POST",
      );
      state.retry();
    } catch (error) {
      setError(error.message);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return (
    <section className="ch-card">
      <div className="ch-card-title">
        <h1>{kind === "favorite" ? "علاقه‌مندی‌ها" : "خرید بعدی"}</h1>
        <a href="/products">دیدن محصولات ←</a>
      </div>
      <p className="ch-muted">
        ذخیره در این فهرست، کالا یا قیمت را رزرو نمی‌کند.
      </p>
      {error && (
        <p role="alert" className="ch-error">
          {error}
        </p>
      )}
      {!state.data ? (
        <LoadState {...state} />
      ) : (
        <>
          <div className="ch-saved-grid">
            {state.data.results.map((row) => (
              <article key={row.id}>
                {safeImage(row.image) ? (
                  <img
                    src={safeImage(row.image)}
                    alt={row.name}
                    loading="lazy"
                  />
                ) : (
                  <span className="ch-saved-placeholder">
                    <HubIcon name="box" size={42} />
                  </span>
                )}
                <h2>{row.name}</h2>
                <strong>{row.available ? money(row.price) : "ناموجود"}</strong>
                <div>
                  {row.public && (
                    <a href={`/products/${row.product_id}`}>
                      مشاهده و انتخاب تنوع ←
                    </a>
                  )}
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => remove(row)}
                  >
                    حذف
                  </button>
                </div>
              </article>
            ))}
          </div>
          {!state.data.results.length && (
            <div className="ch-empty">
              هنوز کالایی در این فهرست ذخیره نشده است.
            </div>
          )}
          <Pagination
            data={state.data}
            href={(change) =>
              `/account?tab=${kind === "favorite" ? "favorites" : "later"}&page=${page + change}`
            }
          />
        </>
      )}
    </section>
  );
}
function Security() {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  async function leaveAll() {
    if (
      lock.current ||
      !window.confirm(
        "تمام نشست‌های مشتری و مدیریت این حساب در همهٔ دستگاه‌ها لغو شوند؟",
      )
    )
      return;
    lock.current = true;
    setBusy(true);
    try {
      await logoutAll();
      window.location.assign("/login");
    } catch (error) {
      setError(error.message);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return (
    <section className="ch-card">
      <div className="ch-card-title">
        <h1>امنیت حساب</h1>
      </div>
      <p>ورود به این فروشگاه با کد یک‌بارمصرف پیامکی انجام می‌شود.</p>
      <p className="ch-muted">
        خروج همگانی، نشست‌های مشتری و مدیریت همین حساب را در تمام دستگاه‌ها لغو
        می‌کند.
      </p>
      <button
        className="ch-soft"
        type="button"
        disabled={busy}
        onClick={leaveAll}
      >
        {busy ? "در حال انجام…" : "خروج از همهٔ دستگاه‌ها"}
      </button>
      {error && (
        <p className="ch-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
export default function CustomerHub() {
  const location = useSyncExternalStore(subscribe, snapshot, snapshot);
  const url = new URL(location, window.location.origin);
  const params = url.searchParams;
  const parts = url.pathname.replace(/\/+$/, "").split("/").filter(Boolean);
  const orderId =
    parts[0] === "orders" ? parts[1] : parts[1] === "orders" ? parts[2] : null;
  const requested =
    orderId || parts[0] === "orders" || parts[1] === "orders"
      ? "orders"
      : params.get("tab") || parts[1] || "overview";
  const tab = MENU.some((row) => row[0] === requested) ? requested : "overview";
  const [user, setUser] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  useEffect(() => {
    const next = `/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`;
    if (!hasSession()) {
      window.location.replace(next);
      return;
    }
    let active = true;
    getProfile()
      .then((data) => {
        if (active) {
          setUser(data);
          setError("");
        }
      })
      .catch((error) => {
        if (active) {
          if (error.status === 401 || !hasSession())
            window.location.replace(next);
          else setError(error.message);
        }
      });
    function expired(event) {
      if (event.detail?.storageKey === "digishop.customer.session")
        window.location.replace(next);
    }
    window.addEventListener("auth-expired", expired);
    return () => {
      active = false;
      window.removeEventListener("auth-expired", expired);
    };
  }, [attempt]);
  useEffect(() => {
    document.title = `${MENU.find((row) => row[0] === tab)?.[1]} | دیجی‌شاپ`;
  }, [tab]);
  async function signOut() {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      await logout();
      window.location.assign("/");
    } catch (error) {
      setError(error.message);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  if (!user)
    return (
      <main id="sf-main" className="sf-container ch-page">
        <LoadState
          error={error ? new Error(error) : null}
          retry={() => setAttempt((v) => v + 1)}
        />
      </main>
    );
  let content;
  if (orderId && !uuid.test(orderId))
    content = <div className="ch-empty">شناسهٔ سفارش معتبر نیست.</div>;
  else if (orderId) content = <OrderDetails key={orderId} orderId={orderId} />;
  else if (tab === "orders") content = <Orders params={params} />;
  else if (tab === "favorites" || tab === "later")
    content = (
      <SavedList
        key={tab}
        kind={tab === "favorites" ? "favorite" : "later"}
        params={params}
      />
    );
  else if (tab === "returns") content = <Returns params={params} />;
  else if (tab === "security") content = <Security />;
  else if (tab === "profile" || tab === "addresses")
    content = (
      <CustomerAccount
        key={tab}
        user={user}
        tab={tab}
        onSaved={setUser}
        onLogout={signOut}
        busy={busy}
        error=""
      />
    );
  else content = <Overview />;
  const name =
    [user.first_name, user.last_name].filter(Boolean).join(" ") ||
    "کاربر فروشگاه";
  return (
    <main id="sf-main" className="sf-container ch-page">
      <nav className="ch-breadcrumb" aria-label="مسیر حساب">
        <a href="/">فروشگاه</a>
        <span> / </span>
        <HubLink href="/account">حساب کاربری</HubLink>
        <span> / {MENU.find((row) => row[0] === tab)?.[1]}</span>
      </nav>
      <div className="ch-layout">
        <aside className="ch-sidebar">
          <div className="ch-identity">
            <span className="ch-avatar">
              {safeImage(user.image) ? (
                <img src={safeImage(user.image)} alt="" />
              ) : (
                name.charAt(0)
              )}
            </span>
            <div>
              <strong>{name}</strong>
              <bdi>{user.phone}</bdi>
            </div>
            <HubLink href="/account?tab=profile" aria-label="ویرایش اطلاعات">
              ✎
            </HubLink>
          </div>
          <nav aria-label="بخش‌های حساب مشتری">
            {MENU.map(([key, label, icon]) => (
              <HubLink
                href={key === "overview" ? "/account" : `/account?tab=${key}`}
                className={tab === key ? "is-active" : ""}
                aria-current={tab === key ? "page" : undefined}
                key={key}
              >
                <HubIcon name={icon} />
                <span>{label}</span>
                <span aria-hidden="true">‹</span>
              </HubLink>
            ))}
          </nav>
          <button
            className="ch-signout"
            type="button"
            disabled={busy}
            onClick={signOut}
          >
            <HubIcon name="logout" />
            {busy ? "در حال خروج…" : "خروج از حساب کاربری"}
          </button>
        </aside>
        <div className="ch-main">
          {error && (
            <p role="alert" className="ch-error">
              {error}
            </p>
          )}
          {content}
        </div>
      </div>
    </main>
  );
}
