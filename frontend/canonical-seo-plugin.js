const escape = (value) =>
  String(value).replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );
export function applyCanonical(html, data) {
  html = html
    .replace(/<link\b[^>]*\brel\s*=\s*(["'])canonical\1[^>]*>/gi, "")
    .replace(/<meta\b[^>]*\bname\s*=\s*(["'])robots\1[^>]*>/gi, "")
    .replace(
      /<script\b[^>]*\bid\s*=\s*(["'])seo-canonical\1[^>]*>[\s\S]*?<\/script>/gi,
      "",
    );
  let head = `<meta name="robots" content="${escape(data.robots)}">`;
  if (data.canonical)
    head += `<link rel="canonical" href="${escape(data.canonical)}">`;
  head += `<script id="seo-canonical" type="application/json">${JSON.stringify(data).replace(/</g, "\\u003c")}</script>`;
  return html.replace(/<\/head\s*>/i, () => head + "</head>");
}
export default function canonicalSEO(backend) {
  const eligible = (path) =>
    /^(\/$|\/products(?:\/|$)|\/categories\/?$|\/pages\/|\/account(?:\/|$)|\/orders(?:\/|$)|\/cart\/?$|\/checkout\/?$|\/login\/?$|\/dashboard(?:\/|$)|\/management(?:\/|$))/.test(
      path,
    ) && !path.startsWith("/products/api/");
  async function resolve(location) {
    const devOrigin = new URL(
      process.env.DEV_PUBLIC_URL || "http://localhost:5173",
    );
    const response = await fetch(
      `${backend}/api/v1/seo/canonical/?${new URLSearchParams({ url: location })}`,
      { signal: AbortSignal.timeout(10000), headers: { Host: devOrigin.host } },
    );
    if (!response.ok) {
      const error = new Error(`Canonical service: ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return response.json();
  }
  return {
    name: "digishop-canonical-head",
    enforce: "post",
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        const url = new URL(req.url, "http://localhost");
        if (!["GET", "HEAD"].includes(req.method) || !eligible(url.pathname))
          return next();
        try {
          const data = await resolve(url.pathname + url.search);
          if (data.redirect) {
            res.statusCode = 301;
            res.setHeader("Location", data.redirect);
            return res.end();
          }
          res.setHeader("X-Robots-Tag", data.robots);
          next();
        } catch (error) {
          res.statusCode = error.status === 404 ? 404 : 503;
          res.setHeader("X-Robots-Tag", "noindex, nofollow");
          res.setHeader("Content-Type", "text/plain; charset=utf-8");
          res.end(
            error.status === 404
              ? "صفحه پیدا نشد"
              : "SEO service temporarily unavailable",
          );
        }
      });
    },
    transformIndexHtml: {
      order: "post",
      async handler(html, context) {
        // Build output has no request or public origin. Dynamic head comes from Django.
        if (!context.server) return html;
        const url = new URL(
          context.originalUrl || context.path,
          "http://localhost",
        );
        if (!eligible(url.pathname)) return html;
        return applyCanonical(html, await resolve(url.pathname + url.search));
      },
    },
  };
}
