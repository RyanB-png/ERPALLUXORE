from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Datos Alluxore", {"fields": ("rol", "telefono", "cargo", "sucursal")}),
    )
    list_display = ("username", "email", "rol", "sucursal", "cargo", "is_staff", "is_active")
    list_filter = UserAdmin.list_filter + ("rol", "sucursal")