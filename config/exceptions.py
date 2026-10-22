from django.http import Http404
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        return None

    if isinstance(exc, ValidationError):
        code = "validation_error"
        message = "اطلاعات واردشده معتبر نیست."
        details = response.data

    elif isinstance(exc, Http404):
        code = "not_found"
        message = str(exc)
        details = None

    elif isinstance(exc, APIException):
        code = str(exc.get_codes())
        message = str(exc.detail)
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
