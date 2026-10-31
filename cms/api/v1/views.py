from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response

from cms.api.v1.serializers import (
    PageDetailSerializer,
    PageSummarySerializer,
    PageWriteSerializer,
    PublicationSerializer,
)
from cms.models import Page
from cms.services.image_service import upload_image
from cms.services.page_service import save_page, set_publication
from dashboard.api.v1.views import OwnerAPIView


def require_permission(user, action):
    if not user.is_authenticated or not user.is_active or not user.is_staff or not user.has_perm(f"cms.{action}_page"):
        raise PermissionDenied("مجوز این عملیات روی صفحات را ندارید.")


class PageOwnerView(OwnerAPIView):
    http_method_names = ["get", "head", "post", "patch", "options"]
    parser_classes = [JSONParser]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_permission(request.user, "view")


class PageListCreateView(PageOwnerView):
    def get(self, request):
        queryset = Page.objects.all()
        search = request.query_params.get("search", "")[:160]
        if search:
            queryset = queryset.filter(title__icontains=search)
        pager = PageNumberPagination()
        pager.page_size = 20
        rows = pager.paginate_queryset(queryset, request)
        return pager.get_paginated_response(PageSummarySerializer(rows, many=True).data)

    def post(self, request):
        require_permission(request.user, "add")
        serializer = PageWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        page = save_page(request.user, serializer.validated_data)
        return Response(PageDetailSerializer(page).data, status=status.HTTP_201_CREATED)


class PageDetailView(PageOwnerView):
    def get(self, request, pk):
        from django.shortcuts import get_object_or_404
        page = get_object_or_404(Page, pk=pk)
        return Response(PageDetailSerializer(page).data)

    def patch(self, request, pk):
        require_permission(request.user, "change")
        serializer = PageWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        page = save_page(request.user, serializer.validated_data, page_id=pk)
        return Response(PageDetailSerializer(page).data)


class PagePublishView(PageOwnerView):
    publish = True

    def post(self, request, pk):
        require_permission(request.user, "publish")
        serializer = PublicationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        page = set_publication(request.user, pk, serializer.validated_data["revision"], self.publish)
        return Response(PageDetailSerializer(page).data)


class PageHideView(PagePublishView):
    publish = False


class PageImageUploadView(OwnerAPIView):
    http_method_names = ["post", "options"]
    parser_classes = [MultiPartParser]

    def post(self, request):
        if not (request.user.has_perm("cms.add_page") or request.user.has_perm("cms.change_page") or request.user.has_perm("cms.change_sitetheme") or request.user.has_perm("cms.change_bannerset")):
            raise PermissionDenied("مجوز بارگذاری تصویر ندارید.")
        image = upload_image(request.user, request.FILES.get("image"))
        return Response({"id": str(image.pk), "url": image.file.url, "width": image.width, "height": image.height}, status=201)
