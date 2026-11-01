import { useState } from "react";
import {
  categoryLink,
  useCategoryTree,
  normalizeCategory,
} from "./category-data";
import { safeImage } from "./store-api";
import "./category-directory.css";

export function CategoryPicture({ category, eager = false }) {
  const [failed, setFailed] = useState("");
  const src = safeImage(category.image_url);
  return (
    <span className="cat-picture" aria-hidden="true">
      {src && failed !== src ? (
        <img
          src={src}
          alt=""
          loading={eager ? "eager" : "lazy"}
          decoding="async"
          onError={() => setFailed(src)}
        />
      ) : (
        <svg
          width="28"
          height="28"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <rect x="3" y="3" width="7" height="7" rx="2" />
          <rect x="14" y="3" width="7" height="7" rx="2" />
          <rect x="3" y="14" width="7" height="7" rx="2" />
          <rect x="14" y="14" width="7" height="7" rx="2" />
        </svg>
      )}
    </span>
  );
}
function matches(node, query) {
  return (
    !query ||
    normalizeCategory(node.name).includes(query) ||
    (node.children || []).some((child) => matches(child, query))
  );
}
function Branch({ node, depth = 0, query }) {
  const [expanded, setExpanded] = useState(depth === 0);
  if (!matches(node, query)) return null;
  const children = node.children || [];
  const show = Boolean(query) || expanded;
  return (
    <li className={`cat-branch cat-depth-${Math.min(depth, 2)}`}>
      <div className="cat-branch-head">
        <a href={categoryLink("", node)} className="cat-node-link">
          <CategoryPicture category={node} />
          <span>
            <strong>{node.name}</strong>
            <small>
              {children.length
                ? `${children.length.toLocaleString("fa-IR")} زیر‌دسته`
                : "دیدن محصولات"}
            </small>
          </span>
        </a>
        {children.length > 0 && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={show}
            aria-label={`${show ? "بستن" : "نمایش"} زیر‌دسته‌های ${node.name}`}
            disabled={Boolean(query)}
          >
            {show ? "−" : "+"}
          </button>
        )}
      </div>
      {show && children.length > 0 && (
        <ul className="cat-children">
          {children.map((child) => (
            <Branch
              key={child.id}
              node={child}
              depth={depth + 1}
              query={query}
            />
          ))}
        </ul>
      )}
    </li>
  );
}
export default function CategoryDirectory() {
  const { data, error, loading, retry } = useCategoryTree();
  const [search, setSearch] = useState("");
  const query = normalizeCategory(search.trim());
  const roots = (data || []).filter((node) => matches(node, query));
  return (
    <section className="cat-directory" aria-labelledby="cat-directory-title">
      <nav className="sf-breadcrumb" aria-label="مسیر صفحه">
        <a href="/">فروشگاه</a>
        <span>/</span>
        <span>همهٔ دسته‌بندی‌ها</span>
      </nav>
      <div className="cat-directory-heading">
        <div>
          <span className="sf-overline">از دستهٔ اصلی تا انتخاب دقیق‌تر</span>
          <h1 id="cat-directory-title">همهٔ دسته‌بندی‌ها</h1>
          <p>
            برای دیدن محصولات، نام دسته را بزنید؛ برای بازکردن زیرشاخه‌ها، دکمهٔ
            + را انتخاب کنید.
          </p>
        </div>
        <label>
          <span>پیداکردن دسته</span>
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="مثلاً لپ‌تاپ یا گیمینگ…"
          />
        </label>
      </div>
      {loading && !data && (
        <p role="status" className="sf-message">
          در حال دریافت دسته‌بندی‌ها…
        </p>
      )}
      {error && (
        <div className="sf-message" role="alert">
          <p>{error}</p>
          <button type="button" className="sf-button" onClick={retry}>
            تلاش دوباره
          </button>
        </div>
      )}
      {data && !roots.length && (
        <div className="sf-message">
          <h2>{query ? "دسته‌ای پیدا نشد" : "هنوز دسته‌ای ثبت نشده است"}</h2>
          {query && (
            <button
              type="button"
              className="sf-button"
              onClick={() => setSearch("")}
            >
              پاک‌کردن جست‌وجو
            </button>
          )}
        </div>
      )}
      {roots.length > 0 && (
        <ul className="cat-directory-grid">
          {roots.map((node) => (
            <Branch key={node.id} node={node} query={query} />
          ))}
        </ul>
      )}
    </section>
  );
}
