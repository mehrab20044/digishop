export const API_BASE = (import.meta.env?.VITE_STORE_API_BASE || '/products/api/v1').replace(/\/$/, '');
export const PRICE_UNIT = import.meta.env?.VITE_STORE_PRICE_UNIT || 'تومان';

export function number(value) {
  return new Intl.NumberFormat('fa-IR').format(value);
}

export function money(value) {
  if (value === null || value === undefined || value === '') return 'قیمت در دسترس نیست';
  const amount = Number(value);
  return Number.isFinite(amount) ? `${number(amount)} ${PRICE_UNIT}` : 'قیمت در دسترس نیست';
}

export function safeImage(value) {
  if (typeof value !== 'string' || !value) return null;
  try {
    const url = new URL(value, window.location.origin);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}

export function cover(product) {
  return safeImage(product.images?.find(image => image.is_primary)?.image)
    || safeImage(product.images?.[0]?.image) || safeImage(product.image);
}

export function pageNumber(value) {
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
}

export function catalogHref(search, changes = {}) {
  const params = new URLSearchParams(search);
  for (const [key, value] of Object.entries(changes)) {
    if (value === '' || value === null || value === undefined) params.delete(key);
    else params.set(key, String(value));
  }
  const query = params.toString();
  return `/products${query ? `?${query}` : ''}`;
}

export async function getStore(path, signal) {
  const response = await fetch(`${API_BASE}/${path}`, {
    headers: { Accept: 'application/json' },
    credentials: 'omit',
    signal,
  });
  const json = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(response.status === 404 ? 'محصول موردنظر پیدا نشد.'
      : typeof json?.detail === 'string' ? json.detail
      : json?.error?.message || `دریافت اطلاعات ناموفق بود (${response.status}).`);
    error.status = response.status;
    throw error;
  }
  if (json === null) throw new Error('پاسخ API معتبر نیست. تنظیمات پروکسی محصولات را بررسی کن.');
  return json;
}
