from django.contrib import admin

from .models import ContratoComercial, Venta, CobroVenta


@admin.register(ContratoComercial)
class ContratoComercialAdmin(admin.ModelAdmin):
    list_display = ("numero", "cliente", "fecha_inicio", "fecha_fin", "estado")
    list_filter = ("estado", "fecha_inicio")
    search_fields = ("numero", "cliente__razon_social", "cliente__nombre_completo")
    autocomplete_fields = ("cliente",)


class CobroVentaInline(admin.TabularInline):
    model = CobroVenta
    extra = 0
    fields = ("movimiento", "monto", "fecha", "observaciones")
    autocomplete_fields = ("movimiento",)


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = (
        "numero", "fecha", "cliente", "tipo", "peso",
        "valor_neto", "moneda", "estado", "monto_cobrado", "saldo_pendiente",
    )
    list_filter = ("estado", "tipo", "moneda", "fecha")
    search_fields = ("numero", "cliente__razon_social", "lote__codigo")
    date_hierarchy = "fecha"
    readonly_fields = ("numero", "valor_neto", "monto_cobrado", "saldo_pendiente")
    autocomplete_fields = ("cliente", "lote")
    inlines = [CobroVentaInline]


@admin.register(CobroVenta)
class CobroVentaAdmin(admin.ModelAdmin):
    list_display = ("venta", "monto", "fecha", "observaciones")
    list_filter = ("fecha",)
    search_fields = ("venta__numero",)
