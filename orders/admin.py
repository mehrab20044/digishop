from django.contrib import admin

from orders.models import StoreSettings


@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    list_display = ("shipping_cost", "updated_at")
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return (
            super().has_add_permission(request)
            and not StoreSettings.objects.exists()
        )

    def has_delete_permission(self, request, obj=None):
        return False