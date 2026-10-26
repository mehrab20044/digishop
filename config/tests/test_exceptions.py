from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import PermissionDenied

from config.exceptions import custom_exception_handler


def test_django_validation_error_returns_400():
    response = custom_exception_handler(
        DjangoValidationError({
            "recipient_name": ["این فیلد الزامی است."],
        }),
        {},
    )

    assert response is not None
    assert response.status_code == 400
    assert response.data["success"] is False
    assert response.data["error"]["code"] == "validation_error"
    assert response.data["error"]["details"] == {
        "recipient_name": ["این فیلد الزامی است."],
    }


def test_structured_permission_error_preserves_details():
    response = custom_exception_handler(
        PermissionDenied({
            "detail": "ابتدا پروفایل را تکمیل کنید.",
            "missing_fields": ["address"],
        }),
        {},
    )

    assert response.status_code == 403
    error = response.data["error"]
    assert error["code"] == "permission_denied"
    assert error["message"] == "ابتدا پروفایل را تکمیل کنید."
    assert error["details"]["missing_fields"] == ["address"]
