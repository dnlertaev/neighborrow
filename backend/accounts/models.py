from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.contrib.auth.hashers import check_password, make_password
from django.db import models


class ResidentialComplex(models.Model):
    name = models.CharField(max_length=150, unique=True)
    code_hash = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def set_code(self, code):
        if len(code) < 8:
            raise ValueError('The residential complex code must have at least 8 characters.')
        self.code_hash = make_password(code)

    def check_code(self, code):
        return check_password(code, self.code_hash)


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        if not extra_fields['is_staff'] or not extra_fields['is_superuser']:
            raise ValueError('Superuser must have is_staff and is_superuser')
        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    address = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    social_url = models.URLField(max_length=500, blank=True)
    residential_complex = models.ForeignKey(ResidentialComplex, on_delete=models.PROTECT,
                                            null=True, blank=True, related_name='residents')
    residential_verified_at = models.DateTimeField(null=True, blank=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = UserManager()

    @property
    def is_resident_verified(self):
        return self.residential_complex_id is not None and self.residential_verified_at is not None

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        super().save(*args, **kwargs)
