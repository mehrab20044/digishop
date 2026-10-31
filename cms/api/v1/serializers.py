from urllib.parse import quote

from rest_framework import serializers

from cms.models import Page, PageImage


class PageWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=160)
    slug = serializers.CharField(max_length=120, required=False, allow_blank=True)
    seo_title = serializers.CharField(max_length=180, required=False, allow_blank=True)
    seo_description = serializers.CharField(max_length=320, required=False, allow_blank=True)
    layout = serializers.ChoiceField(choices=["simple", "about", "landing"], required=False)
    footer_visible = serializers.BooleanField(required=False)
    footer_label = serializers.CharField(max_length=80, required=False, allow_blank=True)
    footer_order = serializers.IntegerField(min_value=0, max_value=9999, required=False)
    blocks = serializers.JSONField()
    revision = serializers.IntegerField(min_value=1, required=False)

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError({"detail": "فیلد غیرمجاز در درخواست صفحه."})
        return super().to_internal_value(data)


class PublicationSerializer(serializers.Serializer):
    revision = serializers.IntegerField(min_value=1)


class PageSummarySerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    has_changes = serializers.SerializerMethodField()

    class Meta:
        model = Page
        fields = ["id", "title", "slug", "url", "is_published", "revision", "published_at", "updated_at", "has_changes"]
        read_only_fields = fields

    def get_url(self, obj):
        return "/pages/" + quote(obj.slug, safe="")

    def get_has_changes(self, obj):
        from cms.services.page_service import snapshot
        return bool(obj.published) and obj.published != snapshot(obj)


class PageDetailSerializer(PageSummarySerializer):
    images = serializers.SerializerMethodField()
    slug_locked = serializers.SerializerMethodField()

    class Meta(PageSummarySerializer.Meta):
        fields = PageSummarySerializer.Meta.fields + ["seo_title", "seo_description", "blocks", "images", "slug_locked", "layout", "footer_visible", "footer_label", "footer_order"]
        read_only_fields = fields

    def get_slug_locked(self, obj):
        return bool(obj.published)

    def get_images(self, obj):
        ids = {block.get("data", {}).get("image_id") for block in obj.blocks}
        return {str(image.pk): image.file.url for image in PageImage.objects.filter(pk__in=[value for value in ids if value])}
