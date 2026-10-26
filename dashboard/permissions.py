from rest_framework.permissions import BasePermission


class IsManagementSession(BasePermission):
    message = "ورود با حساب مجاز مدیریت الزامی است."

    def has_permission(self, request, view):
        user = request.user

        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.is_staff
            and request.auth
            and request.auth.get("purpose") == "management"
        )