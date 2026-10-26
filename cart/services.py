import hashlib
import json
import re

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from products.models import Product, ProductVariant
from .models import Cart, CartItem, CartOperation

MAX_LINES = 100


def guest_digest(request, required=False):
    token = request.headers.get('X-Cart-Token', '')
    if not token and not required:
        return None
    if not re.fullmatch(r'[0-9a-f]{64}', token):
        raise ValidationError({'cart': 'شناسهٔ سبد مهمان معتبر نیست.'})
    return hashlib.sha256(token.encode()).hexdigest()


def resolve_cart(request, create=False, lock=False):
    if request.user.is_authenticated:
        lookup = {'user': request.user}
    else:
        digest = guest_digest(request, required=create)
        if digest is None:
            return None
        lookup = {'guest_digest': digest}
    if create:
        cart, _ = Cart.objects.get_or_create(**lookup)
        return Cart.objects.select_for_update().get(pk=cart.pk) if lock else cart
    query = Cart.objects.select_for_update() if lock else Cart.objects
    return query.filter(**lookup).first()


def touch(cart):
    Cart.objects.filter(pk=cart.pk).update(updated_at=timezone.now())


def selection(product_id, variant_id):
    product = get_object_or_404(Product.objects.select_for_update(), pk=product_id, is_active=True, status=Product.Status.PUBLISHED)
    has_variants = product.variants.exists()
    if has_variants and variant_id is None:
        raise ValidationError({'variant_id': 'ابتدا تنوع محصول را انتخاب کن.'})
    variant = None
    if variant_id is not None:
        variant = get_object_or_404(ProductVariant.objects.select_for_update(), pk=variant_id, product=product, is_active=True)
    price = variant.price if variant else product.price
    stock = variant.stock if variant else product.stock
    if price <= 0 or stock <= 0:
        raise ValidationError({'quantity': 'این کالا فعلاً موجود نیست.'})
    return product, variant, price, stock


def add_item(cart, data):
    fingerprint = hashlib.sha256(json.dumps({key: data[key] for key in ('product_id', 'variant_id', 'quantity')}, sort_keys=True).encode()).hexdigest()
    previous = cart.operations.filter(request_id=data['request_id']).first()
    if previous:
        if previous.fingerprint != fingerprint:
            raise ValidationError({'request_id': 'شناسهٔ درخواست با اطلاعات قبلی مطابقت ندارد.'})
        return
    product, variant, price, stock = selection(data['product_id'], data['variant_id'])
    key = f'p:{product.pk}:v:{variant.pk if variant else 0}'
    item = cart.items.filter(selection_key=key).first()
    quantity = (item.quantity if item else 0) + data['quantity']
    if quantity > 99 or quantity > stock:
        raise ValidationError({'quantity': f'حداکثر تعداد مجاز این انتخاب {min(99, stock)} عدد است.'})
    if item is None and cart.items.count() >= MAX_LINES:
        raise ValidationError({'cart': 'حداکثر ۱۰۰ انتخاب متفاوت در سبد مجاز است.'})
    if item:
        item.quantity = quantity
        # Preserve the previous price until the user acknowledges it with PATCH.
        item.save(update_fields=['quantity'])
    else:
        CartItem.objects.create(cart=cart, product=product, variant=variant, selection_key=key, product_name=product.name, variant_name=' / '.join(filter(None, [variant.color, variant.storage])) if variant else '', had_variant=bool(variant), quantity=quantity, price_seen=price)
    CartOperation.objects.create(cart=cart, request_id=data['request_id'], fingerprint=fingerprint)
    touch(cart)


def update_item(cart, item_id, quantity):
    item = get_object_or_404(cart.items, pk=item_id)
    if item.product_id is None or (item.had_variant and item.variant_id is None):
        raise ValidationError({'item': 'این انتخاب حذف شده است؛ آن را از سبد حذف کن.'})
    product, variant, price, stock = selection(item.product_id, item.variant_id)
    if not item.had_variant and product.variants.exists():
        raise ValidationError({'item': 'این محصول اکنون تنوع دارد؛ انتخاب قبلی را حذف و تنوع را دوباره انتخاب کن.'})
    if quantity > stock:
        raise ValidationError({'quantity': f'فقط {min(stock, 99)} عدد موجود است.'})
    item.quantity = quantity
    item.price_seen = price
    item.variant_name = ' / '.join(filter(None, [variant.color, variant.storage])) if variant else ''
    item.save(update_fields=['quantity', 'price_seen', 'variant_name'])
    touch(cart)


def snapshot(cart, request):
    rows = []
    if cart:
        items = cart.items.select_related('product', 'variant').prefetch_related('product__images', 'product__variants')
        for item in items:
            product, variant = item.product, item.variant
            public = bool(product and product.is_active and product.status == Product.Status.PUBLISHED)
            usable = public and (not item.had_variant or bool(variant and variant.is_active and variant.product_id == item.product_id))
            if usable and not item.had_variant and list(product.variants.all()):
                usable = False
            price = (variant.price if item.had_variant else product.price) if usable else None
            stock = (variant.stock if item.had_variant else product.stock) if usable else 0
            issues = []
            if not usable or not price or stock <= 0:
                issues.append('این انتخاب دیگر قابل خرید نیست؛ حذفش کن یا تنوع دیگری انتخاب کن.')
            elif item.quantity > stock:
                issues.append(f'موجودی کاهش یافته؛ فقط {stock} عدد باقی مانده است.')
            variant_name = ' / '.join(filter(None, [variant.color, variant.storage])) if usable and variant else item.variant_name
            selection_changed = bool(usable and variant and variant_name != item.variant_name)
            if selection_changed:
                issues.append('رنگ یا حافظهٔ این تنوع تغییر کرده؛ انتخاب جدید را بررسی و تأیید کن.')
            changed = price is not None and price != item.price_seen
            if changed:
                issues.append('قیمت تغییر کرده است. قیمت جدید را بررسی و تأیید کن.')
            image = None
            if public:
                images = sorted(product.images.all(), key=lambda image: (not image.is_primary, image.sort_order, image.pk))
                file = images[0].image if images else product.image
                if file:
                    image = file.url
            rows.append({
                'id': item.pk, 'product_id': item.product_id, 'variant_id': item.variant_id,
                'name': product.name if public else item.product_name,
                'variant_name': variant_name, 'selection_changed': selection_changed, 'image': image, 'quantity': item.quantity,
                'stock': max(stock, 0), 'max_quantity': min(max(stock, 0), 99),
                'unit_price': price, 'previous_unit_price': item.price_seen,
                'price_changed': changed, 'line_total': price * item.quantity if price is not None else None,
                'available': bool(usable and price and stock > 0),
                'valid': not issues, 'issues': issues,
            })
    return {
        'items': rows, 'item_count': sum(item['quantity'] for item in rows),
        'line_count': len(rows), 'subtotal': sum(item['line_total'] or 0 for item in rows),
        'has_issues': any(item['issues'] for item in rows),
        'can_checkout': bool(rows) and all(item['valid'] for item in rows),
        'currency': 'تومان', 'notices': [],
    }


def merge_guest(request):
    digest = guest_digest(request)
    cart = resolve_cart(request, create=True, lock=True)
    guest = Cart.objects.select_for_update().filter(guest_digest=digest).first() if digest else None
    notices = []
    if guest:
        target_items = {item.selection_key: item for item in cart.items.all()}
        incoming = list(guest.items.all())
        if len(set(target_items) | {item.selection_key for item in incoming}) > MAX_LINES:
            raise ValidationError({'cart': 'برای ادغام، تعداد انتخاب‌های متفاوت باید حداکثر ۱۰۰ باشد. سبد مهمان حفظ شده است.'})
        for item in incoming:
            target = target_items.get(item.selection_key)
            if target:
                total = target.quantity + item.quantity
                target.quantity = min(99, total)
                target.save(update_fields=['quantity'])
                if total > 99:
                    notices.append(f'تعداد «{item.product_name}» هنگام ادغام به سقف ۹۹ عدد محدود شد.')
            else:
                item.cart = cart
                item.save(update_fields=['cart'])
        CartOperation.objects.filter(cart=guest).exclude(request_id__in=cart.operations.values('request_id')).update(cart=cart)
        guest.delete()
        touch(cart)
    result = snapshot(cart, request)
    result['notices'] = notices
    return result
