from django.contrib import admin

from .models import CategoriaGasto, Gasto


@admin.register(CategoriaGasto)
class CategoriaGastoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "cuenta_contable", "descripcion", "is_active")
    list_filter = ("cuenta_contable",)
    search_fields = ("nombre",)


@admin.register(Gasto)
class GastoAdmin(admin.ModelAdmin):
    list_display = (
        "categoria", "centro_costo", "lote",
        "mostrar_monto", "mostrar_fecha", "descripcion",
    )
    list_filter = ("categoria", "centro_costo")
    search_fields = ("descripcion", "movimiento__concepto", "lote__codigo")
    autocomplete_fields = ("movimiento", "lote")

    def mostrar_monto(self, obj):
        return f"{obj.movimiento.monto} {obj.movimiento.moneda}"
    mostrar_monto.short_description = "Monto"

    def mostrar_fecha(self, obj):
        return obj.movimiento.fecha
    mostrar_fecha.short_description = "Fecha"
