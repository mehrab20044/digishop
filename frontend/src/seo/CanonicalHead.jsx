import { useEffect, useSyncExternalStore } from "react";

const snapshot = () => window.location.pathname + window.location.search;
const subscribe = (listener) => {
  window.addEventListener("digishop:store-navigation", listener);
  window.addEventListener("popstate", listener);
  return () => {
    window.removeEventListener("digishop:store-navigation", listener);
    window.removeEventListener("popstate", listener);
  };
};
function key(value) {
  try {
    const url = new URL(value, window.location.origin);
    return decodeURIComponent(url.pathname).replace(/\/+$/, "") + url.search;
  } catch {
    return value;
  }
}
export function setCanonicalHead(data) {
  document
    .querySelectorAll('link[rel="canonical"]')
    .forEach((node) => node.remove());
  if (data.canonical) {
    const link = document.createElement("link");
    link.rel = "canonical";
    link.href = data.canonical;
    document.head.append(link);
  }
  document
    .querySelectorAll('meta[name="robots"]')
    .forEach((node) => node.remove());
  if (data.robots) {
    const meta = document.createElement("meta");
    meta.name = "robots";
    meta.content = data.robots;
    document.head.append(meta);
  }
}
export default function CanonicalHead() {
  const location = useSyncExternalStore(subscribe, snapshot, snapshot);
  useEffect(() => {
    const controller = new AbortController();
    let bootstrap;
    try {
      bootstrap = JSON.parse(
        document.getElementById("seo-canonical")?.textContent || "null",
      );
    } catch {}
    if (bootstrap && key(bootstrap.requested) === key(location)) {
      setCanonicalHead(bootstrap);
      return () => controller.abort();
    }
    // Never leave a previous route's canonical behind while a new route is loading.
    setCanonicalHead({});
    fetch(`/api/v1/seo/canonical/?${new URLSearchParams({ url: location })}`, {
      signal: controller.signal,
      credentials: "omit",
      headers: { Accept: "application/json" },
    })
      .then(async (response) => {
        if (response.status === 404)
          return { canonical: null, robots: "noindex, nofollow" };
        if (!response.ok) throw new Error("Canonical metadata unavailable");
        return response.json();
      })
      .then((data) => {
        if (!controller.signal.aborted && snapshot() === location)
          setCanonicalHead(data);
      })
      .catch((error) => {
        if (error.name !== "AbortError")
          console.warn("Canonical metadata could not be refreshed.");
      });
    return () => controller.abort();
  }, [location]);
  return null;
}
