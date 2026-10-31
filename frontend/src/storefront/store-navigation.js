import { useEffect, useSyncExternalStore } from "react";

const EVENT = "digishop:store-navigation";

function getSnapshot() {
  return window.location.pathname + window.location.search;
}

function subscribe(listener) {
  window.addEventListener(EVENT, listener);
  window.addEventListener("popstate", listener);

  return () => {
    window.removeEventListener(EVENT, listener);
    window.removeEventListener("popstate", listener);
  };
}

function isCatalogPath(pathname) {
  const path = pathname.replace(/\/+$/, "") || "/";

  return (
    path === "/" ||
    path === "/products" ||
    path.startsWith("/products/category/")
  );
}

export function navigateStore(href) {
  const url = new URL(href, window.location.origin);

  if (
    url.origin !== window.location.origin ||
    !isCatalogPath(url.pathname)
  ) {
    window.location.assign(url.href);
    return;
  }

  if (url.hash) {
    window.location.assign(url.href);
    return;
  }

  const next = url.pathname + url.search;

  if (next === getSnapshot()) return;

  window.history.pushState(null, "", next);
  window.dispatchEvent(new Event(EVENT));

  requestAnimationFrame(() => {
    window.scrollTo({ top: 0, behavior: "instant" });

    const main = document.getElementById("sf-main");

    if (main) {
      main.setAttribute("tabindex", "-1");
      main.focus({ preventScroll: true });
    }
  });
}

export function useStoreLocation() {
  const location = useSyncExternalStore(
    subscribe,
    getSnapshot,
    getSnapshot,
  );

  useEffect(() => {
    function onClick(event) {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey ||
        event.altKey
      ) {
        return;
      }

      const anchor = event.target.closest?.("a[href]");

      if (
        !anchor ||
        !anchor.closest(".sf-root") ||
        anchor.hasAttribute("download") ||
        (anchor.target && anchor.target !== "_self") ||
        anchor.closest('[contenteditable="true"]')
      ) {
        return;
      }

      const url = new URL(anchor.href, window.location.origin);

      if (
        url.origin !== window.location.origin ||
        url.hash ||
        !isCatalogPath(url.pathname)
      ) {
        return;
      }

      event.preventDefault();
      navigateStore(url.href);
    }

    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);

  const queryIndex = location.indexOf("?");

  return {
    pathname:
      (queryIndex < 0
        ? location
        : location.slice(0, queryIndex)
      ).replace(/\/+$/, "") || "/",
    search: queryIndex < 0 ? "" : location.slice(queryIndex),
  };
}