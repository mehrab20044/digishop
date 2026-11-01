"""Pure robots policy compiler and Google-style rule tester; no database or IO."""

import re
from urllib.parse import quote, urlsplit, urlunsplit

MAX_BYTES = 480_000
UNRESERVED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")


class PolicyError(ValueError):
    pass


def normalized_path(value):
    encoded = quote(value, safe="/%?=&:+,;@!~._-*$")
    return re.sub(r"%([0-9a-fA-F]{2})", lambda m: chr(int(m[1], 16)) if chr(int(m[1], 16)) in UNRESERVED else "%" + m[1].upper(), encoded)


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise PolicyError("شناسهٔ گروه یا قانون معتبر نیست.")
    return value


def _bool(value):
    if type(value) is not bool:
        raise PolicyError("وضعیت فعال‌بودن باید روشن یا خاموش باشد.")
    return value


def _fields(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise PolicyError("ساختار تنظیمات کامل یا معتبر نیست؛ صفحه را تازه‌سازی کنید.")


def clean_rule(row):
    _fields(row, {"id", "action", "scope", "path", "enabled"})
    if row["action"] not in {"allow", "disallow"} or row["scope"] not in {"exact", "prefix", "pattern"}:
        raise PolicyError("نوع قانون یا نوع تطبیق معتبر نیست.")
    path = row["path"]
    if not isinstance(path, str) or not path.startswith("/") or path.startswith("//") or len(path) > 2048:
        raise PolicyError("مسیر باید با / شروع شود؛ دامنه را در مسیر وارد نکنید.")
    if any(ord(c) < 32 for c in path) or "#" in path or "\\" in path:
        raise PolicyError("مسیر نباید خط جدید، # یا بک‌اسلش داشته باشد.")
    if re.search(r"%(?![0-9A-Fa-f]{2})", path):
        raise PolicyError("کدگذاری درصدی مسیر معتبر نیست؛ مثلاً %20.")
    if row["scope"] != "pattern" and any(c in path for c in "*$"):
        raise PolicyError("برای * و $، نوع تطبیق «الگوی پیشرفته» را انتخاب کنید.")
    if row["scope"] == "pattern" and ("$" in path[:-1] or path.count("*") > 20):
        raise PolicyError("$ فقط در انتهای الگو مجاز است؛ تعداد * هم بیش از حد است.")
    if row["scope"] == "prefix" and path != "/" and "?" not in path:
        path = path.rstrip("/") + "/"
    return {"id": _id(row["id"]), "action": row["action"], "scope": row["scope"], "path": normalized_path(path), "enabled": _bool(row["enabled"])}


def validate_document(document):
    _fields(document, {"version", "groups", "sitemaps"})
    if type(document["version"]) is not int or document["version"] != 1:
        raise PolicyError("نسخهٔ سند پشتیبانی نمی‌شود.")
    groups, sitemaps = document["groups"], document["sitemaps"]
    if not isinstance(groups, list) or not 1 <= len(groups) <= 40 or not isinstance(sitemaps, list) or len(sitemaps) > 30:
        raise PolicyError("حداقل یک گروه و حداکثر ۴۰ گروه و ۳۰ نقشهٔ سایت مجاز است.")
    clean_groups, agents, identifiers, total = [], set(), set(), 0
    for group in groups:
        _fields(group, {"id", "agent", "enabled", "rules"})
        agent = group["agent"]
        if not isinstance(agent, str) or not (agent == "*" or re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", agent)):
            raise PolicyError("نام ربات معتبر نیست؛ مانند Googlebot، Bingbot یا *.")
        if agent.lower() in agents:
            raise PolicyError("برای هر ربات فقط یک گروه بسازید؛ نام ربات تکراری است.")
        agents.add(agent.lower())
        ident = _id(group["id"])
        if ident in identifiers:
            raise PolicyError("شناسهٔ گروه تکراری است.")
        identifiers.add(ident)
        rules = group["rules"]
        if not isinstance(rules, list):
            raise PolicyError("فهرست قوانین معتبر نیست.")
        total += len(rules)
        if total > 4000:
            raise PolicyError("حداکثر ۴۰۰۰ قانون در یک فایل مجاز است.")
        clean_rules, seen = [], set()
        for row in rules:
            rule = clean_rule(row)
            if rule["id"] in seen:
                raise PolicyError("شناسهٔ قانون تکراری است.")
            seen.add(rule["id"])
            clean_rules.append(rule)
        clean_groups.append({"id": ident, "agent": agent, "enabled": _bool(group["enabled"]), "rules": clean_rules})
    if not any(g["enabled"] for g in clean_groups):
        raise PolicyError("حداقل یک گروه باید فعال باشد.")
    clean_maps, urls, map_ids = [], set(), set()
    for item in sitemaps:
        _fields(item, {"id", "url", "enabled"})
        ident = _id(item["id"])
        url = item["url"]
        if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 32 for c in url):
            raise PolicyError("آدرس نقشهٔ سایت معتبر نیست.")
        try:
            parts = urlsplit(url.strip())
            _port = parts.port
        except ValueError as exc:
            raise PolicyError("آدرس نقشهٔ سایت معتبر نیست.") from exc
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password or parts.fragment or any(c.isspace() for c in parts.netloc):
            raise PolicyError("نقشهٔ سایت باید آدرس کامل http یا https، بدون رمز و # باشد.")
        url = urlunsplit((parts.scheme, parts.netloc, quote(parts.path or "/", safe="/%:@!~._-"), quote(parts.query, safe="%=&:+,;@!~._-/?"), ""))
        if ident in map_ids or url in urls:
            raise PolicyError("نقشهٔ سایت یا شناسهٔ آن تکراری است.")
        map_ids.add(ident)
        urls.add(url)
        clean_maps.append({"id": ident, "url": url, "enabled": _bool(item["enabled"])})
    cleaned = {"version": 1, "groups": clean_groups, "sitemaps": clean_maps}
    if len(render_document(cleaned).encode("utf-8")) > MAX_BYTES:
        raise PolicyError("حجم فایل از حد مجاز این ویرایشگر بیشتر شده است.")
    return cleaned


def rule_pattern(rule):
    return rule["path"] + ("$" if rule["scope"] == "exact" else "")


def render_document(document):
    lines = []
    for group in document["groups"]:
        if not group["enabled"]:
            continue
        lines.append("User-agent: " + group["agent"])
        rules = [rule for rule in group["rules"] if rule["enabled"]]
        # A real directive prevents an empty group merging into the next group.
        if not rules:
            lines.append("Allow: /")
        for rule in rules:
            lines.append(("Allow: " if rule["action"] == "allow" else "Disallow: ") + rule_pattern(rule))
        lines.append("")
    for item in document["sitemaps"]:
        if item["enabled"]:
            lines.append("Sitemap: " + item["url"])
    return "\n".join(lines).rstrip() + "\n"


def pattern_matches(pattern, path):
    anchored = pattern.endswith("$")
    source = pattern[:-1] if anchored else pattern
    parts = source.split("*")
    if len(parts) == 1:
        return path == source if anchored else path.startswith(source)
    if not path.startswith(parts[0]):
        return False
    offset = len(parts[0])
    for part in parts[1:-1]:
        at = path.find(part, offset)
        if at < 0:
            return False
        offset = at + len(part)
    tail = parts[-1]
    if anchored:
        return path.endswith(tail) and len(path) - len(tail) >= offset
    return path.find(tail, offset) >= 0


def evaluate(document, path, agent="Googlebot"):
    """Specific agent replaces *, longest rule wins, Allow wins a tie."""
    if not isinstance(agent, str) or not agent.strip() or len(agent) > 256:
        raise PolicyError("نام ربات آزمایش را وارد کنید.")
    if not isinstance(path, str) or any(ord(c) < 32 for c in path):
        raise PolicyError("آدرس آزمایش معتبر نیست.")
    try:
        parsed = urlsplit(path)
    except ValueError as exc:
        raise PolicyError("آدرس آزمایش معتبر نیست.") from exc
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/") or len(path) > 4096:
        raise PolicyError("برای آزمایش، مسیر داخلی مانند /products/12 وارد کنید.")
    path = normalized_path(parsed.path + ("?" + parsed.query if parsed.query else ""))
    enabled = [group for group in document["groups"] if group["enabled"]]
    specific = [group for group in enabled if group["agent"] != "*" and group["agent"].lower() in agent.lower()]
    if specific:
        longest = max(len(group["agent"]) for group in specific)
        groups = [group for group in specific if len(group["agent"]) == longest]
    else:
        groups = [group for group in enabled if group["agent"] == "*"]
    hits = []
    for group in groups:
        rules = [rule for rule in group["rules"] if rule["enabled"]]
        if not rules:
            rules = [{"id": "implicit-allow", "action": "allow", "scope": "pattern", "path": "/", "enabled": True}]
        for rule in rules:
            pattern = rule_pattern(rule)
            if rule["enabled"] and pattern_matches(pattern, path):
                hits.append((len(pattern.encode("utf-8")), rule["action"] == "allow", group, rule, pattern))
    if hits:
        _, allowed, group, rule, pattern = max(hits, key=lambda hit: (hit[0], hit[1]))
        matched = {"group": group["agent"], "rule_id": rule["id"], "action": rule["action"], "pattern": pattern}
    else:
        allowed, matched = True, None
    return {"allowed": allowed, "matched": matched, "groups": [group["agent"] for group in groups], "agent": agent, "path": path}
