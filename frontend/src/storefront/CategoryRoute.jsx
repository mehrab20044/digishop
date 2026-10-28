import { useEffect, useState } from "react";

export default function CategoryRoute({ renderCatalog }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const path = decodeURIComponent(window.location.pathname.slice("/products/category/".length)).replace(/\/+$/, "");
    fetch(`/products/api/v1/category-resolve/?${new URLSearchParams({ path })}`, { signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error(response.status === 404 ? "دسته‌بندی پیدا نشد." : "دریافت دسته‌بندی ممکن نشد.");
        const data = await response.json();
        if (!active) return;
        document.title = `${data.name} | دیجی‌شاپ`;
        let canonical = document.querySelector('link[rel="canonical"]');
        if (!canonical) { canonical = document.createElement("link"); canonical.rel = "canonical"; document.head.append(canonical); }
        canonical.href = new URL(data.url, window.location.origin).href;
        const params = new URLSearchParams(window.location.search);
        params.delete("categories"); params.set("category", data.id);
        setResult(params.toString()); setError("");
      }).catch(err => { if (active && err.name !== "AbortError") setError(err.message); });
    return () => { active = false; controller.abort(); };
  }, [attempt]);
  if (error) return <div className="sf-message" role="alert"><p>{error}</p><button onClick={() => setAttempt(value => value + 1)}>تلاش دوباره</button><a href="/products">همهٔ محصولات</a></div>;
  if (result === null) return <div className="sf-message" role="status">در حال دریافت دسته‌بندی…</div>;
  return renderCatalog(result);
}
