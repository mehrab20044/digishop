import json
from urllib.parse import quote

from django.http import (
    Http404,
    HttpResponse,
    HttpResponsePermanentRedirect,
    JsonResponse,
)
from django.utils.html import escape
from django.views.decorators.http import require_GET

from products.models import Category
from products.services.category_url_service import PREFIX, current_paths, resolve_path


def metadata(request, path):
    resolved = resolve_path(path)
    if resolved is None:
        raise Http404("دسته پیدا نشد")
    category, canonical_path = resolved
    url = PREFIX + quote(canonical_path, safe="/")
    return category, url


def breadcrumbs(category):
    paths = current_paths()
    result = []
    while category is not None:
        result.append({"name": category.name, "url": PREFIX + quote(paths[category.pk], safe="/")})
        category = Category.objects.filter(pk=category.parent_id).first() if category.parent_id else None
    return list(reversed(result))


@require_GET
def category_resolve(request):
    category_id = request.GET.get("id")
    path = request.GET.get("path", "")
    if category_id and category_id.isascii() and category_id.isdigit():
        path = current_paths().get(int(category_id), "")
    category, url = metadata(request, path)
    return JsonResponse({"id": category.pk, "name": category.name, "description": category.description, "url": url, "breadcrumbs": breadcrumbs(category)})


@require_GET
def category_sitemap(request):
    paths = current_paths()
    entries = "".join("<url><loc>" + str(escape(request.build_absolute_uri(PREFIX + quote(path, safe="/")))) + "</loc></url>" for path in paths.values())
    return HttpResponse('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + entries + '</urlset>', content_type="application/xml")


@require_GET
def category_page(request, path):
    from pathlib import Path

    from django.conf import settings
    category, url = metadata(request, path.rstrip("/"))
    if request.path != url and quote(request.path, safe="/%") != url:
        query = request.META.get("QUERY_STRING", "")
        return HttpResponsePermanentRedirect(url + ("?" + query if query else ""))
    index = Path(settings.BASE_DIR) / "frontend" / "dist" / "index.html"
    if not index.is_file():
        return HttpResponse("Frontend build missing. Run npm run build.", status=503)
    html = index.read_text(encoding="utf-8")
    import re
    html = re.sub(r"<title>.*?</title>", "", html, flags=re.S)
    canonical = request.build_absolute_uri(url)
    head = f'<title>{escape(category.name)} | دیجی‌شاپ</title><link rel="canonical" href="{escape(canonical)}"><meta name="description" content="{escape(category.description or category.name)}">'
    structured = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": index, "name": part["name"], "item": request.build_absolute_uri(part["url"])}
        for index, part in enumerate(breadcrumbs(category), 1)
    ]}
    head += '<script type="application/ld+json">' + json.dumps(structured, ensure_ascii=False).replace("<", "\\u003c") + '</script>'
    html = html.replace("</head>", head + "</head>")
    return HttpResponse(html)
