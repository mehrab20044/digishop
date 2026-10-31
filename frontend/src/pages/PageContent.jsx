import "./page-content.css";
function Buttons({ items = [], preview }) {
  return <div className="pb-buttons">{items.map((button, index) => <a key={index} href={button.href || "#"} onClick={preview ? event => event.preventDefault() : undefined} className={`pb-button pb-button-${button.style === "outline" ? "outline" : "primary"}`}>{button.label}</a>)}</div>;
}
export default function PageContent({ page, images = {}, preview = false }) {
  return <div className={`pb-document pb-layout-${["simple", "about", "landing"].includes(page.layout) ? page.layout : "simple"}`} dir="rtl" lang="fa"><h1 className="pb-page-title">{page.title || "عنوان صفحه"}</h1>{page.blocks.filter(block => block.enabled).map(block => {
    const data = block.data; const src = images[data.image_id];
    if (block.type === "hero") return <section key={block.id} className={`pb-hero ${src ? "pb-hero-image" : ""}`}><div><h2>{data.title}</h2><p className="pb-prose">{data.text}</p><Buttons items={data.buttons} preview={preview} /></div>{src && <img src={src} alt="" />}</section>;
    if (block.type === "text") return <section key={block.id} className={`pb-text pb-align-${data.align === "center" ? "center" : "right"}`}><h2>{data.heading}</h2><p className="pb-prose">{data.body}</p></section>;
    if (block.type === "image") return <figure key={block.id} className="pb-image">{src ? <img src={src} alt={data.alt} /> : <p>تصویر انتخاب نشده</p>}{data.caption && <figcaption>{data.caption}</figcaption>}</figure>;
    if (block.type === "buttons") return <div className="pb-button-section" key={block.id}><Buttons items={data.items} preview={preview} /></div>;
    if (block.type === "spacer") return <div key={block.id} style={{ height: data.height }} aria-hidden="true" />;
    return null;
  })}</div>;
}
