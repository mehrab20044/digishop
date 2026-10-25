const sections = {
  products: {
    icon: "◇",
    description: "محصولات، قیمت، موجودی و اطلاعات کالا",
    color: "blue",
  },
  categories: {
    icon: "▦",
    description: "دسته‌بندی محصولات و ویژگی‌های مجاز",
    color: "purple",
  },
  brands: {
    icon: "◈",
    description: "برندهای ثبت‌شدهٔ فروشگاه",
    color: "orange",
  },
  attributes: {
    icon: "≡",
    description: "ویژگی‌ها و مشخصات قابل استفاده",
    color: "purple",
  },
  users: {
    icon: "○",
    description: "حساب‌ها، پروفایل و اطلاعات کاربران",
    color: "green",
  },
  addresses: {
    icon: "⌖",
    description: "نشانی‌های ثبت‌شدهٔ کاربران",
    color: "orange",
  },
  groups: {
    icon: "▤",
    description: "گروه‌های دسترسی کاربران",
    color: "blue",
  },
};

export default function DashboardHome({
  resources,
  username,
  onNavigate,
}) {
  const today = new Intl.DateTimeFormat("fa-IR", {
    dateStyle: "full",
  }).format(new Date());

  const primaryKeys = [
    "products",
    "categories",
    "brands",
    "users",
  ];

  const primary = primaryKeys
    .map((key) => resources.find((item) => item.key === key))
    .filter(Boolean);

  const products = resources.find(
    (item) => item.key === "products",
  );

  return (
    <div className="dashboard-home">
      <section className="home-welcome">
        <div className="home-welcome-content">
          <span className="home-date">{today}</span>

          <h2>{username}، خوش آمدی.</h2>

          <p>
            اطلاعات فروشگاه و مسیرهای مدیریت،
            همه در یک فضای کاری.
          </p>

          {products && (
            <button
              className="button home-welcome-button"
              onClick={() => onNavigate("products")}
            >
              مدیریت محصولات
              <span aria-hidden="true">←</span>
            </button>
          )}
        </div>

        <div className="home-illustration" aria-hidden="true">
          <div className="home-orbit home-orbit-one" />
          <div className="home-orbit home-orbit-two" />

          <div className="home-box">◇</div>

          <span className="home-floating-tag home-tag-top">
            مدیریت فروشگاه
          </span>

          <span className="home-floating-tag home-tag-bottom">
            DIGISHOP
          </span>
        </div>
      </section>

      <div className="home-section-title">
        <div>
          <h2>فروشگاه در یک نگاه</h2>
          <p>تعداد کل رکوردهای ثبت‌شده در هر بخش</p>
        </div>
        <span className="home-data-label">داده‌های واقعی</span>
      </div>

      <div className="home-stat-grid">
        {primary.map((item) => {
          const config = sections[item.key];

          return (
            <button
              key={item.key}
              className={`home-stat home-color-${config.color}`}
              onClick={() => onNavigate(item.key)}
            >
              <div className="home-stat-top">
                <span>{item.label}</span>
                <span className="home-stat-icon" aria-hidden="true">
                  {config.icon}
                </span>
              </div>

              <strong>
                {item.count.toLocaleString("fa-IR")}
              </strong>

              <div className="home-stat-bottom">
                <span>مشاهدهٔ فهرست</span>
                <span aria-hidden="true">←</span>
              </div>
            </button>
          );
        })}
      </div>

      <div className="home-lower-grid">
        <section className="card">
          <div className="section-heading">
            <h2>دسترسی سریع</h2>
            <span className="counter">
              {resources.length.toLocaleString("fa-IR")} بخش
            </span>
          </div>

          <div className="home-shortcuts">
            {resources.map((item) => {
              const config = sections[item.key] ?? {
                icon: "◇",
                color: "blue",
                description: "مشاهده و مدیریت اطلاعات",
              };

              return (
                <button
                  className={`home-shortcut home-color-${config.color}`}
                  key={item.key}
                  onClick={() => onNavigate(item.key)}
                >
                  <span
                    className="home-shortcut-icon"
                    aria-hidden="true"
                  >
                    {config.icon}
                  </span>

                  <span className="home-shortcut-text">
                    <strong>{item.label}</strong>
                    <small>{config.description}</small>
                  </span>

                  <span className="home-shortcut-arrow" aria-hidden="true">
                    ←
                  </span>
                </button>
              );
            })}

            {resources.length === 0 && (
              <p className="muted">
                بخشی برای نمایش در دسترس نیست.
              </p>
            )}
          </div>
        </section>

        <aside className="card home-guide">
          <div className="section-heading">
            <h2>راهنمای مدیریت</h2>
          </div>

          <div className="home-guide-item">
            <span>۱</span>
            <div>
              <strong>ثبت اطلاعات محصول</strong>
              <p>
                نام، دسته‌بندی، قیمت و موجودی پایه را وارد کن.
              </p>
            </div>
          </div>

          <div className="home-guide-item">
            <span>۲</span>
            <div>
              <strong>تکمیل و انتشار</strong>
              <p>
                محصول جدید پیش‌نویس است؛ تصویر و تنوع‌ها
                را فعلاً در Django Admin تکمیل کن.
              </p>
            </div>
          </div>

          <div className="home-guide-item">
            <span>۳</span>
            <div>
              <strong>بررسی اطلاعات ثبت‌شده</strong>
              <p>
                از صفحهٔ هر بخش، جزئیات رکوردها را باز کن.
                برای دریافت آمار جدید، تازه‌سازی را بزن.
              </p>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}