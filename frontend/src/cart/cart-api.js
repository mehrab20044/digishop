import { customerFetch, hasSession } from '../customerAuth';

const BASE = '/api/v1/cart/';
const GUEST_KEY = 'digishop.cart.guest.v1';
let queue = Promise.resolve();
let booting = null;

function queued(task) {
  const pending = queue.then(task, task);
  queue = pending.catch(() => {});
  return pending;
}

function token(create = false) {
  try {
    let value = localStorage.getItem(GUEST_KEY);
    if (value && !/^[0-9a-f]{64}$/.test(value)) {
      localStorage.removeItem(GUEST_KEY);
      value = null;
    }
    if (!value && create) {
      value = Array.from(crypto.getRandomValues(new Uint8Array(32)), byte => byte.toString(16).padStart(2, '0')).join('');
      localStorage.setItem(GUEST_KEY, value);
    }
    return value;
  } catch {
    throw new Error('ذخیره‌سازی مرورگر در دسترس نیست؛ برای حفظ سبد خرید آن را فعال کن.');
  }
}

function strings(value) {
  if (typeof value === 'string') return [value];
  if (Array.isArray(value)) return value.flatMap(strings);
  return value && typeof value === 'object' ? Object.values(value).flatMap(strings) : [];
}

async function wire(path = '', method = 'GET', body) {
  const authenticated = hasSession();
  const guest = token(!authenticated);
  const headers = { Accept: 'application/json' };
  if (guest) headers['X-Cart-Token'] = guest;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20000);
  try {
    const options = { method, headers, credentials: 'omit', cache: 'no-store', signal: controller.signal, ...(body !== undefined ? { body: JSON.stringify(body) } : {}) };
    const response = authenticated ? await customerFetch(BASE + path, options) : await fetch(BASE + path, options);
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const error = new Error(strings(data?.error?.details).join('، ') || data?.error?.message || strings(data).join('، ') || `خطای سبد خرید (${response.status})`);
      error.status = response.status;
      throw error;
    }
    if (!Array.isArray(data?.items)) throw new Error('پاسخ سبد خرید معتبر نیست. تنظیمات API را بررسی کن.');
    return data;
  } catch (error) {
    if (error.status) throw error;
    if (controller.signal.aborted) throw new Error('پاسخ سرور طول کشید؛ پیش از تکرار افزودن، سبد را بررسی کن.');
    if (error instanceof TypeError) throw new Error('ارتباط با سرور برقرار نشد. سبد قبلی حفظ شده؛ دوباره تلاش کن.');
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export function loadCart() {
  if (booting) return booting;
  booting = queued(async () => {
    if (hasSession() && token()) {
      const result = await wire('merge/', 'POST', {});
      localStorage.removeItem(GUEST_KEY);
      return result;
    }
    return wire();
  }).finally(() => { booting = null; });
  return booting;
}

export const addToCart = data => queued(() => wire('items/', 'POST', data));
export const updateCartItem = (id, quantity) => queued(() => wire(`items/${id}/`, 'PATCH', { quantity }));
export const removeCartItem = id => queued(() => wire(`items/${id}/`, 'DELETE'));

export function newCartRequestId() {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
