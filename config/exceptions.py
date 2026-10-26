from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        details = (
            exc.message_dict
            if hasattr(exc, "error_dict")
            else exc.messages
        )
        exc = ValidationError(details)

    response = exception_handler(exc, context)

    # خطاهای غیرمنتظره باید برای ثبت و پردازش استاندارد باقی بمانند.
    if response is None:
        return None

    data = response.data

    if isinstance(exc, ValidationError):
        code = "validation_error"
        message = "اطلاعات واردشده معتبر نیست."
        details = data

    elif isinstance(exc, APIException):
        codes = exc.get_codes()
        code = codes if isinstance(codes, str) else exc.default_code

        if isinstance(data, dict):
            detail = data.get("detail")
            message = (
                str(detail)
                if isinstance(detail, str)
                else "درخواست انجام نشد."
            )
            details = data if set(data) != {"detail"} else None
        elif isinstance(data, str):
            message = str(data)
            details = None
        else:
            message = "درخواست انجام نشد."
            details = data

    elif response.status_code == 404:
        code = "not_found"
        message = "مورد درخواستی پیدا نشد."
        details = None

    elif response.status_code == 403:
        code = "permission_denied"
        message = "اجازه انجام این عملیات را ندارید."
        details = None

    else:
        code = "error"
        message = "خطایی در پردازش درخواست رخ داده است."
        details = None

    response.data = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
    }

    return response
