from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class DigidockerUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Digidocker', {'fields': ('role', 'roll_number', 'phone')}),
    )
    list_display = ('username', 'email', 'role', 'roll_number', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser')
