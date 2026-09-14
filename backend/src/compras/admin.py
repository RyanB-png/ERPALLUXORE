from django.contrib import admin
from .models import Compra, PagoCompra


class PagoCompraInline(admin.TabularInline):
    model = PagoCompra
    extra = 0
    fields = ("tipo_origen", "aplicacion_anticipo", "movimiento", "monto", "fecha")


@admin.register(Compra)
class CompraAdmin(admin.ModelAdmin):
    list_display = (
        "lote", "fecha_negociacion", "moneda", "valor_neto",
        "estado", "monto_pagado", "saldo_pendiente",
    )
    list_filter = ("estado", "moneda", "fecha_negociacion")
    search_fields = ("lote__codigo",)
    date_hierarchy = "fecha_negociacion"
    readonly_fields = ("monto_pagado", "saldo_pendiente")
    inlines = [PagoCompraInline]


@admin.register(PagoCompra)
class PagoCompraAdmin(admin.ModelAdmin):
    list_display = ("compra", "tipo_origen", "monto", "fecha")
    list_filter = ("tipo_origen", "fecha")