from urllib.parse import quote

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


def import_existing(apps, schema_editor):
    Settings = apps.get_model("seo", "SEOSettings")
    Rule = apps.get_model("seo", "PageSearchRule")
    Document = apps.get_model("seo", "RobotsDocument")
    Category = apps.get_model("products", "Category")
    CategoryURL = apps.get_model("products", "CategoryURL")
    Product = apps.get_model("products", "Product")
    Page = apps.get_model("cms", "Page")
    db = schema_editor.connection.alias
    current, _ = Settings.objects.using(db).get_or_create(pk=1)
    overrides = list(Rule.objects.using(db).exclude(crawl="inherit").order_by("kind", "object_id"))
    compiled = []
    if not current.allow_crawling:
        compiled.append(("disallow", "/"))
    elif not overrides:
        compiled.append(("allow", "/"))
    paths = {("home", 0): {"/"}, ("catalog", 0): {"/products"}, ("directory", 0): {"/categories"}}
    for product in Product.objects.using(db).filter(is_active=True, status="published").values("pk"):
        paths[("product", product["pk"])] = {f'/products/{product["pk"]}'}
    rows = {row["id"]: row for row in Category.objects.using(db).values("id", "slug", "parent_id")}
    for pk, row in rows.items():
        parts, seen = [], set()
        while row and row["id"] not in seen:
            seen.add(row["id"])
            parts.append(row["slug"])
            row = rows.get(row["parent_id"])
        paths[("category", pk)] = {"/products/category/" + quote("/".join(reversed(parts)), safe="/")}
    for pk, path in CategoryURL.objects.using(db).values_list("category_id", "path"):
        if ("category", pk) in paths:
            paths[("category", pk)].add("/products/category/" + quote(path, safe="/"))
    for pk, slug in Page.objects.using(db).filter(is_published=True).exclude(published={}).values_list("pk", "slug"):
        paths[("page", pk)] = {"/pages/" + quote(slug, safe="")}
    for rule in overrides:
        for path in sorted(paths.get((rule.kind, rule.object_id), [])):
            for variant in ([path] if path == "/" else [path, path + "/"]):
                action = "allow" if rule.crawl == "allow" else "disallow"
                compiled.extend([(action, variant + "$"), (action, variant + "?")])
    rules = [{"id": f"legacy-{i}", "action": action, "scope": "pattern", "path": path, "enabled": True} for i, (action, path) in enumerate(compiled)]
    document = {"version": 1, "groups": [{"id": "all", "agent": "*", "enabled": True, "rules": rules}], "sitemaps": []}
    Document.objects.using(db).create(pk=1, draft=document, published=document, revision=1, published_revision=1, published_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [("seo", "0005_page_search_rule"), ("products", "0015_category_urls"), ("cms", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="RobotsDocument",
            fields=[
                ("id", models.PositiveSmallIntegerField(default=1, primary_key=True, serialize=False)),
                ("draft", models.JSONField(default=dict)),
                ("published", models.JSONField(default=dict)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("published_revision", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("published_at", models.DateTimeField(null=True, blank=True)),
                ("updated_by", models.ForeignKey(null=True, blank=True, related_name="+", on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "سند robots.txt", "verbose_name_plural": "اسناد robots.txt", "constraints": [models.CheckConstraint(condition=models.Q(pk=1), name="seo_single_robots_document")]},
        ),
        migrations.RunPython(import_existing, migrations.RunPython.noop),
    ]
