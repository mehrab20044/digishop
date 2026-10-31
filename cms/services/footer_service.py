from copy import deepcopy

from django.contrib.admin.models import CHANGE, LogEntry
from django.db import transaction
from rest_framework import serializers

from cms.models import SiteFooter
from cms.services.validation import safe_link

DEFAULT_FOOTER = {
    "name": "دیجی‌شاپ",
    "description": "محصولات را بررسی کنید و انتخاب مناسب خود را پیدا کنید.",
    "phone": "",
    "email": "",
    "hours": "",
    "address": "",
    "copyright": "",
    "services": [
        {
            "title": "انتخاب آگاهانه",
            "text": "بررسی مشخصات و تنوع کالا",
            "icon": "shield",
        },
        {
            "title": "پیگیری سفارش",
            "text": "مشاهده وضعیت در حساب مشتری",
            "icon": "truck",
        },
        {"title": "آدرس‌های شما", "text": "مدیریت نشانی‌های تحویل", "icon": "return"},
        {"title": "خرید بعدی", "text": "ذخیره کالا برای بررسی بعدی", "icon": "payment"},
    ],
    "socials": [],
    "columns": [
        {
            "title": "راهنمای خرید",
            "links": [
                {"title": "محصولات", "url": "/products"},
                {"title": "سبد خرید", "url": "/cart"},
                {"title": "پیگیری سفارش", "url": "/account?tab=orders"},
            ],
        },
        {
            "title": "حساب مشتری",
            "links": [
                {"title": "حساب کاربری", "url": "/account"},
                {"title": "آدرس‌ها", "url": "/account?tab=addresses"},
                {"title": "علاقه‌مندی‌ها", "url": "/account?tab=favorites"},
            ],
        },
    ],
}


class FooterLink(serializers.Serializer):
    title = serializers.CharField(max_length=80)
    url = serializers.CharField(max_length=1000)

    def validate_url(self, value):
        return safe_link(value)


class FooterColumn(serializers.Serializer):
    title = serializers.CharField(max_length=80)
    links = FooterLink(many=True, max_length=8)


class FooterService(serializers.Serializer):
    title = serializers.CharField(max_length=80)
    text = serializers.CharField(max_length=160, allow_blank=True)
    icon = serializers.ChoiceField(choices=["shield", "truck", "return", "payment"])


class FooterConfig(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(max_length=2000, allow_blank=True)
    phone = serializers.RegexField(r"^[+0-9 ()-]{0,32}$", allow_blank=True)
    email = serializers.EmailField(max_length=254, allow_blank=True)
    hours = serializers.CharField(max_length=200, allow_blank=True)
    address = serializers.CharField(max_length=500, allow_blank=True)
    copyright = serializers.CharField(max_length=300, allow_blank=True)
    columns = FooterColumn(many=True, max_length=4)
    services = FooterService(many=True, max_length=4)
    socials = FooterLink(many=True, max_length=8)

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) != set(self.fields):
            raise serializers.ValidationError(
                "تمام فیلدهای تنظیمات فوتر را ارسال کنید."
            )
        return super().to_internal_value(data)


def footer_data():
    row = SiteFooter.objects.first()
    return {
        "config": row.config if row and row.config else deepcopy(DEFAULT_FOOTER),
        "revision": row.revision if row else 1,
    }


@transaction.atomic
def update_footer(actor, revision, config):
    validated = FooterConfig(data=config)
    validated.is_valid(raise_exception=True)
    SiteFooter.objects.get_or_create(
        pk=1, defaults={"config": deepcopy(DEFAULT_FOOTER)}
    )
    row = SiteFooter.objects.select_for_update().get(pk=1)
    if type(revision) is not int or row.revision != revision:
        raise serializers.ValidationError(
            "تنظیمات تغییر کرده؛ نسخه جدید را دریافت کنید."
        )
    row.config = validated.validated_data
    row.revision += 1
    row.save(update_fields=["config", "revision", "updated_at"])
    LogEntry.objects.log_actions(
        user_id=actor.pk,
        queryset=SiteFooter.objects.filter(pk=1),
        action_flag=CHANGE,
        change_message="Updated store footer",
    )
    return {"config": row.config, "revision": row.revision}
