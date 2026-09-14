from django.contrib import admin

from .models import Activo, DepreciacionActivo, MantenimientoActivo


class DepreciacionActivoInline(admin.TabularInline):
    model = DepreciacionActivo
    extra = 0
    fields = ("periodo", "monto", "fecha", "observaciones")


class MantenimientoActivoInline(admin.TabularInline):
    model = MantenimientoActivo
    extra = 0
    fields = ("fecha", "tipo", "descripcion", "costo", "proveedor", "movimiento")
    autocomplete_fields = ("proveedor", "movimiento")


@admin.register(Activo)
class ActivoAdmin(admin.ModelAdmin):
    list_display = (
        "codigo", "nombre", "tipo", "sucursal", "fecha_adquisicion",
        "valor_adquisicion", "depreciacion_acumulada", "valor_libros", "estado",
    )
    list_filter = ("tipo", "estado", "sucursal", "moneda")
    search_fields = ("codigo", "nombre", "marca", "modelo", "numero_serie", "placa")
    date_hierarchy = "fecha_adquisicion"
    readonly_fields = (
        "depreciacion_mensual", "depreciacion_acumulada",
        "valor_libros", "costo_mantenimiento_total",
    )
    autocomplete_fields = ("proveedor",)
    inlines = [DepreciacionActivoInline, MantenimientoActivoInline]


@admin.register(DepreciacionActivo)
class DepreciacionActivoAdmin(admin.ModelAdmin):
    list_display = ("activo", "periodo", "monto", "fecha")
    list_filter = ("periodo", "fecha")
    search_fields = ("activo__codigo", "activo__nombre")


@admin.register(MantenimientoActivo)
class MantenimientoActivoAdmin(admin.ModelAdmin):
    list_display = ("activo", "tipo", "fecha", "costo", "proveedor")
    list_filter = ("tipo", "fecha")
    search_fields = ("activo__codigo", "descripcion")
    date_hierarchy = "fecha"
