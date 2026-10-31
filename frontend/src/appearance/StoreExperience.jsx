import { useEffect, useRef } from "react";
import "./store-experience.css";

const TARGETS = [
  ".sf-product-card", ".ch-card", ".sf-cart-item", ".sf-cart-summary",
  ".sf-detail-sections > section", ".dg-home-list > a", ".footer-v2-heading",
  ".footer-v2-services > div", ".footer-v2-contact", ".pb-document > section",
].join(",");

export default function StoreExperience() {
  const marker = useRef(null);
  useEffect(() => {
    const root = marker.current?.closest(".sf-root");
    if (!root) return;
    const view = root.ownerDocument.defaultView;
    const reduced = view.matchMedia("(prefers-reduced-motion: reduce)");
    let intersection;
    let mutation;
    let frame;
    function updateScroll() {
      root.toggleAttribute("data-ui-scrolled", view.scrollY > 20);
    }
    function scroll() {
      if (frame) return;
      frame = view.requestAnimationFrame(() => { frame = null; updateScroll(); });
    }
    function finish(event) {
      if (event.animationName === "store-ui-enter") event.target.classList.remove("ui-entering");
    }
    function configure() {
      intersection?.disconnect(); mutation?.disconnect();
      root.querySelectorAll(".ui-entering").forEach(node => node.classList.remove("ui-entering"));
      root.dataset.uiMotion = reduced.matches ? "off" : "on";
      if (reduced.matches || !view.IntersectionObserver) return;
      const observed = new WeakSet();
      intersection = new view.IntersectionObserver(entries => {
        entries.forEach(entry => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("ui-entering");
          intersection.unobserve(entry.target);
        });
      }, { threshold: 0.06, rootMargin: "0px 0px -16px 0px" });
      function observe(node) {
        if (node.nodeType !== 1) return;
        const candidates = [...(node.matches(TARGETS) ? [node] : []), ...node.querySelectorAll(TARGETS)];
        candidates.forEach((element, index) => {
          if (observed.has(element)) return;
          observed.add(element);
          element.style.setProperty("--ui-delay", `${Math.min(index % 4, 3) * 35}ms`);
          intersection.observe(element);
        });
      }
      observe(root);
      mutation = new view.MutationObserver(records => records.forEach(record => record.addedNodes.forEach(observe)));
      mutation.observe(root, { childList: true, subtree: true });
    }
    configure(); updateScroll();
    reduced.addEventListener("change", configure);
    view.addEventListener("scroll", scroll, { passive: true });
    root.addEventListener("animationend", finish);
    return () => {
      intersection?.disconnect(); mutation?.disconnect();
      if (frame) view.cancelAnimationFrame(frame);
      reduced.removeEventListener("change", configure);
      view.removeEventListener("scroll", scroll);
      root.removeEventListener("animationend", finish);
      root.querySelectorAll(".ui-entering").forEach(node => node.classList.remove("ui-entering"));
      root.removeAttribute("data-ui-scrolled");
      root.removeAttribute("data-ui-motion");
    };
  }, []);
  return <span ref={marker} hidden style={{ display: "none" }} />;
}
