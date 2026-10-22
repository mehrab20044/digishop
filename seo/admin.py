from django.contrib import admin
from django.core import signing
from django.db import transaction
from django.template.response import TemplateResponse

from seo.models import SEOSettings, SEOSettingsLog
from seo.services.seo_services import SEOService, SEOSettingsConflict


@admin.register(SEOSettings)
class SEOSettingsAdmin(admin.ModelAdmin):
    list_display = ("allow_crawling", "version")

    def has_add_permission(self, request):
        return request.user.is_superuser and not SEOSettings.objects.exists()

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    def changeform_view(
        self,
        request,
        object_id=None,
        form_url="",
        extra_context=None,
    ):
        if request.method == "POST" and object_id:
            obj = self.get_object(request, object_id)

            if obj is not None and self.has_change_permission(request, obj):
                old_value = obj.allow_crawling
                current_version = obj.version

                form_class = self.get_form(request, obj)
                form = form_class(
                    request.POST,
                    request.FILES,
                    instance=obj,
                )

                if form.is_valid():
                    new_value = form.cleaned_data["allow_crawling"]

                    if new_value != old_value:
                        confirmation = request.POST.get(
                            "_seo_confirmation",
                            "",
                        )

                        expected_data = {
                            "user_id": request.user.pk,
                            "object_id": str(obj.pk),
                            "old_value": old_value,
                            "new_value": new_value,
                            "version": current_version,
                        }

                        try:
                            confirmed_data = signing.loads(
                                confirmation,
                                salt="seo-crawl-confirmation",
                                max_age=300,
                            )
                        except signing.BadSignature:
                            confirmed_data = None

                        if confirmed_data != expected_data:
                            token = signing.dumps(
                                expected_data,
                                salt="seo-crawl-confirmation",
                            )

                            context = {
                                **self.admin_site.each_context(request),
                                "title": "تأیید تغییر اجازه خزش",
                                "old_value": old_value,
                                "new_value": new_value,
                                "object_id": object_id,
                                "original_post": request.POST,
                                "confirmation_token": token,
                            }

                            return TemplateResponse(
                                request,
                                "admin/seo/confirm_change.html",
                                context,
                            )

                        request._seo_expected_version = current_version

        try:
            return super().changeform_view(
                request,
                object_id=object_id,
                form_url=form_url,
                extra_context=extra_context,
            )
        except SEOSettingsConflict:
            context = {
                **self.admin_site.each_context(request),
                "title": "تداخل در تغییر تنظیمات",
                "old_value": None,
                "new_value": None,
                "object_id": object_id,
                "conflict": True,
            }

            return TemplateResponse(
                request,
                "admin/seo/confirm_change.html",
                context,
                status=409,
            )

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        if not change:
            super().save_model(request, obj, form, change)
            return

        expected_version = getattr(
            request,
            "_seo_expected_version",
            None,
        )

        if expected_version is None:
            # No actual change to allow_crawling.
            return

        updated = SEOService.update_crawling(
            expected_version=expected_version,
            allow_crawling=obj.allow_crawling,
            user=request.user,
        )

        obj.version = updated.version
        obj.allow_crawling = updated.allow_crawling


@admin.register(SEOSettingsLog)
class SEOSettingsLogAdmin(admin.ModelAdmin):
    list_display = (
        "changed_by",
        "old_value",
        "new_value",
        "changed_at",
    )

    readonly_fields = (
        "changed_by",
        "old_value",
        "new_value",
        "changed_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False
