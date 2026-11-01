"""Strict import of supported robots.txt directives into the existing policy model."""
import copy
import hashlib
import re
import uuid

from seo.services.robots_engine import MAX_BYTES, PolicyError, validate_document


class TextPolicyError(PolicyError):
    def __init__(self, line, message):
        self.line = line
        super().__init__(f"خط {line}: {message}")


def parse_text(text, previous=None):
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_BYTES:
        raise TextPolicyError(1, "متن خالی یا بیش از حد بزرگ است.")
    if any(ord(c) < 32 and c not in "\r\n\t" for c in text):
        raise TextPolicyError(1, "کاراکتر کنترلی مجاز نیست.")
    groups, maps, agents, pending, warnings = [], [], {}, [], []
    in_rules = False
    def ident(value):
        return "t-" + hashlib.sha256(value.encode()).hexdigest()[:32]
    def group_for(agent):
        key = agent.lower()
        if key not in agents:
            if len(agents) >= 40:
                raise PolicyError("حداکثر ۴۰ گروه مجاز است.")
            agents[key] = {"id": ident("agent:" + key), "agent": agent, "enabled": True, "rules": []}
            groups.append(agents[key])
        return agents[key]
    for number, raw in enumerate(text.lstrip("\ufeff").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            raise TextPolicyError(number, "بعد از نام دستور، : قرار بده.")
        field, value = (part.strip() for part in line.split(":", 1))
        field = field.lower()
        if field == "user-agent":
            if not re.fullmatch(r"\*|[A-Za-z][A-Za-z0-9_-]{0,63}", value):
                raise TextPolicyError(number, "نام ربات معتبر نیست.")
            if in_rules:
                pending = []
                in_rules = False
            if value.lower() not in [agent.lower() for agent in pending]:
                pending.append(value)
            group_for(value)
        elif field in {"allow", "disallow"}:
            if not pending:
                raise TextPolicyError(number, "ابتدا User-agent را بنویس.")
            in_rules = True
            if not value:
                warnings.append(f"خط {number}: قانون با مسیر خالی اثری ندارد و وارد نمی‌شود.")
                continue
            if sum(len(group["rules"]) for group in groups) + len(pending) > 4000:
                raise TextPolicyError(number, "حداکثر ۴۰۰۰ قانون مجاز است.")
            for agent in pending:
                group = group_for(agent)
                rule = {"id": "r-" + uuid.uuid4().hex, "action": field, "scope": "pattern", "path": value, "enabled": True}
                try:
                    validate_document({"version": 1, "groups": [{**group, "rules": [rule]}], "sitemaps": []})
                except PolicyError as exc:
                    raise TextPolicyError(number, str(exc)) from exc
                group["rules"].append(rule)
        elif field == "sitemap":
            item = {"id": ident(f"map:{number}:{value}"), "url": value, "enabled": True}
            try:
                validate_document({"version": 1, "groups": [{"id": "check", "agent": "*", "enabled": True, "rules": []}], "sitemaps": [item]})
            except PolicyError as exc:
                raise TextPolicyError(number, str(exc)) from exc
            if len(maps) >= 30:
                raise TextPolicyError(number, "حداکثر ۳۰ نقشهٔ سایت مجاز است.")
            maps.append(item)
        else:
            raise TextPolicyError(number, "فقط User-agent، Allow، Disallow و Sitemap پشتیبانی می‌شوند؛ noindex را در تب ایندکس تنظیم کن.")
    if not groups:
        raise TextPolicyError(1, "حداقل یک User-agent لازم است.")
    # Text represents enabled directives; retain disabled items as inactive history.
    if previous is not None:
        previous = validate_document(previous)
        for old in previous["groups"]:
            current = agents.get(old["agent"].lower())
            if not old["enabled"]:
                if current is None:
                    groups.append(copy.deepcopy(old))
                else:
                    current["rules"].extend({**rule, "enabled": False} for rule in old["rules"])
            elif current:
                current["rules"].extend(copy.deepcopy(rule) for rule in old["rules"] if not rule["enabled"])
            elif any(not rule["enabled"] for rule in old["rules"]):
                groups.append({**copy.deepcopy(old), "enabled": False, "rules": [copy.deepcopy(rule) for rule in old["rules"] if not rule["enabled"]]})
        maps.extend(copy.deepcopy(item) for item in previous["sitemaps"] if not item["enabled"] and item["url"] not in {row["url"] for row in maps})
    try:
        return validate_document({"version": 1, "groups": groups, "sitemaps": maps}), warnings
    except PolicyError as exc:
        raise TextPolicyError(1, str(exc)) from exc
