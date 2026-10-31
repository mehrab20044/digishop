import { createContext, useContext, useEffect, useState } from "react";
import "./store-theme.css";
export const DEFAULT_THEME = { primary: "#176b61", background: "#ffffff", surface: "#f0f7f5", text: "#17212d", page_width: "standard", font: "tahoma", banner: { enabled: true, title: "یک انتخاب هوشمند، برای هر روز تو.", text: "محصولات را ببین و انتخاب مناسب خودت را پیدا کن.", image_id: null, image_url: null, button_label: "دیدن محصولات", button_href: "/products" } };
export function readBootstrap() {
  try { return JSON.parse(document.getElementById("cms-bootstrap")?.textContent || "null"); } catch { return null; }
}
const Context = createContext(DEFAULT_THEME);
export function StoreThemeProvider({ children, override }) {
  const [theme, setTheme] = useState(() => readBootstrap()?.theme || DEFAULT_THEME);
  useEffect(() => {
    if (override) return undefined;
    const controller = new AbortController();
    fetch("/api/v1/content/theme/", { signal: controller.signal, cache: "no-store" }).then(response => { if (!response.ok) throw new Error("theme"); return response.json(); }).then(setTheme).catch(() => {});
    return () => controller.abort();
  }, [override]);
  return <Context.Provider value={override || theme}>{children}</Context.Provider>;
}
export function useStoreTheme() { return useContext(Context); }
export function themeVariables(theme) {
  const color = (key, fallback) => /^#[0-9a-f]{6}$/i.test(theme[key] || "") ? theme[key] : fallback;
  const primary = color("primary", DEFAULT_THEME.primary);
  const channels = [1, 3, 5].map(i => parseInt(primary.slice(i, i + 2), 16) / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4);
  const luminance = channels.reduce((a, v, i) => a + v * [.2126, .7152, .0722][i], 0);
  return { "--sf-blue": primary, "--sf-ink": color("text", DEFAULT_THEME.text), "--store-primary": primary, "--store-bg": color("background", DEFAULT_THEME.background), "--store-surface": color("surface", DEFAULT_THEME.surface), "--store-text": color("text", DEFAULT_THEME.text), "--store-button-text": luminance < .179 ? "#ffffff" : "#111111", "--store-width": ({ compact: "980px", standard: "1280px", wide: "1480px" })[theme.page_width] || "1280px", "--store-font": theme.font === "system" ? "system-ui,Tahoma,sans-serif" : "Tahoma,Arial,sans-serif" };
}
export function ThemeBanner() {
  const { banner } = useStoreTheme();
  if (!banner?.enabled) return null;
  return <section className={`st-banner ${banner.image_url ? "st-banner-image" : ""}`}><div><span className="st-overline">به فروشگاه ما خوش آمدید</span><h1>{banner.title}</h1><p>{banner.text}</p>{banner.button_label && <a className="sf-button" href={banner.button_href}>{banner.button_label} ←</a>}</div>{banner.image_url && <img src={banner.image_url} alt="" fetchPriority="high" />}</section>;
}
