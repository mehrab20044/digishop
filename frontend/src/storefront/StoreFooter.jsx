import { useEffect, useState } from "react";
import HubIcon from "../customer-hub/Icons";
import { readBootstrap } from "../appearance/StoreTheme";
import "./store-footer.css";

const FALLBACK = {
  name: "دیجی‌شاپ",
  description: "محصولات را بررسی کنید و انتخاب مناسب خود را پیدا کنید.",
  columns: [{ title: "راهنمای خرید", links: [
    { title: "محصولات", url: "/products" },
    { title: "پیگیری سفارش", url: "/account?tab=orders" },
  ] }],
  services: [], socials: [],
};
function safeLink(value) {
  if (typeof value !== "string" || /[\\\s]/.test(value)) return null;
  if (value.startsWith("/") && !value.startsWith("//")) return value;
  try { const url = new URL(value); return ["https:", "http:"].includes(url.protocol) ? url.href : null; }
  catch { return null; }
}
function Link({ row }) {
  const href = safeLink(row.url);
  return href ? <a href={href}>{row.title}</a> : null;
}
export default function StoreFooter({ linksOverride }) {
  const [config, setConfig] = useState(FALLBACK);
  const [pages, setPages] = useState(() => readBootstrap()?.links || []);
  const [mobile, setMobile] = useState(false);
  const [expanded, setExpanded] = useState([]);

  useEffect(() => {
    const query = window.matchMedia("(max-width: 640px)");
    const update = () => setMobile(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/v1/content/footer/", {
      signal: controller.signal, headers: { Accept: "application/json" },
    }).then(response => {
      if (!response.ok) throw new Error("footer");
      return response.json();
    }).then(data => {
      if (!controller.signal.aborted && data && Array.isArray(data.columns)) setConfig(data);
    }).catch(() => {});
    if (!linksOverride) {
      fetch("/api/v1/content/pages/", { signal: controller.signal })
        .then(response => response.ok ? response.json() : { results: [] })
        .then(data => { if (!controller.signal.aborted) setPages(data.results || []); })
        .catch(() => {});
    }
    return () => controller.abort();
  }, [linksOverride]);

  const columns = config.columns || [];
  const existing = new Set(columns.flatMap(column => column.links.map(row => row.url)));
  const extra = (linksOverride || pages).filter(row => !existing.has(row.url));
  const groups = extra.length ? [...columns, { title: "بیشتر دربارهٔ فروشگاه", links: extra }] : columns;

  function toggle(event, index) {
    event.preventDefault();
    if (mobile) setExpanded(previous => previous.includes(index)
      ? previous.filter(value => value !== index) : [...previous, index]);
  }
  function backToTop() {
    window.scrollTo({ top: 0, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
    document.getElementById("sf-main")?.focus({ preventScroll: true });
  }

  return <footer className="store-footer-v2" aria-label="پایین صفحهٔ فروشگاه">
    <div className="sf-container">
      {config.services?.length > 0 && <div className="footer-v2-services">
        {config.services.map((service, index) => <div key={index}>
          <HubIcon name={service.icon} size={32}/>
          <strong>{service.title}</strong><span>{service.text}</span>
        </div>)}
      </div>}
      <div className="footer-v2-heading">
        <div className="footer-v2-brand">
          <a href="/" aria-label={`${config.name}، صفحه اصلی`}>{config.name}</a>
          {config.description && <p>{config.description}</p>}
        </div>
        <button type="button" className="footer-v2-top" aria-label="بازگشت به بالای صفحه" onClick={backToTop}>
          بازگشت به بالا <span aria-hidden="true">↑</span>
        </button>
      </div>
      <div className="footer-v2-body">
        <div className="footer-v2-groups">
          {groups.map((group, index) => <details key={index} open={!mobile || expanded.includes(index)}>
            <summary onClick={event => toggle(event, index)}>
              {group.title}<span aria-hidden="true">⌄</span>
            </summary>
            <nav aria-label={group.title}>{group.links.map((row, i) => <Link key={i} row={row}/>)}</nav>
          </details>)}
        </div>
        {(config.phone || config.email || config.hours || config.address) && <section className="footer-v2-contact" aria-label="تماس با فروشگاه">
          <h2>پاسخ‌گوی شما هستیم</h2>
          {config.hours && <p>{config.hours}</p>}
          {config.phone && <a className="footer-v2-phone" href={`tel:${config.phone.replace(/[^+0-9]/g, "")}`}><bdi>{config.phone}</bdi><span>تماس با فروشگاه ←</span></a>}
          {config.email && <a className="footer-v2-email" href={`mailto:${config.email}`}><bdi>{config.email}</bdi></a>}
          {config.address && <p className="footer-v2-address">{config.address}</p>}
        </section>}
      </div>
      <div className="footer-v2-bottom">
        <small>{config.copyright || `حقوق محتوای این فروشگاه متعلق به ${config.name} است.`}</small>
        {config.socials?.length > 0 && <nav aria-label="شبکه‌های اجتماعی">{config.socials.map((row, index) => <Link row={row} key={index}/>)}</nav>}
      </div>
    </div>
  </footer>;
}
