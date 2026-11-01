"""Canonical URL policy shared by server HTML, Vite and client navigation."""

import os
import re
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import Http404

TRACKING = {"gclid", "dclid", "fbclid", "msclkid", "gbraid", "wbraid", "_ga", "_gl"}
PRIVATE = re.compile(r"^/(account|orders|cart|checkout|login|dashboard|management|admin|payments)(/|$)")


def public_origin(request):
    configured = getattr(settings, "SITE_PUBLIC_URL", "") or os.environ.get("SITE_PUBLIC_URL", "")
    if not configured:
        if not settings.DEBUG:
            raise ImproperlyConfigured("Set SITE_PUBLIC_URL to the public storefront origin.")
        configured = (
            getattr(settings, "DEV_PUBLIC_URL", "")
            or os.environ.get("DEV_PUBLIC_URL", "")
            or "http://localhost:5173"
        )
    parsed = urlsplit(str(configured).strip())
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}):
        raise ImproperlyConfigured("SITE_PUBLIC_URL must be an http(s) origin without a path.")
    return f"{parsed.scheme}://{parsed.netloc}"


def normalized_query(query, *, drop_category=False):
    pairs = []
    source = parse_qsl(query, keep_blank_values=True)
    single_page = sum(key == "page" for key, _ in source) == 1
    for key, value in source:
        lower = key.lower()
        if lower.startswith("utm_") or lower in TRACKING or (drop_category and key == "category"):
            continue
        if key == "page" and single_page and len(value) < 10 and re.fullmatch(r"[0-9]+", value) and int(value) >= 1:
            value = str(int(value))
            if value == "1":
                continue
        pairs.append((key, value))
    # Preserve the order of repeated values; unknown/content-changing filters stay.
    return urlencode(sorted(pairs, key=lambda pair: pair[0]))


def canonical_document(request, location):
    from products.models import Product
    from products.services.category_url_service import PREFIX, current_paths, resolve_path

    parsed = urlsplit(location)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/") or parsed.path.startswith("//"):
        raise Http404("Invalid storefront path")
    path = unquote(parsed.path)
    if any(ord(char) < 32 for char in path) or "\\" in path:
        raise Http404("Invalid storefront path")
    path = path.rstrip("/") or "/"
    requested = quote(path, safe="/") + ("?" + parsed.query if parsed.query else "")
    if PRIVATE.match(path):
        return {"requested": requested, "canonical": None, "robots": "noindex, nofollow", "redirect": None}
    title, description = "دیجی‌شاپ", ""
    resource_kind, resource_id = None, 0
    drop_category = False
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    target_path = path
    if path.startswith(PREFIX):
        resolved = resolve_path(path[len(PREFIX):])
        if resolved is None:
            raise Http404("دسته پیدا نشد")
        category, branch = resolved
        target_path = PREFIX + branch
        resource_kind, resource_id = "category", category.pk
        title, description = category.name, category.description
    elif path == "/products" and re.fullmatch(r"[1-9][0-9]*", query.get("category", "")) and "categories" not in query:
        from products.models import Category
        category_id = int(query["category"])
        branch = current_paths().get(category_id)
        if branch is None:
            raise Http404("دسته پیدا نشد")
        category = Category.objects.get(pk=category_id)
        target_path, drop_category = PREFIX + branch, True
        resource_kind, resource_id = "category", category.pk
        title, description = category.name, category.description
    elif match := re.fullmatch(r"/products/([1-9][0-9]*)", path):
        product = Product.objects.filter(pk=int(match[1]), is_active=True, status=Product.Status.PUBLISHED).first()
        if product is None:
            raise Http404("محصول پیدا نشد")
        resource_kind, resource_id = "product", product.pk
        title, description = product.name, product.short_description
    elif path.startswith("/pages/"):
        from cms.views import published_pages
        page = published_pages().filter(slug=path[len("/pages/"):]).first()
        if page is None:
            raise Http404("صفحه پیدا نشد")
        resource_kind, resource_id = "page", page.pk
        target_path = "/pages/" + page.slug
        title = page.published.get("seo_title") or page.published.get("title") or page.title
        description = page.published.get("seo_description", "")
    elif path in {"/", "/products", "/categories"}:
        resource_kind = {"/": "home", "/products": "catalog", "/categories": "directory"}[path]
        title = {"/": "دیجی‌شاپ", "/products": "همهٔ محصولات", "/categories": "همهٔ دسته‌بندی‌ها"}[path]
    else:
        raise Http404("صفحه پیدا نشد")

    normalized = normalized_query(parsed.query, drop_category=drop_category)
    relative = quote(target_path, safe="/") + ("?" + normalized if normalized else "")
    filters = dict(parse_qsl(normalized, keep_blank_values=True))
    # Search/faceted URLs keep an honest self canonical; they are not equivalents
    # of an unfiltered listing. Keep every pagination and ordering parameter.
    faceted = bool(set(filters) & {"search", "min_price", "max_price", "in_stock", "categories"})
    original_path = quote(unquote(parsed.path), safe="/")
    redirect = None
    if original_path != quote(target_path, safe="/"):
        # Redirect URL aliases/slashes but preserve tracking for attribution.
        redirect_query = urlencode([(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if not (drop_category and k == "category")])
        redirect = quote(target_path, safe="/") + ("?" + redirect_query if redirect_query else "")
    from seo.services.page_rules import apply_index_rule
    robots = apply_index_rule(resource_kind, resource_id, "noindex, follow" if faceted else "index, follow")
    return {
        "requested": requested, "canonical": public_origin(request) + relative,
        "robots": robots,
        "redirect": redirect, "title": title, "description": description,
    }
