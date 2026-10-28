import { useEffect, useRef, useState } from "react";

import { hasSession } from "../customerAuth";
import { money, number } from "../storefront/store-api";
import { cancelOrder, loadOrder } from "./order-api";
import "./orders.css";

function formatDate(value) {
  if (!value) return "—";

  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleString("fa-IR");
}

function OrderProgress({ status }) {
  const stages = [
    { status: "pending_payment", label: "ثبت سفارش" },
    { status: "paid", label: "پرداخت" },
    { status: "shipped", label: "ارسال" },
    { status: "delivered", label: "تحویل" },
  ];
  const current = stages.findIndex(
    (stage) => stage.status === status,
  );

  if (current < 0) return null;

  return (
    <div className="sf-order-progress" aria-label="روند سفارش">
      {stages.map((stage, index) => (
        <div
          key={stage.status}
          className={`sf-order-progress-step ${
            index < current
              ? "is-complete"
              : index === current
                ? "is-current"
                : ""
          }`}
          aria-current={index === current ? "step" : undefined}
        >
          <span aria-hidden="true">
            {index < current ? "✓" : number(index + 1)}
          </span>
          {stage.label}
        </div>
      ))}
    </div>
  );
}

export default function OrderDetailPage({ orderId }) {
  const [order, setOrder] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [attempt, setAttempt] = useState(0);

  const lock = useRef(false);
  const mounted = useRef(false);

  useEffect(() => {
    mounted.current = true;

    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    if (!hasSession()) {
      setError("برای مشاهدهٔ سفارش وارد حساب مشتری شوید.");
      setLoading(false);
      return undefined;
    }

    let active = true;
    const controller = new AbortController();

    setLoading(true);
    setError("");
    setOrder(null);
    setConfirming(false);

    loadOrder(orderId, { signal: controller.signal })
      .then((data) => {
        if (active) setOrder(data);
      })
      .catch((err) => {
        if (active && err.name !== "AbortError") {
          setError(err.message);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [orderId, attempt]);

  async function cancel() {
    if (
      lock.current ||
      !order ||
      order.status !== "pending_payment"
    ) {
      return;
    }

    lock.current = true;
    setBusy(true);
    setError("");

    try {
      const result = await cancelOrder(order.id);

      if (mounted.current) {
        setOrder(result);
        setConfirming(false);
      }
    } catch (err) {
      if (mounted.current) setError(err.message);
    } finally {
      lock.current = false;
      if (mounted.current) setBusy(false);
    }
  }

  const pending = order?.status === "pending_payment";

  return (
    <section className="sf-orders">
      <div className="sf-orders-heading">
        <div>
          <h1>جزئیات سفارش</h1>
          <p>اطلاعات خرید و وضعیت تحویل سفارش شما</p>
        </div>
        <a className="sf-orders-back" href="/orders">
          همهٔ سفارش‌ها ←
        </a>
      </div>

      {loading && (
        <div className="sf-order-empty" role="status">
          <p>در حال دریافت جزئیات سفارش…</p>
        </div>
      )}

      {error && (
        <div className="sf-order-alert" role="alert">
          <p>{error}</p>
          {!hasSession() && (
            <a className="sf-orders-back" href="/login">
              ورود به حساب
            </a>
          )}
        </div>
      )}

      {!loading && !order && hasSession() && (
        <div className="sf-order-empty">
          <p>دریافت اطلاعات سفارش ممکن نشد.</p>
          <button
            className="sf-button"
            type="button"
            onClick={() => setAttempt((value) => value + 1)}
          >
            تلاش دوباره
          </button>
          <a href="/orders">بازگشت به سفارش‌ها</a>
        </div>
      )}

      {order && !loading && (
        <div className="sf-order-detail-layout">
          <div className="sf-order-detail-main">
            <section className="sf-order-panel">
              <div className="sf-order-panel-header">
                <h2>وضعیت سفارش</h2>
                <span
                  className={
                    `sf-order-status sf-order-status--${order.status}`
                  }
                >
                  {order.status_label}
                </span>
              </div>

              <div className="sf-order-panel-body">
                <dl className="sf-order-info-grid">
                  <div className="sf-order-info-wide">
                    <dt>شناسهٔ سفارش</dt>
                    <dd><bdi>{order.id}</bdi></dd>
                  </div>
                  <div>
                    <dt>تاریخ ثبت</dt>
                    <dd>{formatDate(order.created_at)}</dd>
                  </div>
                  <div>
                    <dt>آخرین تغییر</dt>
                    <dd>{formatDate(order.updated_at)}</dd>
                  </div>
                  {order.paid_at && (
                    <div>
                      <dt>تاریخ پرداخت</dt>
                      <dd>{formatDate(order.paid_at)}</dd>
                    </div>
                  )}
                  {order.shipped_at && (
                    <div>
                      <dt>تاریخ ارسال</dt>
                      <dd>{formatDate(order.shipped_at)}</dd>
                    </div>
                  )}
                  {order.delivered_at && (
                    <div>
                      <dt>تاریخ تحویل</dt>
                      <dd>{formatDate(order.delivered_at)}</dd>
                    </div>
                  )}
                  {order.cancelled_at && (
                    <div>
                      <dt>تاریخ لغو</dt>
                      <dd>{formatDate(order.cancelled_at)}</dd>
                    </div>
                  )}
                  {order.expired_at && (
                    <div>
                      <dt>تاریخ انقضا</dt>
                      <dd>{formatDate(order.expired_at)}</dd>
                    </div>
                  )}
                </dl>

                <OrderProgress status={order.status} />
              </div>
            </section>

            <section className="sf-order-panel">
              <div className="sf-order-panel-header">
                <h2>کالاهای سفارش</h2>
                <span className="sf-muted">
                  {number(
                    order.items.reduce(
                      (total, item) => total + item.quantity,
                      0,
                    ),
                  )} عدد
                </span>
              </div>

              <div className="sf-order-panel-body">
                {order.items.map((item) => (
                  <article
                    className="sf-checkout-item"
                    key={item.id}
                  >
                    <div>
                      <h3>{item.product_name}</h3>
                      {item.variant_name && (
                        <p>{item.variant_name}</p>
                      )}
                      {item.sku && (
                        <p>کد کالا: <bdi>{item.sku}</bdi></p>
                      )}
                      <p>
                        تعداد: {number(item.quantity)}
                        {" "} | قیمت واحد: {money(item.unit_price)}
                      </p>
                    </div>
                    <strong className="sf-checkout-item-total">
                      {money(item.line_total)}
                    </strong>
                  </article>
                ))}
              </div>
            </section>

            <section className="sf-order-panel">
              <div className="sf-order-panel-header">
                <h2>اطلاعات تحویل</h2>
              </div>

              <div className="sf-order-panel-body">
                <p className="sf-order-address-text">
                  <strong>{order.recipient_name}</strong>
                </p>
                <p className="sf-order-address-text">
                  {order.province}، {order.city}،
                  {" "}{order.street_address}،
                  پلاک {order.building_number}
                  {order.unit && `، واحد ${order.unit}`}
                </p>
                <p className="sf-order-address-text">
                  شمارهٔ تماس: <bdi>{order.recipient_phone}</bdi>
                </p>
                <p className="sf-order-address-text">
                  کد پستی: <bdi>{order.postal_code}</bdi>
                </p>
              </div>
            </section>

            {order.customer_note && (
              <section className="sf-order-panel">
                <div className="sf-order-panel-header">
                  <h2>یادداشت سفارش</h2>
                </div>
                <div className="sf-order-panel-body">
                  <p className="sf-order-note-text">
                    {order.customer_note}
                  </p>
                </div>
              </section>
            )}
          </div>

          <aside className="sf-order-detail-summary">
            <section className="sf-checkout-summary">
              <h2>خلاصهٔ مبلغ</h2>

              <div className="sf-order-amount-row">
                <span>جمع کالاها</span>
                <strong>{money(order.subtotal)}</strong>
              </div>
              <div className="sf-order-amount-row">
                <span>هزینهٔ ارسال</span>
                <strong>
                  {order.shipping_cost === 0
                    ? "رایگان"
                    : money(order.shipping_cost)}
                </strong>
              </div>
              <div className="sf-order-amount-row is-total">
                <span>مبلغ سفارش</span>
                <strong>{money(order.total)}</strong>
              </div>

              {pending && (
                <>
                  <p className="sf-order-deadline">
                    مهلت پرداخت: {formatDate(order.expires_at)}
                  </p>
                  <p className="sf-order-help">
                    پرداخت آنلاین هنوز فعال نشده است.
                  </p>
                </>
              )}

              {order.status === "cancelled" && (
                <p className="sf-order-help">
                  این سفارش لغو شده و قابل پرداخت نیست.
                </p>
              )}

              {order.status === "expired" && (
                <p className="sf-order-help">
                  مهلت پرداخت تمام شده و رزرو موجودی آزاد شده است.
                </p>
              )}

              <button
                className="sf-cart-action"
                type="button"
                disabled={busy}
                onClick={() =>
                  setAttempt((value) => value + 1)
                }
              >
                بررسی دوبارهٔ وضعیت
              </button>
            </section>

            {pending && (
              <section className="sf-order-panel">
                <div className="sf-order-panel-header">
                  <h2>لغو سفارش</h2>
                </div>

                <div className="sf-order-panel-body">
                  {!confirming ? (
                    <>
                      <p className="sf-order-help">
                        اگر از خرید منصرف شده‌اید، می‌توانید
                        سفارش پرداخت‌نشده را لغو کنید.
                      </p>
                      <div className="sf-order-actions">
                        <button
                          className="sf-order-danger"
                          type="button"
                          disabled={busy}
                          onClick={() => setConfirming(true)}
                        >
                          درخواست لغو سفارش
                        </button>
                      </div>
                    </>
                  ) : (
                    <div className="sf-order-cancel-confirm">
                      <p>
                        سفارش لغو شود؟ رزرو کالاها آزاد می‌شود
                        و این سفارش دیگر قابل پرداخت نیست.
                      </p>

                      <button
                        className="sf-order-danger"
                        type="button"
                        disabled={busy}
                        onClick={cancel}
                      >
                        {busy
                          ? "در حال بررسی…"
                          : "بله، سفارش لغو شود"}
                      </button>

                      <div className="sf-order-actions">
                        <button
                          className="sf-button sf-order-secondary"
                          type="button"
                          disabled={busy}
                          onClick={() => setConfirming(false)}
                        >
                          انصراف
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </section>
            )}
          </aside>
        </div>
      )}
    </section>
  );
}