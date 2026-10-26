export default function CustomerAccount({
  user,
  onLogout,
  busy,
  error,
}) {
  const requestedTab = new URLSearchParams(
    window.location.search,
  ).get("tab");

  const tab = ["profile", "addresses"].includes(requestedTab)
    ? requestedTab
    : "overview";

  const fullName = [user.first_name, user.last_name]
    .filter(Boolean)
    .join(" ");

  const addresses = Array.isArray(user.addresses)
    ? user.addresses
    : [];

  const menu = [
    ["overview", "نمای کلی", "/account"],
    ["profile", "اطلاعات شخصی", "/account?tab=profile"],
    ["addresses", "آدرس‌های من", "/account?tab=addresses"],
  ];

  const title = menu.find(([key]) => key === tab)[1];

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
          <p>اطلاعات و آدرس‌های حسابت را اینجا ببین.</p>
        </div>

        <div className="user-card">
          <span className="avatar">
            {user.first_name?.charAt(0) || "ک"}
          </span>

          <div>
            <strong>{fullName || "کاربر دیجی‌شاپ"}</strong>
            <small><bdi>{user.phone}</bdi></small>
          </div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <span className="breadcrumb">
            حساب من / {title}
          </span>

          <button
            className="button ghost"
            disabled={busy}
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

          {error && (
            <div className="auth-error" role="alert">
              {error}
            </div>
          )}

          {tab === "overview" && (
            <>
              <section className="customer-welcome">
                <span className="customer-welcome-icon" aria-hidden="true">
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
                  <p className="eyebrow">اطلاعات حساب</p>
                  <h2>
                    {user.profile_completed
                      ? "پروفایل تکمیل است"
                      : "پروفایل نیاز به تکمیل دارد"}
                  </h2>

                  <p className="muted" style={{ margin: "12px 0 20px" }}>
                    نام، شماره موبایل و ایمیل حسابت را بررسی کن.
                  </p>

                  <a
                    className="button ghost"
                    href="/account?tab=profile"
                  >
                    مشاهدهٔ اطلاعات ←
                  </a>
                </section>

                <section className="card">
                  <p className="eyebrow">نشانی‌های ثبت‌شده</p>
                  <h2>
                    {addresses.length.toLocaleString("fa-IR")} آدرس
                  </h2>

                  <p className="muted" style={{ margin: "12px 0 20px" }}>
                    نشانی‌های مربوط به حساب خودت را ببین.
                  </p>

                  <a
                    className="button ghost"
                    href="/account?tab=addresses"
                  >
                    مشاهدهٔ آدرس‌ها ←
                  </a>
                </section>
              </div>
            </>
          )}

          {tab === "profile" && (
            <section className="card">
              <div className="section-heading">
                <h2>اطلاعات شخصی</h2>
                <span className="counter">
                  {user.profile_completed ? "تکمیل‌شده" : "ناقص"}
                </span>
              </div>

              <dl className="auth-profile">
                <div>
                  <dt>نام</dt>
                  <dd>{user.first_name || "ثبت نشده"}</dd>
                </div>
                <div>
                  <dt>نام خانوادگی</dt>
                  <dd>{user.last_name || "ثبت نشده"}</dd>
                </div>
                <div>
                  <dt>شماره موبایل</dt>
                  <dd><bdi>{user.phone || "—"}</bdi></dd>
                </div>
                <div>
                  <dt>ایمیل</dt>
                  <dd><bdi>{user.email || "ثبت نشده"}</bdi></dd>
                </div>
              </dl>
            </section>
          )}

          {tab === "addresses" && (
            <section className="card">
              <div className="section-heading">
                <h2>آدرس‌های من</h2>
                <span className="counter">
                  {addresses.length.toLocaleString("fa-IR")} آدرس
                </span>
              </div>

              {addresses.length === 0 ? (
                <div className="empty">
                  هنوز آدرسی برای این حساب ثبت نشده است.
                </div>
              ) : (
                <div className="customer-address-grid">
                  {addresses.map((address) => (
                    <article
                      className="customer-address"
                      key={address.id}
                    >
                      <div className="section-heading">
                        <strong>{address.recipient_name}</strong>

                        {address.is_default && (
                          <span className="counter">
                            پیش‌فرض
                          </span>
                        )}
                      </div>

                      <p>
                        {address.province}، {address.city}
                      </p>

                      <p>{address.street_address}</p>

                      <p className="muted">
                        پلاک {address.building_number}
                        {address.unit ? `، واحد ${address.unit}` : ""}
                      </p>

                      <p className="muted">
                        کد پستی: <bdi>{address.postal_code}</bdi>
                      </p>

                      <p className="muted">
                        موبایل گیرنده:{" "}
                        <bdi>{address.recipient_phone}</bdi>
                      </p>
                    </article>
                  ))}
                </div>
              )}
            </section>
          )}
        </div>
      </main>
    </div>
  );
}