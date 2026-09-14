from django.contrib import admin

from .models import (
    CotizacionMineral,
    ReglaLiquidacion,
    ConceptoDeduccion,
    Liquidacion,
    DetalleLiquidacion,
    DeduccionLiquidacion,
)


@admin.register(CotizacionMineral)
class CotizacionMineralAdmin(admin.ModelAdmin):
    list_display = ("elemento", "fecha", "precio", "unidad", "fuente")
    list_filter = ("elemento", "unidad", "fecha")
    date_hierarchy = "fecha"
    autocomplete_fields = ("elemento",)


@admin.register(ReglaLiquidacion)
class ReglaLiquidacionAdmin(admin.ModelAdmin):
    list_display = (
        "elemento", "proveedor", "porcentaje_pagable", "ley_minima",
        "vigente_desde", "vigente_hasta", "is_active",
    )
    list_filter = ("elemento", "is_active")
    search_fields = ("elemento__simbolo", "proveedor__razon_social")
    autocomplete_fields = ("elemento", "proveedor")


@admin.register(ConceptoDeduccion)
class ConceptoDeduccionAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre")
    search_fields = ("codigo", "nombre")


class DetalleLiquidacionInline(admin.TabularInline):
    model = DetalleLiquidacion
    extra = 0
    fields = (
        "elemento", "ley", "unidad_ley", "cotizacion", "precio_unitario",
        "unidad_precio", "porcentaje_pagable", "contenido_fino", "valor",
    )
    readonly_fields = ("contenido_fino", "valor")


class DeduccionLiquidacionInline(admin.TabularInline):
    model = DeduccionLiquidacion
    extra = 1
    fields = ("concepto", "tipo_calculo", "valor", "monto", "observaciones")
    readonly_fields = ("monto",)


@admin.register(Liquidacion)
class LiquidacionAdmin(admin.ModelAdmin):
    list_display = (
        "numero", "lote", "fecha", "peso_seco",
        "valor_bruto", "total_deducciones", "valor_neto", "estado",
    )
    list_filter = ("estado", "moneda", "fecha")
    search_fields = ("numero", "lote__codigo")
    date_hierarchy = "fecha"
    readonly_fields = (
        "numero", "peso_humedo", "humedad", "peso_seco",
        "valor_bruto", "total_deducciones", "valor_neto",
    )
    autocomplete_fields = ("lote", "muestra")
    inlines = [DetalleLiquidacionInline, DeduccionLiquidacionInline]
    actions = ["accion_generar_detalles", "accion_recalcular"]

    @admin.action(description="Generar detalles desde los resultados de laboratorio")
    def accion_generar_detalles(self, request, queryset):
        for liquidacion in queryset:
            liquidacion.generar_detalles()
        self.message_user(
            request, f"{queryset.count()} liquidación(es) regenerada(s) desde laboratorio."
        )

    @admin.action(description="Recalcular totales")
    def accion_recalcular(self, request, queryset):
        for liquidacion in queryset:
            liquidacion.recalcular()
        self.message_user(request, f"{queryset.count()} liquidación(es) recalculada(s).")


@admin.register(DetalleLiquidacion)
class DetalleLiquidacionAdmin(admin.ModelAdmin):
    list_display = (
        "liquidacion", "elemento", "ley", "contenido_fino",
        "precio_unitario", "porcentaje_pagable", "valor",
    )
    list_filter = ("elemento",)


@admin.register(DeduccionLiquidacion)
class DeduccionLiquidacionAdmin(admin.ModelAdmin):
    list_display = ("liquidacion", "concepto", "tipo_calculo", "valor", "monto")
    list_filter = ("concepto", "tipo_calculo")
