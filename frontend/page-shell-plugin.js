export default function pageShell(backend) {
  return {
    name: "digishop-page-shell",
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        if (!/^\/pages\/[^/?]+\/?(?:\?|$)/.test(req.url || "") || !["GET", "HEAD"].includes(req.method)) return next();
        try {
          const response = await fetch(backend + req.url, { headers: { host: req.headers.host || "localhost" }, redirect: "manual", signal: AbortSignal.timeout(15000) });
          res.statusCode = response.status;
          for (const name of ["content-type", "location", "cache-control", "x-content-type-options", "x-frame-options"]) if (response.headers.get(name)) res.setHeader(name, response.headers.get(name));
          const html = await response.text();
          const body = response.status === 200 ? await server.transformIndexHtml(req.url, html) : html;
          res.end(req.method === "HEAD" ? undefined : body);
        } catch { res.statusCode = 503; res.end("Page service temporarily unavailable"); }
      });
    },
  };
}
