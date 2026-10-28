import { useEffect, useState } from "react";

import { hasSession } from "../customerAuth";
import { money, number } from "../storefront/store-api";
import { loadOrders } from "./order-api";
import "./orders.css";

function formatDate(value) {
  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleString("fa-IR");
}

export default function OrdersPage() {
  const params = new URLSearchParams(window.location.search);
  const rawPage = Number(params.get("page") || 1);
  const page =
    Number.isSafeInteger(rawPage) && rawPage > 0 ? rawPage : 1;

  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!hasSession()) {
      setError("برای مشاهدهٔ سفارش‌ها وارد حساب مشتری شوید.");
      setLoading(false);
      return undefined;
    }

    let active = true;
    const controller = new AbortController();

    setLoading(true);
    setError("");
    setData(null);

    loadOrders({ page, signal: controller.signal })
      .then((result) => {
        if (active) setData(result);
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
  }, [page, attempt]);

  return (
    <section className="sf-orders">
      <div className="sf-account-layout">
        <aside className="sf-account-sidebar">
          <div className="sf-account-sidebar-title">
            <strong>حساب کاربری</strong>
            <span>مدیریت خریدها و اطلاعات شما</span>
          </div>

          <nav aria-label="منوی حساب مشتری">
            <a href="/account">اطلاعات حساب و آدرس‌ها</a>
            <a
              className="is-active"
              href="/orders"
              aria-current="page"
            >
              سفارش‌های من
            </a>
            <a href="/cart">سبد خرید</a>
            <a href="/">بازگشت به فروشگاه</a>
          </nav>
        </aside>

        <div className="sf-order-content">
          <div className="sf-orders-heading">
            <div>
              <h1>سفارش‌های من</h1>
              <p>
                وضعیت خریدها و جزئیات سفارش‌های خود را ببینید.
              </p>
            </div>
            {data && (
              <span className="sf-muted">
                {number(data.count)} سفارش
              </span>
            )}
          </div>

          {loading && (
            <div className="sf-order-empty" role="status">
              <p>در حال دریافت سفارش‌ها…</p>
            </div>
          )}

          {error && (
            <div className="sf-order-empty">
              <h2>سفارش‌ها دریافت نشدند</h2>
              <p role="alert">{error}</p>

              {hasSession() ? (
                <button
                  className="sf-button"
                  type="button"
                  disabled={loading}
                  onClick={() =>
                    setAttempt((value) => value + 1)
                  }
                >
                  تلاش دوباره
                </button>
              ) : (
                <a className="sf-button" href="/login">
                  ورود به حساب
                </a>
              )}
            </div>
          )}

          {!loading && data && data.results.length === 0 && (
            <div className="sf-order-empty">
              <h2>
                {page === 1
                  ? "هنوز سفارشی ثبت نکرده‌اید"
                  : "در این صفحه سفارشی وجود ندارد"}
              </h2>
              <p>
                {page === 1
                  ? "بعد از ثبت خرید، وضعیت و جزئیات آن اینجا نمایش داده می‌شود."
                  : "به صفحهٔ اول سفارش‌ها برگردید."}
              </p>
              <a
                className="sf-button"
                href={page === 1 ? "/products" : "/orders"}
              >
                {page === 1 ? "مشاهدهٔ محصولات" : "صفحهٔ اول"}
              </a>
            </div>
          )}

          {!loading && data && data.results.length > 0 && (
            <div className="sf-order-list">
              {data.results.map((order) => (
                <article className="sf-order-card" key={order.id}>
                  <div className="sf-order-card-head">
                    <span
                      className={
                        `sf-order-status sf-order-status--${order.status}`
                      }
                    >
                      {order.status_label}
                    </span>
                    <span className="sf-order-card-date">
                      ثبت در {formatDate(order.created_at)}
                    </span>
                  </div>

                  <div className="sf-order-card-body">
                    <div className="sf-order-meta">
                      <div>
                        <span className="sf-order-meta-label">
                          شناسهٔ سفارش
                        </span>
                        <bdi className="sf-order-meta-value">
                          {order.id}
                        </bdi>
                      </div>

                      <div className="sf-order-meta-price">
                        <span className="sf-order-meta-label">
                          مبلغ سفارش
                        </span>
                        <strong>{money(order.total)}</strong>
                      </div>
                    </div>

                    {order.status === "pending_payment" && (
                      <p className="sf-order-deadline">
                        مهلت پرداخت: {formatDate(order.expires_at)}
                      </p>
                    )}
                  </div>

                  <div className="sf-order-card-footer">
                    <p>مشاهدهٔ کالاها، آدرس و وضعیت سفارش</p>
                    <a href={`/orders/${order.id}`}>
                      جزئیات سفارش ←
                    </a>
                  </div>
                </article>
              ))}
            </div>
          )}

          {!loading && data && (page > 1 || data.next) && (
            <nav
              className="sf-pagination"
              aria-label="صفحه‌بندی سفارش‌ها"
            >
              {page > 1 ? (
                <a href={`/orders?page=${page - 1}`}>
                  صفحهٔ قبل
                </a>
              ) : (
                <span aria-disabled="true">صفحهٔ قبل</span>
              )}

              <b>صفحهٔ {number(page)}</b>

              {data.next ? (
                <a href={`/orders?page=${page + 1}`}>
                  صفحهٔ بعد
                </a>
              ) : (
                <span aria-disabled="true">صفحهٔ بعد</span>
              )}
            </nav>
          )}
        </div>
      </div>
    </section>
  );
}