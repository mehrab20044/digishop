"""Entity-bound robots rules. URLs are derived, never accepted as raw directives."""
import json
from urllib.parse import quote

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from seo.models import PageSearchRule, SEOSettings

SYSTEM = {"home": ("صفحهٔ اصلی", "/"), "catalog": ("فهرست محصولات", "/products"), "directory": ("فهرست دسته‌بندی‌ها", "/categories")}


class RuleConflict(Exception):
    pass


def target(kind, object_id):
    from products.models import Category, Product
    from products.services.category_url_service import PREFIX, current_paths
    from cms.views import published_pages
    if kind in SYSTEM and object_id == 0:
        name, path = SYSTEM[kind]
        return {"kind": kind, "object_id": 0, "name": name, "url": path}
    if kind == "product":
        obj = Product.objects.filter(pk=object_id, is_active=True, status=Product.Status.PUBLISHED).first()
        path = f"/products/{object_id}"
    elif kind == "category":
        obj = Category.objects.filter(pk=object_id).first()
        branch = current_paths().get(object_id)
        path = PREFIX + branch if branch else None
    elif kind == "page":
        obj = published_pages().filter(pk=object_id).first()
        path = "/pages/" + obj.slug if obj else None
    else:
        raise NotFound("نوع صفحه معتبر نیست.")
    if obj is None or path is None:
        raise NotFound("صفحهٔ عمومی پیدا نشد.")
    name = obj.published.get("title", obj.title) if kind == "page" else obj.name
    return {"kind": kind, "object_id": object_id, "name": name, "url": quote(path, safe="/")}


def rule_data(item, rule, default):
    crawl = rule.crawl if rule else "inherit"
    return {**item, "crawl": crawl, "indexing": rule.indexing if rule else "inherit", "version": rule.version if rule else 0,
            "effective_crawl": crawl == "allow" or (crawl == "inherit" and default)}


def list_targets(kind, search, page):
    from products.models import Category, Product
    from cms.views import published_pages
    default = SEOSettings.get_settings().allow_crawling
    if kind == "system":
        items = [target(key, 0) for key in SYSTEM if search in SYSTEM[key][0]]
        count = len(items)
    else:
        if kind == "product":
            queryset = Product.objects.filter(is_active=True, status=Product.Status.PUBLISHED)
            if search:
                queryset = queryset.filter(Q(name__icontains=search) | Q(slug__icontains=search))
        elif kind == "category":
            queryset = Category.objects.all()
            if search:
                queryset = queryset.filter(Q(name__icontains=search) | Q(slug__icontains=search))
        elif kind == "page":
            queryset = published_pages()
            # Search the public snapshot, not unpublished draft titles.
            if search:
                queryset = queryset.filter(Q(published__title__icontains=search) | Q(slug__icontains=search))
        else:
            raise ValidationError("نوع صفحه معتبر نیست.")
        count = queryset.count()
        objects = list(queryset.order_by("pk")[(page - 1) * 20:page * 20])
        if kind == "category":
            from products.services.category_url_service import PREFIX, current_paths
            paths = current_paths()
            items = [{"kind": kind, "object_id": obj.pk, "name": obj.name, "url": PREFIX + quote(paths[obj.pk], safe="/")} for obj in objects]
        else:
            items = [{"kind": kind, "object_id": obj.pk,
                      "name": obj.published.get("title", obj.title) if kind == "page" else obj.name,
                      "url": "/pages/" + quote(obj.slug, safe="") if kind == "page" else f"/products/{obj.pk}"} for obj in objects]
    keys = [(item["kind"], item["object_id"]) for item in items]
    rules = {(rule.kind, rule.object_id): rule for rule in PageSearchRule.objects.filter(kind__in={key[0] for key in keys}, object_id__in={key[1] for key in keys})}
    return {"results": [rule_data(item, rules.get((item["kind"], item["object_id"])), default) for item in items],
            "count": count, "page": page, "has_next": page * 20 < count, "default_crawl": default}


@transaction.atomic
def save_rule(*, actor, kind, object_id, expected_version, crawl, indexing):
    if not actor.is_active or not actor.has_perm("seo.change_seosettings"):
        raise PermissionDenied("اجازهٔ تغییر سئو را ندارید.")
    if crawl not in {"inherit", "allow", "block"} or indexing not in {"inherit", "index", "noindex"}:
        raise ValidationError("وضعیت معتبر نیست.")
    SEOSettings.get_settings()
    current = SEOSettings.objects.select_for_update().get(pk=1)
    item = target(kind, object_id)
    rule, _ = PageSearchRule.objects.get_or_create(kind=kind, object_id=object_id)
    if rule.version != expected_version:
        raise RuleConflict("این صفحه هم‌زمان تغییر کرده؛ فهرست را تازه‌سازی کنید.")
    before = {"crawl": rule.crawl, "indexing": rule.indexing}
    after = {"crawl": crawl, "indexing": indexing}
    if before != after:
        rule.crawl, rule.indexing = crawl, indexing
        rule.version += 1
        rule.updated_by = actor
        rule.save()
        LogEntry.objects.create(user_id=actor.pk, content_type=ContentType.objects.get_for_model(rule),
                                object_id=str(rule.pk), object_repr=item["name"][:200], action_flag=CHANGE,
                                change_message=json.dumps({"page": item["url"], "before": before, "after": after}, ensure_ascii=False))
    return rule_data(item, rule, current.allow_crawling)


def apply_index_rule(kind, object_id, robots):
    # Facets and private pages cannot be made indexable by an entity override.
    if not robots.startswith("index"):
        return robots
    rule = PageSearchRule.objects.filter(kind=kind, object_id=object_id).first()
    return "noindex, follow" if rule and rule.indexing == "noindex" else robots


def sitemap_ids(kind, ids):
    from products.models import Product
    from products.services.category_url_service import PREFIX, current_paths
    from cms.views import published_pages
    from seo.services.robots_engine import evaluate
    from seo.services.robots_service import current_document
    ids = set(ids)
    paths = {}
    if kind in SYSTEM:
        if 0 in ids:
            paths[0] = SYSTEM[kind][1]
    elif kind == "product":
        paths = {pk: f"/products/{pk}" for pk in Product.objects.filter(pk__in=ids, is_active=True, status=Product.Status.PUBLISHED).values_list("pk", flat=True)}
    elif kind == "category":
        paths = {pk: PREFIX + quote(path, safe="/") for pk, path in current_paths().items() if pk in ids}
    elif kind == "page":
        paths = {pk: "/pages/" + quote(slug, safe="") for pk, slug in published_pages().filter(pk__in=ids).values_list("pk", "slug")}
    excluded = set(PageSearchRule.objects.filter(kind=kind, object_id__in=ids, indexing="noindex").values_list("object_id", flat=True))
    document = current_document().published
    return {ident for ident, path in paths.items() if ident not in excluded and evaluate(document, path, "Googlebot")["allowed"]}


def build_robots():
    from products.models import CategoryURL, Product
    from products.services.category_url_service import PREFIX, current_paths
    from cms.views import published_pages
    default = SEOSettings.get_settings().allow_crawling
    rules = list(PageSearchRule.objects.exclude(crawl="inherit").order_by("kind", "object_id"))
    lines = ["User-agent: *"]
    # Omit a redundant broad Allow when specific blocks exist, including the root.
    if not default:
        lines.append("Disallow: /")
    elif not rules:
        lines.append("Allow: /")
    ids = {kind: {r.object_id for r in rules if r.kind == kind} for kind in ("product", "category", "page")}
    paths = {(kind, 0): {path} for kind, (_, path) in SYSTEM.items()}
    for pk in Product.objects.filter(pk__in=ids["product"], is_active=True, status=Product.Status.PUBLISHED).values_list("pk", flat=True):
        paths[("product", pk)] = {f"/products/{pk}"}
    branches = current_paths() if ids["category"] else {}
    for pk in ids["category"]:
        if pk in branches:
            paths[("category", pk)] = {PREFIX + quote(branches[pk], safe="/")}
    for pk, branch in CategoryURL.objects.filter(category_id__in=ids["category"]).values_list("category_id", "path"):
        if ("category", pk) in paths:
            paths[("category", pk)].add(PREFIX + quote(branch, safe="/"))
    for pk, slug in published_pages().filter(pk__in=ids["page"]).values_list("pk", "slug"):
        paths[("page", pk)] = {"/pages/" + quote(slug, safe="")}
    for rule in rules:
        directive = "Allow" if rule.crawl == "allow" else "Disallow"
        for path in sorted(paths.get((rule.kind, rule.object_id), [])):
            variants = [path] if path == "/" else [path, path + "/"]
            for variant in variants:
                lines.extend([f"{directive}: {variant}$", f"{directive}: {variant}?"])
    return "\n".join(lines) + "\n"
