from html.parser import HTMLParser
from pathlib import Path

from django.conf import settings
from django.utils.html import format_html
from django.utils.safestring import mark_safe


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("type") == "module" and attrs.get("src", "").startswith("/assets/"):
            self.tags.append(format_html('<script type="module" src="{}"></script>', attrs["src"]))
        if tag == "link" and attrs.get("rel") == "stylesheet" and attrs.get("href", "").startswith("/assets/"):
            self.tags.append(format_html('<link rel="stylesheet" href="{}">', attrs["href"]))


def frontend_assets():
    if settings.DEBUG:
        return mark_safe('<script type="module" src="/src/main.jsx"></script>')
    path = Path(settings.BASE_DIR) / "frontend/dist/index.html"
    if not path.is_file():
        return ""
    parser = Assets()
    parser.feed(path.read_text())
    return mark_safe("".join(str(tag) for tag in parser.tags))
