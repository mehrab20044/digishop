from django.http import HttpResponse
from django.views.decorators.http import require_GET

from .models import SEOSettings


@require_GET
def robots_txt(request):
    settings = SEOSettings.get_settings()

    if settings.allow_crawling:
        content = "User-agent: *\nAllow: /\n"
    else:
        content = "User-agent: *\nDisallow: /\n"

    response = HttpResponse(
        content,
        content_type="text/plain; charset=utf-8",
    )
    response["Cache-Control"] = "no-store"

    return response
