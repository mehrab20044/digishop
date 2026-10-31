from django.http import JsonResponse
from django.views.decorators.http import require_GET
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from cms.services.footer_service import footer_data, update_footer
from dashboard.api.v1.views import OwnerAPIView


@require_GET
def public_footer(request):
    return JsonResponse(footer_data()["config"])


class FooterOwnerView(OwnerAPIView):
    http_method_names = ["get", "patch", "head", "options"]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.user.has_perm("cms.view_sitefooter"):
            raise PermissionDenied("مجوز مشاهده فوتر ندارید.")

    def get(self, request):
        return Response(footer_data())

    def patch(self, request):
        if not request.user.has_perm("cms.change_sitefooter"):
            raise PermissionDenied("مجوز تغییر فوتر ندارید.")
        if not isinstance(request.data, dict) or set(request.data) != {
            "revision",
            "config",
        }:
            raise ValidationError("تنظیمات فوتر و نسخه آن را ارسال کنید.")
        return Response(update_footer(request.user, **request.data))


@require_GET
def footer_styles(request):
    from pathlib import Path

    from django.http import HttpResponse

    path = Path(__file__).resolve().parents[2] / "static" / "cms" / "store-footer.css"
    return HttpResponse(path.read_text(), content_type="text/css; charset=utf-8")
