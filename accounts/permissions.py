from rest_framework.permissions import BasePermission

from accounts.services.profile_service import require_complete_profile


class HasCompleteProfile(BasePermission):
    message = "ابتدا پروفایل و آدرس خود را تکمیل کنید."

    def has_permission(self, request, view):
        if (
            not request.user
            or not request.user.is_authenticated
        ):
            return False

        require_complete_profile(request.user)
        return True