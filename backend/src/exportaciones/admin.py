from django.contrib import admin

from .models import Exportacion, CostoExportacion


class CostoExportacionInline(admin.TabularInline):
    model = CostoExportacion
    extra = 1
    fields = ("tipo", "descripcion", "monto", "proveedor", "movimiento", "centro_costo", "fecha")
    autocomplete_fields = ("proveedor", "movimiento")


@admin.register(Exportacion)
class ExportacionAdmin(admin.ModelAdmin):
    list_display = (
        "numero", "fecha", "lote_comercial", "cliente", "pais_destino",
        "incoterm", "peso_total", "valor_bruto", "total_costos", "valor_neto", "estado",
    )
    list_filter = ("estado", "incoterm", "pais_destino", "fecha")
    search_fields = ("numero", "lote_comercial__codigo", "cliente__razon_social")
    date_hierarchy = "fecha"
    readonly_fields = ("numero", "valor_neto", "total_costos")
    autocomplete_fields = ("cliente",)
    inlines = [CostoExportacionInline]


@admin.register(CostoExportacion)
class CostoExportacionAdmin(admin.ModelAdmin):
    list_display = ("exportacion", "tipo", "descripcion", "monto", "proveedor", "fecha")
    list_filter = ("tipo", "fecha")
    search_fields = ("exportacion__numero", "descripcion")
