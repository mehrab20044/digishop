import { useEffect, useState } from "react";
import { readBootstrap } from "../appearance/StoreTheme";
export default function PageLinks({ override }) {
  const [links, setLinks] = useState(() => readBootstrap()?.links || []);
  useEffect(() => {
    if (override) return undefined;
    const controller = new AbortController();
    fetch("/api/v1/content/pages/", { signal: controller.signal, cache: "no-store" }).then(response => response.ok ? response.json() : { results: [] }).then(data => setLinks(data.results || [])).catch(() => {});
    return () => controller.abort();
  }, [override]);
  const rows = override || links;
  return rows.length ? <section className="sf-page-buttons" aria-label="صفحه‌های فروشگاه"><nav className="sf-container sf-page-buttons-inner">{rows.map(link => <a key={link.url} href={link.url}>{link.title}</a>)}</nav></section> : null;
}
