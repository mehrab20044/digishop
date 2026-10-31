from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from cms.services.theme_service import (
    DEFAULT_THEME,
    get_theme,
    theme_document,
    update_theme,
)
from dashboard.api.v1.views import OwnerAPIView


def theme_data(row):
    return {"draft": row.draft, "published": row.published, "revision": row.revision, "defaults": DEFAULT_THEME, "preview": theme_document(row.draft)}


class ThemeView(OwnerAPIView):
    http_method_names = ["get", "post", "patch", "options"]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.user.is_staff or not request.user.has_perm("cms.view_sitetheme"):
            raise PermissionDenied("مجوز مشاهدهٔ ظاهر فروشگاه ندارید.")

    def get(self, request):
        return Response(theme_data(get_theme()))

    def patch(self, request):
        if not request.user.has_perm("cms.change_sitetheme"):
            raise PermissionDenied("مجوز تغییر ظاهر فروشگاه ندارید.")
        if not isinstance(request.data, dict) or set(request.data) != {"revision", "config"}:
            raise ValidationError("تنظیمات معتبر ارسال کنید.")
        return Response(theme_data(update_theme(request.user, request.data["revision"], request.data["config"])))

    def post(self, request):
        if not request.user.has_perm("cms.publish_sitetheme"):
            raise PermissionDenied("مجوز انتشار ظاهر فروشگاه ندارید.")
        if not isinstance(request.data, dict) or set(request.data) != {"revision"}:
            raise ValidationError("نسخهٔ تنظیمات را ارسال کنید.")
        return Response(theme_data(update_theme(request.user, request.data["revision"], publish=True)))
