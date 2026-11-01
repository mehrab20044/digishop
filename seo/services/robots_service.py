import hashlib
import json

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from seo.models import RobotsDocument
from seo.services.robots_engine import render_document, validate_document


class RobotsConflict(Exception):
    pass


def current_document():
    row = RobotsDocument.objects.filter(pk=1).first()
    if row is not None:
        return row
    # Recovery after a fresh test DB flush; existing installations seed in migration.
    from seo.services.page_rules import build_robots
    rules = []
    for line in build_robots().splitlines():
        if line.startswith(("Allow: ", "Disallow: ")):
            action, path = line.split(": ", 1)
            rules.append({"id": f"legacy-{len(rules)}", "action": action.lower(), "scope": "pattern", "path": path, "enabled": True})
    document = {"version": 1, "groups": [{"id": "all", "agent": "*", "enabled": True, "rules": rules}], "sitemaps": []}
    row, _ = RobotsDocument.objects.get_or_create(pk=1, defaults={"draft": document, "published": document, "published_at": timezone.now()})
    return row


def document_data(row):
    return {
        "draft": row.draft, "published": row.published, "revision": row.revision,
        "published_revision": row.published_revision,
        "updated_at": row.updated_at, "published_at": row.published_at,
        "draft_text": render_document(row.draft), "published_text": render_document(row.published),
        "unpublished": row.draft != row.published,
    }


@transaction.atomic
def update_document(*, actor, expected_revision, document=None, action="save"):
    if not actor.is_active or not actor.has_perm("seo.change_seosettings"):
        raise PermissionDenied("اجازهٔ تغییر تنظیمات سئو را ندارید.")
    if action not in {"save", "publish", "reset"}:
        raise ValueError("Invalid action")
    current_document()
    row = RobotsDocument.objects.select_for_update().get(pk=1)
    if row.revision != expected_revision:
        raise RobotsConflict("تنظیمات هم‌زمان تغییر کرده‌اند. ابتدا نسخهٔ تازه را دریافت کنید.")
    cleaned = validate_document(row.published if action == "reset" else document)
    old_hash = hashlib.sha256(render_document(row.published).encode()).hexdigest()
    row.draft = cleaned
    row.revision += 1
    if action == "publish":
        row.published = cleaned
        row.published_revision = row.revision
        row.published_at = timezone.now()
    row.updated_by = actor
    row.save()
    LogEntry.objects.create(
        user_id=actor.pk, content_type=ContentType.objects.get_for_model(row), object_id="1",
        object_repr="robots.txt", action_flag=CHANGE,
        change_message=json.dumps({"action": action, "revision": row.revision, "published_before": old_hash, "published_after": hashlib.sha256(render_document(row.published).encode()).hexdigest()}),
    )
    return row
