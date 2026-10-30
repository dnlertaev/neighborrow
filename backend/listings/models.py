from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name


class Listing(models.Model):
    class Kind(models.TextChoices):
        OFFER = 'offer', 'Offer'
        REQUEST = 'request', 'Request'

    class Condition(models.TextChoices):
        GOOD = 'good', 'Good'
        LIKE_NEW = 'like_new', 'Like new'
        ANY = 'any_working', 'Any working'

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='listings')
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='listings')
    type = models.CharField(max_length=7, choices=Kind.choices)
    title = models.CharField(max_length=100)
    description = models.TextField(max_length=2000)
    condition = models.CharField(max_length=16, choices=Condition.choices, default=Condition.GOOD)
    duration = models.CharField(max_length=100)
    needed_until = models.DateField(null=True, blank=True)
    available = models.BooleanField(default=True)
    neighborhood = models.CharField(max_length=150, blank=True)
    latitude = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    image_url = models.URLField(max_length=1000, blank=True)
    contact_phone = models.CharField(max_length=32, blank=True)
    contact_social = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['type', 'category', 'available']),
                   models.Index(fields=['owner', '-created_at'])]
        constraints = [
            models.CheckConstraint(condition=Q(type__in=['offer', 'request']), name='valid_listing_type'),
            models.CheckConstraint(condition=(Q(latitude__isnull=True, longitude__isnull=True) |
                                   Q(latitude__isnull=False, longitude__isnull=False)), name='paired_coordinates'),
        ]

    def __str__(self):
        return self.title


class Interest(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='interests')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='interests')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['listing', 'user'], name='one_interest_per_user')]


class Activity(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='activities')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    listing = models.ForeignKey(Listing, on_delete=models.SET_NULL, null=True, related_name='+')
    type = models.CharField(max_length=32)
    item_title = models.CharField(max_length=100)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
