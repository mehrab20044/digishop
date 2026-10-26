import { useEffect, useRef, useState } from "react";

import CustomerAccount from "./CustomerAccount";
import {
  getProfile,
  hasSession,
  logout,
  requestOTP,
  verifyOTP,
} from "./customerAuth";

function normalizeDigits(value) {
  return value
    .replace(/[۰-۹]/g, (digit) =>
      String("۰۱۲۳۴۵۶۷۸۹".indexOf(digit)),
    )
    .replace(/[٠-٩]/g, (digit) =>
      String("٠١٢٣٤٥٦٧٨٩".indexOf(digit)),
    );
}

function normalizePhone(value) {
  const phone = normalizeDigits(value).replace(/\s/g, "");

  if (phone.startsWith("+98")) {
    return `0${phone.slice(3)}`;
  }

  if (phone.startsWith("0098")) {
    return `0${phone.slice(4)}`;
  }

  return phone;
}

function formatTime(seconds) {
  const minutes = Math.floor(seconds / 60);
  const rest = String(seconds % 60).padStart(2, "0");
  return `${minutes}:${rest}`;
}

export default function CustomerPortal() {
  const accountPage =
    window.location.pathname.replace(/\/+$/, "") === "/account";

  const [screen, setScreen] = useState(() =>
    hasSession() || accountPage ? "loading" : "phone",
  );
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [user, setUser] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [retryAt, setRetryAt] = useState(0);
  const [now, setNow] = useState(() => Date.now());

  const locked = useRef(false);

  const remaining = Math.max(
    0,
    Math.ceil((retryAt - now) / 1000),
  );

  useEffect(() => {
    document.title = accountPage
      ? "حساب کاربری | دیجی‌شاپ"
      : "ورود و ثبت‌نام | دیجی‌شاپ";

    if (!hasSession()) {
      if (accountPage) {
        window.location.replace("/login");
      }
      return undefined;
    }

    let active = true;

    getProfile()
      .then((profile) => {
        if (!active) return;

        if (!accountPage) {
          window.location.replace("/account");
          return;
        }

        setUser(profile);
        setScreen("account");
      })
      .catch((err) => {
        if (!active) return;

        if (accountPage && !hasSession()) {
          window.location.replace("/login");
          return;
        }

        setError(err.message);
        setScreen(hasSession() ? "failure" : "phone");
      });

    return () => {
      active = false;
    };
  }, [accountPage]);

  useEffect(() => {
    if (!retryAt) return undefined;

    const timer = window.setInterval(() => {
      const time = Date.now();
      setNow(time);

      if (time >= retryAt) {
        window.clearInterval(timer);
      }
    }, 1000);

    return () => window.clearInterval(timer);
  }, [retryAt]);

  function startCountdown(seconds) {
    const time = Date.now();
    const wait = Number(seconds);

    setNow(time);
    setRetryAt(
      time + (Number.isFinite(wait) && wait > 0 ? wait : 60) * 1000,
    );
  }

  function showError(err) {
    setError(err.message || "درخواست انجام نشد.");

    if (err.retryAfter > 0) {
      startCountdown(err.retryAfter);
    }
  }

  async function sendCode(event) {
    event.preventDefault();

    if (locked.current) return;

    if (remaining > 0) {
      setError("برای درخواست کد جدید، تا پایان زمان نمایش‌داده‌شده صبر کن.");
      return;
    }

    const normalized = normalizePhone(phone);

    if (!/^09[0-9]{9}$/.test(normalized)) {
      setError("شماره موبایل معتبر وارد کن.");
      return;
    }

    locked.current = true;
    setBusy(true);
    setError("");

    try {
      const result = await requestOTP(normalized);

      setPhone(normalized);
      setCode("");
      startCountdown(result.retry_after);
      setScreen("code");
    } catch (err) {
      showError(err);
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }

  async function confirmCode(event) {
    event.preventDefault();

    if (locked.current) return;

    const normalized = normalizeDigits(code).trim();

    if (!/^[0-9]{6}$/.test(normalized)) {
      setError("کد تأیید باید ۶ رقم باشد.");
      return;
    }

    locked.current = true;
    setBusy(true);
    setError("");

    try {
      await verifyOTP(phone, normalized);
      window.location.replace("/account");
    } catch (err) {
      showError(err);
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }

  async function signOut() {
    if (locked.current) return;

    locked.current = true;
    setBusy(true);
    setError("");

    try {
      await logout();
      window.location.replace("/login");
    } catch (err) {
      showError(err);
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }

  function changePhone() {
    setCode("");
    setError("");
    setRetryAt(0);
    setScreen("phone");
  }

  function useExistingCode() {
    const normalized = normalizePhone(phone);

    if (!/^09[0-9]{9}$/.test(normalized)) {
      setError("ابتدا شماره موبایل معتبر وارد کن.");
      return;
    }

    setPhone(normalized);
    setCode("");
    setError("");
    setScreen("code");
  }

  if (screen === "account" && user) {
    return (
      <CustomerAccount
        user={user}
        onLogout={signOut}
        busy={busy}
        error={error}
      />
    );
  }

  return (
    <main className="signin-page" dir="rtl" lang="fa">
      <div className="signin-container">
        <div className="signin-brand">
          <span className="signin-logo" aria-hidden="true">
            D
          </span>
          <div>
            <strong>دیجی‌شاپ</strong>
            <span>حساب مشتری</span>
          </div>
        </div>

        <section className="signin-card">
          {screen === "loading" && (
            <p role="status" className="signin-status">
              در حال بررسی حساب کاربری…
            </p>
          )}

          {error && (
            <div
              className="signin-error"
              id="signin-error"
              role="alert"
            >
              {error}
            </div>
          )}

          {screen === "failure" && (
            <>
              <h1>حساب دریافت نشد</h1>
              <p className="signin-description">
                اتصال را بررسی کن و دوباره تلاش کن.
              </p>

              <div className="signin-actions">
                <button
                  className="signin-primary"
                  type="button"
                  onClick={() => window.location.reload()}
                  disabled={busy}
                >
                  تلاش دوباره
                </button>
                <button
                  className="signin-link"
                  type="button"
                  onClick={signOut}
                  disabled={busy}
                >
                  خروج از حساب
                </button>
              </div>
            </>
          )}

          {screen === "phone" && (
            <>
              <span className="signin-step">شروع خرید، با حساب تو</span>
              <h1>ورود | ثبت‌نام</h1>
              <p className="signin-description">
                شماره موبایلت را وارد کن.
                اگر حساب نداشته باشی، بعد از تأیید شماره ساخته می‌شود.
              </p>

              <form onSubmit={sendCode}>
                <label className="signin-field">
                  <span>شماره موبایل</span>
                  <input
                    type="tel"
                    inputMode="tel"
                    autoComplete="tel"
                    dir="ltr"
                    placeholder="09xxxxxxxxx"
                    maxLength={20}
                    value={phone}
                    disabled={busy}
                    aria-describedby={error ? "signin-error" : undefined}
                    onChange={(event) => setPhone(event.target.value)}
                    required
                  />
                </label>

                <button
                  className="signin-primary"
                  type="submit"
                  disabled={busy || remaining > 0}
                >
                  {busy
                    ? "در حال درخواست…"
                    : remaining > 0
                      ? `تلاش دوباره در ${formatTime(remaining)}`
                      : "دریافت کد ورود"}
                </button>
              </form>

              <button
                className="signin-link"
                type="button"
                disabled={busy}
                onClick={useExistingCode}
              >
                کد ورود دارم
              </button>
            </>
          )}

          {screen === "code" && (
            <>
              <button
                className="signin-back"
                type="button"
                disabled={busy}
                onClick={changePhone}
              >
                → تغییر شماره
              </button>

              <span className="signin-step">تأیید شماره موبایل</span>
              <h1>کد ورود را وارد کن</h1>
              <p className="signin-description">
                کد ۶ رقمی مربوط به شماره <bdi>{phone}</bdi>
              </p>

              <form onSubmit={confirmCode}>
                <label className="signin-field">
                  <span>کد تأیید</span>
                  <input
                    className="signin-code"
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    dir="ltr"
                    placeholder="000000"
                    maxLength={12}
                    value={code}
                    disabled={busy}
                    aria-describedby={error ? "signin-error" : undefined}
                    onChange={(event) =>
                      setCode(
                        normalizeDigits(event.target.value)
                          .replace(/\D/g, "")
                          .slice(0, 6),
                      )
                    }
                    required
                  />
                </label>

                <button
                  className="signin-primary"
                  type="submit"
                  disabled={busy || code.length !== 6}
                >
                  {busy ? "در حال بررسی…" : "تأیید و ورود"}
                </button>
              </form>

              <div className="signin-resend">
                {remaining > 0 ? (
                  <span>
                    دریافت کد جدید تا{" "}
                    <bdi>{formatTime(remaining)}</bdi>
                  </span>
                ) : (
                  <button
                    className="signin-link"
                    type="button"
                    disabled={busy}
                    onClick={sendCode}
                  >
                    دریافت کد جدید
                  </button>
                )}
              </div>
            </>
          )}
        </section>

        <p className="signin-footer">
          کد ورود را در اختیار دیگران قرار نده.
        </p>
      </div>
    </main>
  );
}