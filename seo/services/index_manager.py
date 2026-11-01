"""Paginated index controls; crawl rules remain in RobotsDocument."""
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import ValidationError, PermissionDenied

from seo.models import PageSearchRule, SEOSettings
from seo.services.page_rules import SYSTEM, RuleConflict, list_targets, save_rule


def list_index_targets(*, kind="product", search="", page=1, page_size=20, indexing="all", category=None):
    from products.models import Product, Category
    from cms.views import published_pages
    from products.services.category_query_service import filter_category_branches
    from products.services.category_url_service import PREFIX, current_paths
    from urllib.parse import quote
    if page_size not in (20, 50, 100) or indexing not in {"all", "inherit", "index", "noindex"}:
        raise ValidationError("فیلتر یا تعداد ردیف معتبر نیست.")
    if category is not None and kind != "product":
        raise ValidationError("فیلتر دسته فقط برای محصولات است.")
    category_rows = list(Category.objects.order_by("sort_order", "name", "pk").values("id", "name", "parent_id")) if kind == "product" else []
    if kind == "system":
        result = list_targets(kind, search, 1)
        items = result["results"]
        if indexing != "all":
            items = [item for item in items if item["indexing"] == indexing]
        count = len(items)
        items = items[(page-1)*page_size:page*page_size]
    else:
        if kind == "product":
            queryset = Product.objects.filter(is_active=True, status=Product.Status.PUBLISHED).select_related("category")
            if category is not None:
                queryset = filter_category_branches(queryset, [category])
        elif kind == "category":
            queryset = Category.objects.all()
        elif kind == "page":
            queryset = published_pages()
        else:
            raise ValidationError("نوع صفحه معتبر نیست.")
        if search:
            field = "published__title" if kind == "page" else "name"
            condition = Q(**{field + "__icontains": search}) | Q(slug__icontains=search)
            if search.isdecimal() and len(search) <= 18:
                condition |= Q(pk=int(search))
            queryset = queryset.filter(condition)
        rules = PageSearchRule.objects.filter(kind=kind)
        if indexing == "inherit":
            queryset = queryset.exclude(pk__in=rules.exclude(indexing="inherit").values("object_id"))
        elif indexing != "all":
            queryset = queryset.filter(pk__in=rules.filter(indexing=indexing).values("object_id"))
        count = queryset.count()
        objects = list(queryset.order_by("pk")[(page-1)*page_size:page*page_size])
        paths = current_paths() if kind == "category" else {}
        overrides = {row.object_id: row for row in rules.filter(object_id__in=[obj.pk for obj in objects])}
        items = []
        for obj in objects:
            rule = overrides.get(obj.pk)
            path = PREFIX + quote(paths[obj.pk], safe="/") if kind == "category" else "/pages/" + quote(obj.slug, safe="") if kind == "page" else f"/products/{obj.pk}"
            items.append({"kind": kind, "object_id": obj.pk, "name": obj.published.get("title", obj.title) if kind == "page" else obj.name,
                          "url": path, "indexing": rule.indexing if rule else "inherit", "version": rule.version if rule else 0,
                          "category_name": obj.category.name if kind == "product" and obj.category_id else ""})
    return {"results": items, "count": count, "page": page, "page_size": page_size, "has_next": page*page_size < count, "categories": category_rows}


@transaction.atomic
def bulk_index(*, actor, items, indexing):
    if not actor.is_active or not actor.has_perm("seo.change_seosettings"):
        raise PermissionDenied("اجازهٔ ویرایش سئو را ندارید.")
    if indexing not in {"inherit", "index", "noindex"} or not 1 <= len(items) <= 100:
        raise ValidationError("حداکثر ۱۰۰ صفحه در هر عملیات انتخاب کن.")
    keys = [(item["kind"], item["object_id"]) for item in items]
    if len(set(keys)) != len(keys):
        raise ValidationError("صفحهٔ تکراری در انتخاب وجود دارد.")
    SEOSettings.get_settings()
    SEOSettings.objects.select_for_update().get(pk=1)
    results = []
    for item in sorted(items, key=lambda row: (row["kind"], row["object_id"])):
        item = dict(item)
        row_indexing = item.pop("indexing", indexing)
        if row_indexing not in {"inherit", "index", "noindex"}:
            raise ValidationError("وضعیت ایندکس معتبر نیست.")
        previous = PageSearchRule.objects.filter(kind=item["kind"], object_id=item["object_id"]).first()
        results.append(save_rule(actor=actor, **item, crawl=previous.crawl if previous else "inherit", indexing=row_indexing))
    return {"updated": len(results), "results": results}
