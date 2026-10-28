import { useEffect, useId, useRef, useState } from "react";
import { useCategoryTree } from "./CategoryBrowser";
import "./category-browser.css";

function Branch({ node }) {
  return <div className="sb-menu-branch"><a href={node.url || `/products?category=${node.id}`}>{node.name}</a>{node.children?.length > 0 && <details><summary>زیر‌دسته‌ها</summary><div>{node.children.map(child => <Branch key={child.id} node={child} />)}</div></details>}</div>;
}
export default function CategoryMenu() {
  const { data, error, retry } = useCategoryTree();
  const [open, setOpen] = useState(false); const [activeId, setActiveId] = useState(null);
  const container = useRef(null); const trigger = useRef(null); const id = useId();
  const selected = data?.find(row => row.id === activeId) || data?.[0];
  useEffect(() => {
    if (!open) return undefined;
    function outside(event) { if (!container.current?.contains(event.target)) setOpen(false); }
    function escape(event) { if (event.key === "Escape") { setOpen(false); trigger.current?.focus(); } }
    document.addEventListener("pointerdown", outside); document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape); };
  }, [open]);
  return <div className="sb-menu" ref={container} onBlur={event => { if (event.relatedTarget && !container.current?.contains(event.relatedTarget)) setOpen(false); }}>
    <button className="sb-menu-trigger" ref={trigger} type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen(value => !value)}><span aria-hidden="true">☰</span> دسته‌بندی کالاها <span aria-hidden="true">⌄</span></button>
    {open && <section id={id} className="sb-menu-panel" aria-label="دسته‌بندی کالاها"><div className="sb-menu-title"><strong>دسته‌بندی کالاها</strong><button type="button" aria-label="بستن دسته‌بندی‌ها" onClick={() => { setOpen(false); trigger.current?.focus(); }}>×</button></div>
      {error ? <div className="sb-menu-message" role="alert"><p>{error}</p><button type="button" onClick={retry}>تلاش دوباره</button></div> : data === null ? <p className="sb-menu-message" role="status">در حال دریافت دسته‌ها…</p> : !data.length ? <p className="sb-menu-message">دسته‌ای ثبت نشده است.</p> : <div className="sb-menu-layout"><div className="sb-menu-roots">{data.map(root => <button key={root.id} type="button" className={selected?.id === root.id ? "is-active" : ""} aria-pressed={selected?.id === root.id} onClick={() => setActiveId(root.id)}>{root.name}<span aria-hidden="true">‹</span></button>)}</div>
      {selected && <div className="sb-menu-content"><a className="sb-menu-all" href={selected.url || `/products?category=${selected.id}`}>همهٔ محصولات {selected.name} ←</a><div className="sb-menu-columns">{(selected.children || []).map(child => <section className="sb-menu-group" key={child.id}><h3><a href={child.url || `/products?category=${child.id}`}>{child.name} ‹</a></h3>{(child.children || []).map(node => <Branch key={node.id} node={node} />)}</section>)}</div>{!selected.children?.length && <p className="sb-menu-message">برای دیدن کالاها، «همهٔ محصولات» را انتخاب کنید.</p>}</div>}
      </div>}
    </section>}
  </div>;
}
