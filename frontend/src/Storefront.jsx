import VariantPicker from "./attributes/VariantPicker";
import RichContent from "./richtext/RichContent";
import { Promotions } from "./banners/Promotions";
import PublicPage from "./pages/PublicPage";
import {
  StoreThemeProvider,
  useStoreTheme,
  themeVariables,
  readBootstrap,
} from "./appearance/StoreTheme";
import StoreFooter from "./storefront/StoreFooter";
import SavedButtons from "./customer-hub/SavedButtons";
import CategoryRoute from "./storefront/CategoryRoute";
import CategoryBrowser, {
  HomeCategoryStrip,
  flattenCategoryTree,
} from "./storefront/CategoryBrowser";

import { CartProvider, CartBadge } from "./cart/CartProvider";
import AddToCart from "./cart/AddToCart";
import CartPage from "./cart/CartPage";
import { useEffect, useState } from "react";
import {
  catalogHref,
  cover,
  getStore,
  money,
  number,
  pageNumber,
  safeImage,
} from "./storefront/store-api";
import "./storefront/storefront.css";
import StoreCustomerLink from "./StoreCustomerLink";
import CheckoutPage from "./orders/CheckoutPage";
import OrdersPage from "./orders/OrdersPage";
import OrderDetailPage from "./orders/OrderDetailPage";
import FakePaymentPage from "./payments/FakePaymentPage";
import CategoryMenu from "./storefront/CategoryMenu";

import { navigateStore, useStoreLocation } from "./storefront/store-navigation";

import { useCategoryTree } from "./storefront/category-data";
import ClickSelect from "./components/ClickSelect.jsx";

import StoreExperience from "./appearance/StoreExperience";

function Icon({ name, size = 22, ...props }) {
  const paths = {
    search: (
      <>
        <circle cx="10.5" cy="10.5" r="6.5" />
        <path d="m16 16 4.5 4.5" />
      </>
    ),
    user: (
      <>
        <circle cx="12" cy="8" r="4" />
        <path d="M4 22v-3a8 8 0 0 1 16 0v3" />
      </>
    ),
    bag: (
      <>
        <path d="M5 7h14l1 14H4L5 7Z" />
        <path d="M8 8V6a4 4 0 0 1 8 0v2" />
      </>
    ),
    arrow: (
      <>
        <path d="M19 12H5m6-6-6 6 6 6" />
      </>
    ),
    grid: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="2" />
        <rect x="14" y="3" width="7" height="7" rx="2" />
        <rect x="3" y="14" width="7" height="7" rx="2" />
        <rect x="14" y="14" width="7" height="7" rx="2" />
      </>
    ),
    phone: (
      <>
        <rect x="6" y="2" width="12" height="20" rx="3" />
        <path d="M10 18h4M10 5h4" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    close: <path d="m6 6 12 12M6 18 18 6" />,
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {paths[name] || paths.grid}
    </svg>
  );
}

function useStore(path) {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState({ key: "", data: null, error: null });
  const key = `${path}:${attempt}`;
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, 15000);
    getStore(path, controller.signal)
      .then((data) => {
        if (active) setResult({ key, data, error: null });
      })
      .catch((error) => {
        if (active)
          setResult({
            key,
            data: null,
            error: timedOut
              ? new Error("پاسخ سرور طول کشید. دوباره تلاش کن.")
              : error,
          });
      })
      .finally(() => clearTimeout(timer));
    return () => {
      active = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, [path, key]);
  return {
    data: result.key === key ? result.data : null,
    error: result.key === key ? result.error : null,
    retry: () => setAttempt((value) => value + 1),
  };
}

function Failure({ error, retry }) {
  return (
    <div className="sf-message" role="alert">
      <h2>اطلاعات دریافت نشد</h2>
      <p>{error.message}</p>
      <button className="sf-button" onClick={retry}>
        تلاش دوباره
      </button>
    </div>
  );
}

function ProductImage({ src, name, eager = false }) {
  const [failed, setFailed] = useState(false);
  if (!src || failed)
    return (
      <div className="sf-no-image">
        <Icon name="phone" size={54} />
        <span>تصویر ثبت نشده</span>
      </div>
    );
  return (
    <img
      src={src}
      alt={name}
      loading={eager ? "eager" : "lazy"}
      onError={() => setFailed(true)}
    />
  );
}

function Header({ search }) {
  return (
    <>
      <header className="sf-header">
        <div className="sf-container sf-header-main">
          <a className="sf-brand" href="/" aria-label="دیجی‌شاپ، صفحهٔ اصلی">
            <span className="sf-brand-symbol">
              D<span />
            </span>
            <span>
              دیجی‌شاپ<small>DIGISHOP</small>
            </span>
          </a>
          <form
            key={search}
            className="sf-search"
            action="/products"
            method="get"
            role="search"
            onSubmit={(event) => {
              event.preventDefault();

              const params = new URLSearchParams(
                new FormData(event.currentTarget),
              );

              navigateStore(`/products?${params}`);
            }}
          >
            <Icon name="search" />
            <input
              name="search"
              aria-label="جست‌وجوی محصول"
              placeholder="دنبال چه محصولی می‌گردی؟"
              defaultValue={search}
              maxLength={150}
            />
            <button type="submit">جست‌وجو</button>
          </form>
          <StoreCustomerLink />
          <CartBadge />
        </div>
        <nav
          className="sf-container sf-nav sf-category-nav"
          aria-label="منوی فروشگاه"
        >
          <CategoryMenu />
          <a href="/products">همهٔ محصولات</a>
          <a href="/products?in_stock=true">کالاهای موجود</a>
          <a href="/products?ordering=-created_at">جدیدترین‌ها</a>
          <a href="/orders">سفارش‌های من</a>
        </nav>
      </header>
    </>
  );
}

function StoreWelcome() {
  const theme = useStoreTheme();
  return <section className="sf-welcome sf-container" aria-labelledby="sf-welcome-title">
    <div><span className="sf-welcome-eyebrow"><span /> دنیای انتخاب‌های تو</span>
    <h1 id="sf-welcome-title">{theme.banner?.title || "انتخاب بهتر، هر روز."}</h1></div>
    <p>{theme.banner?.text || "محصولات را مقایسه کن، جزئیات را ببین و انتخاب خودت را پیدا کن."}</p>
  </section>;
}

function CategoryStrip() {
  return <HomeCategoryStrip />;
}

function ProductCard({ product }) {
  const image = cover(product);
  return (
    <article className="sf-product-card">
      <a href={`/products/${product.id}`} className="sf-product-link">
        <div className="sf-product-image">
          <span
            className={`sf-stock ${product.is_available ? "" : "sf-unavailable"}`}
          >
            {product.is_available ? "موجود" : "ناموجود"}
          </span>
          <ProductImage key={image} src={image} name={product.name} />
        </div>
        <div className="sf-product-info">
          <span className="sf-product-brand">
            {product.brand?.name || product.category?.name || "دیجی‌شاپ"}
          </span>
          <h3>{product.name}</h3>
          <p>
            {product.short_description ||
              product.category?.name ||
              "مشاهدهٔ مشخصات محصول"}
          </p>
          <div className="sf-product-bottom">
            <strong>
              {product.is_available
                ? money(product.effective_price)
                : "ناموجود"}
            </strong>
            <span className="sf-card-arrow">
              <Icon name="arrow" size={18} />
            </span>
          </div>
        </div>
      </a>
    </article>
  );
}

function Skeletons() {
  return (
    <div
      className="sf-products"
      role="status"
      aria-label="در حال دریافت محصولات"
    >
      {[1, 2, 3, 4].map((key) => (
        <div className="sf-skeleton" key={key}>
          <span />
          <i />
          <i />
        </div>
      ))}
    </div>
  );
}

function pageHref(search, page) {
  if (!window.location.pathname.startsWith("/products/category/"))
    return catalogHref(search, { page });
  const params = new URLSearchParams(search);
  params.delete("category");
  params.set("page", String(page));
  return window.location.pathname + `?${params}`;
}
function Catalog({ home, search }) {
  const params = new URLSearchParams(search);
  const page = pageNumber(params.get("page"));
  function submitFilters(event) {
    event.preventDefault();
    const values = new URLSearchParams(new FormData(event.currentTarget));
    const id = values.get("category");
    const selected = categoryRows.find((row) => String(row.id) === id);
    if (selected?.url) values.delete("category");
    for (const [key, value] of [...values]) if (!value) values.delete(key);
    navigateStore(
      (selected?.url || "/products") + (values.size ? `?${values}` : ""),
    );
  }
  const allowed = [
    "search",
    "category",
    "categories",
    "min_price",
    "max_price",
    "in_stock",
    "ordering",
  ];
  const query = new URLSearchParams();
  for (const key of allowed)
    if (params.get(key)) query.set(key, params.get(key));
  query.set("page", String(page));
  const list = useStore(`products/?${query}`);
  const categories = useCategoryTree();
  const categoryRows = flattenCategoryTree(categories.data || []);
  const rows = Array.isArray(list.data) ? list.data : list.data?.results || [];
  const count = list.data?.count ?? rows.length;
  const [filtersOpen, setFiltersOpen] = useState(false);
  const Heading = home ? "h2" : "h1";
  const currentCategory = categoryRows.find(
    (category) => String(category.id) === params.get("category"),
  );
  return (
    <section className="sf-catalog" id="products">
      {!home && <CategoryBrowser search={search} />}
      <div className="sf-section-title">
        <div>
          <span className="sf-overline">یک قدم نزدیک‌تر به انتخابت</span>
          <Heading>
            {home
              ? "تازه‌های دیجی‌شاپ"
              : currentCategory?.name || "همهٔ محصولات"}
          </Heading>
        </div>
        {home ? (
          <a href="/products">
            مشاهدهٔ همه
            <Icon name="arrow" size={16} />
          </a>
        ) : (
          <span className="sf-muted">
            {list.data ? `${number(count)} محصول` : "در حال دریافت…"}
          </span>
        )}
      </div>
      {!home && (
        <>
          <button
            className="sf-filter-toggle"
            aria-expanded={filtersOpen}
            aria-controls="sf-filters"
            onClick={() => setFiltersOpen((value) => !value)}
          >
            فیلتر و مرتب‌سازی
          </button>
          <form
            key={search}
            id="sf-filters"
            className={`sf-filters ${filtersOpen ? "sf-filters-open" : ""}`}
            onSubmit={submitFilters}
            action="/products"
            method="get"
          >
            <label>
              جست‌وجو
              <input
                type="search"
                name="search"
                maxLength={150}
                defaultValue={params.get("search") || ""}
                placeholder="نام محصول"
              />
            </label>
            <div className="sf-filter-field">
              <span>دسته‌بندی</span>

              <ClickSelect
                key={`category:${search}`}
                name="category"
                label="دسته‌بندی"
                defaultValue={params.get("category") || ""}
                searchable
                options={[
                  {
                    value: "",
                    label: "همهٔ دسته‌بندی‌ها",
                  },
                  ...categoryRows.map((category) => ({
                    value: String(category.id),
                    label: category.name,
                    description:
                      category.path
                        ?.slice(0, -1)
                        .map((part) => part.name)
                        .join(" / ") || "دستهٔ اصلی",
                    searchText:
                      category.path?.map((part) => part.name).join(" ") ||
                      category.name,
                  })),
                ]}
              />
            </div>{" "}
            <label>
              از قیمت
              <input
                type="number"
                min="0"
                step="1"
                name="min_price"
                defaultValue={params.get("min_price") || ""}
                placeholder="حداقل"
              />
            </label>
            <label>
              تا قیمت
              <input
                type="number"
                min="0"
                step="1"
                name="max_price"
                defaultValue={params.get("max_price") || ""}
                placeholder="حداکثر"
              />
            </label>
            <div className="sf-filter-field">
              <span>مرتب‌سازی</span>

              <ClickSelect
                key={`ordering:${search}`}
                name="ordering"
                label="مرتب‌سازی"
                defaultValue={params.get("ordering") || "-created_at"}
                options={[
                  { value: "-created_at", label: "جدیدترین" },
                  { value: "effective_price", label: "ارزان‌ترین" },
                  { value: "-effective_price", label: "گران‌ترین" },
                  { value: "created_at", label: "قدیمی‌ترین" },
                ]}
              />
            </div>{" "}
            <label className="sf-checkbox">
              <input
                type="checkbox"
                name="in_stock"
                value="true"
                defaultChecked={params.get("in_stock") === "true"}
              />
              فقط موجودها
            </label>
            <button className="sf-button" type="submit">
              اعمال فیلتر
            </button>
            <a className="sf-reset" href="/products">
              حذف فیلترها
            </a>
            {params.get("categories") && (
              <input
                type="hidden"
                name="categories"
                value={params.get("categories")}
              />
            )}
          </form>
          {categories.error && (
            <div className="sf-inline-error" role="alert">
              فهرست دسته‌بندی‌ها دریافت نشد.{" "}
              <button onClick={categories.retry}>تلاش مجدد</button>
            </div>
          )}
        </>
      )}
      {params.get("search") && (
        <p className="sf-search-result">
          نتایج جست‌وجوی «{params.get("search")}»
        </p>
      )}
      {list.error ? (
        <Failure error={list.error} retry={list.retry} />
      ) : !list.data ? (
        <Skeletons />
      ) : rows.length === 0 ? (
        <div className="sf-message">
          <Icon name="search" size={36} />
          <h2>محصولی پیدا نشد</h2>
          <p>جست‌وجو یا فیلترها را تغییر بده.</p>
          <a className="sf-button" href="/products">
            دیدن همهٔ محصولات
          </a>
        </div>
      ) : (
        <>
          <div className="sf-products">
            {rows.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
          {!home && (
            <nav className="sf-pagination" aria-label="صفحه‌بندی محصولات">
              {list.data.previous ? (
                <a href={pageHref(search, page - 1)}>صفحهٔ قبل</a>
              ) : (
                <span aria-disabled="true">صفحهٔ قبل</span>
              )}
              <b>صفحهٔ {number(page)}</b>
              {list.data.next ? (
                <a href={pageHref(search, page + 1)}>صفحهٔ بعد</a>
              ) : (
                <span aria-disabled="true">صفحهٔ بعد</span>
              )}
            </nav>
          )}
        </>
      )}
      {!home && currentCategory?.description?.trim() && (
        <section
          className="sf-category-description"
          aria-label={`توضیحات ${currentCategory.name}`}
        >
          <h2>دربارهٔ {currentCategory.name}</h2>
          <p>{currentCategory.description}</p>
        </section>
      )}
    </section>
  );
}

function ProductDetail({ id }) {
  const result = useStore(`products/${id}/`);
  if (result.error)
    return <Failure error={result.error} retry={result.retry} />;
  if (!result.data)
    return (
      <div className="sf-message" role="status">
        در حال دریافت محصول…
      </div>
    );
  return <ProductContent key={id} product={result.data} />;
}

function ProductContent({ product }) {
  const gallery = (product.images || [])
    .map((image) => ({
      ...image,
      image: safeImage(image.image),
    }))
    .filter((image) => image.image)
    .sort(
      (a, b) =>
        Number(b.is_primary) - Number(a.is_primary) ||
        a.sort_order - b.sort_order ||
        a.id - b.id,
    );

  if (!gallery.length && safeImage(product.image)) {
    gallery.push({
      id: "legacy",
      image: safeImage(product.image),
    });
  }

  const variants = (product.variants || []).filter(
    (variant) => variant.is_active,
  );

  const [selectedId, setSelectedId] = useState(
    product.default_variant?.id || variants[0]?.id || null,
  );

  const [imageIndex, setImageIndex] = useState(0);

  const selected = variants.find((variant) => variant.id === selectedId);

  const price = selected ? selected.price : product.effective_price;

  const available = Boolean(
    product.is_available &&
    (!selected || (selected.stock > 0 && selected.price > 0)),
  );

  return (
    <>
      <nav className="sf-breadcrumb" aria-label="مسیر صفحه">
        <a href="/">فروشگاه</a>
        <span>/</span>
        <a href={catalogHref("", { category: product.category?.id })}>
          {product.category?.name || "محصولات"}
        </a>
        <span>/</span>
        <span>{product.name}</span>
      </nav>

      <div className="sf-product-layout">
        <section className="sf-detail">
          <div className="sf-gallery">
            <div className="sf-main-image">
              <ProductImage
                key={gallery[imageIndex]?.image}
                src={gallery[imageIndex]?.image}
                name={product.name}
                eager
              />
            </div>

            {gallery.length > 1 && (
              <div className="sf-thumbnails" aria-label="تصاویر محصول">
                {gallery.map((image, index) => (
                  <button
                    key={image.id}
                    type="button"
                    className={index === imageIndex ? "is-active" : ""}
                    aria-label={`تصویر ${number(index + 1)}`}
                    aria-pressed={index === imageIndex}
                    onClick={() => setImageIndex(index)}
                  >
                    <ProductImage
                      src={image.image}
                      name={`${product.name}، تصویر ${number(index + 1)}`}
                    />
                  </button>
                ))}
              </div>
            )}

            {(product.gallery_description_html ||
              product.gallery_description) && (
              <RichContent
                className="sf-gallery-caption"
                html={product.gallery_description_html}
                plainText={product.gallery_description}
              />
            )}
          </div>

          <div className="sf-detail-copy">
            <span className="sf-overline">
              {product.brand?.name || product.category?.name}
            </span>

            <h1>{product.name}</h1>
            <p className="sf-detail-intro">{product.short_description}</p>

            <span
              className={`sf-availability ${
                available ? "" : "sf-availability-off"
              }`}
            >
              <span />
              {available ? "موجود در فروشگاه" : "این انتخاب فعلاً ناموجود است"}
            </span>

            {variants.length > 0 && (
              <VariantPicker
                axes={product.variant_schema || []}
                variants={variants}
                selectedId={selectedId}
                onChange={setSelectedId}
              />
            )}
          </div>
        </section>

        <aside className="sf-purchase-column" aria-label="خرید محصول">
          <div className="sf-purchase sf-purchase-sticky">
            <div className="sf-purchase-heading">
              <span>انتخاب شما</span>
              <h2>{product.name}</h2>

              {selected && (
                <p>
                  {selected.label ||
                    [selected.color, selected.storage]
                      .filter(Boolean)
                      .join(" / ")}
                </p>
              )}
            </div>
            <span>قیمت {selected ? "تنوع انتخاب‌شده" : "محصول"}</span>

            <strong>{available ? money(price) : "ناموجود"}</strong>

            {selected && (
              <small>
                کد کالا: <bdi>{selected.sku}</bdi>
              </small>
            )}

            <AddToCart
              key={`${product.id}:${selected?.id || 0}`}
              product={product}
              variant={selected}
              available={available}
            />
            <SavedButtons productId={product.id} />
          </div>
        </aside>

        <div className="sf-detail-sections">
          <section>
            <h2>دربارهٔ محصول</h2>
            <RichContent
              html={product.long_description_html}
              plainText={
                product.long_description ||
                product.description ||
                "توضیحات تکمیلی ثبت نشده است."
              }
            />
          </section>

          <section>
            <h2>مشخصات فنی</h2>

            <dl>
              {product.brand && (
                <div>
                  <dt>برند</dt>
                  <dd>{product.brand.name}</dd>
                </div>
              )}

              <div>
                <dt>دسته‌بندی</dt>
                <dd>{product.category?.name || "—"}</dd>
              </div>

              {(product.attribute_values || []).map((item) => (
                <div key={item.id}>
                  <dt>{item.attribute}</dt>
                  <dd>
                    {item.value}
                    {item.unit ? ` ${item.unit}` : ""}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        </div>
      </div>
    </>
  );
}

export default function Storefront() {
  const { pathname, search } = useStoreLocation();

  const home = pathname === "/";
  const isCart = pathname === "/cart";
  const isCheckout = pathname === "/checkout";
  const isOrders = pathname === "/orders";

  const orderDetail = pathname.match(
    /^\/orders\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i,
  );

  const fakePayment = pathname.match(
    /^\/payments\/fake\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i,
  );

  const detail = pathname.match(/^\/products\/([1-9][0-9]*)$/);

  const found = home || pathname === "/products" || Boolean(detail);

  useEffect(() => {
    document.documentElement.lang = "fa";

    let title = "صفحه پیدا نشد";

    if (
      /^\/payments\/fake\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
        pathname,
      )
    ) {
      title = "پرداخت آزمایشی";
    } else if (pathname === "/orders") {
      title = "سفارش‌های من";
    } else if (
      /^\/orders\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
        pathname,
      )
    ) {
      title = "جزئیات سفارش";
    } else if (pathname === "/checkout") {
      title = "تأیید سفارش";
    } else if (pathname === "/cart") {
      title = "سبد خرید";
    } else if (pathname === "/") {
      title = "انتخاب بهتر برای زندگی امروز";
    } else if (/^\/products\/[1-9][0-9]*$/.test(pathname)) {
      title = "جزئیات محصول";
    } else if (pathname.startsWith("/pages/")) {
      const boot = readBootstrap();
      title = boot?.page?.seo_title || boot?.page?.title || "صفحهٔ فروشگاه";
    } else if (pathname === "/products") {
      title = "محصولات";
    }

    document.title = `${title} | دیجی‌شاپ`;
  }, [pathname]);

  let content;

  if (fakePayment) {
    content = (
      <FakePaymentPage key={fakePayment[1]} paymentId={fakePayment[1]} />
    );
  } else if (isOrders) {
    content = <OrdersPage />;
  } else if (orderDetail) {
    content = <OrderDetailPage key={orderDetail[1]} orderId={orderDetail[1]} />;
  } else if (isCheckout) {
    content = <CheckoutPage />;
  } else if (isCart) {
    content = <CartPage />;
  } else if (detail) {
    content = <ProductDetail id={detail[1]} />;
  } else if (pathname.startsWith("/products/category/")) {
    content = (
      <CategoryRoute
        key={pathname}
        pathname={pathname}
        search={search}
        renderCatalog={(categorySearch) => (
          <Catalog
            key={`${pathname}:${categorySearch}`}
            home={false}
            search={categorySearch}
          />
        )}
      />
    );
  } else if (pathname.startsWith("/pages/")) {
    content = <PublicPage slug={decodeURIComponent(pathname.slice(7))} />;
  } else if (found) {
    content = <Catalog home={home} search={search} />;
  } else {
    content = (
      <div className="sf-message">
        <h1>صفحه پیدا نشد</h1>
        <a className="sf-button" href="/">
          بازگشت به فروشگاه
        </a>
      </div>
    );
  }

  return (
    <StoreLayout>

      {home && (
        <div className="bn-hero-wide">
          <Promotions placement="hero" />
        </div>
      )}
      <main id="sf-main" className="sf-container">
        {home && (
          <>

            <CategoryStrip />
            <Promotions placement="tiles" />
          </>
        )}

        {content}

        {home && (
          <div className="sf-bottom-banner">
            <div>
              <span className="sf-overline">
                انتخاب خوب، از شناخت شروع می‌شود
              </span>
              <h2>قبل از انتخاب، جزئیات را ببین.</h2>
              <p>مشخصات فنی، تصاویر و تنوع‌های هر محصول را یک‌جا بررسی کن.</p>
            </div>

            <a href="/products">
              شروع جست‌وجو
              <Icon name="arrow" />
            </a>
          </div>
        )}
      </main>
    </StoreLayout>
  );
}

export function StoreLayout({
  children,
  themeOverride,
  preview = false,
  linksOverride,
}) {
  return (
    <CartProvider>
      <StoreThemeProvider override={themeOverride}>
        <ThemedShell preview={preview} linksOverride={linksOverride}>
          {children}
        </ThemedShell>
      </StoreThemeProvider>
    </CartProvider>
  );
}
function ThemedShell({ children, preview, linksOverride }) {
  const theme = useStoreTheme();

  return (
    <div
      className="sf-root sf-themed sf-experience sf-studio"
      dir="rtl"
      lang="fa"
      style={themeVariables(theme)}
      onClickCapture={
        preview
          ? (event) => {
              if (event.target.closest?.("a[href]")) {
                event.preventDefault();
              }
            }
          : undefined
      }
      onSubmitCapture={preview ? (event) => event.preventDefault() : undefined}
    >
      <StoreExperience />
      <a className="sf-skip" href="#sf-main">
        رفتن به محتوای اصلی
      </a>

      <Header
        search={
          preview
            ? ""
            : new URLSearchParams(window.location.search).get("search") || ""
        }
      />

      {children}

      <StoreFooter linksOverride={linksOverride} />


    </div>
  );
}
