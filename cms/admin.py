from django.contrib import admin

from cms.models import Page, PageImage


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "is_published", "updated_at"]
    search_fields = ["title", "slug"]
    readonly_fields = [field.name for field in Page._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PageImage)
class PageImageAdmin(admin.ModelAdmin):
    list_display = ["id", "width", "height", "created_at"]
    readonly_fields = [field.name for field in PageImage._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
