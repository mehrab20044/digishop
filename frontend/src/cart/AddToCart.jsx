import { useRef, useState } from 'react';
import { useCart } from './CartProvider';
import { newCartRequestId } from './cart-api';

export default function AddToCart({ product, variant, available }) {
  const { add, busy, error } = useCart();
  const [quantity, setQuantity] = useState(1);
  const [added, setAdded] = useState(false);
  const pending = useRef(null);
  const stock = variant ? variant.stock : product.stock;
  const max = Math.min(99, Math.max(0, stock));

  async function submit(event) {
    event.preventDefault();
    if (busy || !available || !Number.isInteger(quantity) || quantity < 1 || quantity > max) return;
    const fingerprint = `${product.id}:${variant?.id || 0}:${quantity}`;
    if (pending.current?.fingerprint !== fingerprint) pending.current = { fingerprint, id: newCartRequestId() };
    setAdded(false);
    const success = await add({ product_id: product.id, variant_id: variant?.id || null, quantity, request_id: pending.current.id });
    if (success) { pending.current = null; setAdded(true); }
  }

  return <div className="sf-add-cart"><form onSubmit={submit}><label>تعداد<input type="number" min="1" max={max || 1} step="1" value={quantity} onChange={event => { setQuantity(Number(event.target.value)); setAdded(false); }} disabled={busy || !available} required aria-label="تعداد برای افزودن به سبد" /></label><button className="sf-button" type="submit" disabled={busy || !available}>{busy ? 'در حال ثبت…' : available ? 'افزودن به سبد خرید' : 'ناموجود'}</button></form>{added && <p className="sf-cart-success" role="status">به سبد اضافه شد. <a href="/cart">مشاهدهٔ سبد خرید ←</a></p>}{error && <p className="sf-cart-error" role="alert">{error}</p>}<p>افزودن به سبد، کالا را رزرو نمی‌کند؛ قیمت و موجودی هنگام ثبت سفارش دوباره بررسی می‌شوند.</p></div>;
}
