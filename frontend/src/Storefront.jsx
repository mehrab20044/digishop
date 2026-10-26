
import { useEffect, useState } from 'react';
import { catalogHref, cover, getStore, money, number, pageNumber, safeImage } from './storefront/store-api';
import './storefront/storefront.css';
import StoreCustomerLink from "./StoreCustomerLink";

function Icon({ name, size = 22, ...props }) {
  const paths = {
    search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 4.5 4.5" /></>,
    user: <><circle cx="12" cy="8" r="4" /><path d="M4 22v-3a8 8 0 0 1 16 0v3" /></>,
    bag: <><path d="M5 7h14l1 14H4L5 7Z" /><path d="M8 8V6a4 4 0 0 1 8 0v2" /></>,
    arrow: <><path d="M19 12H5m6-6-6 6 6 6" /></>,
    grid: <><rect x="3" y="3" width="7" height="7" rx="2" /><rect x="14" y="3" width="7" height="7" rx="2" /><rect x="3" y="14" width="7" height="7" rx="2" /><rect x="14" y="14" width="7" height="7" rx="2" /></>,
    phone: <><rect x="6" y="2" width="12" height="20" rx="3" /><path d="M10 18h4M10 5h4" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    close: <path d="m6 6 12 12M6 18 18 6" />,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[name] || paths.grid}</svg>;
}

function useStore(path) {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState({ key: '', data: null, error: null });
  const key = `${path}:${attempt}`;
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, 15000);
    getStore(path, controller.signal)
      .then(data => { if (active) setResult({ key, data, error: null }); })
      .catch(error => {
        if (active) setResult({ key, data: null, error: timedOut ? new Error('پاسخ سرور طول کشید. دوباره تلاش کن.') : error });
      })
      .finally(() => clearTimeout(timer));
    return () => { active = false; clearTimeout(timer); controller.abort(); };
  }, [path, key]);
  return { data: result.key === key ? result.data : null, error: result.key === key ? result.error : null, retry: () => setAttempt(value => value + 1) };
}

function Failure({ error, retry }) {
  return <div className="sf-message" role="alert"><h2>اطلاعات دریافت نشد</h2><p>{error.message}</p><button className="sf-button" onClick={retry}>تلاش دوباره</button></div>;
}

function ProductImage({ src, name, eager = false }) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) return <div className="sf-no-image"><Icon name="phone" size={54} /><span>تصویر ثبت نشده</span></div>;
  return <img src={src} alt={name} loading={eager ? 'eager' : 'lazy'} onError={() => setFailed(true)} />;
}

function Header({ search }) {
  return <>
    <div className="sf-announcement">انتخاب دقیق‌تر، خرید آسوده‌تر <span>به دیجی‌شاپ خوش آمدید</span></div>
    <header className="sf-header">
      <div className="sf-container sf-header-main">
        <a className="sf-brand" href="/" aria-label="دیجی‌شاپ، صفحه اصلی"><span className="sf-brand-symbol">D<span /></span><span>دیجی‌شاپ<small>DIGISHOP</small></span></a>
        <form className="sf-search" action="/products" method="get" role="search"><Icon name="search" /><input name="search" aria-label="جست‌وجوی محصول" placeholder="دنبال چه محصولی می‌گردی؟" defaultValue={search} maxLength={150} /><button type="submit">جست‌وجو</button></form>
        <StoreCustomerLink />
      </div>
      <nav className="sf-container sf-nav" aria-label="منوی فروشگاه"><a href="/products"><Icon name="grid" size={18} />همهٔ محصولات</a><a href="/products?in_stock=true">کالاهای موجود</a><a href="/products?ordering=-created_at">جدیدترین‌ها</a><span>فروشگاه آنلاین کالای دیجیتال</span></nav>
    </header>
  </>;
}

function Hero() {
  return <section className="sf-hero">
    <div className="sf-hero-copy"><span className="sf-kicker"><span />دنیای دیجیتال، انتخاب تو</span><h1>یک انتخاب هوشمند،<br /><em>برای هر روز تو.</em></h1><p>محصولات را ببین، مشخصات را مقایسه کن و رنگ و حافظهٔ مناسب خودت را انتخاب کن.</p><a className="sf-button" href="/products">کشف محصولات<Icon name="arrow" size={18} /></a><div className="sf-hero-meta"><span>انتخاب بر اساس مشخصات</span><i /><span>قیمت و موجودی به‌روز</span></div></div>
    <div className="sf-hero-art" aria-hidden="true"><div className="sf-orbit sf-orbit-one" /><div className="sf-orbit sf-orbit-two" /><span className="sf-art-star">✦</span><div className="sf-phone sf-phone-back"><span className="sf-camera"><i /><i /><i /></span><span className="sf-phone-logo">D</span></div><div className="sf-phone sf-phone-front"><div className="sf-phone-screen"><i /><span className="sf-screen-time">09:41</span><span className="sf-screen-caption">MAKE IT<br />YOURS.</span><b /></div></div><div className="sf-art-chip"><Icon name="check" size={18} /><span>انتخاب، به سبک تو</span></div><span className="sf-art-label">YOUR NEXT<br /><b>EVERYDAY ESSENTIAL.</b></span></div>
  </section>;
}

function CategoryStrip() {
  const { data, error, retry } = useStore('categories/');
  const rows = Array.isArray(data) ? data : data?.results || [];
  return <section className="sf-category-section" aria-label="دسته‌بندی محصولات"><div className="sf-section-title"><div><span className="sf-overline">از اینجا شروع کن</span><h2>دسته‌بندی محصولات</h2></div><a href="/products">مشاهدهٔ همه<Icon name="arrow" size={16} /></a></div>{error ? <div className="sf-inline-error" role="alert">دسته‌بندی‌ها دریافت نشدند. <button onClick={retry}>تلاش مجدد</button></div> : !data ? <p role="status">در حال دریافت دسته‌بندی‌ها…</p> : <div className="sf-categories"><a className="sf-category sf-category-all" href="/products"><span><Icon name="grid" size={30} /></span><b>همهٔ محصولات</b></a>{rows.map((category, index) => <a className={`sf-category sf-category-${index % 4}`} key={category.id} href={catalogHref('', { category: category.id })}><span><Icon name="phone" size={30} /></span><b>{category.name}</b></a>)}</div>}</section>;
}

function ProductCard({ product }) {
  const image = cover(product);
  return <article className="sf-product-card"><a href={`/products/${product.id}`} className="sf-product-link"><div className="sf-product-image"><span className={`sf-stock ${product.is_available ? '' : 'sf-unavailable'}`}>{product.is_available ? 'موجود' : 'ناموجود'}</span><ProductImage key={image} src={image} name={product.name} /></div><div className="sf-product-info"><span className="sf-product-brand">{product.brand?.name || product.category?.name || 'دیجی‌شاپ'}</span><h3>{product.name}</h3><p>{product.short_description || product.category?.name || 'مشاهدهٔ مشخصات محصول'}</p><div className="sf-product-bottom"><strong>{product.is_available ? money(product.effective_price) : 'ناموجود'}</strong><span className="sf-card-arrow"><Icon name="arrow" size={18} /></span></div></div></a></article>;
}

function Skeletons() {
  return <div className="sf-products" role="status" aria-label="در حال دریافت محصولات">{[1, 2, 3, 4].map(key => <div className="sf-skeleton" key={key}><span /><i /><i /></div>)}</div>;
}

function Catalog({ home, search }) {
  const params = new URLSearchParams(search);
  const page = pageNumber(params.get('page'));
  const allowed = ['search', 'category', 'min_price', 'max_price', 'in_stock', 'ordering'];
  const query = new URLSearchParams();
  for (const key of allowed) if (params.get(key)) query.set(key, params.get(key));
  query.set('page', String(page));
  const list = useStore(`products/?${query}`);
  const categories = useStore('categories/');
  const categoryRows = Array.isArray(categories.data) ? categories.data : categories.data?.results || [];
  const rows = Array.isArray(list.data) ? list.data : list.data?.results || [];
  const count = list.data?.count ?? rows.length;
  const [filtersOpen, setFiltersOpen] = useState(false);
  const Heading = home ? 'h2' : 'h1';
  const currentCategory = categoryRows.find(category => String(category.id) === params.get('category'));
  return <section className="sf-catalog" id="products">
    <div className="sf-section-title"><div><span className="sf-overline">یک قدم نزدیک‌تر به انتخابت</span><Heading>{home ? 'تازه‌های دیجی‌شاپ' : currentCategory?.name || 'همهٔ محصولات'}</Heading></div>{home ? <a href="/products">مشاهدهٔ همه<Icon name="arrow" size={16} /></a> : <span className="sf-muted">{list.data ? `${number(count)} محصول` : 'در حال دریافت…'}</span>}</div>
    {!home && <><button className="sf-filter-toggle" aria-expanded={filtersOpen} aria-controls="sf-filters" onClick={() => setFiltersOpen(value => !value)}>فیلتر و مرتب‌سازی</button><form id="sf-filters" className={`sf-filters ${filtersOpen ? 'sf-filters-open' : ''}`} action="/products" method="get">
      <label>جست‌وجو<input type="search" name="search" maxLength={150} defaultValue={params.get('search') || ''} placeholder="نام محصول" /></label>
      <label>دسته‌بندی<select key={categoryRows.length} name="category" defaultValue={params.get('category') || ''}><option value="">همهٔ دسته‌ها</option>{categoryRows.map(category => <option value={category.id} key={category.id}>{category.name}</option>)}</select></label>
      <label>از قیمت<input type="number" min="0" step="1" name="min_price" defaultValue={params.get('min_price') || ''} placeholder="حداقل" /></label>
      <label>تا قیمت<input type="number" min="0" step="1" name="max_price" defaultValue={params.get('max_price') || ''} placeholder="حداکثر" /></label>
      <label>مرتب‌سازی<select name="ordering" defaultValue={params.get('ordering') || '-created_at'}><option value="-created_at">جدیدترین</option><option value="effective_price">ارزان‌ترین</option><option value="-effective_price">گران‌ترین</option><option value="created_at">قدیمی‌ترین</option></select></label>
      <label className="sf-checkbox"><input type="checkbox" name="in_stock" value="true" defaultChecked={params.get('in_stock') === 'true'} />فقط موجودها</label><button className="sf-button" type="submit">اعمال فیلتر</button><a className="sf-reset" href="/products">حذف فیلترها</a>
    </form>{categories.error && <div className="sf-inline-error" role="alert">فهرست دسته‌بندی‌ها دریافت نشد. <button onClick={categories.retry}>تلاش مجدد</button></div>}</>}
    {params.get('search') && <p className="sf-search-result">نتایج جست‌وجوی «{params.get('search')}»</p>}
    {list.error ? <Failure error={list.error} retry={list.retry} /> : !list.data ? <Skeletons /> : rows.length === 0 ? <div className="sf-message"><Icon name="search" size={36} /><h2>محصولی پیدا نشد</h2><p>جست‌وجو یا فیلترها را تغییر بده.</p><a className="sf-button" href="/products">دیدن همهٔ محصولات</a></div> : <><div className="sf-products">{rows.map(product => <ProductCard key={product.id} product={product} />)}</div>{!home && <nav className="sf-pagination" aria-label="صفحه‌بندی محصولات">{list.data.previous ? <a href={catalogHref(search, { page: page - 1 })}>صفحهٔ قبل</a> : <span aria-disabled="true">صفحهٔ قبل</span>}<b>صفحهٔ {number(page)}</b>{list.data.next ? <a href={catalogHref(search, { page: page + 1 })}>صفحهٔ بعد</a> : <span aria-disabled="true">صفحهٔ بعد</span>}</nav>}</>}
  </section>;
}

function ProductDetail({ id }) {
  const result = useStore(`products/${id}/`);
  if (result.error) return <Failure error={result.error} retry={result.retry} />;
  if (!result.data) return <div className="sf-message" role="status">در حال دریافت محصول…</div>;
  return <ProductContent key={id} product={result.data} />;
}

function ProductContent({ product }) {
  const gallery = (product.images || []).map(image => ({ ...image, image: safeImage(image.image) })).filter(image => image.image).sort((a, b) => Number(b.is_primary) - Number(a.is_primary) || a.sort_order - b.sort_order || a.id - b.id);
  if (!gallery.length && safeImage(product.image)) gallery.push({ id: 'legacy', image: safeImage(product.image) });
  const variants = (product.variants || []).filter(variant => variant.is_active);
  const [selectedId, setSelectedId] = useState(product.default_variant?.id || variants[0]?.id || null);
  const selected = variants.find(variant => variant.id === selectedId);
  const [imageIndex, setImageIndex] = useState(0);
  const price = selected ? selected.price : product.effective_price;
  const available = Boolean(product.is_available && (!selected || (selected.stock > 0 && selected.price > 0)));
  return <>
    <nav className="sf-breadcrumb" aria-label="مسیر صفحه"><a href="/">فروشگاه</a><span>/</span><a href={catalogHref('', { category: product.category?.id })}>{product.category?.name || 'محصولات'}</a><span>/</span><span>{product.name}</span></nav>
    <section className="sf-detail"><div className="sf-gallery"><div className="sf-main-image"><ProductImage key={gallery[imageIndex]?.image} src={gallery[imageIndex]?.image} name={product.name} eager /></div>{gallery.length > 1 && <div className="sf-thumbnails" aria-label="تصاویر محصول">{gallery.map((image, index) => <button className={index === imageIndex ? 'is-active' : ''} aria-label={`تصویر ${number(index + 1)}`} aria-pressed={index === imageIndex} onClick={() => setImageIndex(index)} key={image.id}><ProductImage src={image.image} name={`${product.name}، تصویر ${number(index + 1)}`} /></button>)}</div>}{product.gallery_description && <p className="sf-gallery-caption">{product.gallery_description}</p>}</div>
      <div className="sf-detail-copy"><span className="sf-overline">{product.brand?.name || product.category?.name}</span><h1>{product.name}</h1><p className="sf-detail-intro">{product.short_description}</p><span className={`sf-availability ${available ? '' : 'sf-availability-off'}`}><span />{available ? 'موجود در فروشگاه' : 'این انتخاب فعلاً ناموجود است'}</span>
        {variants.length > 0 && <fieldset className="sf-variants"><legend>رنگ و حافظه را انتخاب کن</legend><div>{variants.map(variant => <button key={variant.id} type="button" className={variant.id === selectedId ? 'is-active' : ''} aria-pressed={variant.id === selectedId} onClick={() => setSelectedId(variant.id)}><b>{[variant.color, variant.storage].filter(Boolean).join(' / ')}</b><span>{variant.stock > 0 && variant.price > 0 ? money(variant.price) : 'ناموجود'}</span></button>)}</div></fieldset>}
        <div className="sf-purchase"><span>قیمت {selected ? 'تنوع انتخاب‌شده' : 'محصول'}</span><strong>{price !== null && price !== undefined ? money(price) : 'ناموجود'}</strong>{selected && <small>کد کالا: <bdi>{selected.sku}</bdi></small>}<button className="sf-button" type="button" disabled><Icon name="bag" size={20} />افزودن به سبد خرید</button><p>امکان خرید آنلاین پس از راه‌اندازی سبد خرید فعال می‌شود.</p></div>
      </div>
    </section>
    <div className="sf-detail-sections"><section><h2>دربارهٔ محصول</h2><p>{product.long_description || product.description || 'توضیحات تکمیلی ثبت نشده است.'}</p></section><section><h2>مشخصات فنی</h2><dl>{product.brand && <div><dt>برند</dt><dd>{product.brand.name}</dd></div>}<div><dt>دسته‌بندی</dt><dd>{product.category?.name || '—'}</dd></div>{(product.attribute_values || []).map(item => <div key={item.id}><dt>{item.attribute}</dt><dd>{item.value}</dd></div>)}</dl></section></div>
  </>;
}

function Footer() {
  return <footer className="sf-footer"><div className="sf-container"><div><a className="sf-footer-brand" href="/">دیجی‌شاپ<span>.</span></a><p>برای انتخابی که به کارِ هر روزت می‌آید.</p></div><nav aria-label="پیوندهای پایین صفحه"><a href="/products">محصولات</a><a href="/account">حساب کاربری</a><a href="/login">ورود / ثبت‌نام</a></nav><small>دیجی‌شاپ · فروشگاه کالای دیجیتال</small></div></footer>;
}

export default function Storefront() {
  const pathname = window.location.pathname.replace(/\/+$/, '') || '/';
  const search = window.location.search;
  const home = pathname === '/';
  
  const detail = pathname.match(/^\/products\/([1-9][0-9]*)$/);
  const found = home || pathname === '/products' || Boolean(detail);
  useEffect(() => {
    document.documentElement.lang = 'fa';
    document.title = home ? 'دیجی‌شاپ | انتخاب هوشمند کالای دیجیتال' : detail ? 'جزئیات محصول | دیجی‌شاپ' : 'محصولات | دیجی‌شاپ';
  }, [home, pathname]);
  return <div className="sf-root" dir="rtl" lang="fa"><a className="sf-skip" href="#sf-main">رفتن به محتوای اصلی</a><Header search={new URLSearchParams(search).get('search') || ''} /><main id="sf-main" className="sf-container">{home && <><Hero /><CategoryStrip /></>}{detail ? <ProductDetail id={detail[1]} /> : found ? <Catalog home={home} search={search} /> : <div className="sf-message"><h1>صفحه پیدا نشد</h1><a className="sf-button" href="/">بازگشت به فروشگاه</a></div>}{home && <div className="sf-bottom-banner"><div><span className="sf-overline">انتخاب خوب، از شناخت شروع می‌شود</span><h2>قبل از انتخاب، جزئیات را ببین.</h2><p>مشخصات فنی، تصاویر و تنوع‌های هر محصول را یک‌جا بررسی کن.</p></div><a href="/products">شروع جست‌وجو<Icon name="arrow" /></a></div>}</main><Footer /></div>;
}
