from django.contrib import admin
from .models import Category, Listing


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ('title', 'type', 'category', 'owner', 'available', 'created_at')
    list_filter = ('type', 'category', 'available')
    search_fields = ('title', 'owner__email')
    autocomplete_fields = ('owner',)
