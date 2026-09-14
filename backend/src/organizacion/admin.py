from django.contrib import admin
from .models import Empresa, Sucursal, Caja, CuentaBancaria


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("razon_social", "nit", "telefono", "email", "is_active")
    search_fields = ("razon_social", "nit")


@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ("nombre", "empresa", "es_principal", "is_active")
    list_filter = ("empresa", "es_principal")


@admin.register(Caja)
class CajaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "empresa", "moneda", "saldo_actual", "is_active")
    list_filter = ("empresa", "moneda")


@admin.register(CuentaBancaria)
class CuentaBancariaAdmin(admin.ModelAdmin):
    list_display = ("banco", "numero_cuenta", "empresa", "moneda", "saldo_actual", "is_active")
    list_filter = ("empresa", "banco", "moneda")
    search_fields = ("numero_cuenta", "banco")