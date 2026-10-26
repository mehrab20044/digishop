import re

from django.contrib.auth import get_user_model
from rest_framework import serializers

from accounts.models import Address
from accounts.services.profile_service import (
    complete_profile,
    create_address,
    get_profile_status,
    update_address,
    update_profile,
)
from accounts.profile_validators import validate_avatar

User = get_user_model()

DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


class PhoneField(serializers.CharField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        value = value.translate(DIGIT_TRANSLATION)

        if value.startswith("+98"):
            value = "0" + value[3:]
        elif value.startswith("0098"):
            value = "0" + value[4:]

        if re.fullmatch(r"09[0-9]{9}", value) is None:
            raise serializers.ValidationError(
                "شماره موبایل معتبر وارد کنید؛ مانند 09123456789."
            )

        return value


class OTPRequestSerializer(serializers.Serializer):
    phone = PhoneField(max_length=32)


class OTPVerifySerializer(OTPRequestSerializer):
    code = serializers.CharField(
        min_length=6,
        max_length=6,
        trim_whitespace=True,
    )

    def validate_code(self, value):
        value = value.translate(DIGIT_TRANSLATION)

        if re.fullmatch(r"[0-9]{6}", value) is None:
            raise serializers.ValidationError(
                "کد باید ۶ رقم باشد."
            )

        return value


class AddressSerializer(serializers.ModelSerializer):
    recipient_phone = PhoneField(max_length=32)
    postal_code = serializers.CharField(max_length=10)

    class Meta:
        model = Address
        fields = [
            "id",
            "recipient_name",
            "recipient_phone",
            "province",
            "city",
            "street_address",
            "building_number",
            "unit",
            "postal_code",
            "is_default",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]
        # Service handles switching defaults atomically.
        validators = []

    def validate_postal_code(self, value):
        value = value.translate(DIGIT_TRANSLATION)

        if re.fullmatch(r"[0-9]{10}", value) is None:
            raise serializers.ValidationError(
                "کد پستی باید ۱۰ رقم باشد."
            )

        return value

    def create(self, validated_data):
        user = validated_data.pop("user")
        return create_address(user, validated_data)

    def update(self, instance, validated_data):
        return update_address(instance, validated_data)


class ProfileSerializer(serializers.ModelSerializer):
    phone = serializers.SerializerMethodField()
    profile_completed = serializers.SerializerMethodField()
    missing_fields = serializers.SerializerMethodField()

    image = serializers.ImageField(
        source="profile.image",
        required=False,
        allow_null=True,
        validators=[validate_avatar],
    )
    description = serializers.CharField(
        source="profile.description",
        required=False,
        allow_blank=True,
        max_length=2000,
    )
    addresses = AddressSerializer(
        many=True,
        read_only=True,
    )
    profile_created_at = serializers.DateTimeField(
        source="profile.created_at",
        read_only=True,
    )
    profile_updated_at = serializers.DateTimeField(
        source="profile.updated_at",
        read_only=True,
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "phone",
            "first_name",
            "last_name",
            "email",
            "image",
            "description",
            "addresses",
            "profile_completed",
            "missing_fields",
            "profile_created_at",
            "profile_updated_at",
        ]
        read_only_fields = [
            "id",
            "username",
            "phone",
        ]

    def get_phone(self, obj) -> str | None:
        identity = getattr(obj, "phone_identity", None)
        return identity.phone if identity else None

    def _state(self, obj):
        states = getattr(self, "_states", None)

        if states is None:
            self._states = states = {}

        if obj.pk not in states:
            states[obj.pk] = get_profile_status(obj)

        return states[obj.pk]

    def get_profile_completed(self, obj) -> bool:
        return self._state(obj)["profile_completed"]

    def get_missing_fields(self, obj) -> list[str]:
        return self._state(obj)["missing_fields"]

    def update(self, instance, validated_data):
        self._states = {}
        return update_profile(instance, validated_data)


class CompleteProfileSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField(
        required=False,
        allow_blank=True,
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000,
    )
    address = AddressSerializer(required=False)

    def create(self, validated_data):
        user = validated_data.pop("user")
        return complete_profile(user, validated_data)


class OTPRequestResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    retry_after = serializers.IntegerField()


class OTPVerifyResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    is_new_user = serializers.BooleanField()
    user = ProfileSerializer()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )