from django.contrib import admin
from .models import (
    MovimientoFinanciero,
    TransferenciaEntreCuentas,
    Anticipo,
    AplicacionAnticipo,
)


@admin.register(MovimientoFinanciero)
class MovimientoFinancieroAdmin(admin.ModelAdmin):
    list_display = ("fecha", "tipo", "origen", "caja", "cuenta_bancaria", "tercero", "concepto", "monto", "moneda")
    list_filter = ("tipo", "origen", "moneda", "fecha")
    search_fields = ("concepto", "tercero__razon_social", "tercero__nombre_completo")
    date_hierarchy = "fecha"


@admin.register(TransferenciaEntreCuentas)
class TransferenciaEntreCuentasAdmin(admin.ModelAdmin):
    list_display = ("fecha", "origen_tipo", "destino_tipo", "monto")
    list_filter = ("origen_tipo", "destino_tipo", "fecha")
    date_hierarchy = "fecha"


class AplicacionAnticipoInline(admin.TabularInline):
    model = AplicacionAnticipo
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Anticipo)
class AnticipoAdmin(admin.ModelAdmin):
    list_display = ("tercero", "fecha", "monto_total", "moneda", "estado", "monto_aplicado", "saldo_disponible")
    list_filter = ("estado", "moneda", "fecha")
    search_fields = ("tercero__razon_social", "tercero__nombre_completo")
    date_hierarchy = "fecha"
    inlines = [AplicacionAnticipoInline]
    readonly_fields = ("monto_aplicado", "saldo_disponible")


@admin.register(AplicacionAnticipo)
class AplicacionAnticipoAdmin(admin.ModelAdmin):
    list_display = ("anticipo", "monto", "fecha", "referencia")
    list_filter = ("fecha",)