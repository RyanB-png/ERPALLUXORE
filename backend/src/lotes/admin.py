from django.contrib import admin
from .models import Lote, LoteComercial, TipoMaterial


@admin.register(TipoMaterial)
class TipoMaterialAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre")


@admin.register(Lote)
class LoteAdmin(admin.ModelAdmin):
    list_display = (
        "codigo", "proveedor", "mostrar_tipo_material", "placa_vehiculo",
        "fecha_recepcion", "peso_neto", "estado", "lote_comercial","documento_liquidacion",
    )
    list_filter = ("tipo_material", "estado", "fecha_recepcion")
    search_fields = ("codigo", "proveedor__razon_social", "proveedor__nombre_completo", "placa_vehiculo")
    readonly_fields = ("codigo", "peso_neto")
    date_hierarchy = "fecha_recepcion"
    filter_horizontal = ("tipo_material",)

    def mostrar_tipo_material(self, obj):
        return ", ".join(t.nombre for t in obj.tipo_material.all())
    mostrar_tipo_material.short_description = "Tipo de Material"


class LoteInline(admin.TabularInline):
    model = Lote
    extra = 0
    fields = ("codigo", "proveedor", "peso_neto", "estado")
    readonly_fields = ("codigo", "proveedor", "peso_neto", "estado")
    can_delete = False


@admin.register(LoteComercial)
class LoteComercialAdmin(admin.ModelAdmin):
    list_display = ("codigo", "fecha_creacion", "peso_total", "estado")
    list_filter = ("estado", "fecha_creacion")
    date_hierarchy = "fecha_creacion"
    inlines = [LoteInline]