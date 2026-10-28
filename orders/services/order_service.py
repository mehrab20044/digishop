import hashlib
import json
from datetime import timedelta
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import Address
from accounts.services.profile_service import require_complete_profile
from cart.models import Cart
from cart.services import MAX_LINES
from orders.models import Order, OrderItem, StoreSettings
from products.models import Product, ProductVariant

User = get_user_model()

ADDRESS_FIELDS = (
    "recipient_name",
    "recipient_phone",
    "province",
    "city",
    "street_address",
    "building_number",
    "unit",
    "postal_code",
)


def _lock_user(user):
    if not user or not user.is_authenticated:
        raise PermissionDenied("ابتدا وارد حساب شوید.")

    current = User.objects.select_for_update().get(pk=user.pk)

    if not current.is_active:
        raise PermissionDenied("حساب کاربری فعال نیست.")

    return current


def _checkout_settings():
    store_settings = StoreSettings.objects.filter(pk=1).first()

    if store_settings is None:
        raise ImproperlyConfigured(
            "Configure the store shipping cost before enabling checkout."
        )

    return store_settings.shipping_cost, 120


def _checkout_input(
    address_id,
    request_id,
    customer_note,
    expected_total=None,
):
    if type(address_id) is not int or address_id <= 0:
        raise ValidationError({
            "address_id": "شناسهٔ آدرس معتبر نیست.",
        })

    try:
        request_id = UUID(str(request_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError({
            "request_id": "شناسهٔ درخواست معتبر نیست.",
        }) from exc

    if not isinstance(customer_note, str):
        raise ValidationError({
            "customer_note": "توضیحات باید متن باشد.",
        })

    customer_note = customer_note.strip()

    if len(customer_note) > 1000:
        raise ValidationError({
            "customer_note": "توضیحات حداکثر ۱۰۰۰ نویسه مجاز است.",
        })
    if expected_total is not None:
        if type(expected_total) is not int or expected_total <= 0:
            raise ValidationError({
                "expected_total": "مبلغ تأییدشده معتبر نیست.",
            })
    payload = {
        "address_id": address_id,
        "customer_note": customer_note,
        "expected_total": expected_total,
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    return request_id, customer_note, fingerprint


def _address_snapshot(user, address_id):
    # Address services also lock the user before changing addresses.
    address = get_object_or_404(
        Address.objects.filter(user=user),
        pk=address_id,
    )

    try:
        address.full_clean(
            exclude=["user"],
            validate_unique=False,
            validate_constraints=False,
        )
    except DjangoValidationError as exc:
        raise ValidationError({
            "address_id": "آدرس انتخاب‌شده معتبر نیست؛ آن را اصلاح کنید.",
        }) from exc

    return {
        field: getattr(address, field)
        for field in ADDRESS_FIELDS
    }


def _lock_catalog(items):
    product_ids = sorted({
        item.product_id
        for item in items
        if item.product_id is not None
    })
    variant_ids = sorted({
        item.variant_id
        for item in items
        if item.variant_id is not None
    })

    # Always lock products first, then variants, in ascending ID order.
    products = {
        product.pk: product
        for product in Product.objects.select_for_update()
        .filter(pk__in=product_ids)
        .order_by("pk")
    }
    variants = {
        variant.pk: variant
        for variant in ProductVariant.objects.select_for_update()
        .filter(pk__in=variant_ids)
        .order_by("pk")
    }

    return products, variants


def _prepare_items(items, products, variants):
    prepared = []
    issues = {}

    products_with_variants = set(
        ProductVariant.objects.filter(
            product_id__in=products,
        ).values_list("product_id", flat=True)
    )

    for item in items:
        product = products.get(item.product_id)
        variant = variants.get(item.variant_id)
        errors = []

        if (
            product is None
            or not product.is_active
            or product.status != Product.Status.PUBLISHED
        ):
            errors.append("این محصول دیگر قابل خرید نیست.")

        if item.had_variant:
            if (
                variant is None
                or not variant.is_active
                or variant.product_id != item.product_id
            ):
                errors.append("تنوع انتخاب‌شده دیگر قابل خرید نیست.")
        elif (
            item.variant_id is not None
            or item.product_id in products_with_variants
        ):
            errors.append("تنوع محصول را دوباره انتخاب کنید.")

        if errors:
            issues[str(item.pk)] = errors
            continue

        stock_owner = variant if item.had_variant else product
        variant_name = (
            " / ".join(filter(None, [variant.color, variant.storage]))
            if item.had_variant
            else ""
        )

        if stock_owner.price <= 0:
            errors.append("قیمت این انتخاب معتبر نیست.")

        if stock_owner.price != item.price_seen:
            errors.append(
                "قیمت تغییر کرده است؛ قیمت جدید را در سبد تأیید کنید."
            )

        if variant_name != item.variant_name:
            errors.append(
                "مشخصات تنوع تغییر کرده است؛ انتخاب را در سبد تأیید کنید."
            )

        if not 1 <= item.quantity <= 99:
            errors.append("تعداد انتخاب‌شده معتبر نیست.")
        elif item.quantity > stock_owner.stock:
            errors.append(
                f"موجودی کافی نیست؛ موجودی فعلی {stock_owner.stock} عدد است."
            )

        if errors:
            issues[str(item.pk)] = errors
            continue

        prepared.append({
            "stock_owner": stock_owner,
            "product": product,
            "variant": variant if item.had_variant else None,
            "selection_key": item.selection_key,
            "product_name": product.name,
            "product_slug": product.slug,
            "variant_name": variant_name,
            "sku": variant.sku if item.had_variant else "",
            "had_variant": item.had_variant,
            "quantity": item.quantity,
            "unit_price": stock_owner.price,
            "line_total": stock_owner.price * item.quantity,
        })

    if issues:
        raise ValidationError({
            "detail": "ابتدا مشکلات سبد خرید را برطرف کنید.",
            "items": issues,
        })

    return prepared


@transaction.atomic
def create_order(
    user,
    *,
    address_id,
    request_id,
    customer_note="",
    expected_total=None,
):
    request_id, customer_note, fingerprint = _checkout_input(
        address_id,
        request_id,
        customer_note,
        expected_total=expected_total,
    )
    user = _lock_user(user)

    previous = Order.objects.filter(
        user=user,
        request_id=request_id,
    ).first()

    if previous is not None:
        if previous.request_fingerprint != fingerprint:
            raise ValidationError({
                "request_id": (
                    "این شناسه قبلاً با اطلاعات دیگری استفاده شده است."
                ),
            })

        return previous, False

    require_complete_profile(user)
    address_data = _address_snapshot(user, address_id)
    shipping_cost, reservation_minutes = _checkout_settings()

    cart = (
        Cart.objects.select_for_update()
        .filter(user=user)
        .first()
    )

    if cart is None:
        raise ValidationError({"cart": "سبد خرید خالی است."})

    # Cart mutation services must hold the same cart lock.
    items = list(cart.items.order_by("pk"))

    if not items:
        raise ValidationError({"cart": "سبد خرید خالی است."})

    if len(items) > MAX_LINES:
        raise ValidationError({
            "cart": "تعداد انتخاب‌های سبد بیش از حد مجاز است.",
        })

    products, variants = _lock_catalog(items)
    prepared = _prepare_items(items, products, variants)
    subtotal = sum(row["line_total"] for row in prepared)

    total = subtotal + shipping_cost

    if expected_total is not None and expected_total != total:
        raise ValidationError({
            "expected_total": (
                "مبلغ سفارش تغییر کرده است؛ "
                "پیش‌نمایش جدید را بررسی و دوباره تأیید کنید."
            ),
        })

    order = Order.objects.create(
        user=user,
        request_id=request_id,
        request_fingerprint=fingerprint,
        customer_note=customer_note,
        subtotal=subtotal,
        shipping_cost=shipping_cost,
        total=total,
        expires_at=timezone.now() + timedelta(
            minutes=reservation_minutes,
        ),
        **address_data,
    )

    order_items = []

    for row in prepared:
        stock_owner = row["stock_owner"]

        changed = type(stock_owner).objects.filter(
            pk=stock_owner.pk,
            stock__gte=row["quantity"],
        ).update(
            stock=F("stock") - row["quantity"],
        )

        if changed != 1:
            raise ValidationError({
                "cart": "موجودی تغییر کرده است؛ دوباره بررسی کنید.",
            })

        order_items.append(OrderItem(
            order=order,
            **{
                key: value
                for key, value in row.items()
                if key != "stock_owner"
            },
        ))

    OrderItem.objects.bulk_create(order_items)

    # Delete only the checked-out rows.
    cart.items.filter(
        pk__in=[item.pk for item in items],
    ).delete()
    Cart.objects.filter(pk=cart.pk).update(
        updated_at=timezone.now(),
    )

    return order, True


def _release_stock(order):
    items = list(order.items.order_by("pk"))
    products, variants = _lock_catalog(items)

    for item in items:
        if item.had_variant:
            stock_owner = variants.get(item.variant_id)

            if (
                stock_owner is None
                or stock_owner.product_id != item.product_id
            ):
                continue
        else:
            stock_owner = products.get(item.product_id)

            if stock_owner is None:
                continue

        type(stock_owner).objects.filter(
            pk=stock_owner.pk,
        ).update(
            stock=F("stock") + item.quantity,
        )


def _close_pending_order(order, *, status, now):
    _release_stock(order)
    order.status = status

    timestamp_field = (
        "expired_at"
        if status == Order.Status.EXPIRED
        else "cancelled_at"
    )
    setattr(order, timestamp_field, now)

    order.save(update_fields=[
        "status",
        timestamp_field,
        "updated_at",
    ])

    return order


@transaction.atomic
def cancel_order(user, *, order_id):
    user = _lock_user(user)
    order = get_object_or_404(
        Order.objects.select_for_update().filter(user=user),
        pk=order_id,
    )

    if order.status in {
        Order.Status.CANCELLED,
        Order.Status.EXPIRED,
    }:
        return order

    if order.status != Order.Status.PENDING_PAYMENT:
        raise ValidationError({
            "order": "لغو مستقیم این سفارش امکان‌پذیر نیست.",
        })

    now = timezone.now()
    status = (
        Order.Status.EXPIRED
        if order.expires_at <= now
        else Order.Status.CANCELLED
    )

    return _close_pending_order(order, status=status, now=now)


@transaction.atomic
def expire_order(*, order_id):
    owner_id = (
        Order.objects.filter(pk=order_id)
        .values_list("user_id", flat=True)
        .first()
    )

    if owner_id is None:
        return False

    # Match the lock order used by checkout and cancellation.
    User.objects.select_for_update().get(pk=owner_id)
    order = Order.objects.select_for_update().get(pk=order_id)
    now = timezone.now()

    if (
        order.status != Order.Status.PENDING_PAYMENT
        or order.expires_at > now
    ):
        return False

    _close_pending_order(
        order,
        status=Order.Status.EXPIRED,
        now=now,
    )
    return True

@transaction.atomic
def preview_order(user, *, address_id):
    if type(address_id) is not int or address_id <= 0:
        raise ValidationError({
            "address_id": "شناسهٔ آدرس معتبر نیست.",
        })

    user = _lock_user(user)
    require_complete_profile(user)

    address_data = _address_snapshot(user, address_id)
    shipping_cost, reservation_minutes = _checkout_settings()

    cart = (
        Cart.objects.select_for_update()
        .filter(user=user)
        .first()
    )

    if cart is None:
        raise ValidationError({"cart": "سبد خرید خالی است."})

    items = list(cart.items.order_by("pk"))

    if not items:
        raise ValidationError({"cart": "سبد خرید خالی است."})

    if len(items) > MAX_LINES:
        raise ValidationError({
            "cart": "تعداد انتخاب‌های سبد بیش از حد مجاز است.",
        })

    products, variants = _lock_catalog(items)
    prepared = _prepare_items(items, products, variants)

    subtotal = sum(row["line_total"] for row in prepared)

    return {
        "address_id": address_id,
        "address": address_data,
        "currency": "IRT",
        "items": [
            {
                "product_id": row["product"].pk,
                "variant_id": (
                    row["variant"].pk
                    if row["variant"] is not None
                    else None
                ),
                "product_name": row["product_name"],
                "variant_name": row["variant_name"],
                "quantity": row["quantity"],
                "unit_price": row["unit_price"],
                "line_total": row["line_total"],
            }
            for row in prepared
        ],
        "item_count": sum(row["quantity"] for row in prepared),
        "subtotal": subtotal,
        "shipping_cost": shipping_cost,
        "total": subtotal + shipping_cost,
        "reservation_minutes": reservation_minutes,
    }