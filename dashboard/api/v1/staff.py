from django.contrib.auth import get_user_model
from django.db import IntegrityError
from rest_framework import serializers, status
from rest_framework.response import Response

from accounts.api.v1.serializers import PhoneField
from accounts.services.staff_service import (
    can_manage,
    create_staff,
    permission_catalog,
    require_action,
    staff_data,
    update_staff,
)
from dashboard.api.v1.views import DashboardPagination, OwnerAPIView

User = get_user_model()


class StaffInputSerializer(serializers.Serializer):
    phone = PhoneField(max_length=32, required=False)
    first_name = serializers.CharField(
        max_length=150,
        allow_blank=True,
        required=False,
    )
    last_name = serializers.CharField(
        max_length=150,
        allow_blank=True,
        required=False,
    )
    is_active = serializers.BooleanField(required=False)
    permissions = serializers.ListField(
        child=serializers.CharField(max_length=200),
        max_length=500,
        required=False,
    )

    def to_internal_value(self, data):
        unknown = set(data.keys()) - set(self.fields)

        if unknown:
            raise serializers.ValidationError({
                "fields": (
                    "فیلد غیرمجاز: " + "، ".join(sorted(unknown))
                ),
            })

        return super().to_internal_value(data)


class StaffListCreateView(OwnerAPIView):
    http_method_names = ["get", "post", "head", "options"]

    def get(self, request):
        require_action(request.user, "view")

        search = request.query_params.get("search", "").strip()

        if len(search) > 150:
            raise serializers.ValidationError({
                "search": "جست‌وجو حداکثر ۱۵۰ کاراکتر باشد.",
            })

        queryset = User.objects.filter(
            is_staff=True,
        ).order_by("-pk")

        if search:
            from django.db.models import Q

            queryset = queryset.filter(
                Q(phone__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )

        paginator = DashboardPagination()
        page = paginator.paginate_queryset(
            queryset,
            request,
            view=self,
        )
        response = paginator.get_paginated_response([
            staff_data(user, request.user)
            for user in page
        ])
        response.data["permission_catalog"] = permission_catalog(
            request.user,
        )
        response.data["can_create"] = can_manage(
            request.user,
            "add",
        )
        return response

    def post(self, request):
        serializer = StaffInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if "phone" not in data:
            raise serializers.ValidationError({
                "phone": "شماره موبایل الزامی است.",
            })

        if "is_active" in data:
            raise serializers.ValidationError({
                "is_active": (
                    "همکار جدید فعال ساخته می‌شود؛ "
                    "وضعیت را از ویرایش تغییر دهید."
                ),
            })

        try:
            user = create_staff(request.user, data)
        except IntegrityError as exc:
            # Only translate the known phone uniqueness conflict.
            if User.objects.filter(phone=data["phone"]).exists():
                raise serializers.ValidationError({
                    "phone": "این شماره قبلاً ثبت شده است.",
                }) from exc
            raise

        return Response(
            staff_data(user, request.user),
            status=status.HTTP_201_CREATED,
        )


class StaffUpdateView(OwnerAPIView):
    http_method_names = ["patch", "options"]

    def patch(self, request, pk):
        serializer = StaffInputSerializer(
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if "phone" in data:
            raise serializers.ValidationError({
                "phone": "تغییر شماره از این مسیر مجاز نیست.",
            })

        user = update_staff(request.user, pk, data)

        return Response(staff_data(user, request.user))