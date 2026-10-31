import { useState } from "react";
import { createPortal } from "react-dom";
export default function PreviewFrame({ children, mobile = false }) {
  const [body, setBody] = useState(null);
  return <iframe title={mobile ? "پیش‌نمایش موبایل فروشگاه" : "پیش‌نمایش دسکتاپ فروشگاه"} className={`st-preview-frame ${mobile ? "is-mobile" : ""}`} srcDoc={'<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head><body style="margin:0"><div id="preview-root"></div></body></html>'} onLoad={event => {
    const doc = event.currentTarget.contentDocument;
    if (!doc) return;
    doc.head.querySelectorAll('[data-preview-style]').forEach(node => node.remove());
    document.querySelectorAll('style,link[rel="stylesheet"]').forEach(node => { const copy = node.cloneNode(true); copy.dataset.previewStyle = "true"; doc.head.append(copy); });
    setBody(doc.getElementById("preview-root"));
  }}>{body && createPortal(children, body)}</iframe>;
}
