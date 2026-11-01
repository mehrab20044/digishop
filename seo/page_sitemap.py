from urllib.parse import quote

from django.http import HttpResponse
from django.utils.html import escape
from django.views.decorators.http import require_safe

from seo.services.canonical_service import public_origin
from seo.services.page_rules import SYSTEM, sitemap_ids


@require_safe
def page_rules_sitemap(request):
    from products.models import Product
    from products.services.category_url_service import PREFIX, current_paths
    from cms.views import published_pages
    paths = []
    for kind, (_, path) in SYSTEM.items():
        if 0 in sitemap_ids(kind, [0]):
            paths.append(path)
    products = list(Product.objects.filter(is_active=True, status=Product.Status.PUBLISHED).values_list("pk", flat=True))
    paths.extend(f"/products/{pk}" for pk in sorted(sitemap_ids("product", products)))
    categories = current_paths()
    paths.extend(PREFIX + quote(categories[pk], safe="/") for pk in sorted(sitemap_ids("category", categories)))
    pages = dict(published_pages().values_list("pk", "slug"))
    paths.extend("/pages/" + quote(pages[pk], safe="") for pk in sorted(sitemap_ids("page", pages)))
    origin = public_origin(request)
    xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    xml += "".join(f"<url><loc>{escape(origin + path)}</loc></url>" for path in paths)
    xml += "</urlset>"
    response = HttpResponse(xml, content_type="application/xml")
    response["Cache-Control"] = "no-cache"
    return response
