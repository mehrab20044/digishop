import copy
import re

from django.db import transaction
from rest_framework.exceptions import ValidationError

from cms.models import SiteTheme
from cms.services.page_service import check_revision
from cms.services.validation import image_id, safe_link, text

DEFAULT_THEME = {
    "primary": "#176b61", "background": "#ffffff", "surface": "#f0f7f5", "text": "#17212d",
    "page_width": "standard", "font": "tahoma",
    "banner": {"enabled": True, "title": "یک انتخاب هوشمند، برای هر روز تو.", "text": "محصولات را ببین و انتخاب مناسب خودت را پیدا کن.", "image_id": None, "button_label": "دیدن محصولات", "button_href": "/products"},
}


def luminance(color):
    values = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in values]
    return sum(
        value * weight
        for value, weight in zip(
            linear,
            [.2126, .7152, .0722],
            strict=True,
        )
    )

def validate_theme(data):
    if not isinstance(data, dict) or set(data) != set(DEFAULT_THEME):
        raise ValidationError("ساختار تنظیمات ظاهر معتبر نیست.")
    result = copy.deepcopy(data)
    for key in ("primary", "background", "surface", "text"):
        if not isinstance(result[key], str) or not re.fullmatch(r"#[a-fA-F0-9]{6}", result[key]):
            raise ValidationError({key: "رنگ معتبر شش‌رقمی انتخاب کنید."})
        result[key] = result[key].lower()
    for background in ("background", "surface"):
        values = sorted([luminance(result["text"]), luminance(result[background])])
        if (values[1] + .05) / (values[0] + .05) < 4.5:
            raise ValidationError({"text": "رنگ متن نسبت به پس‌زمینه خوانا نیست؛ رنگ تیره‌تر یا روشن‌تر انتخاب کنید."})
    if result["page_width"] not in {"compact", "standard", "wide"} or result["font"] not in {"tahoma", "system"}:
        raise ValidationError("قالب انتخاب‌شده معتبر نیست.")
    banner = result["banner"]
    allowed = {"enabled", "title", "text", "image_id", "button_label", "button_href"}
    if not isinstance(banner, dict) or set(banner) != allowed or type(banner["enabled"]) is not bool:
        raise ValidationError("ساختار بنر معتبر نیست.")
    banner["title"] = text(banner["title"], 160, banner["enabled"])
    banner["text"] = text(banner["text"], 2000)
    banner["image_id"] = image_id(banner["image_id"])
    banner["button_label"] = text(banner["button_label"], 80)
    banner["button_href"] = safe_link(banner["button_href"]) if banner["button_label"] else "/products"
    return result


def get_theme():
    row, _ = SiteTheme.objects.get_or_create(pk=1, defaults={"draft": copy.deepcopy(DEFAULT_THEME), "published": copy.deepcopy(DEFAULT_THEME)})
    return row


@transaction.atomic
def update_theme(actor, revision, data=None, publish=False):
    get_theme()
    row = SiteTheme.objects.select_for_update().get(pk=1)
    check_revision(row, revision)
    if data is not None:
        row.draft = validate_theme(data)
    if publish:
        row.published = validate_theme(row.draft)
    row.revision += 1
    row.updated_by = actor
    row.save()
    return row


def theme_document(config):
    from cms.models import PageImage
    result = copy.deepcopy(config or DEFAULT_THEME)
    image = PageImage.objects.filter(pk=result["banner"].get("image_id")).first() if result["banner"].get("image_id") else None
    result["banner"]["image_url"] = image.file.url if image else None
    result["button_text"] = "#ffffff" if luminance(result["primary"]) < .179 else "#111111"
    return result
