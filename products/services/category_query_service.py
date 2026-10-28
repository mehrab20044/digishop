from collections import defaultdict

from django.db.models import Exists, OuterRef, Q
from rest_framework.exceptions import ValidationError

from products.models import Category, Product

MAX_SELECTED_CATEGORIES = 10


def category_graph():
    rows = list(
        Category.objects.order_by(
            "sort_order",
            "name",
            "id",
        ).values(
            "id",
            "name",
            "slug",
            "parent_id",
            "description",
            "sort_order",
        )
    )

    by_id = {row["id"]: row for row in rows}
    children = defaultdict(list)

    for row in rows:
        children[row["parent_id"]].append(row["id"])

    return rows, by_id, children


def descendant_ids(category_id, by_id, children):
    if category_id not in by_id:
        raise ValidationError({
            "category": "دسته‌بندی انتخاب‌شده وجود ندارد.",
        })

    result = set()
    pending = [category_id]

    while pending:
        current_id = pending.pop()

        if current_id in result:
            continue

        result.add(current_id)
        pending.extend(children.get(current_id, []))

    return result


def filter_category_branches(queryset, category_ids):
    selected = []

    for value in category_ids:
        if type(value) is not int or value <= 0:
            raise ValidationError({
                "categories": "شناسه‌های دسته‌بندی باید عدد صحیح مثبت باشند.",
            })

        if value not in selected:
            selected.append(value)

    if len(selected) > MAX_SELECTED_CATEGORIES:
        raise ValidationError({
            "categories": (
                f"انتخاب هم‌زمان حداکثر "
                f"{MAX_SELECTED_CATEGORIES} دسته مجاز است."
            ),
        })

    if not selected:
        return queryset

    _, by_id, children = category_graph()
    membership_model = Product.categories.through

    for category_id in selected:
        branch_ids = descendant_ids(
            category_id,
            by_id,
            children,
        )

        memberships = membership_model.objects.filter(
            product_id=OuterRef("pk"),
            category_id__in=branch_ids,
        )

        # Each selected branch adds an AND condition.
        # Membership in any descendant inside one branch is sufficient.
        queryset = queryset.alias(
            _matches_category_branch=Exists(memberships),
        ).filter(
            Q(category_id__in=branch_ids)
            | Q(_matches_category_branch=True)
        )

    return queryset


def public_category_tree():
    rows, by_id, _ = category_graph()
    from urllib.parse import quote

    from products.services.category_url_service import paths_for
    paths = paths_for(rows)

    related_by_id = {
        category.pk: [
            {
                "id": related.pk,
                "name": related.name,
                "slug": related.slug,
            }
            for related in category.related_categories.all()
        ]
        for category in Category.objects.prefetch_related(
            "related_categories",
        ).order_by("sort_order", "name", "id")
    }

    nodes = {
        row["id"]: {
            "id": row["id"],
            "name": row["name"],
            "slug": row["slug"],
            "parent_id": row["parent_id"],
            "url": "/products/category/" + quote(paths[row["id"]], safe="/"),
            "description": row["description"],
            "sort_order": row["sort_order"],
            "related_categories": related_by_id.get(row["id"], []),
            "children": [],
        }
        for row in rows
    }

    # Validate before linking nodes, so corrupt data cannot produce
    # circular Python objects or an incomplete tree.
    checked = set()

    for row in rows:
        current_id = row["id"]
        path = set()

        while current_id is not None and current_id not in checked:
            if current_id in path:
                raise ValidationError({
                    "categories": "ساختار دسته‌بندی دارای چرخه است.",
                })

            if current_id not in by_id:
                raise ValidationError({
                    "categories": "والد یکی از دسته‌بندی‌ها وجود ندارد.",
                })

            path.add(current_id)
            current_id = by_id[current_id]["parent_id"]

        checked.update(path)

    roots = []

    for row in rows:
        node = nodes[row["id"]]
        parent_id = row["parent_id"]

        if parent_id is None:
            roots.append(node)
        else:
            nodes[parent_id]["children"].append(node)

    return roots