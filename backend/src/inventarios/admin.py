from django.contrib import admin

from .models import (
    Almacen,
    ExistenciaLote,
    MovimientoInventario,
    TransferenciaAlmacen,
    InventarioFisico,
    DetalleInventarioFisico,
)


@admin.register(Almacen)
class AlmacenAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "sucursal", "ubicacion", "is_active")
    list_filter = ("sucursal",)
    search_fields = ("codigo", "nombre", "ubicacion")


@admin.register(ExistenciaLote)
class ExistenciaLoteAdmin(admin.ModelAdmin):
    """Solo lectura: el stock lo mantienen las señales, no se edita a mano."""

    list_display = ("lote", "almacen", "peso_actual")
    list_filter = ("almacen",)
    search_fields = ("lote__codigo", "almacen__codigo")
    readonly_fields = ("almacen", "lote", "peso_actual")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ("fecha", "tipo", "motivo", "almacen", "lote", "peso", "referencia")
    list_filter = ("tipo", "motivo", "almacen", "fecha")
    search_fields = ("lote__codigo", "referencia")
    date_hierarchy = "fecha"
    autocomplete_fields = ("lote",)


@admin.register(TransferenciaAlmacen)
class TransferenciaAlmacenAdmin(admin.ModelAdmin):
    list_display = ("fecha", "lote", "almacen_origen", "almacen_destino", "peso")
    list_filter = ("almacen_origen", "almacen_destino", "fecha")
    search_fields = ("lote__codigo",)
    date_hierarchy = "fecha"
    autocomplete_fields = ("lote",)


class DetalleInventarioFisicoInline(admin.TabularInline):
    model = DetalleInventarioFisico
    extra = 1
    fields = ("lote", "peso_sistema", "peso_fisico", "mostrar_diferencia", "observaciones")
    readonly_fields = ("mostrar_diferencia",)
    autocomplete_fields = ("lote",)

    def mostrar_diferencia(self, obj):
        return obj.diferencia
    mostrar_diferencia.short_description = "Diferencia"


@admin.register(InventarioFisico)
class InventarioFisicoAdmin(admin.ModelAdmin):
    list_display = ("almacen", "fecha", "estado", "diferencia_total")
    list_filter = ("estado", "almacen", "fecha")
    date_hierarchy = "fecha"
    readonly_fields = ("diferencia_total",)
    inlines = [DetalleInventarioFisicoInline]


@admin.register(DetalleInventarioFisico)
class DetalleInventarioFisicoAdmin(admin.ModelAdmin):
    list_display = ("inventario", "lote", "peso_sistema", "peso_fisico", "diferencia")
    search_fields = ("lote__codigo",)
