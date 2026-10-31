import json
import re
from urllib.parse import urlsplit
from uuid import UUID

from rest_framework.exceptions import ValidationError

from cms.models import PageImage


def fail(message):
    raise ValidationError({"blocks": message})


def text(value, limit, required=False):
    if not isinstance(value, str) or len(value) > limit or "\x00" in value:
        fail(f"متن باید حداکثر {limit} کاراکتر باشد.")
    if required and not value.strip():
        fail("متن الزامی را وارد کنید.")
    return value.strip()


def safe_link(value):
    value = text(value, 1000, True)
    if re.search(r"[\x00-\x20\x7f\\]", value):
        fail("آدرس دکمه معتبر نیست؛ فاصله‌ها را کدگذاری کنید.")
    if value.startswith("/") and not value.startswith("//"):
        return value
    if re.fullmatch(r"#[A-Za-z][A-Za-z0-9_-]*", value):
        return value
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password:
            _ = parsed.port
            return value
    except ValueError:
        pass
    fail("آدرس دکمه باید مسیر داخلی مانند /products یا لینک کامل https باشد.")


def button_list(value):
    if not isinstance(value, list) or len(value) > 4:
        fail("هر بخش حداکثر چهار دکمه می‌پذیرد.")
    result = []
    for item in value:
        if not isinstance(item, dict) or set(item) - {"label", "href", "style"}:
            fail("ساختار دکمه معتبر نیست.")
        style = item.get("style", "primary")
        if style not in {"primary", "outline"}:
            fail("ظاهر دکمه معتبر نیست.")
        result.append({"label": text(item.get("label"), 80, True), "href": safe_link(item.get("href")), "style": style})
    return result


def image_id(value):
    if value in (None, ""):
        return None
    try:
        ident = UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        fail("شناسهٔ تصویر معتبر نیست.")
    if not PageImage.objects.filter(pk=ident).exists():
        fail("تصویر انتخاب‌شده پیدا نشد؛ دوباره بارگذاری کنید.")
    return str(ident)


def validate_blocks(value):
    if not isinstance(value, list) or len(value) > 60:
        fail("صفحه حداکثر ۶۰ بخش می‌پذیرد.")
    try:
        if len(json.dumps(value, ensure_ascii=False).encode()) > 300000:
            fail("حجم محتوای صفحه بیش از حد مجاز است.")
    except (TypeError, ValueError):
        fail("محتوا معتبر نیست.")
    seen, result = set(), []
    for block in value:
        if not isinstance(block, dict) or set(block) - {"id", "type", "enabled", "data"}:
            fail("ساختار بخش معتبر نیست.")
        ident = block.get("id")
        if not isinstance(ident, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", ident) or ident in seen:
            fail("شناسه‌های بخش‌ها باید معتبر و یکتا باشند.")
        seen.add(ident)
        kind, data = block.get("type"), block.get("data")
        enabled = block.get("enabled", True)
        if type(enabled) is not bool or not isinstance(data, dict):
            fail("ساختار بخش معتبر نیست.")
        allowed = {
            "hero": {"title", "text", "image_id", "buttons"},
            "text": {"heading", "body", "align"},
            "image": {"image_id", "alt", "caption"},
            "buttons": {"items"}, "spacer": {"height"},
        }
        if kind not in allowed or set(data) - allowed[kind]:
            fail("نوع یا فیلدهای بخش مجاز نیست.")
        if kind == "hero":
            clean = {"title": text(data.get("title", ""), 160, True), "text": text(data.get("text", ""), 2000), "image_id": image_id(data.get("image_id")), "buttons": button_list(data.get("buttons", []))}
        elif kind == "text":
            align = data.get("align", "right")
            if align not in {"right", "center"}:
                fail("چیدمان متن معتبر نیست.")
            clean = {"heading": text(data.get("heading", ""), 160), "body": text(data.get("body", ""), 15000, True), "align": align}
        elif kind == "image":
            image = image_id(data.get("image_id"))
            if enabled and not image:
                fail("برای بخش تصویر، عکس انتخاب کنید یا بخش را خاموش کنید.")
            clean = {"image_id": image, "alt": text(data.get("alt", ""), 250, enabled), "caption": text(data.get("caption", ""), 500)}
        elif kind == "buttons":
            clean = {"items": button_list(data.get("items", []))}
            if enabled and not clean["items"]:
                fail("حداقل یک دکمه اضافه کنید یا بخش را خاموش کنید.")
        else:
            height = data.get("height", 32)
            if type(height) is not int or not 8 <= height <= 120:
                fail("فاصله باید بین ۸ تا ۱۲۰ باشد.")
            clean = {"height": height}
        result.append({"id": ident, "type": kind, "enabled": enabled, "data": clean})
    return result
