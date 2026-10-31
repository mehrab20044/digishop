import { useRef, useState } from "react";

import { useCart } from "./CartProvider";
import { newCartRequestId } from "./cart-api";
import "./quantity-control.css";

const formatNumber = new Intl.NumberFormat("fa-IR");

export default function AddToCart({ product, variant, available }) {
  const { add, busy, error } = useCart();

  const [quantity, setQuantity] = useState(1);
  const [added, setAdded] = useState(false);

  const pending = useRef(null);
  const submitting = useRef(false);

  const stock = Number(variant ? variant.stock : product.stock);
  const maximum = Number.isFinite(stock)
    ? Math.min(99, Math.max(0, Math.floor(stock)))
    : 0;

  const purchasable = Boolean(available && maximum > 0);
  const count = Math.min(quantity, maximum || 1);
  const disabled = busy || !purchasable;

  function changeQuantity(change) {
    if (disabled || submitting.current) return;

    setQuantity(Math.min(maximum, Math.max(1, count + change)));
    setAdded(false);
  }

  async function submit(event) {
    event.preventDefault();

    if (disabled || submitting.current) return;

    submitting.current = true;
    setAdded(false);

    const fingerprint = `${product.id}:${variant?.id || 0}:${count}`;

    if (pending.current?.fingerprint !== fingerprint) {
      pending.current = {
        fingerprint,
        id: newCartRequestId(),
      };
    }

    try {
      const success = await add({
        product_id: product.id,
        variant_id: variant?.id || null,
        quantity: count,
        request_id: pending.current.id,
      });

      if (success) {
        pending.current = null;
        setAdded(true);
      }
    } finally {
      submitting.current = false;
    }
  }

  return (
    <div className="sf-add-cart purchase-actions">
      <form className="purchase-form" onSubmit={submit}>
        <div className="purchase-quantity-heading">
          <span>تعداد سفارش</span>

          {purchasable && (
            <small>
              حداکثر {formatNumber.format(maximum)} عدد
            </small>
          )}
        </div>

        <div className="purchase-action-row">
          <div
            className="purchase-stepper"
            role="group"
            aria-label="تعداد برای افزودن به سبد"
          >
            <button
              type="button"
              aria-label="کاهش تعداد"
              disabled={disabled || count <= 1}
              onClick={() => changeQuantity(-1)}
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                aria-hidden="true"
              >
                <path d="M5 12h14" />
              </svg>
            </button>

            <output
              className="purchase-count"
              aria-live="polite"
              aria-atomic="true"
              aria-label="تعداد انتخاب‌شده"
            >
              {formatNumber.format(count)}
            </output>

            <button
              type="button"
              aria-label="افزایش تعداد"
              disabled={disabled || count >= maximum}
              onClick={() => changeQuantity(1)}
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                aria-hidden="true"
              >
                <path d="M5 12h14M12 5v14" />
              </svg>
            </button>
          </div>

          <button
            className="sf-button purchase-submit"
            type="submit"
            disabled={disabled}
            aria-busy={busy}
          >
            {busy
              ? "در حال افزودن…"
              : purchasable
                ? "افزودن به سبد"
                : "ناموجود"}
          </button>
        </div>
      </form>

      {added && (
        <p className="sf-cart-success" role="status">
          به سبد اضافه شد.
          {" "}
          <a href="/cart">مشاهدهٔ سبد ←</a>
        </p>
      )}

      {error && (
        <p className="sf-cart-error" role="alert">
          {error}
        </p>
      )}

      <p className="purchase-note">
        قیمت و موجودی هنگام ثبت سفارش دوباره بررسی می‌شوند.
      </p>
    </div>
  );
}