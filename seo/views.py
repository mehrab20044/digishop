from django.http import HttpResponse
from django.views.decorators.http import require_safe

from seo.services.robots_service import current_document
from seo.services.robots_engine import render_document


@require_safe
def robots_txt(request):
    content = render_document(current_document().published)

    response = HttpResponse(
        content,
        content_type="text/plain; charset=utf-8",
    )
    response["Cache-Control"] = "no-store"

    return response
