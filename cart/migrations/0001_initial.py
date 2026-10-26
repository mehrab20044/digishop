import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('products', '0010_product_status'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Cart',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('guest_digest', models.CharField(blank=True, max_length=64, null=True, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='shopping_cart', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='CartItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('selection_key', models.CharField(max_length=100)),
                ('product_name', models.CharField(max_length=200)),
                ('variant_name', models.CharField(blank=True, max_length=210)),
                ('had_variant', models.BooleanField(default=False)),
                ('quantity', models.PositiveIntegerField()),
                ('price_seen', models.PositiveBigIntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('cart', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='cart.cart')),
                ('product', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='products.product')),
                ('variant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='products.productvariant')),
            ],
            options={
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='CartOperation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('request_id', models.UUIDField()),
                ('fingerprint', models.CharField(max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('cart', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='operations', to='cart.cart')),
            ],
        ),
        migrations.AddConstraint(
            model_name='cart',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('guest_digest__isnull', True), ('user__isnull', False)), models.Q(('guest_digest__isnull', False), ('user__isnull', True)), _connector='OR'), name='cart_exactly_one_owner'),
        ),
        migrations.AddConstraint(
            model_name='cartitem',
            constraint=models.UniqueConstraint(fields=('cart', 'selection_key'), name='cart_unique_selection'),
        ),
        migrations.AddConstraint(
            model_name='cartitem',
            constraint=models.CheckConstraint(condition=models.Q(('quantity__gte', 1), ('quantity__lte', 99)), name='cart_quantity_1_to_99'),
        ),
        migrations.AddConstraint(
            model_name='cartoperation',
            constraint=models.UniqueConstraint(fields=('cart', 'request_id'), name='cart_unique_operation'),
        ),
    ]
