from django.contrib.auth import get_user_model
from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)
from django.db import transaction
from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)

from accounts.models import Address, PhoneIdentity, Profile

User = get_user_model()


def get_profile_status(user):
    missing = []

    if not user.first_name.strip():
        missing.append("first_name")

    if not user.last_name.strip():
        missing.append("last_name")

    if not PhoneIdentity.objects.filter(
        user_id=user.pk,
    ).exists():
        missing.append("phone")

    valid_address = False

    for address in Address.objects.filter(user_id=user.pk):
        try:
            address.full_clean(
                exclude=["user"],
                validate_unique=False,
                validate_constraints=False,
            )
        except DjangoValidationError:
            continue

        valid_address = True
        break

    if not valid_address:
        missing.append("address")

    return {
        "profile_completed": not missing,
        "missing_fields": missing,
    }


def require_complete_profile(user, *, lock=False):
    """With lock=True, caller must use transaction.atomic()."""
    users = (
        User.objects.select_for_update()
        if lock
        else User.objects
    )
    current = users.get(pk=user.pk)
    state = get_profile_status(current)

    if not state["profile_completed"]:
        raise PermissionDenied({
            "detail": "ابتدا پروفایل و آدرس خود را تکمیل کنید.",
            "missing_fields": state["missing_fields"],
        })

    return current


def _ensure_default(user_id):
    addresses = Address.objects.filter(user_id=user_id)

    if not addresses.filter(is_default=True).exists():
        first = addresses.order_by("id").first()

        if first:
            addresses.filter(pk=first.pk).update(
                is_default=True,
            )


def _save_address(user, data, instance=None):
    # Caller holds the user's row lock in this transaction.
    address = instance or Address(user=user)

    for field, value in data.items():
        setattr(address, field, value)

    address.full_clean(
        validate_unique=False,
        validate_constraints=False,
    )

    if address.is_default:
        Address.objects.filter(
            user=user,
            is_default=True,
        ).exclude(
            pk=address.pk,
        ).update(is_default=False)

    address.save()
    _ensure_default(user.pk)
    address.refresh_from_db()

    return address


@transaction.atomic
def create_address(user, data):
    user = User.objects.select_for_update().get(pk=user.pk)
    return _save_address(user, data)


@transaction.atomic
def update_address(instance, data):
    user = User.objects.select_for_update().get(
        pk=instance.user_id,
    )
    current = Address.objects.get(
        pk=instance.pk,
        user=user,
    )
    return _save_address(user, data, current)


@transaction.atomic
def delete_address(instance):
    User.objects.select_for_update().get(
        pk=instance.user_id,
    )
    Address.objects.filter(
        pk=instance.pk,
        user_id=instance.user_id,
    ).delete()

    _ensure_default(instance.user_id)


@transaction.atomic
def update_profile(user, data):
    user = User.objects.select_for_update().get(pk=user.pk)
    profile, _ = Profile.objects.get_or_create(user=user)
    profile_data = data.pop("profile", {})

    for field in ["first_name", "last_name", "email"]:
        if field in data:
            setattr(user, field, data[field])

    user.save(
        update_fields=["first_name", "last_name", "email"],
    )

    for field, value in profile_data.items():
        if field == "image" and value is None:
            value = ""
        setattr(profile, field, value)

    profile.save()
    return user


@transaction.atomic
def complete_profile(user, data):
    user = User.objects.select_for_update().get(pk=user.pk)
    address_data = data.pop("address", None)
    profile_data = {}

    if "description" in data:
        profile_data["description"] = data.pop(
            "description",
        )

    user = update_profile(
        user,
        {**data, "profile": profile_data},
    )

    if address_data is not None:
        _save_address(user, address_data)

    state = get_profile_status(user)

    if not state["profile_completed"]:
        raise ValidationError({
            "detail": "اطلاعات پروفایل کامل نیست.",
            "missing_fields": state["missing_fields"],
        })

    return user