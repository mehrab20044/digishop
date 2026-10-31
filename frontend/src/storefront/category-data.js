import { useEffect, useSyncExternalStore } from "react";
import { API_BASE } from "./store-api";

const MAX_AGE = 60_000;

let snapshot = {
  data: null,
  error: "",
  loading: false,
};

let loadedAt = 0;
let pending = null;

const listeners = new Set();

function emit(next) {
  snapshot = { ...snapshot, ...next };
  listeners.forEach((listener) => listener());
}

function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot() {
  return snapshot;
}

export function readCategoryTree() {
  return snapshot.data;
}

export function loadCategoryTree(force = false) {
  if (pending) return pending;

  if (
    !force &&
    snapshot.data !== null &&
    Date.now() - loadedAt < MAX_AGE
  ) {
    return Promise.resolve(snapshot.data);
  }

  emit({ loading: true, error: "" });

  pending = (async () => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 12_000);

    try {
      const response = await fetch(`${API_BASE}/categories/tree/`, {
        signal: controller.signal,
        credentials: "omit",
        headers: { Accept: "application/json" },
      });

      const data = await response.json().catch(() => null);

      if (!response.ok || !Array.isArray(data)) {
        throw new Error(
          data?.error?.message || "دریافت دسته‌بندی‌ها انجام نشد.",
        );
      }

      loadedAt = Date.now();
      emit({ data, error: "" });

      return data;
    } catch (error) {
      emit({
        error:
          error.name === "AbortError"
            ? "دریافت دسته‌ها طول کشید. دوباره تلاش کنید."
            : error.message,
      });

      throw error;
    } finally {
      clearTimeout(timer);
      pending = null;
      emit({ loading: false });
    }
  })();

  return pending;
}

export function useCategoryTree() {
  const state = useSyncExternalStore(
    subscribe,
    getSnapshot,
    getSnapshot,
  );

  useEffect(() => {
    const refresh = () => {
      if (document.visibilityState !== "hidden") {
        loadCategoryTree().catch(() => {});
      }
    };

    refresh();

    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, []);

  return {
    ...state,
    retry: () => loadCategoryTree(true).catch(() => {}),
  };
}

export function flattenCategoryTree(roots = []) {
  const rows = [];
  const seen = new Set();

  function visit(node, ancestors) {
    if (seen.has(node.id)) return;
    seen.add(node.id);

    const path = [
      ...ancestors,
      { id: node.id, name: node.name, url: node.url },
    ];

    rows.push({ ...node, path });

    for (const child of node.children || []) {
      visit(child, path);
    }
  }

  for (const root of roots || []) visit(root, []);

  return rows;
}

export function categoryLink(search = "", category = null) {
  const params = new URLSearchParams(search);

  params.delete("category");
  params.delete("categories");
  params.delete("page");

  let base = "/products";

  if (category?.url) {
    base = category.url;
  } else if (category?.id) {
    params.set("category", String(category.id));
  }

  return base + (params.size ? `?${params}` : "");
}

export function normalizeCategory(value) {
  return String(value || "")
    .replace(/ي/g, "ی")
    .replace(/ك/g, "ک")
    .replace(/\u200c/g, " ")
    .trim()
    .toLocaleLowerCase();
}