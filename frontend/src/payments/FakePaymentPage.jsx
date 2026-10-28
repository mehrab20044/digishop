import { useEffect, useRef, useState } from "react";

import { hasSession } from "../customerAuth";
import { money } from "../storefront/store-api";
import {
  decideFakePayment,
  loadFakePayment,
  verifyFakePayment,
} from "./payment-api";
import "../orders/orders.css";

function formatDate(value) {
  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleString("fa-IR");
}

function statusMessage(status) {
  switch (status) {
    case "succeeded":
      return "پرداخت آزمایشی موفق بود. هیچ پول واقعی جابه‌جا نشده است.";
    case "cancelled":
      return "این تلاش پرداخت لغو شد. اگر سفارش هنوز مهلت دارد، از جزئیات سفارش دوباره اقدام کنید.";
    case "expired":
      return "مهلت این پرداخت پایان یافته است.";
    case "failed":
      return "این تلاش پرداخت موفق نبود.";
    case "review_required":
      return "نتیجهٔ پرداخت نیازمند بررسی است. پرداخت تازه‌ای شروع نکنید.";
    case "verifying":
      return "نتیجهٔ پرداخت در حال بررسی است.";
    default:
      return "برای آزمایش، نتیجهٔ پرداخت را انتخاب کنید.";
  }
}

export default function FakePaymentPage({ paymentId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [uncertain, setUncertain] = useState(false);

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
      setError("برای مشاهدهٔ پرداخت وارد حساب مشتری شوید.");
      setLoading(false);
      return undefined;
    }

    let active = true;
    const controller = new AbortController();

    setLoading(true);
    setError("");
    setData(null);

    loadFakePayment(paymentId, { signal: controller.signal })
      .then((result) => {
        if (active) {
          setData(result);
          setUncertain(false);
        }
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
  }, [paymentId, attempt]);

  async function perform(outcome) {
    if (lock.current || !data) return;

    lock.current = true;
    setBusy(true);
    setError("");

    try {
      const payment = outcome
        ? await decideFakePayment(paymentId, outcome)
        : await verifyFakePayment(paymentId);

      if (!mounted.current) return;

      setData((current) => ({
        ...current,
        payment,
        // Reload the page data to obtain a fresh can_decide value.
        can_decide: false,
      }));
      setUncertain(false);
    } catch (err) {
      if (!mounted.current) return;

      setError(err.message);
      setUncertain(true);
    } finally {
      lock.current = false;

      if (mounted.current) setBusy(false);
    }
  }

  const payment = data?.payment;
  const canDecide = Boolean(data?.can_decide && !uncertain);

  return (
    <section className="sf-orders">
      <div className="sf-orders-heading">
        <div>
          <h1>درگاه پرداخت آزمایشی</h1>
          <p>ویژهٔ آزمایش فرایند خرید فروشگاه</p>
        </div>
        <a className="sf-orders-back" href="/orders">
          سفارش‌های من
        </a>
      </div>

      <div className="sf-order-alert is-warning" role="note">
        این صفحه درگاه بانکی نیست. هیچ پول واقعی جابه‌جا
        نمی‌شود و نیازی به اطلاعات کارت بانکی ندارید.
      </div>

      {loading && (
        <div className="sf-order-empty" role="status">
          <p>در حال دریافت اطلاعات پرداخت…</p>
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

      {!loading && !data && hasSession() && (
        <div className="sf-order-empty">
          <p>اطلاعات پرداخت دریافت نشد.</p>
          <button
            className="sf-button"
            type="button"
            onClick={() => setAttempt((value) => value + 1)}
          >
            تلاش دوباره
          </button>
        </div>
      )}

      {payment && !loading && (
        <div className="sf-order-success">
          <h1>{payment.status_label}</h1>

          <p role="status">{statusMessage(payment.status)}</p>

          <div className="sf-order-success-details">
            <div className="sf-order-amount-row">
              <span>شناسهٔ پرداخت</span>
              <bdi>{payment.id}</bdi>
            </div>

            <div className="sf-order-amount-row">
              <span>شناسهٔ سفارش</span>
              <bdi>{payment.order_id}</bdi>
            </div>

            <div className="sf-order-amount-row is-total">
              <span>مبلغ آزمایشی</span>
              <strong>{money(payment.amount)}</strong>
            </div>

            <div className="sf-order-amount-row">
              <span>مهلت پرداخت</span>
              <span>{formatDate(payment.expires_at)}</span>
            </div>

            {payment.reference_id && (
              <div className="sf-order-amount-row">
                <span>شمارهٔ پیگیری آزمایشی</span>
                <bdi>{payment.reference_id}</bdi>
              </div>
            )}
          </div>

          {canDecide && (
            <div className="sf-order-actions">
              <button
                className="sf-button"
                type="button"
                disabled={busy}
                onClick={() => perform("success")}
              >
                {busy
                  ? "در حال بررسی…"
                  : "شبیه‌سازی پرداخت موفق"}
              </button>

              <button
                className="sf-button sf-order-secondary"
                type="button"
                disabled={busy}
                onClick={() => perform("cancel")}
              >
                انصراف از پرداخت
              </button>
            </div>
          )}

          {uncertain && (
            <p className="sf-order-help" role="status">
              نتیجهٔ درخواست قطعی نیست؛ ابتدا وضعیت پرداخت
              را بررسی کنید.
            </p>
          )}

          {(payment.status === "pending" ||
            payment.status === "verifying" ||
            uncertain) && (
            <div className="sf-order-actions">
              <button
                className="sf-button sf-order-secondary"
                type="button"
                disabled={busy}
                onClick={() => perform()}
              >
                بررسی نتیجهٔ پرداخت
              </button>

              <button
                className="sf-cart-action"
                type="button"
                disabled={busy}
                onClick={() =>
                  setAttempt((value) => value + 1)
                }
              >
                تازه‌سازی اطلاعات صفحه
              </button>
            </div>
          )}

          <div className="sf-order-actions">
            <a
              className="sf-button sf-order-secondary"
              href={`/orders/${payment.order_id}`}
            >
              بازگشت به جزئیات سفارش
            </a>
          </div>
        </div>
      )}
    </section>
  );
}