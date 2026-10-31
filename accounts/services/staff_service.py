from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import AuthSession

User = get_user_model()

# Only business permissions are delegated through this API.
BUSINESS_APPS = ("products", "seo", "cms", "orders")
USER_MODEL_NAME = User._meta.model_name


def user_permission(action):
    return f"{User._meta.app_label}.{action}_{USER_MODEL_NAME}"


def permission_key(permission):
    return f"{permission.content_type.app_label}.{permission.codename}"


def effective_permissions(user):
    from django.db.models import Q

    permissions = (
        Permission.objects.filter(
            Q(user=user) | Q(group__user=user),
        )
        .select_related("content_type")
        .distinct()
    )

    return {permission_key(permission) for permission in permissions}


def can_manage(user, action):
    if not user.is_active or not user.is_staff:
        return False

    return user.is_superuser or user_permission(action) in effective_permissions(user)


def require_action(user, action):
    if not can_manage(user, action):
        raise PermissionDenied("مجوز این عملیات را ندارید.")


def business_permissions():
    return (
        Permission.objects.filter(
            content_type__app_label__in=BUSINESS_APPS,
        )
        .exclude(content_type__app_label="cms", content_type__model="pageimage")
        .exclude(
            content_type__app_label="orders",
            codename__in=[
                "add_order",
                "delete_order",
                "add_orderitem",
                "change_orderitem",
                "delete_orderitem",
                "view_orderitem",
                "add_shipment",
                "change_shipment",
                "delete_shipment",
                "view_shipment",
                "add_orderevent",
                "change_orderevent",
                "delete_orderevent",
                "view_orderevent",
                "add_returnrequest",
                "delete_returnrequest",
                "add_storesettings",
                "delete_storesettings",
            ],
        )
        .select_related("content_type")
        .order_by(
            "content_type__app_label",
            "content_type__model",
            "codename",
        )
    )


def assignable_permissions(user):
    permissions = business_permissions()

    if user.is_superuser:
        return list(permissions)

    own = effective_permissions(user)

    return [
        permission for permission in permissions if permission_key(permission) in own
    ]


def permission_catalog(user):
    return [
        {
            "id": permission.pk,
            "key": permission_key(permission),
            "name": permission.name,
            "app": permission.content_type.app_label,
        }
        for permission in assignable_permissions(user)
    ]


def staff_data(user, actor):
    direct = list(
        user.user_permissions.select_related(
            "content_type",
        ).order_by("pk")
    )

    can_edit = False

    if actor.pk != user.pk and not user.is_superuser:
        if actor.is_superuser:
            can_edit = True
        elif can_manage(actor, "change"):
            own = effective_permissions(actor)
            target = effective_permissions(user)

            # Managers cannot alter users with stronger or
            # non-business permissions.
            allowed = {
                permission_key(permission) for permission in business_permissions()
            }
            can_edit = target <= own and target <= allowed

    return {
        "id": user.pk,
        "phone": user.phone,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.get_full_name(),
        "is_active": user.is_active,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "permissions": [permission_key(permission) for permission in direct],
        "effective_permissions": sorted(effective_permissions(user)),
        "has_groups": user.groups.exists(),
        "can_edit": can_edit,
    }


def _resolve_permissions(actor, keys):
    catalog = {
        permission_key(permission): permission
        for permission in assignable_permissions(actor)
    }

    unknown = sorted(set(keys) - set(catalog))

    if unknown:
        raise ValidationError(
            {
                "permissions": ("واگذاری این مجوزها مجاز نیست: " + "، ".join(unknown)),
            }
        )

    return [catalog[key] for key in sorted(set(keys))]


def _lock_actor(actor, action):
    current = User.objects.select_for_update().get(pk=actor.pk)
    require_action(current, action)
    return current


@transaction.atomic
def create_staff(actor, data):
    actor = _lock_actor(actor, "add")
    require_action(actor, "view")

    permissions = _resolve_permissions(
        actor,
        data.get("permissions", []),
    )

    phone = data["phone"]

    # Existing accounts are not silently promoted.
    if User.objects.filter(phone=phone).exists():
        raise ValidationError(
            {
                "phone": (
                    "این شماره حساب دارد. ارتقای حساب موجود از این "
                    "فرم مجاز نیست؛ مدیر اصلی باید آن را بررسی کند."
                ),
            }
        )

    # Serialize staff creation among cooperating service callers.
    # The unique phone constraint remains the final DB safeguard.
    user = User.objects.create_user(
        phone=phone,
        first_name=data.get("first_name", ""),
        last_name=data.get("last_name", ""),
        is_staff=True,
        is_active=True,
    )
    user.user_permissions.set(permissions)
    return user


@transaction.atomic
def update_staff(actor, target_id, data):
    # Deterministic lock ordering avoids reciprocal user-row deadlocks.
    locked = {
        user.pk: user
        for user in User.objects.select_for_update()
        .filter(pk__in=[actor.pk, target_id])
        .order_by("pk")
    }

    current_actor = locked.get(actor.pk)
    target = locked.get(target_id)

    if current_actor is None:
        raise PermissionDenied("حساب مدیریت معتبر نیست.")

    require_action(current_actor, "view")
    require_action(current_actor, "change")

    if target is None or not target.is_staff:
        raise ValidationError(
            {
                "user": "همکار موردنظر وجود ندارد.",
            }
        )

    if target.pk == current_actor.pk:
        raise PermissionDenied("ویرایش حساب خودتان از مدیریت همکاران مجاز نیست.")

    if target.is_superuser:
        raise PermissionDenied("حساب مدیر اصلی از این مسیر قابل تغییر نیست.")

    if not current_actor.is_superuser:
        own = effective_permissions(current_actor)
        target_permissions = effective_permissions(target)
        allowed = {permission_key(permission) for permission in business_permissions()}

        if not target_permissions <= own or not target_permissions <= allowed:
            raise PermissionDenied("اختیارات این همکار خارج از محدودهٔ مدیریت شماست.")

        # Group assignments must be reviewed by the owner.
        if target.groups.exists():
            raise PermissionDenied(
                "ویرایش همکار دارای گروه فقط برای مدیر اصلی مجاز است."
            )

    permissions = None

    if "permissions" in data:
        permissions = _resolve_permissions(
            current_actor,
            data["permissions"],
        )

        if target.groups.exists():
            raise ValidationError(
                {
                    "permissions": (
                        "این همکار مجوز گروهی دارد. ابتدا مدیر اصلی "
                        "گروه‌های او را بررسی کند؛ این فرم فقط مجوز مستقیم "
                        "را مدیریت می‌کند."
                    ),
                }
            )

    changed_fields = []

    for field in ("first_name", "last_name", "is_active"):
        if field in data:
            setattr(target, field, data[field])
            changed_fields.append(field)

    if changed_fields:
        target.save(update_fields=changed_fields)

    if permissions is not None:
        target.user_permissions.set(permissions)

    # Invalidate management sessions after any staff change.
    # Customer sessions remain governed by account activity.
    from django.utils import timezone

    AuthSession.objects.filter(
        user=target,
        purpose="management",
        revoked_at__isnull=True,
    ).update(revoked_at=timezone.now())

    return target
