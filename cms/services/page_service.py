import re
import unicodedata

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify
from rest_framework.exceptions import APIException, NotFound, ValidationError

from cms.models import Page
from cms.services.validation import validate_blocks


class RevisionConflict(APIException):
    status_code = 409
    default_detail = "صفحه در جای دیگری تغییر کرده است؛ نسخهٔ تازه را دریافت کنید."
    default_code = "revision_conflict"


def normalize_slug(value):
    value = unicodedata.normalize("NFKC", value).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩كي", "01234567890123456789کی"))
    return slugify(re.sub(r"[\s\u200c\u200d_]+", "-", value), allow_unicode=True).strip("-")[:110].rstrip("-")


def field_text(data, key, limit, default="", required=False):
    value = data.get(key, default)
    if not isinstance(value, str) or len(value) > limit or "\x00" in value or (required and not value.strip()):
        raise ValidationError({key: "مقدار این فیلد معتبر نیست."})
    return value.strip()


def check_revision(page, revision):
    if type(revision) is not int or revision != page.revision:
        raise RevisionConflict()


def snapshot(page):
    return {"title": page.title, "slug": page.slug, "seo_title": page.seo_title, "seo_description": page.seo_description, "blocks": page.blocks, "layout": page.layout, "footer_visible": page.footer_visible, "footer_label": page.footer_label, "footer_order": page.footer_order}


def lock_page(page_id):
    try:
        return Page.objects.select_for_update().get(pk=page_id)
    except Page.DoesNotExist as exc:
        raise NotFound("صفحه پیدا نشد.") from exc


@transaction.atomic
def save_page(actor, data, page_id=None):
    allowed = {"title", "slug", "seo_title", "seo_description", "blocks", "revision", "layout", "footer_visible", "footer_label", "footer_order"}
    if not isinstance(data, dict) or set(data) - allowed:
        raise ValidationError("فیلد غیرمجاز در درخواست صفحه.")
    page = lock_page(page_id) if page_id is not None else Page()
    if page_id is not None:
        check_revision(page, data.get("revision"))
    page.title = field_text(data, "title", 160, page.title or "", True)
    page.seo_title = field_text(data, "seo_title", 180, page.seo_title)
    page.seo_description = field_text(data, "seo_description", 320, page.seo_description)
    requested = field_text(data, "slug", 120, page.slug)
    if page.published and requested != page.slug:
        raise ValidationError({"slug": "نامک صفحه پس از اولین انتشار ثابت است تا لینک‌ها خراب نشوند."})
    slug = normalize_slug(requested or page.title)
    if not slug:
        raise ValidationError({"slug": "نامک باید شامل حرف یا عدد باشد."})
    if not requested and page_id is None:
        base, suffix = slug, 2
        while Page.objects.filter(slug=slug).exists():
            slug = f"{base}-{suffix}"
            suffix += 1
    page.slug = slug
    page.blocks = validate_blocks(data.get("blocks", page.blocks))
    layout = data.get("layout", page.layout)
    if layout not in {"simple", "about", "landing"}:
        raise ValidationError({"layout": "قالب معتبر نیست."})
    page.layout = layout
    visible = data.get("footer_visible", page.footer_visible)
    order = data.get("footer_order", page.footer_order)
    if type(visible) is not bool or type(order) is not int or not 0 <= order <= 9999:
        raise ValidationError("تنظیمات نمایش در فوتر معتبر نیست.")
    page.footer_visible, page.footer_order = visible, order
    page.footer_label = field_text(data, "footer_label", 80, page.footer_label)
    page.updated_by = actor
    if page_id is not None:
        page.revision += 1
    try:
        with transaction.atomic():
            page.save()
    except IntegrityError as exc:
        raise ValidationError({"slug": "این نامک قبلاً استفاده شده؛ نامک دیگری انتخاب کنید."}) from exc
    return page


@transaction.atomic
def set_publication(actor, page_id, revision, publish):
    page = lock_page(page_id)
    check_revision(page, revision)
    if publish:
        if not any(block.get("enabled") and block.get("type") != "spacer" for block in page.blocks):
            raise ValidationError("برای انتشار حداقل یک بخش محتوای روشن لازم است.")
        page.blocks = validate_blocks(page.blocks)
        page.published = snapshot(page)
        page.published_at = timezone.now()
    page.is_published = publish
    page.updated_by = actor
    page.revision += 1
    page.save()
    return page
