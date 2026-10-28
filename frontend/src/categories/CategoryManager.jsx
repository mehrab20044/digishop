import { useEffect, useRef, useState } from "react";
import { managementFetch } from "../managementAuth";
import "./categories.css";

const BASE = "/api/v1/owner/categories/";
const SLUG = /^[\p{L}\p{N}]+(?:-[\p{L}\p{N}]+)*$/u;
function messages(value) {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(messages);
  return value && typeof value === "object" ? Object.values(value).flatMap(messages) : [];
}
async function read(response) {
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(messages(data?.error?.details).join("، ") || data?.error?.message || messages(data).join("، ") || `خطای ${response.status}`);
  if (data === null) throw new Error("پاسخ سرور معتبر نیست.");
  return data;
}
async function loadAll(signal) {
  const result = [];
  for (let page = 1; ; page += 1) {
    const data = await read(await managementFetch(`${BASE}?page=${page}`, { signal }));
    if (!Array.isArray(data.results)) throw new Error("فهرست دسته‌ها معتبر نیست.");
    result.push(...data.results);
    if (!data.next) return result;
  }
}
function treeData(rows) {
  const nodes = new Map(rows.map(row => [row.id, { ...row, children: [] }]));
  const roots = [];
  for (const node of nodes.values()) {
    if (node.parent_id == null) roots.push(node);
    else {
      const parent = nodes.get(node.parent_id);
      if (!parent) throw new Error("ساختار دسته‌ها ناقص است؛ والد یکی از دسته‌ها پیدا نشد.");
      parent.children.push(node);
    }
  }
  const visited = new Set();
  function walk(node, path) {
    if (path.has(node.id)) throw new Error("ساختار دسته‌ها دارای چرخه است.");
    visited.add(node.id);
    const next = new Set(path); next.add(node.id);
    node.children.sort(compare);
    for (const child of node.children) walk(child, next);
  }
  for (const root of roots) walk(root, new Set());
  if (visited.size !== nodes.size) throw new Error("ساختار دسته‌ها دارای چرخه است.");
  return roots.sort(compare);
}
function compare(a, b) { return (a.sort_order || 0) - (b.sort_order || 0) || a.name.localeCompare(b.name, "fa") || a.id - b.id; }
function pathFor(row, rows) {
  const byId = new Map(rows.map(item => [item.id, item]));
  const names = []; const visited = new Set(); let current = row;
  while (current && !visited.has(current.id)) { visited.add(current.id); names.unshift(current.name); current = byId.get(current.parent_id); }
  return names.join(" / ");
}
function blockedIds(rows, id) {
  const ids = new Set(id ? [id] : []); let changed = true;
  while (changed) { changed = false; for (const row of rows) if (ids.has(row.parent_id) && !ids.has(row.id)) { ids.add(row.id); changed = true; } }
  return ids;
}
function hasMatch(node, query) { return !query || node.name.toLocaleLowerCase().includes(query) || node.children.some(child => hasMatch(child, query)); }
function CategoryNode({ node, query, onAdd, onEdit, canAdd, canEdit }) {
  const [expanded, setExpanded] = useState(false);
  if (!hasMatch(node, query)) return null;
  const showChildren = Boolean(query) || expanded;
  return <li className="dc-node">
    <div className="dc-row">
      <button type="button" className="dc-expand" disabled={!node.children.length} aria-label={`${showChildren ? "بستن" : "نمایش"} زیر‌دسته‌های ${node.name}`} aria-expanded={node.children.length ? showChildren : undefined} onClick={() => setExpanded(value => !value)}>{node.children.length ? (showChildren ? "−" : "+") : "·"}</button>
      <div className="dc-node-label"><strong>{node.name}</strong><small>{node.children.length ? `${node.children.length.toLocaleString("fa-IR")} زیر‌دسته` : "بدون زیر‌دسته"}</small></div>
      <div className="dc-row-actions">{canAdd && <button type="button" className="dc-link" onClick={() => onAdd(node)}>+ افزودن زیر‌دسته</button>}{canEdit && <button type="button" className="dc-link dc-muted" onClick={() => onEdit(node)}>ویرایش</button>}</div>
    </div>
    {showChildren && node.children.length > 0 && <ul className="dc-children">{node.children.map(child => <CategoryNode key={child.id} node={child} query={query} onAdd={onAdd} onEdit={onEdit} canAdd={canAdd} canEdit={canEdit} />)}</ul>}
  </li>;
}
function CategoryForm({ editor, rows, onCancel, onSaved }) {
  const editing = Boolean(editor.record);
  const [name, setName] = useState(editor.record?.name || "");
  const [slug, setSlug] = useState(editor.record?.slug || "");
  const [parentId, setParentId] = useState(String(editor.record?.parent_id ?? editor.parent?.id ?? ""));
  const [description, setDescription] = useState(editor.record?.description || "");
  const [sortOrder, setSortOrder] = useState(editor.record?.sort_order ?? 0);
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const lock = useRef(false); const heading = useRef(null);
  useEffect(() => { heading.current?.focus(); }, []);
  const blocked = blockedIds(rows, editor.record?.id);
  const parent = rows.find(row => String(row.id) === parentId);
  async function submit(event) {
    event.preventDefault(); if (lock.current) return;
    if (!name.trim()) { setError("نام دسته را بنویسید."); return; }
    if (slug.trim() && !SLUG.test(slug.trim())) { setError("نامک فقط حرف، عدد و خط تیره می‌پذیرد؛ بین کلمات خط تیره بگذارید."); return; }
    const order = Number(sortOrder);
    if (!Number.isSafeInteger(order) || order < 0) { setError("ترتیب نمایش باید عدد صحیح نامنفی باشد."); return; }
    lock.current = true; setBusy(true); setError("");
    try {
      const csrf = await read(await managementFetch("/api/v1/owner/csrf/"));
      const saved = await read(await managementFetch(editing ? `${BASE}${editor.record.id}/edit/` : `${BASE}create/`, {
        method: editing ? "PATCH" : "POST", headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrf.csrfToken },
        body: JSON.stringify({ name: name.trim(), ...(slug.trim() ? { slug: slug.trim() } : editing ? { slug: editor.record.slug } : {}), parent_id: parentId ? Number(parentId) : null, description, sort_order: order }),
      }));
      onSaved(saved);
    } catch (err) { setError(`${err.message} اگر پاسخ ارتباط نامشخص بود، قبل از تلاش مجدد وجود دسته را بررسی کنید.`); }
    finally { lock.current = false; setBusy(false); }
  }
  return <section className="dc-form-box" aria-labelledby="dc-form-title">
    <div className="dc-form-heading"><div><h3 id="dc-form-title" ref={heading} tabIndex={-1}>{editing ? "ویرایش دسته" : parent ? `افزودن زیر‌دسته به «${parent.name}»` : "افزودن دستهٔ اصلی"}</h3><p>{parent ? pathFor(parent, rows) : "این دسته در سطح اصلی منو قرار می‌گیرد."}</p></div><button className="dc-link" type="button" disabled={busy} onClick={onCancel}>بستن</button></div>
    {error && <p className="dc-error" role="alert">{error}</p>}
    <form onSubmit={submit}><fieldset disabled={busy}>
      <label className="dc-field"><span>نام دسته</span><input autoComplete="off" value={name} maxLength={100} required placeholder={parent ? "مثلاً ایسوس یا گیمینگ" : "مثلاً لپ‌تاپ"} onChange={event => setName(event.target.value)} /></label>
      <details className="dc-advanced"><summary>تنظیمات بیشتر، اختیاری</summary><div className="dc-advanced-fields">
        <label className="dc-field"><span>دستهٔ بالاتر</span><select value={parentId} onChange={event => setParentId(event.target.value)}><option value="">بدون والد؛ دستهٔ اصلی</option>{rows.filter(row => !blocked.has(row.id)).map(row => <option key={row.id} value={row.id}>{pathFor(row, rows)}</option>)}</select></label>
        <label className="dc-field"><span>نامک آدرس</span><input dir="ltr" value={slug} maxLength={120} title="حروف فارسی یا انگلیسی، عدد و خط تیره" placeholder="asus-gaming" spellCheck={false} autoCapitalize="none" onChange={event => setSlug(event.target.value)} /><small>خالی باشد، سایت از نام دسته نامک می‌سازد. تغییر نام نمایشی، آدرس را عوض نمی‌کند. تغییر نامک یا والد، لینک قبلی را به آدرس جدید هدایت می‌کند.</small></label>
        <label className="dc-field"><span>توضیح</span><textarea rows={3} value={description} onChange={event => setDescription(event.target.value)} /></label>
        <label className="dc-field"><span>ترتیب نمایش</span><input type="number" min="0" step="1" value={sortOrder} onChange={event => setSortOrder(event.target.value)} /></label>
      </div></details>
      <div className="dc-form-actions"><button type="submit" className="button primary">{busy ? "در حال ذخیره…" : editing ? "ذخیرهٔ تغییرات" : "ساخت دسته"}</button><button type="button" className="button ghost" onClick={onCancel}>انصراف</button></div>
    </fieldset></form>
  </section>;
}
export default function CategoryManager({ resource, revision }) {
  const [rows, setRows] = useState([]); const [loading, setLoading] = useState(true); const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0); const [search, setSearch] = useState(""); const [editor, setEditor] = useState(null); const [opening, setOpening] = useState(false); const [notice, setNotice] = useState("");
  const mounted = useRef(false); const openingLock = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    const controller = new AbortController(); let active = true; setLoading(true); setError("");
    loadAll(controller.signal).then(data => { treeData(data); if (active) setRows(data); }).catch(err => { if (active && err.name !== "AbortError") setError(err.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [revision, attempt]);
  async function edit(row) {
    if (openingLock.current) return; openingLock.current = true; setOpening(true); setError("");
    try { const data = await read(await managementFetch(`${BASE}${row.id}/`)); if (mounted.current) setEditor({ record: data }); }
    catch (err) { if (mounted.current) setError(err.message); }
    finally { openingLock.current = false; if (mounted.current) setOpening(false); }
  }
  const roots = treeData(rows); const query = search.trim().toLocaleLowerCase();
  return <section className="card dc-manager" dir="rtl">
    <div className="dc-heading"><div><h2>دسته‌بندی کالاها</h2><p>کنار هر دسته، «افزودن زیر‌دسته» را بزنید؛ دستهٔ بالاتر خودکار مشخص می‌شود.</p></div>{resource.capabilities?.add && !editor && <button className="button primary" type="button" disabled={opening || loading} onClick={() => { setNotice(""); setEditor({ parent: null }); }}>+ دستهٔ اصلی</button>}</div>
    {notice && <p className="dc-notice" role="status">{notice}</p>}{error && <div className="dc-error" role="alert"><p>{error}</p><button className="dc-link" type="button" onClick={() => setAttempt(value => value + 1)}>دریافت دوباره</button></div>}
    {editor ? <CategoryForm key={editor.record ? `edit-${editor.record.id}` : `new-${editor.parent?.id || 0}`} editor={editor} rows={rows} onCancel={() => setEditor(null)} onSaved={saved => { setRows(previous => previous.some(row => row.id === saved.id) ? previous.map(row => row.id === saved.id ? saved : row) : [...previous, saved]); setEditor(null); setSearch(saved.name); setNotice(`«${saved.name}» ذخیره شد. برای دیدن همهٔ دسته‌ها، جست‌وجو را پاک کنید.`); }} /> : <>
      <label className="dc-search"><span className="dc-sr-only">جست‌وجوی دسته‌ها</span><input type="search" placeholder="پیداکردن دسته…" value={search} onChange={event => setSearch(event.target.value)} /></label>
      {loading ? <p role="status" className="dc-empty">در حال دریافت دسته‌ها…</p> : <ul className="dc-tree">{roots.map(root => <CategoryNode key={root.id} node={root} query={query} canAdd={Boolean(resource.capabilities?.add) && !opening} canEdit={Boolean(resource.capabilities?.change) && !opening} onAdd={parent => { setNotice(""); setEditor({ parent }); }} onEdit={edit} />)}</ul>}
      {!loading && !roots.some(root => hasMatch(root, query)) && <p className="dc-empty">{rows.length ? "دسته‌ای با این نام پیدا نشد." : "از «دستهٔ اصلی» شروع کنید؛ مثلاً لپ‌تاپ."}</p>}
      {opening && <p role="status">در حال دریافت دسته…</p>}
    </>}
  </section>;
}
