import { useEffect, useRef, useState } from "react";

import {
  createAddress,
  deleteAddress,
  getProfile,
  logoutAll,
  updateAddress,
  updateProfile,
} from "./customerAuth";

const EMPTY_ADDRESS = {
  recipient_name: "",
  recipient_phone: "",
  province: "",
  city: "",
  street_address: "",
  building_number: "",
  unit: "",
  postal_code: "",
  is_default: false,
};

const ADDRESS_FIELDS = [
  ["recipient_name", "نام گیرنده", 150],
  ["recipient_phone", "موبایل گیرنده", 32],
  ["province", "استان", 100],
  ["city", "شهر", 100],
  ["street_address", "نشانی کامل", 500],
  ["building_number", "پلاک", 20],
  ["unit", "واحد", 20],
  ["postal_code", "کد پستی", 10],
];

function Field({ label, ...props }) {
  return (
    <label className="account-field">
      <span>{label}</span>
      <input {...props} />
    </label>
  );
}

export default function CustomerAccount({
  user,
  onLogout,
  busy,
  error,
}) {
  const [account, setAccount] = useState(user);
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState("");
  const [notice, setNotice] = useState("");
  const [address, setAddress] = useState(null);
  const [allLogoutOpen, setAllLogoutOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [removeImage, setRemoveImage] = useState(false);
  const [profileRevision, setProfileRevision] = useState(0);

  const lock = useRef(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;

    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    setAccount(user);
  }, [user]);

  useEffect(() => {
    function onExpired(event) {
      if (
        event.detail?.storageKey ===
        "digishop.customer.session"
      ) {
        window.location.replace("/login");
      }
    }

    window.addEventListener("auth-expired", onExpired);

    return () => {
      window.removeEventListener("auth-expired", onExpired);
    };
  }, []);

  const requestedTab = new URLSearchParams(
    window.location.search,
  ).get("tab");

  const tab = ["profile", "addresses"].includes(requestedTab)
    ? requestedTab
    : "overview";

  const menu = [
    ["overview", "نمای کلی", "/account"],
    ["profile", "اطلاعات شخصی", "/account?tab=profile"],
    ["addresses", "آدرس‌های من", "/account?tab=addresses"],
  ];

  const title = menu.find(([key]) => key === tab)[1];

  const fullName = [
    account.first_name,
    account.last_name,
  ].filter(Boolean).join(" ");

  const addresses = Array.isArray(account.addresses)
    ? account.addresses
    : [];

  const disabled = busy || pending;

  async function perform(action, successMessage) {
    if (lock.current || busy) return;

    lock.current = true;
    setPending(true);
    setFailure("");
    setNotice("");

    try {
      await action();

      if (mounted.current && successMessage) {
        setNotice(successMessage);
      }
    } catch (err) {
      if (mounted.current) {
        setFailure(err.message || "درخواست انجام نشد.");
      }
    } finally {
      lock.current = false;

      if (mounted.current) setPending(false);
    }
  }

  async function reloadAccount() {
    const fresh = await getProfile();

    if (mounted.current) {
      setAccount(fresh);
    }
  }

  function saveProfile(event) {
    event.preventDefault();

    const form = new FormData(event.currentTarget);

    const data = new FormData();
    data.set("first_name", String(form.get("first_name") || "").trim());
    data.set("last_name", String(form.get("last_name") || "").trim());
    data.set("email", String(form.get("email") || "").trim());
    data.set("description", String(form.get("description") || ""));

    const image = form.get("image");

    if (removeImage) {
      // JSON null explicitly clears the existing avatar.
      perform(async () => {
        const updated = await updateProfile({
          first_name: data.get("first_name"),
          last_name: data.get("last_name"),
          email: data.get("email"),
          description: data.get("description"),
          image: null,
        });

        if (mounted.current) {
          setAccount(updated);
          setRemoveImage(false);
          setProfileRevision((value) => value + 1);
        }
      }, "اطلاعات شخصی ذخیره شد.");

      return;
    }

    if (image instanceof File && image.size > 0) {
      data.set("image", image);
    }

    perform(async () => {
      const updated = await updateProfile(data);

      if (mounted.current) {
        setAccount(updated);
        setProfileRevision((value) => value + 1);
      }
    }, "اطلاعات شخصی ذخیره شد.");
  }

  function saveAddress(event) {
    event.preventDefault();

    const form = new FormData(event.currentTarget);
    const data = {};

    for (const [name] of ADDRESS_FIELDS) {
      data[name] = String(form.get(name) || "").trim();
    }

    data.is_default = form.get("is_default") === "on";
    const current = address;

    perform(async () => {
      if (current.id) {
        await updateAddress(current.id, data);
      } else {
        await createAddress(data);
      }

      if (mounted.current) setAddress(null);
      await reloadAccount();
    }, "آدرس ذخیره شد.");
  }

  function makeDefault(id) {
    perform(async () => {
      await updateAddress(id, { is_default: true });
      await reloadAccount();
    }, "آدرس پیش‌فرض تغییر کرد.");
  }

  function confirmDelete() {
    const id = deleteTarget;

    perform(async () => {
      await deleteAddress(id);

      if (mounted.current) {
        setDeleteTarget(null);

        if (address?.id === id) setAddress(null);
      }

      await reloadAccount();
    }, "آدرس حذف شد.");
  }

  function signOutEverywhere() {
    perform(async () => {
      await logoutAll();
      window.location.replace("/login");
    });
  }

  return (
    <div className="app customer-account" dir="rtl" lang="fa">
      <aside className="sidebar">
        <a className="brand" href="/account">
          <span className="brand-mark">D</span>
          <span>
            دیجی‌شاپ
            <small>MY ACCOUNT</small>
          </span>
        </a>

        <p className="nav-caption">حساب کاربری من</p>

        <nav aria-label="منوی حساب">
          {menu.map(([key, label, href]) => (
            <a
              key={key}
              href={href}
              className={`nav-item ${tab === key ? "active" : ""}`}
              aria-current={tab === key ? "page" : undefined}
            >
              {label}
            </a>
          ))}
        </nav>

        <div className="sidebar-note">
          <p>اطلاعات و آدرس‌های حسابت را اینجا مدیریت کن.</p>
        </div>

        <div className="user-card">
          <span className="avatar">
            {account.first_name?.charAt(0) || "ک"}
          </span>
          <div>
            <strong>{fullName || "کاربر دیجی‌شاپ"}</strong>
            <small><bdi>{account.phone}</bdi></small>
          </div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <span className="breadcrumb">حساب من / {title}</span>

          <button
            type="button"
            className="button ghost"
            disabled={disabled}
            onClick={onLogout}
          >
            {busy ? "در حال خروج…" : "خروج از حساب"}
          </button>
        </header>

        <div className="content">
          <div className="page-heading">
            <div>
              <p className="eyebrow">فضای شخصی تو</p>
              <h1>{title}</h1>
            </div>
          </div>

          {(failure || error) && (
            <div className="auth-error" role="alert">
              {failure || error}
            </div>
          )}

          {notice && (
            <div className="notice" role="status">{notice}</div>
          )}

          {pending && (
            <p role="status">در حال انجام درخواست…</p>
          )}

          {tab === "overview" && (
            <>
              <section className="customer-welcome">
                <span
                  className="customer-welcome-icon"
                  aria-hidden="true"
                >
                  ◇
                </span>
                <div>
                  <p className="eyebrow">به حساب خودت خوش آمدی</p>
                  <h2>{fullName || "کاربر دیجی‌شاپ"}، سلام!</h2>
                  <p>
                    اطلاعات شخصی و نشانی‌های ثبت‌شده‌ات
                    از اینجا در دسترس هستند.
                  </p>
                </div>
              </section>

              <div className="customer-summary">
                <section className="card">
                  <h2>
                    {account.profile_completed
                      ? "پروفایل تکمیل است"
                      : "پروفایل نیاز به تکمیل دارد"}
                  </h2>
                  <p className="muted account-spacing">
                    نام، نام خانوادگی و حداقل یک آدرس معتبر
                    برای تکمیل پروفایل لازم است.
                  </p>
                  <a
                    className="button ghost"
                    href="/account?tab=profile"
                  >
                    ویرایش اطلاعات ←
                  </a>
                </section>

                <section className="card">
                  <h2>
                    {addresses.length.toLocaleString("fa-IR")} آدرس
                  </h2>
                  <p className="muted account-spacing">
                    آدرس‌های خودت را ثبت و مدیریت کن.
                  </p>
                  <a
                    className="button ghost"
                    href="/account?tab=addresses"
                  >
                    مدیریت آدرس‌ها ←
                  </a>
                </section>
              </div>

              <section className="card account-spacing">
                <h2>نشست‌های حساب</h2>
                <p className="muted account-spacing">
                  خروج همگانی، تمام نشست‌های مشتری و مدیریت
                  این حساب را در همهٔ دستگاه‌ها لغو می‌کند.
                </p>

                {!allLogoutOpen ? (
                  <button
                    type="button"
                    className="button ghost"
                    disabled={disabled}
                    onClick={() => setAllLogoutOpen(true)}
                  >
                    خروج از همهٔ نشست‌ها
                  </button>
                ) : (
                  <div className="account-actions">
                    <span>از همهٔ نشست‌ها خارج شوی؟</span>
                    <button
                      type="button"
                      className="button primary"
                      disabled={disabled}
                      onClick={signOutEverywhere}
                    >
                      بله، خروج همگانی
                    </button>
                    <button
                      type="button"
                      className="button ghost"
                      disabled={disabled}
                      onClick={() => setAllLogoutOpen(false)}
                    >
                      انصراف
                    </button>
                  </div>
                )}
              </section>
            </>
          )}

          {tab === "profile" && (
            <section className="card">
              <div className="section-heading">
                <h2>اطلاعات شخصی</h2>
                <span className="counter">
                  {account.profile_completed ? "تکمیل‌شده" : "ناقص"}
                </span>
              </div>

              <form
                key={profileRevision}
                onSubmit={saveProfile}
                className="account-form"
              >
                <fieldset disabled={disabled}>
                  <div className="account-form-grid">
                    <Field
                      label="نام"
                      name="first_name"
                      defaultValue={account.first_name || ""}
                      maxLength={150}
                      autoComplete="given-name"
                      required
                    />
                    <Field
                      label="نام خانوادگی"
                      name="last_name"
                      defaultValue={account.last_name || ""}
                      maxLength={150}
                      autoComplete="family-name"
                      required
                    />
                    <Field
                      label="شماره موبایل"
                      value={account.phone || ""}
                      readOnly
                      dir="ltr"
                    />
                    <Field
                      label="ایمیل — اختیاری"
                      name="email"
                      type="email"
                      defaultValue={account.email || ""}
                      maxLength={254}
                      autoComplete="email"
                      dir="ltr"
                    />
                  </div>

                  <label className="account-field">
                    <span>توضیحات — اختیاری</span>
                    <textarea
                      name="description"
                      defaultValue={account.description || ""}
                      maxLength={2000}
                      rows={4}
                    />
                  </label>

                  {account.image && (
                    <img
                      className="account-profile-image"
                      src={account.image}
                      alt="تصویر پروفایل"
                    />
                  )}

                  <Field
                    label="تصویر پروفایل — اختیاری"
                    name="image"
                    type="file"
                    accept="image/*"
                    disabled={disabled || removeImage}
                  />

                  {account.image && (
                    <label className="account-check">
                      <input
                        type="checkbox"
                        checked={removeImage}
                        onChange={(event) =>
                          setRemoveImage(event.target.checked)
                        }
                      />
                      حذف تصویر فعلی
                    </label>
                  )}

                  <button
                    type="submit"
                    className="button primary"
                  >
                    ذخیرهٔ اطلاعات
                  </button>
                </fieldset>
              </form>
            </section>
          )}

          {tab === "addresses" && (
            <>
              <section className="card">
                <div className="section-heading">
                  <h2>آدرس‌های من</h2>
                  <button
                    type="button"
                    className="button primary"
                    disabled={disabled}
                    onClick={() => {
                      setAddress({
                        ...EMPTY_ADDRESS,
                        recipient_name: fullName,
                        recipient_phone: account.phone || "",
                      });
                      setDeleteTarget(null);
                      setFailure("");
                    }}
                  >
                    افزودن آدرس
                  </button>
                </div>

                {address && (
                  <form
                    key={address.id || "new"}
                    className="account-form account-address-form"
                    onSubmit={saveAddress}
                  >
                    <h3>
                      {address.id ? "ویرایش آدرس" : "آدرس جدید"}
                    </h3>

                    <fieldset disabled={disabled}>
                      <div className="account-form-grid">
                        {ADDRESS_FIELDS.map(([name, label, max]) => (
                          <Field
                            key={name}
                            label={label}
                            name={name}
                            defaultValue={address[name] || ""}
                            maxLength={max}
                            required={name !== "unit"}
                            inputMode={
                              ["recipient_phone", "postal_code"].includes(name)
                                ? "numeric"
                                : undefined
                            }
                          />
                        ))}
                      </div>

                      <label className="account-check">
                        <input
                          name="is_default"
                          type="checkbox"
                          defaultChecked={address.is_default}
                        />
                        آدرس پیش‌فرض
                      </label>

                      <div className="account-actions">
                        <button
                          type="submit"
                          className="button primary"
                        >
                          ذخیرهٔ آدرس
                        </button>
                        <button
                          type="button"
                          className="button ghost"
                          onClick={() => setAddress(null)}
                        >
                          انصراف
                        </button>
                      </div>
                    </fieldset>
                  </form>
                )}

                {addresses.length === 0 ? (
                  <div className="empty">
                    هنوز آدرسی ثبت نشده است.
                  </div>
                ) : (
                  <div className="customer-address-grid">
                    {addresses.map((item) => (
                      <article
                        className="customer-address"
                        key={item.id}
                      >
                        <div className="section-heading">
                          <strong>{item.recipient_name}</strong>
                          {item.is_default && (
                            <span className="counter">پیش‌فرض</span>
                          )}
                        </div>

                        <p>{item.province}، {item.city}</p>
                        <p>{item.street_address}</p>
                        <p className="muted">
                          پلاک {item.building_number}
                          {item.unit ? `، واحد ${item.unit}` : ""}
                        </p>
                        <p className="muted">
                          کد پستی: <bdi>{item.postal_code}</bdi>
                        </p>
                        <p className="muted">
                          موبایل گیرنده:{" "}
                          <bdi>{item.recipient_phone}</bdi>
                        </p>

                        <div className="account-actions">
                          <button
                            type="button"
                            className="button ghost"
                            disabled={disabled}
                            onClick={() => {
                              setAddress(item);
                              setDeleteTarget(null);
                            }}
                          >
                            ویرایش
                          </button>

                          {!item.is_default && (
                            <button
                              type="button"
                              className="button ghost"
                              disabled={disabled}
                              onClick={() => makeDefault(item.id)}
                            >
                              انتخاب پیش‌فرض
                            </button>
                          )}

                          <button
                            type="button"
                            className="button ghost"
                            disabled={disabled}
                            onClick={() => setDeleteTarget(item.id)}
                          >
                            حذف
                          </button>
                        </div>

                        {deleteTarget === item.id && (
                          <div className="account-confirm" role="group">
                            <p>این آدرس حذف شود؟</p>
                            <div className="account-actions">
                              <button
                                type="button"
                                className="button primary"
                                disabled={disabled}
                                onClick={confirmDelete}
                              >
                                تأیید حذف
                              </button>
                              <button
                                type="button"
                                className="button ghost"
                                disabled={disabled}
                                onClick={() => setDeleteTarget(null)}
                              >
                                انصراف
                              </button>
                            </div>
                          </div>
                        )}
                      </article>
                    ))}
                  </div>
                )}
              </section>
            </>
          )}
        </div>
      </main>
    </div>
  );
}