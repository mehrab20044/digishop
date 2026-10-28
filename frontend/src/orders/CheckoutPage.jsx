import { useEffect, useRef, useState } from "react";

import { getProfile, hasSession } from "../customerAuth";
import { useCart } from "../cart/CartProvider";
import { money, number } from "../storefront/store-api";
import { createOrder, previewOrder } from "./order-api";
import "./orders.css";

function storageKey(userId) {
  return `digishop.checkout.pending.${userId}`;
}

function readPending(userId) {
  const raw = sessionStorage.getItem(storageKey(userId));

  if (!raw) return null;

  const value = JSON.parse(raw);

  if (
    !Number.isSafeInteger(value?.addressId) ||
    value.addressId <= 0 ||
    !Number.isSafeInteger(value.expectedTotal) ||
    value.expectedTotal <= 0 ||
    typeof value.requestId !== "string" ||
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
      value.requestId,
    ) ||
    typeof value.customerNote !== "string" ||
    value.customerNote.length > 1000
  ) {
    throw new Error("اطلاعات تلاش قبلی ثبت سفارش معتبر نیست.");
  }

  return value;
}

function formatDate(value) {
  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleString("fa-IR");
}

function CheckoutSteps() {
  return (
    <ol className="sf-checkout-steps" aria-label="مراحل خرید">
      <li className="is-complete">
        <span className="sf-checkout-step-number">✓</span>
        <span>سبد خرید</span>
      </li>
      <li className="is-current" aria-current="step">
        <span className="sf-checkout-step-number">۲</span>
        <span>آدرس و تأیید سفارش</span>
      </li>
      <li>
        <span className="sf-checkout-step-number">۳</span>
        <span>پرداخت</span>
      </li>
    </ol>
  );
}

export default function CheckoutPage() {
  const { retry: refreshCart } = useCart();

  const [profile, setProfile] = useState(null);
  const [addressId, setAddressId] = useState("");
  const [note, setNote] = useState("");
  const [preview, setPreview] = useState(null);
  const [pending, setPending] = useState(null);
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [previewAttempt, setPreviewAttempt] = useState(0);

  const submitting = useRef(false);
  const mounted = useRef(false);

  useEffect(() => {
    let active = true;
    mounted.current = true;

    async function initialize() {
      if (!hasSession()) {
        window.location.replace("/login?next=%2Fcart");
        return;
      }

      try {
        const data = await getProfile();

        if (!active) return;

        // Restore unresolved requests before enabling a new checkout.
        const saved = readPending(data.id);

        if (saved) {
          setPending(saved);
          setAddressId(String(saved.addressId));
          setNote(saved.customerNote);
        } else {
          const addresses = data.addresses || [];
          const initial =
            addresses.find((address) => address.is_default) ||
            addresses[0];

          setAddressId(initial ? String(initial.id) : "");
        }

        setProfile(data);
      } catch (err) {
        if (active) setError(err.message);
      } finally {
        if (active) setLoading(false);
      }
    }

    initialize();

    return () => {
      active = false;
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    if (
      !profile?.profile_completed ||
      !addressId ||
      pending ||
      order
    ) {
      return undefined;
    }

    let active = true;
    const controller = new AbortController();

    setPreview(null);
    setPreviewLoading(true);
    setError("");

    previewOrder(Number(addressId), {
      signal: controller.signal,
    })
      .then((data) => {
        if (active) setPreview(data);
      })
      .catch((err) => {
        if (active && err.name !== "AbortError") {
          setError(err.message);
        }
      })
      .finally(() => {
        if (active) setPreviewLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [profile, addressId, pending, order, previewAttempt]);

  async function submit(event) {
    event.preventDefault();

    if (submitting.current || !profile) return;
    if (!pending && (!preview || previewLoading)) return;

    submitting.current = true;
    setBusy(true);
    setError("");

    let attempt = pending;

    try {
      if (!attempt) {
        if (
          !Number.isSafeInteger(preview.total) ||
          preview.total <= 0
        ) {
          throw new Error(
            "مبلغ سفارش معتبر نیست؛ پیش‌نمایش را دوباره دریافت کنید.",
          );
        }

        attempt = {
          addressId: Number(addressId),
          requestId: crypto.randomUUID(),
          expectedTotal: preview.total,
          customerNote: note.trim(),
        };

        sessionStorage.setItem(
          storageKey(profile.id),
          JSON.stringify(attempt),
        );

        setPending(attempt);
      }

      const result = await createOrder(attempt);

      if (!mounted.current) return;

      setOrder(result);
      setPending(null);

      try {
        sessionStorage.removeItem(storageKey(profile.id));
      } catch {
        // Replaying the original request returns the existing order.
      }

      await refreshCart();
    } catch (err) {
      if (!mounted.current) return;

      setError(err.message);

      if ([400, 403, 404, 415, 429].includes(err.status)) {
        try {
          sessionStorage.removeItem(storageKey(profile.id));
          setPending(null);
          setPreview(null);
        } catch {
          setError(
            "ذخیره‌سازی مرورگر در دسترس نیست؛ نتیجهٔ سفارش را از بخش سفارش‌های من بررسی کنید.",
          );
        }
      }
    } finally {
      submitting.current = false;

      if (mounted.current) setBusy(false);
    }
  }

  if (loading) {
    return (
      <section className="sf-orders">
        <div className="sf-order-empty" role="status">
          <p>در حال دریافت اطلاعات خرید…</p>
        </div>
      </section>
    );
  }

  if (order) {
    return (
      <section className="sf-orders">
        <div className="sf-order-success">
          <div className="sf-order-success-icon" aria-hidden="true">
            ✓
          </div>

          <h1>سفارش شما ثبت شد</h1>
          <p>
            وضعیت فعلی: <strong>{order.status_label}</strong>
          </p>

          <div className="sf-order-success-details">
            <div className="sf-order-amount-row">
              <span>شناسهٔ سفارش</span>
              <bdi>{order.id}</bdi>
            </div>
            <div className="sf-order-amount-row">
              <span>مبلغ سفارش</span>
              <strong>{money(order.total)}</strong>
            </div>
            <div className="sf-order-amount-row">
              <span>مهلت پرداخت</span>
              <span>{formatDate(order.expires_at)}</span>
            </div>
          </div>

          <p>
            پرداخت آنلاین هنوز فعال نشده است. وضعیت و امکان
            لغو سفارش را از صفحهٔ جزئیات بررسی کنید.
          </p>

          <div className="sf-order-actions">
            <a
              className="sf-button"
              href={`/orders/${order.id}`}
            >
              مشاهدهٔ سفارش
            </a>
            <a
              className="sf-button sf-order-secondary"
              href="/"
            >
              بازگشت به فروشگاه
            </a>
          </div>
        </div>
      </section>
    );
  }

  if (!profile) {
    return (
      <section className="sf-orders">
        <div className="sf-order-empty">
          <h2>اطلاعات خرید دریافت نشد</h2>
          <p role="alert">
            {error || "دریافت حساب کاربری ممکن نشد."}
          </p>
          <button
            className="sf-button"
            type="button"
            onClick={() => window.location.reload()}
          >
            تلاش دوباره
          </button>
          <a href="/orders">بررسی سفارش‌های قبلی</a>
        </div>
      </section>
    );
  }

  if (!profile.profile_completed && !pending) {
    return (
      <section className="sf-orders">
        <CheckoutSteps />

        <div className="sf-order-empty">
          <h2>اطلاعات تحویل را تکمیل کنید</h2>
          <p>
            نام، نام خانوادگی و آدرس معتبر برای ثبت سفارش
            ضروری است.
          </p>
          <a className="sf-button" href="/account">
            تکمیل حساب و آدرس
          </a>
          <a href="/cart">بازگشت به سبد خرید</a>
        </div>
      </section>
    );
  }

  const addresses = profile.addresses || [];
  const controlsDisabled = busy || Boolean(pending);

  return (
    <section className="sf-orders">
      <div className="sf-orders-heading">
        <div>
          <h1>تأیید سفارش</h1>
          <p>آدرس تحویل و مبلغ خرید را بررسی کنید.</p>
        </div>
        <a className="sf-orders-back" href="/cart">
          بازگشت به سبد خرید
        </a>
      </div>

      <CheckoutSteps />

      {error && (
        <div className="sf-order-alert" role="alert">
          {error}
        </div>
      )}

      {pending && (
        <div
          className="sf-order-alert is-warning"
          role="status"
        >
          نتیجهٔ تلاش قبلی هنوز مشخص نیست. با «بررسی نتیجهٔ
          ثبت سفارش» همان درخواست را دوباره بررسی کنید.
          <a className="sf-orders-back" href="/orders">
            {" "}مشاهدهٔ سفارش‌های من
          </a>
        </div>
      )}

      <form className="sf-checkout-layout" onSubmit={submit}>
        <div className="sf-checkout-main">
          <section className="sf-order-panel">
            <div className="sf-order-panel-header">
              <h2>آدرس تحویل سفارش</h2>
              {!controlsDisabled && (
                <a href="/account">مدیریت آدرس‌ها</a>
              )}
            </div>

            <div className="sf-order-panel-body">
              <fieldset
                className="sf-order-fieldset"
                disabled={controlsDisabled}
              >
                <legend>سفارش به کدام آدرس ارسال شود؟</legend>

                <div className="sf-address-options">
                  {addresses.map((address) => {
                    const selected =
                      addressId === String(address.id);

                    return (
                      <label
                        className={`sf-address-option ${
                          selected ? "is-selected" : ""
                        }`}
                        key={address.id}
                      >
                        <input
                          type="radio"
                          name="delivery-address"
                          value={address.id}
                          checked={selected}
                          required
                          onChange={() => {
                            setPreview(null);
                            setError("");
                            setAddressId(String(address.id));
                          }}
                        />

                        <div>
                          <div className="sf-address-option-title">
                            <strong>
                              {address.recipient_name}
                            </strong>
                            {address.is_default && (
                              <span className="sf-address-default">
                                آدرس پیش‌فرض
                              </span>
                            )}
                          </div>

                          <p>
                            {address.province}، {address.city}،
                            {" "}{address.street_address}،
                            پلاک {address.building_number}
                            {address.unit &&
                              `، واحد ${address.unit}`}
                          </p>

                          <small>
                            تماس: <bdi>{address.recipient_phone}</bdi>
                            {" "} | کد پستی:{" "}
                            <bdi>{address.postal_code}</bdi>
                          </small>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </fieldset>
            </div>
          </section>

          <section className="sf-order-panel">
            <div className="sf-order-panel-header">
              <h2>کالاهای سفارش</h2>
              {!controlsDisabled && (
                <a href="/cart">ویرایش سبد خرید</a>
              )}
            </div>

            <div
              className="sf-order-panel-body"
              aria-busy={previewLoading && !pending}
            >
              {pending ? (
                <p className="sf-order-help">
                  ابتدا نتیجهٔ تلاش قبلی را بررسی کنید.
                </p>
              ) : previewLoading ? (
                <p role="status">در حال بررسی کالاها و مبلغ…</p>
              ) : preview ? (
                preview.items.map((item) => (
                  <article
                    className="sf-checkout-item"
                    key={`${item.product_id}:${item.variant_id || 0}`}
                  >
                    <div>
                      <h3>{item.product_name}</h3>
                      {item.variant_name && (
                        <p>{item.variant_name}</p>
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
                ))
              ) : (
                <div>
                  <p className="sf-order-help">
                    پیش‌نمایش سفارش آماده نیست. اگر سبد نیاز به
                    اصلاح دارد، به سبد خرید برگردید.
                  </p>
                  <button
                    className="sf-cart-action"
                    type="button"
                    disabled={busy || !addressId}
                    onClick={() =>
                      setPreviewAttempt((value) => value + 1)
                    }
                  >
                    دریافت دوبارهٔ پیش‌نمایش
                  </button>
                </div>
              )}
            </div>
          </section>

          <section className="sf-order-panel">
            <div className="sf-order-panel-header">
              <h2>یادداشت سفارش</h2>
            </div>
            <div className="sf-order-panel-body">
              <label htmlFor="checkout-note">
                توضیحات تکمیلی، اختیاری
              </label>
              <textarea
                id="checkout-note"
                className="sf-order-note"
                value={note}
                maxLength={1000}
                rows={3}
                disabled={controlsDisabled}
                placeholder="اگر توضیحی دربارهٔ تحویل سفارش دارید، بنویسید."
                onChange={(event) => setNote(event.target.value)}
              />
              <p className="sf-order-help">
                حداکثر ۱۰۰۰ نویسه
              </p>
            </div>
          </section>
        </div>

        <aside className="sf-checkout-summary">
          <h2>خلاصهٔ سفارش</h2>

          {pending ? (
            <div className="sf-order-amount-row is-total">
              <span>مبلغ تأییدشده</span>
              <strong>{money(pending.expectedTotal)}</strong>
            </div>
          ) : preview ? (
            <>
              <div className="sf-order-amount-row">
                <span>
                  کالاها ({number(preview.item_count)} عدد)
                </span>
                <strong>{money(preview.subtotal)}</strong>
              </div>

              <div className="sf-order-amount-row">
                <span>هزینهٔ ارسال</span>
                <strong>
                  {preview.shipping_cost === 0
                    ? "رایگان"
                    : money(preview.shipping_cost)}
                </strong>
              </div>

              <div className="sf-order-amount-row is-total">
                <span>مبلغ قابل پرداخت</span>
                <strong>{money(preview.total)}</strong>
              </div>
            </>
          ) : (
            <p className="sf-order-help">
              {previewLoading
                ? "در حال محاسبهٔ مبلغ نهایی…"
                : "پس از دریافت پیش‌نمایش، مبلغ نمایش داده می‌شود."}
            </p>
          )}

          <button
            className="sf-button sf-order-submit"
            type="submit"
            disabled={
              busy ||
              (!pending && (!preview || previewLoading))
            }
          >
            {busy
              ? "در حال بررسی سفارش…"
              : pending
                ? "بررسی نتیجهٔ ثبت سفارش"
                : "تأیید و ثبت سفارش"}
          </button>

          <p className="sf-order-reservation">
            با ثبت سفارش، موجودی کالاها برای دو ساعت رزرو
            می‌شود. در صورت پرداخت‌نشدن، سفارش منقضی و
            موجودی آزاد خواهد شد.
          </p>

          <p className="sf-order-help">
            پرداخت آنلاین هنوز فعال نشده است.
          </p>
        </aside>
      </form>
    </section>
  );
}