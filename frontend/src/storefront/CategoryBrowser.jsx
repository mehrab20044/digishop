import {
  categoryLink,
  flattenCategoryTree,
  useCategoryTree,
} from "./category-data";

import "./category-dropdown.css";

export {
  categoryLink,
  flattenCategoryTree,
  normalizeCategory,
  useCategoryTree,
} from "./category-data";

export function HomeCategoryStrip() {
  const { data } = useCategoryTree();

  if (!data?.length) return null;

  return (
    <section className="dg-home-categories" aria-label="دسته‌بندی کالاها">
      <div className="dg-home-title">
        <h2>خرید بر اساس دسته‌بندی</h2>
        <a href="/products">همهٔ کالاها ←</a>
      </div>

      <div className="dg-home-list">
        {data.map((category) => (
          <a href={categoryLink("", category)} key={category.id}>
            <span className="sf-category-mark" aria-hidden="true"><svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><path d="M14 17.5h7m-3.5-3.5v7"/></svg></span>
            <strong>{category.name}</strong>
            <small>{category.children?.length ? category.children.slice(0, 2).map(child => child.name).join(" · ") : "دیدن محصولات"}</small>
            <i aria-hidden="true">↖</i>
          </a>
        ))}
      </div>
    </section>
  );
}

export default function CategoryBrowser({ search }) {
  const { data } = useCategoryTree();
  const params = new URLSearchParams(search);

  const ids = [
    ...new Set(
      [
        params.get("category"),
        ...(params.get("categories") || "").split(","),
      ].filter((id) => /^[1-9][0-9]*$/.test(id || "")),
    ),
  ];

  const flat = flattenCategoryTree(data);
  const selected = ids
    .map((id) => flat.find((row) => String(row.id) === id))
    .filter(Boolean);

  const current = selected.at(-1);

  if (!current) return null;

  return (
    <section className="dg-category-context" aria-label="مسیر دسته‌بندی">
      <nav className="dg-breadcrumb" aria-label="مسیر فعلی">
        <a href="/">فروشگاه</a>
        <span aria-hidden="true">/</span>
        <a href="/products">همهٔ کالاها</a>

        {current.path.map((part, index) => (
          <span className="dg-breadcrumb-part" key={part.id}>
            <span aria-hidden="true">/</span>

            {index === current.path.length - 1 ? (
              <strong aria-current="page">{part.name}</strong>
            ) : (
              <a href={categoryLink(search, part)}>{part.name}</a>
            )}
          </span>
        ))}
      </nav>

      {selected.length > 1 && (
        <p className="dg-context-note">
          دسته‌های انتخاب‌شده:{" "}
          {selected.map((row) => row.name).join("، ")}
        </p>
      )}

      {current.children?.length > 0 && (
        <div className="dg-child-links" aria-label="زیرشاخه‌ها">
          {current.children.map((child) => (
            <a key={child.id} href={categoryLink(search, child)}>
              {child.name}
              <span aria-hidden="true">‹</span>
            </a>
          ))}
        </div>
      )}
    </section>
  );
}