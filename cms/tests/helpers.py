from django.contrib.auth import get_user_model


def user(number="09120000001", **kwargs):
    model = get_user_model()
    key = "phone" if any(field.name == "phone" for field in model._meta.fields) else model.USERNAME_FIELD
    return model.objects.create_user(**{key: number}, **kwargs)


def block(kind="text", **data):
    defaults = {"text": {"heading": "عنوان", "body": "متن اصلی", "align": "right"}, "buttons": {"items": [{"label": "محصولات", "href": "/products", "style": "primary"}]}}
    return {"id": "block-1", "type": kind, "enabled": True, "data": {**defaults.get(kind, {}), **data}}


def content(**kwargs):
    return {"title": "درباره ما", "blocks": [block()], **kwargs}
