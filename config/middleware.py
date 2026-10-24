from django.utils import translation


class AdminPersianLocaleMiddleware:
    """Use Django's Persian translations only inside the admin interface."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/admin/"):
            return self.get_response(request)

        with translation.override("fa"):
            return self.get_response(request)
