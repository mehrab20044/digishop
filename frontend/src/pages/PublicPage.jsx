import { useEffect, useState } from "react";
import { readBootstrap } from "../appearance/StoreTheme";
import PageContent from "./PageContent";
export default function PublicPage({ slug }) {
  const [data, setData] = useState(() => { const initial = readBootstrap(); return initial?.page?.slug === slug ? initial : null; });
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/v1/content/page/${encodeURIComponent(slug)}/`, { signal: controller.signal, cache: "no-store" }).then(async response => { if (!response.ok) throw new Error(response.status === 404 ? "صفحه پیدا نشد." : "دریافت صفحه ممکن نشد."); return response.json(); }).then(value => { setData(value); document.title = `${value.page.seo_title || value.page.title} | دیجی‌شاپ`; }).catch(err => { if (err.name !== "AbortError") setError(err.message); });
    return () => controller.abort();
  }, [slug]);
  if (error) return <div className="sf-message" role="alert">{error}<a href="/">بازگشت به فروشگاه</a></div>;
  if (!data) return <p className="sf-message" role="status">در حال دریافت صفحه…</p>;
  return <PageContent page={data.page} images={data.images} />;
}
