from django.contrib import admin
from django.utils.html import format_html

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


class DeduccionLiquidacionInline(admin.TabularInline):
    model = DeduccionLiquidacion
    extra = 0
    fields = ("concepto", "tipo_calculo", "valor", "monto", "observaciones")


@admin.register(Liquidacion)
class LiquidacionAdmin(admin.ModelAdmin):
    """
    Vista de registro: el calculo se hace en el frontend, aqui se consulta
    lo guardado y se verifica que los importes cuadren entre si.
    """

    list_display = (
        "numero", "lote", "fecha", "peso_seco",
        "valor_bruto", "total_deducciones", "valor_neto",
        "estado", "mostrar_cuadra", "mostrar_pdf",
    )
    list_filter = ("estado", "moneda", "fecha")
    search_fields = ("numero", "lote__codigo")
    date_hierarchy = "fecha"
    readonly_fields = ("numero", "mostrar_verificacion", "mostrar_pdf")
    autocomplete_fields = ("lote", "muestra")
    inlines = [DetalleLiquidacionInline, DeduccionLiquidacionInline]
    actions = ["accion_generar_pdf"]

    @admin.action(description="Generar / regenerar el PDF de la liquidación")
    def accion_generar_pdf(self, request, queryset):
        """
        Regenera el documento desde lo guardado. Se hace una por una y se
        capturan los fallos individualmente: que una liquidacion sin detalles
        reviente no debe impedir que se generen las demas de la seleccion.
        """
        generadas = 0
        for liquidacion in queryset:
            try:
                liquidacion.generar_pdf()
                generadas += 1
            except Exception as e:
                self.message_user(
                    request, f"{liquidacion.numero}: {e}", level="ERROR",
                )
        if generadas:
            self.message_user(request, f"{generadas} PDF(s) generado(s).")

    def mostrar_pdf(self, obj):
        if not obj.archivo_pdf:
            return "—"
        return format_html(
            '<a href="{}" target="_blank">Ver PDF</a>', obj.archivo_pdf.url,
        )
    mostrar_pdf.short_description = "PDF"

    def mostrar_cuadra(self, obj):
        return obj.cuadra
    mostrar_cuadra.short_description = "Cuadra"
    mostrar_cuadra.boolean = True

    def mostrar_verificacion(self, obj):
        """Discrepancias entre los totales de la cabecera y sus lineas."""
        if obj.pk is None:
            return "Se verifica al guardar."
        problemas = obj.verificar_consistencia()
        if not problemas:
            return "Los totales coinciden con el detalle."
        return format_html(
            '<ul style="margin:0;padding-left:18px;color:#ba2121;">{}</ul>',
            format_html("".join(f"<li>{p}</li>" for p in problemas)),
        )
    mostrar_verificacion.short_description = "Verificación de totales"


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