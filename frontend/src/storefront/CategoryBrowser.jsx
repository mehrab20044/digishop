import { useEffect, useState } from "react";
import { catalogHref, getStore } from "./store-api";
import "./category-browser.css";

export function useCategoryTree() {
  const [data, setData] = useState(null); const [error, setError] = useState(""); const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController(); let active = true; let timeout = false;
    const timer = setTimeout(() => { timeout = true; controller.abort(); }, 15000);
    setError("");
    getStore("categories/tree/", controller.signal).then(result => {
      if (!Array.isArray(result)) throw new Error("ساختار دسته‌بندی‌ها معتبر نیست.");
      if (active) setData(result);
    }).catch(err => { if (active) setError(timeout ? "دریافت دسته‌بندی‌ها طول کشید." : err.message); }).finally(() => clearTimeout(timer));
    return () => { active = false; clearTimeout(timer); controller.abort(); };
  }, [attempt]);
  return { data, error, retry: () => setAttempt(value => value + 1) };
}
export function flattenCategoryTree(roots) {
  const rows = []; const seen = new Set();
  function walk(node, ancestors) {
    if (seen.has(node.id)) return;
    seen.add(node.id);
    const path = [...ancestors, { id: node.id, name: node.name, url: node.url }];
    rows.push({ ...node, path });
    for (const child of node.children || []) walk(child, path);
  }
  for (const root of roots || []) walk(root, []);
  return rows;
}
function href(search, category) {
  if (!category?.url) return catalogHref(search, { category: category?.id || null, categories: null, page: null });
  const params = new URLSearchParams(search);
  for (const key of ["category", "categories", "page"]) params.delete(key);
  return category.url + (params.size ? `?${params}` : "");
}
export function HomeCategoryStrip() {
  const { data, error, retry } = useCategoryTree();
  return <section className="sf-category-section" aria-label="دسته‌بندی کالاها"><div className="sf-section-title"><div><span className="sf-overline">از دستهٔ دلخواهت شروع کن</span><h2>دسته‌بندی کالاها</h2></div><a href="/products">همهٔ محصولات ←</a></div>
    {error ? <div className="sf-inline-error" role="alert">{error} <button type="button" onClick={retry}>تلاش دوباره</button></div> : data === null ? <p role="status">در حال دریافت دسته‌ها…</p> : <div className="sb-home-categories">{data.map(category => <a key={category.id} href={href("", category)}><span className="sb-category-symbol" aria-hidden="true">▦</span><strong>{category.name}</strong><small>{category.children?.length ? "مشاهدهٔ زیر‌دسته‌ها" : "مشاهدهٔ محصولات"}</small></a>)}</div>}
  </section>;
}
export default function CategoryBrowser({ search }) {
  const { data, error, retry } = useCategoryTree();
  const params = new URLSearchParams(search);
  const selectedIds = [...new Set([params.get("category"), ...(params.get("categories") || "").split(",")].filter(value => /^[1-9][0-9]*$/.test(value || "")).map(Number))];
  const flat = flattenCategoryTree(data); const byId = new Map(flat.map(row => [row.id, row]));
  const selected = selectedIds.map(id => byId.get(id)).filter(Boolean);
  const current = selected[selected.length - 1];
  const children = current ? current.children || [] : data || [];
  function remove(id) {
    const remaining = selectedIds.filter(value => value !== id);
    return catalogHref(search, { category: remaining.length === 1 ? remaining[0] : null, categories: remaining.length > 1 ? remaining.join(",") : null, page: null });
  }
  if (error) return <div className="sf-inline-error" role="alert">{error} <button type="button" onClick={retry}>تلاش دوباره</button></div>;
  if (data === null) return <p role="status" className="sb-loading">در حال دریافت دسته‌ها…</p>;
  return <section className="sb-browser" aria-label="مرور دسته‌بندی‌ها">
    {current && <nav className="sb-breadcrumb" aria-label="مسیر دسته‌بندی"><a href={href(search, null)}>همهٔ دسته‌ها</a>{current.path.map((part, index) => <span key={part.id}><span aria-hidden="true"> / </span>{index === current.path.length - 1 ? <strong>{part.name}</strong> : <a href={href(search, part)}>{part.name}</a>}</span>)}</nav>}
    {selected.length > 1 && <div className="sb-selected">{selected.map(category => <a key={category.id} href={remove(category.id)} aria-label={`حذف فیلتر ${category.name}`}>{category.name} ×</a>)}</div>}
    {children.length > 0 && <><div className="sb-browser-heading"><h2>{current ? `انتخاب از ${current.name}` : "کدام دسته را می‌خواهی؟"}</h2><span>محصولات همهٔ این زیر‌دسته‌ها پایین صفحه نمایش داده می‌شوند.</span></div><div className="sb-category-cards">{children.map(child => <a key={child.id} href={href(search, child)}><strong>{child.name}</strong><span>{child.children?.length ? "ادامهٔ انتخاب" : "مشاهدهٔ کالاها"} ←</span></a>)}</div></>}
    {current && !children.length && <p className="sb-leaf-label">محصولات «{current.name}»</p>}
  </section>;
}
