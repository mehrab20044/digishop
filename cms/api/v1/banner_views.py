from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from cms.services.banner_service import banner_documents, get_banners, update_banners
from dashboard.api.v1.views import OwnerAPIView


def data_for(row):
    return {"draft": row.draft, "published": row.published, "revision": row.revision, "preview": banner_documents(row.draft)}


class BannerView(OwnerAPIView):
    http_method_names = ["get", "patch", "post", "options"]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.user.is_staff or not request.user.has_perm("cms.view_bannerset"):
            raise PermissionDenied("مجوز مشاهدهٔ بنرها ندارید.")

    def get(self, request):
        return Response(data_for(get_banners()))

    def patch(self, request):
        if not request.user.has_perm("cms.change_bannerset"):
            raise PermissionDenied("مجوز ویرایش بنر ندارید.")
        if not isinstance(request.data, dict) or set(request.data) != {"revision", "banners"}:
            raise ValidationError("درخواست بنر معتبر نیست.")
        return Response(data_for(update_banners(request.user, request.data["revision"], request.data["banners"])))

    def post(self, request):
        if not request.user.has_perm("cms.publish_bannerset"):
            raise PermissionDenied("مجوز انتشار بنر ندارید.")
        if not isinstance(request.data, dict) or set(request.data) != {"revision"}:
            raise ValidationError("نسخهٔ بنرها را ارسال کنید.")
        return Response(data_for(update_banners(request.user, request.data["revision"], publish=True)))


class BannerVideoUploadView(OwnerAPIView):
    http_method_names = ["post", "options"]

    def post(self, request):
        from cms.services.video_service import upload_video

        if not request.user.is_staff or not request.user.has_perm("cms.change_bannerset"):
            raise PermissionDenied("مجوز ویرایش بنر ندارید.")
        asset = upload_video(request.user, request.FILES.get("video"))
        return Response({"id": str(asset.pk), "url": asset.file.url, "width": asset.width, "height": asset.height, "duration": asset.duration}, status=201)
