import { useEffect, useState } from "react";

import { API_BASE } from "./store-api";
import {
  flattenCategoryTree,
  readCategoryTree,
} from "./category-data";

function pathKey(value) {
  try {
    return decodeURIComponent(
      new URL(value, window.location.origin).pathname,
    ).replace(/\/+$/, "");
  } catch {
    return null;
  }
}

function knownCategory(pathname) {
  const wanted = pathKey(pathname);

  return flattenCategoryTree(readCategoryTree()).find(
    (row) => row.url && pathKey(row.url) === wanted,
  );
}

function CatalogPlaceholder() {
  return (
    <div
      className="dg-route-loading"
      role="status"
      aria-label="در حال دریافت محصولات"
    >
      <div className="dg-route-placeholder" />

      <div className="sf-products" aria-hidden="true">
        {[1, 2, 3, 4].map((id) => (
          <div className="sf-skeleton" key={id}>
            <span />
            <i />
            <i />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function CategoryRoute({
  pathname,
  search,
  renderCatalog,
}) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);

  const known = knownCategory(pathname);
  const resolved = result?.pathname === pathname ? result.data : null;
  const category = known || resolved;

  useEffect(() => {
    setError("");

    if (knownCategory(pathname)) return;

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 12_000);
    let active = true;

    async function resolve() {
      const prefix = "/products/category/";
      const rawPath = pathname.slice(prefix.length);
      const path = decodeURIComponent(rawPath).replace(/\/+$/, "");

      const response = await fetch(
        `${API_BASE}/category-resolve/?${new URLSearchParams({ path })}`,
        {
          signal: controller.signal,
          credentials: "omit",
          headers: { Accept: "application/json" },
        },
      );

      if (!response.ok) {
        throw new Error(
          response.status === 404
            ? "دسته‌بندی پیدا نشد."
            : "دریافت دسته‌بندی انجام نشد.",
        );
      }

      const data = await response.json();

      if (!data?.id || !data?.url) {
        throw new Error("پاسخ دسته‌بندی معتبر نیست.");
      }

      if (active) setResult({ pathname, data });
    }

    resolve()
      .catch((err) => {
        if (!active) return;

        setError(
          err.name === "AbortError"
            ? "دریافت دسته‌بندی طول کشید؛ دوباره تلاش کنید."
            : err.message,
        );
      })
      .finally(() => clearTimeout(timer));

    return () => {
      active = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, [pathname, attempt]);

  useEffect(() => {
    if (!category) return;

    document.title = `${category.name} | دیجی‌شاپ`;

    let canonical = document.querySelector('link[rel="canonical"]');
    const created = !canonical;

    if (!canonical) {
      canonical = document.createElement("link");
      canonical.rel = "canonical";
      document.head.append(canonical);
    }

    const previous = canonical.getAttribute("href");
    canonical.href = new URL(
      category.url,
      window.location.origin,
    ).href;

    return () => {
      if (created) {
        canonical.remove();
      } else if (previous === null) {
        canonical.removeAttribute("href");
      } else {
        canonical.setAttribute("href", previous);
      }
    };
  }, [category?.id, category?.name, category?.url, pathname]);

  if (error && !category) {
    return (
      <div className="sf-message" role="alert">
        <p>{error}</p>
        <button
          type="button"
          className="sf-button"
          onClick={() => {
            setError("");
            setAttempt((value) => value + 1);
          }}
        >
          تلاش دوباره
        </button>
        <a href="/products">همهٔ محصولات</a>
      </div>
    );
  }

  if (!category) return <CatalogPlaceholder />;

  const params = new URLSearchParams(search);
  params.delete("categories");
  params.set("category", String(category.id));

  return (
    <>
      {renderCatalog(params.toString())}

      {category.description && (
        <section className="dg-category-description">
          <h2>دربارهٔ {category.name}</h2>
          <p>{category.description}</p>
        </section>
      )}
    </>
  );
}