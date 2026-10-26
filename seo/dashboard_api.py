from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core import signing
from django.db import transaction
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import SessionJWTAuthentication
from dashboard.permissions import IsManagementSession
from seo.models import SEOSettings, SEOSettingsLog
from seo.services.seo_services import (
    SEOService,
    SEOSettingsConflict,
)

User = get_user_model()

SEO_PERMISSIONS = {
    "view": "seo.view_seosettings",
    "change": "seo.change_seosettings",
    "history": "seo.view_seosettingslog",
}

CONFIRMATION_SALT = "seo-dashboard-confirmation"


class CanOpenDashboard(IsManagementSession):
    pass



class PrepareSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["prepare"])
    expected_version = serializers.IntegerField(min_value=1)
    allow_crawling = serializers.BooleanField()


class ConfirmSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["confirm"])
    confirmation = serializers.CharField(max_length=4096)


class AccessSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)
    view = serializers.BooleanField()
    change = serializers.BooleanField()
    history = serializers.BooleanField()

    def validate(self, attrs):
        if attrs["change"] and not attrs["view"]:
            raise serializers.ValidationError(
                "مجوز تغییر، به مجوز مشاهده هم نیاز دارد."
            )

        return attrs


def can(user, key):
    return user.has_perm(SEO_PERMISSIONS[key])


def require_owner(request):
    if not request.user.is_superuser:
        raise PermissionDenied(
            "فقط صاحب سایت اجازهٔ مدیریت دسترسی‌ها را دارد."
        )


def access_data(user):
    direct = {
        f"{permission.content_type.app_label}.{permission.codename}"
        for permission in user.user_permissions.select_related(
            "content_type",
        )
    }
    inherited = user.get_group_permissions()

    return {
        "id": user.pk,
        "username": user.phone,
        "full_name": user.get_full_name(),
        "direct": {
            key: permission in direct
            for key, permission in SEO_PERMISSIONS.items()
        },
        "inherited": {
            key: permission in inherited
            for key, permission in SEO_PERMISSIONS.items()
        },
        "effective": {
            key: user.has_perm(permission)
            for key, permission in SEO_PERMISSIONS.items()
        },
    }


@method_decorator(never_cache, name="dispatch")
class SEOBaseView(APIView):
    authentication_classes = [SessionJWTAuthentication]
    permission_classes = [CanOpenDashboard]


class SEODashboardView(SEOBaseView):
    http_method_names = ["get", "post", "head", "options"]

    def get(self, request):
        user = request.user

        if not any(
            user.has_perm(permission)
            for permission in SEO_PERMISSIONS.values()
        ):
            raise PermissionDenied("اجازه مشاهده بخش سئو را ندارید.")

        current = SEOSettings.get_settings()

        can_view = can(user, "view") or can(user, "change")
        can_history = can(user, "history")

        logs = []

        if can_history:
            queryset = SEOSettingsLog.objects.select_related(
                "changed_by",
            ).order_by("-changed_at", "-pk")[:20]

            logs = [
                {
                    "id": item.pk,
                    "changed_by": (
                        item.changed_by.phone
                        if item.changed_by
                        else "کاربر حذف‌شده"
                    ),
                    "old_value": item.old_value,
                    "new_value": item.new_value,
                    "changed_at": item.changed_at,
                }
                for item in queryset
            ]

        return Response({
            "csrfToken": get_token(request),
            "settings": (
                {
                    "allow_crawling": current.allow_crawling,
                    "version": current.version,
                }
                if can_view
                else None
            ),
            "capabilities": {
                "view": can_view,
                "change": can(user, "change"),
                "history": can_history,
                "manage_access": user.is_superuser,
            },
            "logs": logs,
        })

    def post(self, request):
        if not can(request.user, "change"):
            raise PermissionDenied(
                "اجازهٔ تغییر تنظیمات SEO را ندارید."
            )

        action = request.data.get("action")

        if action == "prepare":
            serializer = PrepareSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            values = serializer.validated_data

            current = SEOSettings.get_settings()

            if current.version != values["expected_version"]:
                return Response(
                    {
                        "detail": (
                            "تنظیمات تغییر کرده‌اند؛ "
                            "صفحه را تازه‌سازی کنید."
                        ),
                    },
                    status=409,
                )

            if current.allow_crawling == values["allow_crawling"]:
                return Response({"unchanged": True})

            token = signing.dumps(
                {
                    "user_id": request.user.pk,
                    "version": current.version,
                    "old_value": current.allow_crawling,
                    "new_value": values["allow_crawling"],
                },
                salt=CONFIRMATION_SALT,
            )

            return Response({
                "confirmation": token,
                "old_value": current.allow_crawling,
                "new_value": values["allow_crawling"],
            })

        if action == "confirm":
            serializer = ConfirmSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            try:
                values = signing.loads(
                    serializer.validated_data["confirmation"],
                    salt=CONFIRMATION_SALT,
                    max_age=300,
                )
            except signing.BadSignature:
                return Response(
                    {
                        "detail": (
                            "تأیید معتبر نیست یا منقضی شده؛ "
                            "دوباره تغییر را آماده کنید."
                        ),
                    },
                    status=400,
                )

            if values["user_id"] != request.user.pk:
                raise PermissionDenied(
                    "این تأیید متعلق به حساب شما نیست."
                )

            try:
                updated = SEOService.update_crawling(
                    expected_version=values["version"],
                    allow_crawling=values["new_value"],
                    user=request.user,
                )
            except SEOSettingsConflict as exc:
                return Response(
                    {"detail": str(exc)},
                    status=409,
                )

            return Response({
                "allow_crawling": updated.allow_crawling,
                "version": updated.version,
            })

        raise serializers.ValidationError({
            "action": "عملیات نامعتبر است.",
        })


class SEOAccessView(SEOBaseView):
    http_method_names = ["get", "post", "head", "options"]

    def get(self, request):
        require_owner(request)

        users = User.objects.filter(
            is_active=True,
            is_staff=True,
            is_superuser=False,
        ).prefetch_related(
            "user_permissions__content_type",
            "groups__permissions__content_type",
        ).order_by("pk")

        paginator = PageNumberPagination()
        paginator.page_size = 25

        page = paginator.paginate_queryset(
            users,
            request,
            view=self,
        )

        return paginator.get_paginated_response([
            access_data(user)
            for user in page
        ])

    @transaction.atomic
    def post(self, request):
        require_owner(request)

        serializer = AccessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data

        user = get_object_or_404(
            User.objects.select_for_update(),
            pk=values["user_id"],
            is_active=True,
            is_staff=True,
            is_superuser=False,
        )

        for key, permission_name in SEO_PERMISSIONS.items():
            app_label, codename = permission_name.split(".")

            permission = Permission.objects.get(
                content_type__app_label=app_label,
                codename=codename,
            )

            if values[key]:
                user.user_permissions.add(permission)
            else:
                user.user_permissions.remove(permission)

        model_admin = admin.site.get_model_admin(User)
        model_admin.log_change(
            request,
            user,
            "SEO direct permissions updated through dashboard.",
        )

        # Read a fresh user instance, without cached permissions.
        user = User.objects.get(pk=user.pk)

        return Response(access_data(user))