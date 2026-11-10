from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django import forms
from .models import ResidentialComplex, User


class ResidentialComplexForm(forms.ModelForm):
    code = forms.CharField(label='Resident code', min_length=8, max_length=128,
                           required=False, widget=forms.PasswordInput,
                           help_text='Required when creating a complex. Leave blank to keep the current code.')

    class Meta:
        model = ResidentialComplex
        fields = ('name', 'is_active')

    def clean_code(self):
        code = self.cleaned_data['code']
        if not self.instance.pk and not code:
            raise forms.ValidationError('Enter a resident code.')
        return code


@admin.register(ResidentialComplex)
class ResidentialComplexAdmin(admin.ModelAdmin):
    form = ResidentialComplexForm
    fields = ('name', 'is_active', 'code')
    list_display = ('name', 'is_active')
    search_fields = ('name',)

    def save_model(self, request, obj, form, change):
        code = form.cleaned_data['code']
        if code:
            obj.set_code(code)
        super().save_model(request, obj, form, change)


@admin.register(User)
class NeighborUserAdmin(UserAdmin):
    ordering = ('email',)
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'is_active')
    search_fields = ('email', 'first_name', 'last_name')
    readonly_fields = ('residential_complex', 'residential_verified_at')
    fieldsets = ((None, {'fields': ('email', 'password')}),
                 ('Profile', {'fields': ('first_name', 'last_name', 'address', 'phone', 'social_url')}),
                 ('Residence', {'fields': ('residential_complex', 'residential_verified_at')}),
                 ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
                 ('Dates', {'fields': ('last_login', 'date_joined')}))
    add_fieldsets = ((None, {'classes': ('wide',), 'fields': ('email', 'password1', 'password2')}),)
