from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, phone, password, **extra_fields):
        if not phone:
            raise ValueError("شماره موبایل الزامی است.")

        phone = self.model._meta.get_field("phone").clean(phone, None)

        email = extra_fields.get("email")
        if email:
            extra_fields["email"] = self.normalize_email(email)

        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(phone, password, **extra_fields)

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        for field in ("is_staff", "is_superuser", "is_active"):
            if extra_fields.get(field) is not True:
                raise ValueError(f"مدیر اصلی باید {field}=True داشته باشد.")

        if not password:
            raise ValueError("رمز عبور مدیر اصلی الزامی است.")

        return self._create_user(phone, password, **extra_fields)