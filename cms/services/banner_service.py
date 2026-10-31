import copy
import re
import uuid
from datetime import timezone as dt_timezone

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from cms.models import BannerSet, BannerVideo, PageImage
from cms.services.page_service import check_revision
from cms.services.theme_service import get_theme
from cms.services.validation import image_id, safe_link, text


def timestamp(value):
    if value in (None, ""):
        return None
    if not isinstance(value, str) or len(value) > 60:
        raise ValidationError("زمان نمایش بنر معتبر نیست.")
    try:
        parsed = parse_datetime(value)
    except ValueError:
        parsed = None
    if parsed is None or timezone.is_naive(parsed):
        raise ValidationError("زمان بنر باید همراه منطقهٔ زمانی ارسال شود.")
    return parsed.astimezone(dt_timezone.utc).isoformat()


EXTRA = {"media_type": "image", "video_id": None, "mobile_video_id": None, "layout": "split", "fit": "cover", "position": "center", "height": "standard", "width": "full", "text_color": "light", "overlay": 35, "interval": 6, "autoplay": False, "loop": True}


def normalized(row):
    return {**EXTRA, **row}


def video_id(value):
    if value is None:
        return None
    try:
        ident = uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError("شناسهٔ ویدیو معتبر نیست.") from exc
    if not BannerVideo.objects.filter(pk=ident).exists():
        raise ValidationError("ویدیو پیدا نشد؛ دوباره بارگذاری کنید.")
    return str(ident)


def validate_banners(rows):
    if not isinstance(rows, list) or len(rows) > 40:
        raise ValidationError("حداکثر ۴۰ بنر مجاز است.")
    result, seen = [], set()
    fields = {"id", "placement", "title", "body", "image_id", "mobile_image_id", "alt", "href", "button_label", "enabled", "show_text", "start_at", "end_at"}
    for row in rows:
        if not isinstance(row, dict) or not fields <= set(row) or set(row) - fields - set(EXTRA):
            raise ValidationError("ساختار بنر معتبر نیست.")
        row = normalized(row)
        ident = row["id"]
        if not isinstance(ident, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", ident) or ident in seen:
            raise ValidationError("شناسهٔ بنرها باید یکتا باشد.")
        seen.add(ident)
        clean = copy.deepcopy(row)
        if not isinstance(row["placement"], str) or row["placement"] not in {"hero", "tiles", "top","bottom"} or type(row["enabled"]) is not bool or type(row["show_text"]) is not bool:
            raise ValidationError("جایگاه یا وضعیت بنر معتبر نیست.")
        clean["title"] = text(row["title"], 160, True)
        clean["body"] = text(row["body"], 2000)
        clean["image_id"] = image_id(row["image_id"])
        clean["mobile_image_id"] = image_id(row["mobile_image_id"])
        clean["alt"] = text(row["alt"], 250, bool(clean["image_id"] or clean["mobile_image_id"]))
        clean["href"] = safe_link(row["href"]) if row["href"] else ""
        clean["button_label"] = text(row["button_label"], 80)
        clean["start_at"], clean["end_at"] = timestamp(row["start_at"]), timestamp(row["end_at"])
        if clean["start_at"] and clean["end_at"] and parse_datetime(clean["start_at"]) >= parse_datetime(clean["end_at"]):
            raise ValidationError("پایان نمایش بنر باید بعد از شروع آن باشد.")
        for key, allowed in {"media_type": {"image", "video"}, "layout": {"split", "overlay"}, "fit": {"cover", "contain"}, "position": {"right", "center", "left"}, "height": {"compact", "standard", "tall", "natural"}, "width": {"full", "contained"}, "text_color": {"light", "dark"}}.items():
            if not isinstance(row[key], str) or row[key] not in allowed:
                raise ValidationError("تنظیمات چیدمان بنر معتبر نیست.")
        for key, low, high in [("overlay", 0, 80), ("interval", 3, 30)]:
            if type(row[key]) is not int or not low <= row[key] <= high:
                raise ValidationError("مقدار تیرگی یا زمان اسلاید معتبر نیست.")
        if any(type(row[key]) is not bool for key in ("autoplay", "loop")):
            raise ValidationError("تنظیمات پخش معتبر نیست.")
        clean["video_id"], clean["mobile_video_id"] = video_id(row["video_id"]), video_id(row["mobile_video_id"])
        if clean["media_type"] == "video" and (not clean["video_id"] or not clean["alt"]):
            raise ValidationError("ویدیوی اصلی و توضیح دسترس‌پذیر آن را وارد کنید.")
        result.append(clean)
    return result


def legacy_banners():
    old = get_theme().published.get("banner", {})
    if not old.get("enabled"):
        return []
    return [{"id": "legacy-home", "placement": "hero", "title": old.get("title") or "فروشگاه", "body": old.get("text", ""), "image_id": old.get("image_id"), "mobile_image_id": None, "alt": old.get("title") or "بنر فروشگاه", "href": old.get("button_href", "/products"), "button_label": old.get("button_label", ""), "enabled": True, "show_text": True, "start_at": None, "end_at": None}]


def get_banners():
    row = BannerSet.objects.filter(pk=1).first()
    if row:
        return row
    legacy = legacy_banners()
    row, _ = BannerSet.objects.get_or_create(pk=1, defaults={"draft": legacy, "published": legacy})
    return row


@transaction.atomic
def update_banners(actor, revision, rows=None, publish=False):
    get_banners()

    record = BannerSet.objects.select_for_update().get(pk=1)
    check_revision(record, revision)

    if rows is not None:
        record.draft = validate_banners(rows)

    if publish:
        published = validate_banners(record.draft)

        for row in published:
            if not row["enabled"]:
                continue

            is_video = row.get("media_type") == "video"

            has_media = (
                row.get("video_id")
                if is_video
                else row.get("image_id") or row.get("mobile_image_id")
            )

            if not has_media:
                raise ValidationError(
                    f'برای بنر «{row["title"]}» فایل انتخاب کنید.'
                )

            if not row["href"]:
                raise ValidationError(
                    f'لینک مقصد بنر «{row["title"]}» را وارد کنید.'
                )

        record.published = published

    record.revision += 1
    record.updated_by = actor
    record.save()

    return record


def banner_documents(rows):
    rows = [normalized(row) for row in rows]
    ids = {row[key] for row in rows for key in ("image_id", "mobile_image_id") if row.get(key)}
    images = {str(image.pk): image.file.url for image in PageImage.objects.filter(pk__in=ids)}
    video_ids = {row[key] for row in rows for key in ("video_id", "mobile_video_id") if row.get(key)}
    videos = {str(video.pk): video.file.url for video in BannerVideo.objects.filter(pk__in=video_ids)}
    return [{**row, "image_url": images.get(row["image_id"]), "mobile_image_url": images.get(row["mobile_image_id"]) or images.get(row["image_id"]), "video_url": videos.get(row["video_id"]), "mobile_video_url": videos.get(row["mobile_video_id"]) or videos.get(row["video_id"])} for row in rows]


def public_banners(now=None):
    now = now or timezone.now()
    active, transitions = [], []
    for row in get_banners().published:
        if not row["enabled"]:
            continue
        start = parse_datetime(row["start_at"]) if row["start_at"] else None
        end = parse_datetime(row["end_at"]) if row["end_at"] else None
        transitions.extend(value for value in (start, end) if value and value > now)
        if (start is None or start <= now) and (end is None or now < end):
            active.append(row)
    docs = banner_documents(active)
    return {**{placement: [row for row in docs if row["placement"] == placement] for placement in ("hero", "tiles", "top", "bottom")}, "next_change_at": min(transitions).isoformat() if transitions else None, "server_time": now.isoformat()}
