import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

import nh3
from django.core.exceptions import ValidationError

RICH_FIELDS = ("long_description", "gallery_description")
TAGS = {"p", "br", "strong", "b", "em", "i", "u", "s", "h2", "h3", "h4", "ul", "ol", "li", "blockquote", "a", "span", "hr"}


def allowed_link(value):
    if re.search(r"[\x00-\x20\x7f\\]", value):
        return None
    if value.startswith("/") and not value.startswith("//"):
        return value
    if value.startswith("#"):
        return value
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password:
            _ = parsed.port
            return value
    except ValueError:
        pass
    return None


def attribute_filter(tag, attr, value):
    if attr == "href":
        return allowed_link(value)
    if attr == "style":
        clean = []
        for declaration in value.split(";"):
            name, _, val = declaration.partition(":")
            name, val = name.strip().lower(), val.strip().strip('"\'').lower()
            if name == "font-family" and val in {"tahoma", "arial", "georgia", "times new roman", "sans-serif", "serif"}:
                clean.append(f"font-family:{val}")
            elif name == "font-size" and re.fullmatch(r"(?:12|14|16|18|20|24|28|32)px", val):
                clean.append(f"font-size:{val}")
            elif name == "text-align" and val in {"right", "left", "center", "justify"}:
                clean.append(f"text-align:{val}")
            elif name == "color" and re.fullmatch(r"#[a-f0-9]{6}|rgb\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*\)", val):
                clean.append(f"color:{val}")
        return ";".join(clean) or None
    return value if attr == "title" else None


def sanitize_richtext(value):
    if not isinstance(value, str) or len(value.encode("utf-8")) > 160000:
        raise ValidationError("توضیحات قالب‌بندی‌شده باید حداکثر ۱۶۰ کیلوبایت باشد.")
    cleaned = nh3.clean(value, tags=TAGS, attributes={"a": {"href", "title"}, "span": {"style"}, "p": {"style"}, "h2": {"style"}, "h3": {"style"}, "h4": {"style"}}, attribute_filter=attribute_filter, clean_content_tags={"script", "style", "iframe", "svg", "math", "object", "template"}, url_schemes={"http", "https"}, link_rel="noopener noreferrer", strip_comments=True)
    return cleaned if plain_text(cleaned).strip() else ""


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_endtag(self, tag):
        if tag in {"p", "li", "h2", "h3", "h4", "blockquote"}:
            self.parts.append("\n")

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self.parts.append("\n")


def plain_text(html):
    parser = TextExtractor()
    parser.feed(html)
    return "".join(parser.parts).strip()


def sync_product_richtext(instance, update_fields=None):
    relevant = {field for base in RICH_FIELDS for field in (base, base + "_html")}
    if update_fields is not None and not relevant.intersection(update_fields):
        return update_fields
    previous = type(instance).objects.filter(pk=instance.pk).values(*sorted(relevant)).first() if instance.pk else None
    updates = set(update_fields) if update_fields is not None else None
    for base in RICH_FIELDS:
        rich = base + "_html"
        html, text = getattr(instance, rich), getattr(instance, base)
        if previous is None or html != previous[rich]:
            clean = sanitize_richtext(html)
            setattr(instance, rich, clean)
            if html or (previous and html != previous[rich]):
                setattr(instance, base, plain_text(clean))
                if base == "long_description":
                    instance.description = plain_text(clean)
                    if updates is not None:
                        updates.add("description")
            if updates is not None:
                updates.update({base, rich})
        elif text != previous[base]:
            # Older plain-text API/admin edits stay authoritative.
            setattr(instance, rich, "")
            if updates is not None:
                updates.add(rich)
    return updates
