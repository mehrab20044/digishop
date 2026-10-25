import { useEffect, useRef, useState } from "react";

import DashboardHome from "./DashboardHome";
import Editor, { CREATABLE, EDITABLE } from "./Editor";
import ProductCreate from "./ProductCreate";
import ProductGallery from "./ProductGallery";
import ProductPublication from "./ProductPublication";
import SEOManager from "./SEOManager";

const BASE = "/api/v1/owner/";

const labels = {
  id: "شناسه",
  name: "نام",
  username: "نام کاربری",
  full_name: "نام کامل",
  first_name: "نام",
  last_name: "نام خانوادگی",
  email: "ایمیل",
  phone: "موبایل",
  category: "دسته‌بندی",
  category_id: "شناسه دسته‌بندی",
  brand: "برند",
  brand_id: "شناسه برند",
  slug: "نامک",
  price: "قیمت ثبت‌شده",
  stock: "موجودی",
  status: "وضعیت انتشار",
  is_active: "فعال",
  is_staff: "عضو مدیریت",
  is_superuser: "مدیر اصلی",
  short_description: "توضیح کوتاه",
  long_description: "توضیحات کامل",
  gallery_description: "توضیحات گالری",
  description: "توضیحات",
  created_at: "زمان ایجاد",
  updated_at: "آخرین تغییر",
  date_joined: "تاریخ عضویت",
  last_login: "آخرین ورود",
  phone_verified_at: "زمان تأیید موبایل",
  variants: "تنوع‌های محصول",
  sku: "کد اختصاصی",
  color: "رنگ",
  storage: "حافظه",
  images: "گالری تصاویر",
  image: "تصویر",
  sort_order: "ترتیب",
  is_primary: "تصویر اصلی",
  attribute_values: "مشخصات محصول",
  attribute: "ویژگی",
  value: "مقدار",
  allowed_attributes: "ویژگی‌های مجاز",
  profile: "پروفایل",
  profile_status: "وضعیت پروفایل",
  profile_completed: "پروفایل کامل",
  missing_fields: "اطلاعات ناقص",
  addresses: "آدرس‌های کاربر",
  address: "آدرس",
  user: "کاربر",
  user_id: "شناسه کاربر",
  recipient_name: "نام گیرنده",
  recipient_phone: "موبایل گیرنده",
  province: "استان",
  city: "شهر",
  street_address: "نشانی",
  building_number: "پلاک",
  unit: "واحد",
  postal_code: "کد پستی",
  is_default: "آدرس پیش‌فرض",
  groups: "گروه‌ها",
  user_permissions: "مجوزهای مستقیم",
  permissions: "مجوزها",
  codename: "شناسه مجوز",
};

function display(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  if (typeof value === "boolean") {
    return value ? "بله" : "خیر";
  }

  if (typeof value === "number") {
    return value.toLocaleString("fa-IR");
  }

  return String(value);
}

/* Browser navigation */

function readLocation() {
  return {
    pathname: window.location.pathname,
    search: window.location.search,
  };
}

function useNavigation() {
  const [location, setLocation] = useState(readLocation);

  useEffect(() => {
    function onPopState() {
      setLocation(readLocation());
    }

    window.addEventListener("popstate", onPopState);

    return () => {
      window.removeEventListener("popstate", onPopState);
    };
  }, []);

  function navigate(href, { replace = false } = {}) {
    const next = new URL(href, window.location.origin);

    if (next.origin !== window.location.origin) {
      window.location.assign(next.href);
      return;
    }

    const target = `${next.pathname}${next.search}${next.hash}`;
    const current =
      window.location.pathname +
      window.location.search +
      window.location.hash;

    if (target !== current) {
      if (replace) {
        window.history.replaceState(null, "", target);
      } else {
        window.history.pushState(null, "", target);
      }
    }

    setLocation(readLocation());
  }

  return { location, navigate };
}

function PageLink({
  href,
  navigate,
  children,
  className = "button ghost",
  ...props
}) {
  return (
    <a
      {...props}
      className={className}
      href={href}
      onClick={(event) => {
        if (
          event.defaultPrevented ||
          event.button !== 0 ||
          event.ctrlKey ||
          event.metaKey ||
          event.shiftKey ||
          event.altKey
        ) {
          return;
        }

        event.preventDefault();
        navigate(href);
      }}
    >
      {children}
    </a>
  );
}

function parseRoute(pathname) {
  const path = pathname.replace(/\/+$/, "") || "/";

  if (path === "/" || path === "/dashboard") {
    return { type: "home" };
  }

  const match = path.match(
    /^\/dashboard\/([a-z][a-z0-9_-]*)(?:\/(new|[1-9][0-9]*)(?:\/(edit))?)?$/,
  );

  if (!match) {
    return { type: "not-found" };
  }

  const [, resource, identifier, edit] = match;

  if (resource === "seo") {
    return identifier
      ? { type: "not-found" }
      : { type: "seo", resource };
  }

  if (!identifier) {
    return { type: "list", resource };
  }

  if (identifier === "new") {
    return edit
      ? { type: "not-found" }
      : { type: "create", resource };
  }

  return {
    type: edit ? "edit" : "detail",
    resource,
    id: identifier,
  };
}

function readFilters(search) {
  const params = new URLSearchParams(search);
  const value = Number(params.get("page") || 1);

  return {
    page:
      Number.isSafeInteger(value) && value > 0
        ? value
        : 1,
    search: (params.get("search") || "").slice(0, 150),
  };
}

function listQuery(page, search) {
  const params = new URLSearchParams();

  if (page > 1) {
    params.set("page", String(page));
  }

  if (search) {
    params.set("search", search);
  }

  const query = params.toString();
  return query ? `?${query}` : "";
}

/* API */

function useApi(path) {
  const [result, setResult] = useState({
    path: null,
    data: null,
    error: null,
  });

  useEffect(() => {
    if (path === null) {
      return undefined;
    }

    const controller = new AbortController();

    async function load() {
      try {
        const response = await fetch(`${BASE}${path}`, {
          credentials: "same-origin",
          headers: { Accept: "application/json" },
          cache: "no-store",
          signal: controller.signal,
        });

        const data = await response.json().catch(() => null);

        if (!response.ok) {
          const error = new Error(
            typeof data?.detail === "string"
              ? data.detail
              : data?.error?.message ??
                `دریافت اطلاعات ناموفق بود؛ کد ${response.status}`,
          );

          error.status = response.status;
          throw error;
        }

        if (data === null) {
          throw new Error("پاسخ API از نوع JSON نیست.");
        }

        if (!controller.signal.aborted) {
          setResult({ path, data, error: null });
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setResult({ path, data: null, error });
        }
      }
    }

    load();

    return () => controller.abort();
  }, [path]);

  const ready = path !== null && result.path === path;

  return {
    data: ready ? result.data : null,
    error: ready ? result.error : null,
    loading: path !== null && !ready,
  };
}

/* Shared presentation */

function ErrorMessage({ error }) {
  return (
    <div
      role="alert"
      style={{
        padding: 15,
        marginBottom: 15,
        background: "#fff0f0",
        color: "#9c3030",
        border: "1px solid #f1d3d3",
        borderRadius: 12,
        overflowWrap: "anywhere",
      }}
    >
      {error.message}
    </div>
  );
}

function Value({ name, value }) {
  if (value === null || value === undefined || value === "") {
    return <span className="muted">ثبت نشده</span>;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="muted">موردی ثبت نشده است.</span>;
    }

    return (
      <div style={{ display: "grid", gap: 12 }}>
        {value.map((item, index) => (
          <div
            key={
              item !== null && typeof item === "object"
                ? item.id ?? index
                : index
            }
            style={{
              padding: 14,
              background: "#f5f8fc",
              border: "1px solid #e3eaf4",
              borderRadius: 12,
            }}
          >
            {item !== null && typeof item === "object" ? (
              <Record data={item} />
            ) : (
              labels[item] ?? display(item)
            )}
          </div>
        ))}
      </div>
    );
  }

  if (typeof value === "object") {
    return <Record data={value} />;
  }

  const imageUrl =
    typeof value === "string" &&
    (
      (value.startsWith("/") && !value.startsWith("//")) ||
      /^https?:\/\//i.test(value)
    );

  if (name === "image" && imageUrl) {
    return (
      <a href={value} target="_blank" rel="noreferrer">
        <img
          src={value}
          alt="تصویر ثبت‌شده"
          loading="lazy"
          style={{
            display: "block",
            width: 140,
            maxWidth: "100%",
            height: 140,
            objectFit: "contain",
            background: "#f4f7fc",
            borderRadius: 12,
          }}
        />
      </a>
    );
  }

  return (
    <span
      style={{
        whiteSpace: "pre-wrap",
        overflowWrap: "anywhere",
      }}
    >
      {display(value)}
    </span>
  );
}

function Record({ data, exclude = [] }) {
  return (
    <dl style={{ margin: 0 }}>
      {Object.entries(data)
        .filter(([name]) => !exclude.includes(name))
        .map(([name, value]) => (
          <div
            key={name}
            style={{
              padding: "13px 0",
              borderBottom: "1px solid #e5ebf3",
            }}
          >
            <dt
              style={{
                color: "#718096",
                fontSize: 11,
                marginBottom: 7,
              }}
            >
              {labels[name] ?? name}
            </dt>

            <dd
              style={{
                margin: 0,
                minWidth: 0,
                fontSize: 13,
              }}
            >
              <Value name={name} value={value} />
            </dd>
          </div>
        ))}
    </dl>
  );
}

function PageActions({ children }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        flexWrap: "wrap",
        gap: 10,
        marginBottom: 22,
      }}
    >
      {children}
    </div>
  );
}

function Unavailable({ navigate, message }) {
  return (
    <section className="card">
      <h2>صفحه در دسترس نیست</h2>

      <p style={{ marginTop: 15 }}>
        {message || "آدرس نامعتبر است یا به این بخش دسترسی نداری."}
      </p>

      <PageLink href="/dashboard" navigate={navigate}>
        بازگشت به صفحهٔ نخست
      </PageLink>
    </section>
  );
}

/* List page */

function ResourceList({
  resource,
  revision,
  filters,
  navigate,
}) {
  const base = `/dashboard/${resource.key}`;
  const query = listQuery(filters.page, filters.search);

  const params = new URLSearchParams({
    page: String(filters.page),
    search: filters.search,
    refresh: String(revision),
  });

  const list = useApi(`${resource.key}/?${params}`);

  const canCreate =
    resource.key === "products" ||
    CREATABLE.includes(resource.key);

  function submitSearch(event) {
    event.preventDefault();

    const form = new FormData(event.currentTarget);
    const search = String(form.get("search") || "").trim();

    navigate(`${base}${listQuery(1, search)}`);
  }

  return (
    <section className="card">
      <div className="section-heading">
        <h2>فهرست {resource.label}</h2>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 10,
          }}
        >
          {canCreate && (
            <PageLink
              href={`${base}/new${query}`}
              navigate={navigate}
              className="button primary"
            >
              {resource.key === "products"
                ? "+ افزودن محصول"
                : "+ افزودن"}
            </PageLink>
          )}

          <span className="counter">
            {list.data
              ? `${display(list.data.count)} رکورد`
              : "در حال دریافت"}
          </span>
        </div>
      </div>

      <form
        key={filters.search}
        onSubmit={submitSearch}
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 10,
          marginBottom: 20,
        }}
      >
        <input
          name="search"
          aria-label={`جست‌وجو در ${resource.label}`}
          placeholder="جست‌وجو…"
          maxLength={150}
          defaultValue={filters.search}
          style={{ flex: "1 1 180px" }}
        />

        <button className="button primary" type="submit">
          جست‌وجو
        </button>
      </form>

      {list.loading && (
        <p role="status">در حال دریافت اطلاعات…</p>
      )}

      {list.error && <ErrorMessage error={list.error} />}

      {list.data && (
        <>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {resource.columns.map(([key, label]) => (
                    <th key={key} scope="col">
                      {label}
                    </th>
                  ))}
                  <th scope="col">عملیات</th>
                </tr>
              </thead>

              <tbody>
                {list.data.results.map((row) => (
                  <tr key={row.id}>
                    {resource.columns.map(([key]) => (
                      <td key={key}>{display(row[key])}</td>
                    ))}

                    <td>
                      <div
                        style={{
                          display: "flex",
                          gap: 8,
                        }}
                      >
                        <PageLink
                          href={`${base}/${row.id}${query}`}
                          navigate={navigate}
                        >
                          مشاهده
                        </PageLink>

                        {EDITABLE.includes(resource.key) && (
                          <PageLink
                            href={`${base}/${row.id}/edit${query}`}
                            navigate={navigate}
                          >
                            ویرایش
                          </PageLink>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {list.data.results.length === 0 && (
            <div className="empty">رکوردی پیدا نشد.</div>
          )}

          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexWrap: "wrap",
              gap: 15,
              marginTop: 22,
            }}
          >
            <button
              type="button"
              className="button ghost"
              disabled={!list.data.previous}
              onClick={() =>
                navigate(
                  `${base}${listQuery(
                    filters.page - 1,
                    filters.search,
                  )}`,
                )
              }
            >
              قبلی
            </button>

            <span>صفحهٔ {display(filters.page)}</span>

            <button
              type="button"
              className="button ghost"
              disabled={!list.data.next}
              onClick={() =>
                navigate(
                  `${base}${listQuery(
                    filters.page + 1,
                    filters.search,
                  )}`,
                )
              }
            >
              بعدی
            </button>
          </div>
        </>
      )}
    </section>
  );
}

/* Detail and edit pages */


function ProductImageGrid({ images = [] }) {
  return (
    <section className="product-image-box">
      <div className="section-heading">
        <h2>تصاویر محصول</h2>
        <span className="counter">
          {images.length.toLocaleString("fa-IR")} تصویر
        </span>
      </div>

      {images.length === 0 ? (
        <p className="muted">تصویری ثبت نشده است.</p>
      ) : (
        <div className="product-image-grid">
          {images.map((image) => (
            <a
              key={image.id}
              className="product-image-tile"
              href={image.image}
              target="_blank"
              rel="noreferrer"
              aria-label={`باز کردن تصویر ${image.id}`}
            >
              <img
                src={image.image}
                alt={`تصویر محصول ${image.id}`}
                loading="lazy"
              />

              {image.is_primary && (
                <span className="product-image-badge">
                  تصویر اصلی
                </span>
              )}
            </a>
          ))}
        </div>
      )}
    </section>
  );
}


function ResourceRecord({
  resource,
  route,
  revision,
  query,
  navigate,
  onSaved,
}) {
  const base = `/dashboard/${resource.key}`;
  const listHref = `${base}${query}`;
  const detailHref = `${base}/${route.id}${query}`;
  const editing = route.type === "edit";
  const isProduct = resource.key === "products";
  const canEdit = EDITABLE.includes(resource.key);

  const detail = useApi(
    `${resource.key}/${route.id}/?refresh=${revision}`,
  );

  if (editing && !canEdit) {
    return (
      <Unavailable
        navigate={navigate}
        message="ویرایش این بخش هنوز فعال نشده است."
      />
    );
  }

  const recordName =
    detail.data?.name ||
    detail.data?.full_name ||
    detail.data?.username ||
    `رکورد ${display(route.id)}`;

  return (
    <>
      <PageActions>
        <PageLink href={listHref} navigate={navigate}>
          → بازگشت به فهرست
        </PageLink>

        {editing && (
          <PageLink href={detailHref} navigate={navigate}>
            مشاهدهٔ جزئیات
          </PageLink>
        )}

        {!editing && canEdit && detail.data && (
          <PageLink
            href={`${base}/${route.id}/edit${query}`}
            navigate={navigate}
            className="button primary"
          >
            ویرایش
          </PageLink>
        )}
      </PageActions>

      {detail.loading && (
        <section className="card">
          <p role="status">در حال دریافت اطلاعات…</p>
        </section>
      )}

      {detail.error && (
        <section className="card">
          <ErrorMessage error={detail.error} />
        </section>
      )}

      {detail.data && editing && (
        <>
          <Editor
            key={`${resource.key}-${route.id}-${revision}`}
            resource={resource}
            initial={detail.data}
            onClose={() => navigate(detailHref)}
            onSaved={() => onSaved(detailHref)}
          />

          {isProduct && (
            <section className="card" style={{ marginTop: 22 }}>
              <ProductGallery
                key={`gallery-${route.id}-${revision}`}
                productId={detail.data.id}
              />
            </section>
          )}
        </>
      )}

      {detail.data && !editing && (
        <section className="card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">{resource.label}</p>
              <h2>{recordName}</h2>
            </div>

            <span className="counter">
              شناسه: {display(detail.data.id)}
            </span>
          </div>

          {isProduct && (
            <ProductPublication
              key={`publication-${route.id}-${revision}`}
              product={detail.data}
              onSaved={() => onSaved(detailHref)}
            />
          )}
          {isProduct && (
  <ProductImageGrid images={detail.data.images ?? []} />
)}

<Record
  data={detail.data}
  exclude={isProduct ? ["images"] : []}
/>

        </section>
      )}
    </>
  );
}

/* Create page */

function ResourceCreate({
  resource,
  query,
  navigate,
  onSaved,
}) {
  const listHref = `/dashboard/${resource.key}${query}`;
  const isProduct = resource.key === "products";

  if (!isProduct && !CREATABLE.includes(resource.key)) {
    return (
      <Unavailable
        navigate={navigate}
        message="افزودن رکورد در این بخش هنوز فعال نیست."
      />
    );
  }

  return (
    <>
      <PageActions>
        <PageLink href={listHref} navigate={navigate}>
          → بازگشت به فهرست
        </PageLink>
      </PageActions>

      {isProduct ? (
        <ProductCreate
          onClose={() => navigate(listHref)}
          onSaved={() => onSaved(listHref)}
        />
      ) : (
        <Editor
          resource={resource}
          initial={null}
          onClose={() => navigate(listHref)}
          onSaved={() => onSaved(listHref)}
        />
      )}
    </>
  );
}

/* Application */

export default function App() {
  const [revision, setRevision] = useState(0);
  const [notice, setNotice] = useState("");

  const headingRef = useRef(null);
  const { location, navigate } = useNavigation();

  const route = parseRoute(location.pathname);
  const filters = readFilters(location.search);
  const query = listQuery(filters.page, filters.search);

  const index = useApi(`?refresh=${revision}`);

  const resources = (
    index.data?.resources ?? []
  ).filter((item) => item.key !== "addresses");

  const current = resources.find(
    (item) => item.key === route.resource,
  );

  let title = "صفحهٔ نخست";

  if (route.type === "not-found") {
    title = "صفحه پیدا نشد";
  } else if (route.type !== "home") {
    if (!current) {
      title = "بخش در دسترس نیست";
    } else if (route.type === "create") {
      title = `افزودن — ${current.label}`;
    } else if (route.type === "edit") {
      title = `ویرایش — ${current.label}`;
    } else if (route.type === "detail") {
      title = `${current.label} — رکورد ${display(route.id)}`;
    } else {
      title = current.label;
    }
  }

  useEffect(() => {
    document.title = `${title} | دیجی‌شاپ`;
    headingRef.current?.focus();

    window.scrollTo({
      top: 0,
      left: 0,
      behavior: "instant",
    });
  }, [location.pathname, location.search, title]);

  function go(href) {
    setNotice("");
    navigate(href);
  }

  function openSection(key) {
    go(
      key === "home"
        ? "/dashboard"
        : `/dashboard/${key}`,
    );
  }

  function refresh() {
    setRevision((value) => value + 1);
  }

  function handleSaved(destination) {
    setNotice("تغییرات در دیتابیس ذخیره شد.");
    navigate(destination, { replace: true });
    refresh();
  }

  if (!index.data) {
    const forbidden = [401, 403].includes(
      index.error?.status,
    );

    return (
      <main
        dir="rtl"
        lang="fa"
        style={{
          maxWidth: 700,
          margin: "60px auto",
          padding: 20,
        }}
      >
        <section className="card">
          <p className="eyebrow">دیجی‌شاپ</p>
          <h1>پنل مدیریت</h1>

          {index.loading && (
            <p role="status">در حال اتصال به Backend…</p>
          )}

          {index.error && (
            <>
              <ErrorMessage error={index.error} />

              {forbidden && (
                <p>
                  با حساب مجاز مدیریت وارد Django Admin
                  شو و به این صفحه برگرد.
                </p>
              )}

              <PageActions>
                <a
                  className="button primary"
                  href="http://localhost:8000/admin/"
                  target="_blank"
                  rel="noreferrer"
                >
                  ورود به Django Admin
                </a>

                <button
                  type="button"
                  className="button ghost"
                  onClick={refresh}
                >
                  بررسی دوباره
                </button>
              </PageActions>

              <p className="muted">
                هر دو سایت را با localhost باز کن.
              </p>
            </>
          )}
        </section>
      </main>
    );
  }

  const username =
    index.data.user.full_name ||
    index.data.user.username;

  const validSection = Boolean(current);

  return (
    <div className="app" dir="rtl" lang="fa">
      <aside className="sidebar">
        <PageLink
          className="brand"
          href="/dashboard"
          navigate={go}
        >
          <span className="brand-mark">D</span>

          <span>
            دیجی‌شاپ
            <small>MANAGEMENT WORKSPACE</small>
          </span>
        </PageLink>

        <p className="nav-caption">بخش‌های مدیریت</p>

        <nav aria-label="منوی مدیریت">
          <PageLink
            href="/dashboard"
            navigate={go}
            className={`nav-item ${
              route.type === "home" ? "active" : ""
            }`}
            aria-current={
              route.type === "home" ? "page" : undefined
            }
          >
            <span aria-hidden="true">◫</span>
            صفحهٔ نخست
          </PageLink>

          {resources.map((item) => (
            <PageLink
              key={item.key}
              href={`/dashboard/${item.key}`}
              navigate={go}
              className={`nav-item ${
                current?.key === item.key ? "active" : ""
              }`}
              aria-current={
                current?.key === item.key ? "page" : undefined
              }
            >
              {item.label}

              <small style={{ marginInlineStart: "auto" }}>
                {display(item.count)}
              </small>
            </PageLink>
          ))}
        </nav>

        <div className="sidebar-note">
          <span className="live-dot" />
          متصل به فروشگاه
        </div>

        <div className="user-card">
          <span className="avatar">
            {username.trim().charAt(0) || "م"}
          </span>

          <div>
            <strong>{username}</strong>
            <small>حساب مدیریت</small>
          </div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <span className="breadcrumb">
            مدیریت / {title}
          </span>

          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 10,
            }}
          >
            <a
              className="button ghost"
              href="http://localhost:8000/admin/"
              target="_blank"
              rel="noreferrer"
            >
              Django Admin
            </a>

            <button
              type="button"
              className="button primary"
              onClick={refresh}
            >
              تازه‌سازی
            </button>
          </div>
        </header>

        <div className="content">
          <div className="page-heading">
            <div>
              <p className="eyebrow">مدیریت فروشگاه</p>
              <h1
                ref={headingRef}
                tabIndex={-1}
                style={{ outline: "none" }}
              >
                {title}
              </h1>
            </div>
          </div>

          {notice && (
            <div className="notice" role="status">
              <span>{notice}</span>

              <button
                type="button"
                aria-label="بستن پیام"
                onClick={() => setNotice("")}
              >
                ×
              </button>
            </div>
          )}

          {route.type === "home" && (
            <DashboardHome
              key={`home-${revision}`}
              resources={resources}
              username={username}
              onNavigate={openSection}
            />
          )}

          {route.type === "seo" && validSection && (
            <SEOManager key={`seo-${revision}`} />
          )}

          {route.type === "list" && validSection && (
            <ResourceList
              key={current.key}
              resource={current}
              revision={revision}
              filters={filters}
              navigate={go}
            />
          )}

          {route.type === "create" && validSection && (
            <ResourceCreate
              key={`create-${current.key}-${revision}`}
              resource={current}
              query={query}
              navigate={go}
              onSaved={handleSaved}
            />
          )}

          {["detail", "edit"].includes(route.type) &&
            validSection && (
              <ResourceRecord
                key={`${current.key}-${route.id}-${route.type}`}
                resource={current}
                route={route}
                revision={revision}
                query={query}
                navigate={go}
                onSaved={handleSaved}
              />
            )}

          {(route.type === "not-found" ||
            (route.type !== "home" && !validSection)) && (
            <Unavailable navigate={go} />
          )}
        </div>
      </main>
    </div>
  );
}