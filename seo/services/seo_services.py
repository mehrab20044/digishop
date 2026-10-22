from django.db import transaction
from django.db.models import F

from seo.models import SEOSettings, SEOSettingsLog


class SEOSettingsConflict(Exception):
    """Raised when SEO settings have changed since they were read."""


class SEOService:
    @staticmethod
    @transaction.atomic
    def update_crawling(*, expected_version, allow_crawling, user):
        current = SEOSettings.objects.get(pk=1)

        if current.version != expected_version:
            raise SEOSettingsConflict(
                "تنظیمات سئو تغییر کرده‌اند. صفحه را دوباره بارگذاری کنید."
            )

        if current.allow_crawling == allow_crawling:
            return current

        updated = SEOSettings.objects.filter(
            pk=1,
            version=expected_version,
        ).update(
            allow_crawling=allow_crawling,
            version=F("version") + 1,
        )

        if updated != 1:
            raise SEOSettingsConflict(
                "تنظیمات سئو تغییر کرده‌اند. صفحه را دوباره بارگذاری کنید."
            )

        SEOSettingsLog.objects.create(
            changed_by=user,
            old_value=current.allow_crawling,
            new_value=allow_crawling,
        )

        return SEOSettings.objects.get(pk=1)
