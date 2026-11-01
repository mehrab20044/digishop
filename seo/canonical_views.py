"""Initial document head and public metadata endpoint for the storefront."""

import json
import re
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse, HttpResponsePermanentRedirect, JsonResponse
from django.utils.html import escape
from django.views.decorators.http import require_safe

from seo.services.canonical_service import canonical_document

TAG = re.compile(r"<link\b[^>]*\brel\s*=\s*(['\"])canonical\1[^>]*>|<meta\b[^>]*\bname\s*=\s*(['\"])robots\2[^>]*>", re.I)


def inject_canonical(html, data):
    html = TAG.sub("", html)
    html = re.sub(r'<script\b[^>]*\bid=[\'\"]seo-canonical[\'\"][^>]*>[\s\S]*?</script>', "", html, flags=re.I)
    head = f'<meta name="robots" content="{escape(data["robots"])}">'
    if data.get("canonical"):
        head += f'<link rel="canonical" href="{escape(data["canonical"])}">'
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    head += f'<script id="seo-canonical" type="application/json">{payload}</script>'
    return re.sub(r"</head\s*>", lambda _: head + "</head>", html, count=1, flags=re.I)


@require_safe
def canonical_metadata(request):
    try:
        data = canonical_document(request, request.GET.get("url", "/"))
    except ImproperlyConfigured:
        return JsonResponse({"detail": "Public storefront origin is not configured."}, status=503)
    response = JsonResponse(data)
    response["Cache-Control"] = "no-store"
    return response


@require_safe
def storefront_document(request, pk=None):
    try:
        data = canonical_document(request, request.get_full_path())
    except ImproperlyConfigured:
        return HttpResponse("Public storefront origin is not configured.", status=503)
    if data["redirect"]:
        return HttpResponsePermanentRedirect(data["redirect"])
    index = Path(settings.BASE_DIR) / "frontend/dist/index.html"
    if not index.is_file():
        return HttpResponse("Frontend build missing. Run npm run build.", status=503)
    html = index.read_text(encoding="utf-8")
    title = str(escape(data.get("title", "دیجی‌شاپ")))
    html = re.sub(r"<title>[\s\S]*?</title>", lambda _: f"<title>{title}</title>", html, count=1, flags=re.I)
    response = HttpResponse(inject_canonical(html, data))
    response["Cache-Control"] = "no-cache"
    response["X-Robots-Tag"] = data["robots"]
    return response
