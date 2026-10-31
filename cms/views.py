from pathlib import Path
from urllib.parse import quote

from django.http import FileResponse, HttpResponsePermanentRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_safe

from cms.models import Page
from cms.services.footer_service import footer_data
from cms.services.render_service import public_document


def published_pages():
    return (
        Page.objects.filter(is_published=True)
        .exclude(published={})
        .order_by("title", "pk")
    )


@require_safe
def page_view(request, slug):
    page = get_object_or_404(published_pages(), slug=slug)
    url = "/pages/" + quote(page.slug, safe="")
    if quote(request.path, safe="/%") != url:
        return HttpResponsePermanentRedirect(url)
    document = public_document(page)
    from cms.services.frontend_service import frontend_assets

    bootstrap = page_payload(page)
    response = render(
        request,
        "cms/page.html",
        {
            "page": document,
            "canonical": request.build_absolute_uri(url),
            "navigation": footer_links(),
            "store_footer": footer_data()["config"],
            "bootstrap": bootstrap,
            "frontend_assets": frontend_assets(),
        },
    )
    response["Cache-Control"] = "no-cache"
    return response


@require_safe
def page_links(request):
    return JsonResponse({"results": footer_links()})


@require_safe
def page_styles(request):
    response = FileResponse(
        (Path(__file__).parent / "static/cms/page-content.css").open("rb"),
        content_type="text/css",
    )
    response["Cache-Control"] = "no-cache"
    return response


@require_safe
def page_sitemap(request):
    from django.http import HttpResponse
    from django.utils.html import escape

    rows = "".join(
        "<url><loc>"
        + str(escape(request.build_absolute_uri("/pages/" + quote(row.slug, safe=""))))
        + "</loc></url>"
        for row in published_pages()
    )
    return HttpResponse(
        '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + rows
        + "</urlset>",
        content_type="application/xml",
    )


def footer_links():
    rows = [
        page for page in published_pages() if page.published.get("footer_visible", True)
    ]
    rows.sort(key=lambda page: (page.published.get("footer_order", 0), page.pk))
    return [
        {
            "title": page.published.get("footer_label") or page.published["title"],
            "url": "/pages/" + quote(page.slug, safe=""),
        }
        for page in rows[:50]
    ]


def page_payload(page):
    from cms.services.theme_service import get_theme, theme_document

    document = public_document(page)
    images = {
        block["data"]["image_id"]: block["data"]["image_url"]
        for block in document["blocks"]
        if block["data"].get("image_url")
    }
    return {
        "page": document,
        "images": images,
        "theme": theme_document(get_theme().published),
        "links": footer_links(),
    }


@require_safe
def page_document(request, slug):
    response = JsonResponse(
        page_payload(get_object_or_404(published_pages(), slug=slug))
    )
    response["Cache-Control"] = "no-store"
    return response


@require_safe
def public_theme(request):
    from cms.services.theme_service import get_theme, theme_document

    response = JsonResponse(theme_document(get_theme().published))
    response["Cache-Control"] = "no-store"
    return response


@require_safe
def theme_styles(request):
    from django.http import HttpResponse

    from cms.services.theme_service import get_theme, theme_document

    theme = theme_document(get_theme().published)
    font = (
        "system-ui,Tahoma,sans-serif"
        if theme["font"] == "system"
        else "Tahoma,Arial,sans-serif"
    )
    css = (
        ":root{--store-primary:"
        + theme["primary"]
        + ";--store-bg:"
        + theme["background"]
        + ";--store-surface:"
        + theme["surface"]
        + ";--store-text:"
        + theme["text"]
        + ";--store-button-text:"
        + theme["button_text"]
        + ";--store-font:"
        + font
        + "}.pb-public{background:var(--store-bg);color:var(--store-text);font-family:var(--store-font)}.pb-document{color:var(--store-text)}.pb-hero{background:var(--store-surface)}.pb-hero p{color:var(--store-text)}.pb-document .pb-button{background:var(--store-primary);color:var(--store-button-text);border-color:var(--store-primary)}.pb-site-footer{background:var(--store-surface)}.ssr-footer-buttons{display:flex;flex-wrap:wrap;gap:12px;justify-content:center;padding:24px}.ssr-footer-buttons a{border:1px solid var(--store-primary);padding:10px 20px;border-radius:10px}"
    )
    response = HttpResponse(css, content_type="text/css")
    response["Cache-Control"] = "no-cache"
    return response


@require_safe
def banner_feed(request):
    from cms.services.banner_service import public_banners

    response = JsonResponse(public_banners())
    response["Cache-Control"] = "no-store"
    return response
