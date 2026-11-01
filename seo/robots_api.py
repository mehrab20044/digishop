from urllib.parse import urlsplit

from django.middleware.csrf import get_token
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from seo.services.robots_text import TextPolicyError, parse_text
from seo.dashboard_api import SEOBaseView, can
from seo.services.canonical_service import public_origin
from seo.services.robots_engine import PolicyError, evaluate, render_document, validate_document
from seo.services.robots_service import RobotsConflict, current_document, document_data, update_document


class Input(serializers.Serializer):
    action = serializers.ChoiceField(choices=["save", "publish", "reset", "preview", "test", "parse"])
    expected_revision = serializers.IntegerField(min_value=1, required=False)
    document = serializers.JSONField(required=False)
    text = serializers.CharField(max_length=480000, trim_whitespace=False, allow_blank=True, required=False)
    path = serializers.CharField(max_length=4096, required=False)
    agent = serializers.CharField(max_length=256, default="Googlebot")
    source = serializers.ChoiceField(choices=["draft", "published"], default="draft")


class RobotsStudioView(SEOBaseView):
    http_method_names = ["get", "post", "head", "options"]

    def require_view(self, request):
        if not (can(request.user, "view") or can(request.user, "change")):
            raise PermissionDenied("اجازهٔ مشاهدهٔ سئو را ندارید.")

    def result(self, request, row):
        return {**document_data(row), "csrfToken": get_token(request), "can_change": can(request.user, "change"), "site_origin": public_origin(request)}

    def get(self, request):
        self.require_view(request)
        return Response(self.result(request, current_document()))

    def post(self, request):
        self.require_view(request)
        serializer = Input(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        action = values["action"]
        try:
            if action in {"save", "publish", "reset"}:
                if not can(request.user, "change"):
                    raise PermissionDenied("اجازهٔ ویرایش یا انتشار ندارید.")
                if "expected_revision" not in values or (action != "reset" and "document" not in values):
                    raise ValidationError("نسخه و سند تنظیمات را بفرستید.")
                row = update_document(actor=request.user, expected_revision=values["expected_revision"], document=values.get("document"), action=action)
                return Response(self.result(request, row))
            if action == "parse":
                if "text" not in values:
                    raise ValidationError("متن را وارد کنید.")
                document, warnings = parse_text(values["text"], values.get("document"))
                return Response({"document": document, "text": render_document(document), "warnings": warnings, "valid": True})
            if action == "preview":
                document = validate_document(values.get("document"))
                return Response({"document": document, "text": render_document(document), "valid": True})
            if "path" not in values:
                raise ValidationError("آدرس آزمایش را وارد کنید.")
            path = values["path"]
            try:
                parts = urlsplit(path)
            except ValueError as exc:
                raise ValidationError("آدرس آزمایش معتبر نیست.") from exc
            if parts.scheme or parts.netloc:
                origin = urlsplit(public_origin(request))
                if (parts.scheme, parts.netloc.lower()) != (origin.scheme, origin.netloc.lower()):
                    raise ValidationError("فقط آدرس‌های همین فروشگاه را آزمایش کنید.")
                path = parts.path + ("?" + parts.query if parts.query else "")
            row = current_document()
            document = row.published if values["source"] == "published" else validate_document(values.get("document", row.draft))
            result = evaluate(document, path, values["agent"])
            result["source"] = values["source"]
            return Response(result)
        except TextPolicyError as exc:
            return Response({"detail": str(exc), "line": exc.line}, status=400)
        except PolicyError as exc:
            raise ValidationError(str(exc)) from exc
        except RobotsConflict as exc:
            return Response({"detail": str(exc)}, status=409)
