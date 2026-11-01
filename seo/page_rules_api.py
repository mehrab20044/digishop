from django.middleware.csrf import get_token
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from seo.services.index_manager import list_index_targets, bulk_index
from seo.models import PageSearchRule
from seo.dashboard_api import SEOBaseView, can
from seo.services.page_rules import RuleConflict, save_rule


class RuleInput(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["home", "catalog", "directory", "product", "category", "page"])
    object_id = serializers.IntegerField(min_value=0)
    expected_version = serializers.IntegerField(min_value=0)
    crawl = serializers.ChoiceField(choices=["inherit", "allow", "block"])
    indexing = serializers.ChoiceField(choices=["inherit", "index", "noindex"])


class ListingInput(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["product", "category", "page", "system"], default="product")
    search = serializers.CharField(max_length=100, allow_blank=True, default="")
    page = serializers.IntegerField(min_value=1, max_value=1000000, default=1)
    page_size = serializers.ChoiceField(choices=[20, 50, 100], default=20)
    indexing = serializers.ChoiceField(choices=["all", "inherit", "index", "noindex"], default="all")
    category = serializers.IntegerField(min_value=1, required=False)


class BulkItem(serializers.Serializer):
    indexing = serializers.ChoiceField(choices=["inherit", "index", "noindex"], required=False)
    kind = serializers.ChoiceField(choices=["home", "catalog", "directory", "product", "category", "page"])
    object_id = serializers.IntegerField(min_value=0)
    expected_version = serializers.IntegerField(min_value=0)


class BulkInput(serializers.Serializer):
    action = serializers.ChoiceField(choices=["bulk_index"])
    indexing = serializers.ChoiceField(choices=["inherit", "index", "noindex"])
    items = BulkItem(many=True, allow_empty=False, max_length=100)


class PageRulesView(SEOBaseView):
    http_method_names = ["get", "post", "head", "options"]

    def get(self, request):
        if not (can(request.user, "view") or can(request.user, "change")):
            raise PermissionDenied("اجازهٔ مشاهدهٔ سئو را ندارید.")
        serializer = ListingInput(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        result = list_index_targets(**serializer.validated_data)
        result["can_change"] = can(request.user, "change")
        result["csrfToken"] = get_token(request)
        return Response(result)

    def post(self, request):
        if not can(request.user, "change"):
            raise PermissionDenied("اجازهٔ تغییر سئو را ندارید.")
        if request.data.get("action") == "bulk_index":
            serializer = BulkInput(data=request.data)
            serializer.is_valid(raise_exception=True)
            values = serializer.validated_data
            try:
                return Response(bulk_index(actor=request.user, items=values["items"], indexing=values["indexing"]))
            except RuleConflict as exc:
                return Response({"detail": str(exc)}, status=409)
        serializer = RuleInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        previous = PageSearchRule.objects.filter(kind=values["kind"], object_id=values["object_id"]).first()
        if values["crawl"] != (previous.crawl if previous else "inherit"):
            raise serializers.ValidationError("قوانین خزش را از ویرایشگر robots.txt تغییر دهید؛ این بخش فقط برای ایندکس است.")
        try:
            return Response(save_rule(actor=request.user, **values))
        except RuleConflict as exc:
            return Response({"detail": str(exc)}, status=409)
