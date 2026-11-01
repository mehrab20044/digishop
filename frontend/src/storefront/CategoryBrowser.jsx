import { CategoryPicture } from "./CategoryDirectory";
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
  const categories = flattenCategoryTree(data || [])
    .filter((category) => category.is_home_featured === true)
    .sort((a, b) => a.home_featured_order - b.home_featured_order || a.id - b.id)
    .slice(0, 5);

  return (
    <section className="category-circles" aria-label="خرید بر اساس دسته‌بندی">
      <div className="category-circles-list">
        {categories.map((category) => (
          <a className="category-circle" key={category.id} href={categoryLink("", category)}>
            <CategoryPicture category={category} />
            <span className="category-circle-name">{category.name}</span>
          </a>
        ))}
      </div>
<a className="category-circles-more" href="/categories">
  <span>مشاهدهٔ همهٔ دسته‌بندی‌ها</span>

  <span className="category-more-icon" aria-hidden="true">
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M19 12H5m6-6-6 6 6 6" />
    </svg>
  </span>
</a>
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
          دسته‌های انتخاب‌شده: {selected.map((row) => row.name).join("، ")}
        </p>
      )}

      {current.children?.length > 0 && (
        <div className="dg-child-links" aria-label="زیرشاخه‌ها">
          {current.children.map((child) => (
            <a key={child.id} href={categoryLink(search, child)}>
              <CategoryPicture category={child} />
              {child.name}
              <span aria-hidden="true">‹</span>
            </a>
          ))}
        </div>
      )}
    </section>
  );
}
