const prefix = "/products/category/";
export default function categorySEO(backend) {
  async function resolve(url) {
    const path = decodeURIComponent(url.pathname.slice(prefix.length)).replace(/\/+$/, "");
    const params = url.pathname === "/products" ? new URLSearchParams({ id: url.searchParams.get("category") }) : new URLSearchParams({ path });
    const response = await fetch(`${backend}/products/api/v1/category-resolve/?${params}`, { signal: AbortSignal.timeout(10000) });
    if (response.status === 404) return null;
    if (!response.ok) throw new Error(`Category API: ${response.status}`);
    return response.json();
  }
  const escape = value => String(value).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  return {
    name: "digishop-category-seo",
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        const url = new URL(req.url, "http://localhost");
        const legacy = url.pathname === "/products" && /^[1-9][0-9]*$/.test(url.searchParams.get("category") || "") && !url.searchParams.has("categories");
        if ((!url.pathname.startsWith(prefix) && !legacy) || !["GET", "HEAD"].includes(req.method)) return next();
        try {
          const data = await resolve(url);
          if (!data) { res.statusCode = 404; res.setHeader("Content-Type", "text/html; charset=utf-8"); return res.end('<html lang="fa" dir="rtl"><title>دسته پیدا نشد</title><h1>دسته‌بندی پیدا نشد</h1><a href="/products">محصولات</a></html>'); }
          if (legacy) url.searchParams.delete("category");
          if (url.pathname !== data.url) { res.statusCode = 301; res.setHeader("Location", data.url + url.search); return res.end(); }
          next();
        } catch { res.statusCode = 503; res.end("Category service temporarily unavailable"); }
      });
    },
    async transformIndexHtml(html, context) {
      const url = new URL(context.originalUrl || context.path, "http://localhost");
      if (!url.pathname.startsWith(prefix)) return html;
      try {
        const data = await resolve(url);
        if (!data) return html;
        let head = `<title>${escape(data.name)} | دیجی‌شاپ</title><link rel="canonical" href="${escape(data.url)}"><meta name="description" content="${escape(data.description || data.name)}">`;
        const structured = { "@context": "https://schema.org", "@type": "BreadcrumbList", itemListElement: (data.breadcrumbs || []).map((part, index) => ({ "@type": "ListItem", position: index + 1, name: part.name, item: part.url })) };
        head += '<script type="application/ld+json">' + JSON.stringify(structured).replace(/</g, "\\u003c") + '</script>';
        return html.replace(/<title>[\s\S]*?<\/title>/i, "").replace("</head>", head + "</head>");
      } catch { return html; }
    },
  };
}
