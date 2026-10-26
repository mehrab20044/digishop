import { createContext, useContext, useEffect, useRef, useState } from 'react';
import { addToCart, loadCart, removeCartItem, updateCartItem } from './cart-api';
import './cart.css';

const CartContext = createContext(null);

export function CartProvider({ children }) {
  const [cart, setCart] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const lock = useRef(false);
  const mounted = useRef(false);

  useEffect(() => {
    let active = true;
    mounted.current = true;
    function onExpired(event) {
      if (event.detail?.storageKey === 'digishop.customer.session') {
        setCart(null);
        setLoading(false);
        setError('نشست مشتری پایان یافته است. برای دیدن سبد حساب دوباره وارد شو، یا سبد مهمان را بررسی کن.');
      }
    }
    window.addEventListener('auth-expired', onExpired);
    loadCart().then(data => {
      if (active) { setCart(data); setError(''); }
    }).catch(error => { if (active) setError(error.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; mounted.current = false; window.removeEventListener('auth-expired', onExpired); };
  }, []);

  async function perform(action) {
    if (lock.current) return false;
    lock.current = true;
    setBusy(true);
    setError('');
    try {
      const data = await action();
      if (mounted.current) setCart(data);
      return true;
    } catch (error) {
      if (mounted.current) setError(error.message);
      return false;
    } finally {
      lock.current = false;
      if (mounted.current) { setBusy(false); setLoading(false); }
    }
  }

  return <CartContext.Provider value={{ cart, error, busy, loading,
    retry: () => perform(loadCart),
    add: data => perform(() => addToCart(data)),
    update: (id, quantity) => perform(() => updateCartItem(id, quantity)),
    remove: id => perform(() => removeCartItem(id)),
  }}>{cart?.notices?.length > 0 && <div className="sf-merge-notices" dir="rtl" role="status">{cart.notices.map((notice, index) => <p key={index}>{notice}</p>)}<a href="/cart">بررسی سبد خرید</a></div>}{children}</CartContext.Provider>;
}

export function useCart() {
  const value = useContext(CartContext);
  if (!value) throw new Error('Cart components must be inside CartProvider.');
  return value;
}

export function CartBadge() {
  const { cart, error, loading } = useCart();
  return <a className="sf-cart-link" href="/cart" aria-label={cart ? `سبد خرید؛ ${cart.item_count} کالا` : 'سبد خرید'}><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M5 7h14l1 14H4L5 7Z" /><path d="M8 8V6a4 4 0 0 1 8 0v2" /></svg><span>سبد خرید</span><b>{loading || (!cart && error) ? '…' : new Intl.NumberFormat('fa-IR').format(cart?.item_count || 0)}</b></a>;
}
