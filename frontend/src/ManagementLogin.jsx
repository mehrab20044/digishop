import { useEffect, useRef, useState } from "react";

import { managementAuth } from "./managementAuth";

function digits(value) {
  return value
    .replace(/[۰-۹]/g, (char) =>
      String("۰۱۲۳۴۵۶۷۸۹".indexOf(char)),
    )
    .replace(/[٠-٩]/g, (char) =>
      String("٠١٢٣٤٥٦٧٨٩".indexOf(char)),
    );
}

function normalizePhone(value) {
  const phone = digits(value.trim());

  if (phone.startsWith("+98")) {
    return "0" + phone.slice(3);
  }

  if (phone.startsWith("0098")) {
    return "0" + phone.slice(4);
  }

  return phone;
}

function destination() {
  const next = new URLSearchParams(
    window.location.search,
  ).get("next");

  if (!next) return "/dashboard";

  try {
    const url = new URL(next, window.location.origin);

    if (
      url.origin === window.location.origin &&
      (
        url.pathname === "/dashboard" ||
        url.pathname.startsWith("/dashboard/")
      )
    ) {
      return url.pathname + url.search;
    }
  } catch {
    // Invalid destinations are ignored.
  }

  return "/dashboard";
}

export default function ManagementLogin() {
  const [step, setStep] = useState("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [remaining, setRemaining] = useState(0);
  const pending = useRef(false);

  useEffect(() => {
    document.title = "ورود مدیریت | دیجی‌شاپ";
  }, []);

  useEffect(() => {
    if (remaining <= 0) return undefined;

    const timer = window.setTimeout(() => {
      setRemaining((value) => Math.max(0, value - 1));
    }, 1000);

    return () => window.clearTimeout(timer);
  }, [remaining]);

  async function sendCode() {
    const normalized = normalizePhone(phone);

    if (!/^09[0-9]{9}$/.test(normalized)) {
      setError("شماره موبایل معتبر وارد کنید.");
      return;
    }

    setPhone(normalized);

    const data = await managementAuth.requestOTP(normalized);

    setRemaining(
      Math.max(1, Number(data.retry_after) || 60),
    );
    setCode("");
    setStep("code");
  }

  async function submit(event) {
    event.preventDefault();

    if (pending.current) return;

    pending.current = true;
    setBusy(true);
    setError("");

    try {
      if (step === "phone") {
        await sendCode();
      } else {
        const normalizedCode = digits(code.trim());

        if (!/^[0-9]{6}$/.test(normalizedCode)) {
          setError("کد تأیید باید ۶ رقم باشد.");
          return;
        }

        await managementAuth.verifyOTP(
          phone,
          normalizedCode,
        );

        window.location.replace(destination());
      }
    } catch (err) {
      setError(err.message);

      if (err.retryAfter) {
        setRemaining(Math.ceil(err.retryAfter));
      }
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  async function resend() {
    if (pending.current || remaining > 0) return;

    pending.current = true;
    setBusy(true);
    setError("");

    try {
      await sendCode();
    } catch (err) {
      setError(err.message);

      if (err.retryAfter) {
        setRemaining(Math.ceil(err.retryAfter));
      }
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  return (
    <main className="owner-auth" dir="rtl" lang="fa">
      <section className="owner-auth-intro">
        <span className="owner-auth-brand">DIGISHOP</span>
        <h1>مدیریت فروشگاه، در یک فضای کاری.</h1>
        <p>
          این بخش مخصوص صاحب سایت و همکارانی است که
          دسترسی مدیریت دریافت کرده‌اند.
        </p>
        <a href="/login">ورود مشتریان ←</a>
      </section>

      <section className="card owner-auth-form">
        <p className="eyebrow">پنل مدیریت فروشگاه</p>
        <h2>ورود مدیریت</h2>
        <p className="muted">
          ثبت‌نام عمومی مدیر وجود ندارد؛ دسترسی باید
          توسط مدیر مجاز ایجاد شده باشد.
        </p>

        {error && (
          <p className="owner-auth-error" role="alert">
            {error}
          </p>
        )}

        <form onSubmit={submit}>
          <fieldset disabled={busy}>
            <label className="field">
              <span>شماره موبایل</span>
              <input
                type="tel"
                dir="ltr"
                autoComplete="tel"
                value={phone}
                readOnly={step === "code"}
                onChange={(event) =>
                  setPhone(event.target.value)
                }
                required
              />
            </label>

            {step === "code" && (
              <label className="field">
                <span>کد تأیید</span>
                <input
                  type="text"
                  dir="ltr"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                  value={code}
                  onChange={(event) =>
                    setCode(digits(event.target.value))
                  }
                  required
                />
              </label>
            )}

            <button
              className="button primary"
              type="submit"
              disabled={busy}
            >
              {busy
                ? "در حال بررسی…"
                : step === "phone"
                  ? "دریافت کد ورود"
                  : "ورود به داشبورد"}
            </button>

            {step === "code" && (
              <div className="owner-auth-actions">
                <button
                  className="button ghost"
                  type="button"
                  onClick={resend}
                  disabled={busy || remaining > 0}
                >
                  {remaining > 0
                    ? `ارسال مجدد تا ${remaining} ثانیه`
                    : "ارسال مجدد کد"}
                </button>

                <button
                  className="button ghost"
                  type="button"
                  onClick={() => {
                    setStep("phone");
                    setCode("");
                    setError("");
                  }}
                >
                  تغییر شماره
                </button>
              </div>
            )}
          </fieldset>
        </form>
      </section>
    </main>
  );
}