import { useRef, useState } from "react";

import { fakePaymentHref, startPayment } from "./payment-api";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function PayOrderButton({ order }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const lock = useRef(false);

  async function pay() {
    if (
      lock.current ||
      order.status !== "pending_payment"
    ) {
      return;
    }

    lock.current = true;
    setBusy(true);
    setError("");

    const key = `digishop.payment.start.${order.id}`;

    try {
      let requestId = sessionStorage.getItem(key);

      if (requestId && !UUID_PATTERN.test(requestId)) {
        throw new Error(
          "شناسهٔ تلاش قبلی معتبر نیست؛ وضعیت سفارش را بررسی کنید.",
        );
      }

      if (!requestId) {
        requestId = crypto.randomUUID();
        sessionStorage.setItem(key, requestId);
      }

      const result = await startPayment({
        orderId: order.id,
        requestId,
      });

      const payment = result.payment;

      if (
        !payment ||
        payment.order_id !== order.id ||
        payment.gateway !== "fake"
      ) {
        throw new Error("پاسخ شروع پرداخت معتبر نیست.");
      }

      if (payment.status === "pending") {
        const destination = fakePaymentHref(payment.id);

        if (result.redirect_url !== destination) {
          throw new Error("آدرس صفحهٔ پرداخت معتبر نیست.");
        }

        window.location.assign(destination);
        return;
      }

      if (payment.status === "succeeded") {
        sessionStorage.removeItem(key);
        window.location.reload();
        return;
      }

      if (
        ["failed", "cancelled", "expired"].includes(payment.status)
      ) {
        sessionStorage.removeItem(key);
        setError(
          "تلاش قبلی پایان یافته است. وضعیت سفارش را تازه‌سازی کنید؛ اگر هنوز قابل پرداخت است، دوباره اقدام کنید.",
        );
        return;
      }

      setError(
        "پرداخت قبلی در حال بررسی است. پرداخت تازه‌ای شروع نکنید.",
      );
    } catch (err) {
      // Keep the original request ID when the result is uncertain.
      setError(err.message);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  if (order.status !== "pending_payment") return null;

  return (
    <div>
      <button
        className="sf-button sf-order-submit"
        type="button"
        disabled={busy}
        onClick={pay}
      >
        {busy ? "در حال بررسی پرداخت…" : "پرداخت آزمایشی سفارش"}
      </button>

      <p className="sf-order-help">
        درگاه آزمایشی است؛ پول واقعی جابه‌جا نمی‌شود.
      </p>

      {error && (
        <p className="sf-order-alert" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}