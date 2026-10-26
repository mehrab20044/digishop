from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.forms.models import BaseInlineFormSet

from .forms import CustomUserChangeForm, CustomUserCreationForm
from .models import Address, Profile
from accounts.services.profile_service import (
    create_address,
    delete_address,
    get_profile_status,
    update_address,
)

User = get_user_model()

ADDRESS_FIELDS = [
    "recipient_name",
    "recipient_phone",
    "province",
    "city",
    "street_address",
    "building_number",
    "unit",
    "postal_code",
    "is_default",
]


def phone_for(user):
    return user.phone


class ProfileInline(admin.StackedInline):
    model = Profile
    extra = 0
    min_num = 1
    max_num = 1
    can_delete = False
    verbose_name = "اطلاعات تکمیلی"
    verbose_name_plural = "عکس و توضیحات"
    fields = ["image", "description"]


class AddressInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

        if any(self.errors):
            return

        default_count = sum(
            1
            for form in self.forms
            if form.cleaned_data
            and not form.cleaned_data.get("DELETE", False)
            and form.cleaned_data.get("is_default", False)
        )

        if default_count > 1:
            raise forms.ValidationError(
                "فقط یک آدرس می‌تواند پیش‌فرض باشد."
            )


class AddressInline(admin.StackedInline):
    model = Address
    formset = AddressInlineFormSet
    extra = 0
    verbose_name = "آدرس"
    verbose_name_plural = "آدرس‌های کاربر"
    fields = ADDRESS_FIELDS


if admin.site.is_registered(User):
    admin.site.unregister(User)

if admin.site.is_registered(Profile):
    admin.site.unregister(Profile)


@admin.register(User)
class ShopUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    inlines = [ProfileInline, AddressInline]
    ordering = ["-date_joined"]

    list_display = [
        "phone",
        "first_name",
        "last_name",
        "completed",
        "is_active",
        "is_staff",
    ]
    search_fields = ["phone", "first_name", "last_name", "email"]
    list_select_related = []
    readonly_fields = [
        "phone_verified_at",
        "completed",
        "last_login",
        "date_joined",
    ]

    fieldsets = (
        ("حساب کاربری", {
            "fields": ("phone", "password", "phone_verified_at", "completed"),
        }),
        ("اطلاعات شخصی", {
            "fields": ("first_name", "last_name", "email"),
        }),
        ("دسترسی‌ها", {
            "fields": (
                "is_active", "is_staff", "is_superuser",
                "groups", "user_permissions",
            ),
        }),
        ("تاریخ‌ها", {
            "fields": ("last_login", "date_joined"),
        }),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("phone", "password1", "password2"),
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        fields = list(self.readonly_fields)
        return fields + ["phone"] if obj else fields

    @admin.display(
        boolean=True,
        description="پروفایل کامل",
    )
    def completed(self, obj):
        return get_profile_status(obj)["profile_completed"]

    def save_model(self, request, obj, form, change):
        if change:
            # Django Admin wraps the change form in a transaction.
            # Lock before saving the user and related addresses.
            User.objects.select_for_update().get(pk=obj.pk)

        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        if formset.model is not Address:
            return super().save_formset(
                request,
                form,
                formset,
                change,
            )

        instances = formset.save(commit=False)

        for address in formset.deleted_objects:
            delete_address(address)

        # Save the explicitly selected default last.
        for address in sorted(
            instances,
            key=lambda item: item.is_default,
        ):
            data = {
                field: getattr(address, field)
                for field in ADDRESS_FIELDS
            }

            if address.pk:
                saved = update_address(address, data)
            else:
                saved = create_address(form.instance, data)

            address.pk = saved.pk
            address.is_default = saved.is_default
            address._state = saved._state

        formset.save_m2m()

        
@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "recipient_name",
        "city",
        "is_default",
    ]
    search_fields = [
        "user__phone",
        "recipient_name",
        "recipient_phone",
    ]
    list_select_related = ["user"]
    actions = ["make_default"]

    def get_readonly_fields(self, request, obj=None):
        fields = [
            "is_default",
            "created_at",
            "updated_at",
        ]
        return fields + ["user"] if obj else fields

    @admin.action(
        description="انتخاب به‌عنوان آدرس پیش‌فرض",
    )
    def make_default(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                "فقط یک آدرس انتخاب کنید.",
                messages.ERROR,
            )
            return

        update_address(
            queryset.get(),
            {"is_default": True},
        )

    def save_model(self, request, obj, form, change):
        fields = [
            "recipient_name",
            "recipient_phone",
            "province",
            "city",
            "street_address",
            "building_number",
            "unit",
            "postal_code",
        ]
        data = {
            field: getattr(obj, field)
            for field in fields
        }

        saved = (
            update_address(obj, data)
            if change
            else create_address(obj.user, data)
        )

        obj.pk = saved.pk
        obj.is_default = saved.is_default
        obj._state = saved._state

    def delete_model(self, request, obj):
        delete_address(obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset.order_by("user_id", "id"):
            delete_address(obj)