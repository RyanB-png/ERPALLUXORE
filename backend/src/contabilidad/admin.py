from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from .models import (
    CentroCosto,
    ConfiguracionContable,
    CuentaContable,
    PeriodoContable,
    Asiento,
    LineaAsiento,
)
from .servicios import generar_asiento


@admin.register(ConfiguracionContable)
class ConfiguracionContableAdmin(admin.ModelAdmin):
    """
    Registro unico. Define que cuenta usa cada tipo de operacion para que el
    sistema pueda armar los asientos solo.
    """

    list_display = ("__str__", "generar_asientos_automaticos", "is_active")
    fieldsets = (
        ("Generación automática", {
            "fields": ("generar_asientos_automaticos",),
        }),
        ("Compras de mineral", {
            "fields": ("inventario_mineral", "cuentas_por_pagar", "anticipos_proveedores"),
        }),
        ("Ventas", {
            "fields": ("cuentas_por_cobrar", "ventas"),
        }),
        ("Movimientos sin documento", {
            "fields": ("ingresos_varios", "egresos_varios"),
            "description": "Se usan para movimientos de caja o banco que no "
                           "corresponden a una compra, venta, gasto o anticipo.",
        }),
    )

    def has_add_permission(self, request):
        # Solo tiene sentido una configuracion; si ya existe, no se agrega otra.
        return not ConfiguracionContable.objects.exists()


@admin.register(CentroCosto)
class CentroCostoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "centro_padre", "permite_imputacion", "is_active")
    list_filter = ("permite_imputacion", "is_active")
    search_fields = ("codigo", "nombre")


@admin.register(CuentaContable)
class CuentaContableAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "tipo", "cuenta_padre", "permite_movimiento")
    list_filter = ("tipo", "permite_movimiento")
    search_fields = ("codigo", "nombre")


@admin.register(PeriodoContable)
class PeriodoContableAdmin(admin.ModelAdmin):
    list_display = ("anio", "mes", "fecha_inicio", "fecha_fin", "estado")
    list_filter = ("estado", "anio")


class LineaAsientoFormSet(BaseInlineFormSet):
    """
    Valida el asiento como CONJUNTO: el clean() del modelo revisa una linea,
    este revisa todas juntas y exige que la suma del Debe iguale a la del Haber.
    """

    def clean(self):
        super().clean()

        total_debe = 0
        total_haber = 0
        lineas_validas = 0

        for form in self.forms:
            # Un formulario que fallo su propia validacion no tiene cleaned_data.
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE"):
                continue

            debe = form.cleaned_data.get("debe") or 0
            haber = form.cleaned_data.get("haber") or 0

            if debe or haber:
                lineas_validas += 1

            total_debe += debe
            total_haber += haber

        if lineas_validas < 2:
            raise ValidationError(
                "Un asiento debe tener al menos 2 líneas (una en Debe y otra en Haber)."
            )

        if total_debe != total_haber:
            raise ValidationError(
                f"El asiento no cuadra: Debe = {total_debe}, Haber = {total_haber}. "
                f"Deben ser iguales."
            )


class LineaAsientoInline(admin.TabularInline):
    model = LineaAsiento
    formset = LineaAsientoFormSet
    extra = 2
    fields = ("cuenta", "centro_costo", "debe", "haber", "glosa")


@admin.register(Asiento)
class AsientoAdmin(admin.ModelAdmin):
    list_display = (
        "numero", "fecha", "periodo", "concepto",
        "mostrar_total_debe", "mostrar_total_haber", "mostrar_cuadrado",
        "automatico", "mostrar_origen",
    )
    list_filter = ("periodo", "automatico")
    search_fields = ("numero", "concepto")
    readonly_fields = ("numero", "periodo", "automatico", "mostrar_origen")
    date_hierarchy = "fecha"
    inlines = [LineaAsientoInline]
    actions = ["accion_regenerar"]

    @admin.action(description="Regenerar asiento desde la operación de origen")
    def accion_regenerar(self, request, queryset):
        """
        Rehace el asiento a partir de la operacion que lo origino. Util cuando
        se corrigio la configuracion contable despues de haberlo generado.
        """
        regenerados = omitidos = 0
        for asiento in queryset:
            origen = asiento.origen
            if not asiento.automatico or origen is None:
                omitidos += 1
                continue
            if generar_asiento(origen, forzar=True):
                regenerados += 1
            else:
                omitidos += 1

        self.message_user(
            request,
            f"{regenerados} asiento(s) regenerado(s). "
            f"{omitidos} omitido(s) (manuales, sin origen, o sin configuración suficiente).",
        )

    def mostrar_origen(self, obj):
        if obj.origen is None:
            return "Manual"
        return f"{obj.origen_content_type.model}: {obj.origen}"
    mostrar_origen.short_description = "Origen"

    def mostrar_total_debe(self, obj):
        return obj.total_debe
    mostrar_total_debe.short_description = "Total Debe"

    def mostrar_total_haber(self, obj):
        return obj.total_haber
    mostrar_total_haber.short_description = "Total Haber"

    def mostrar_cuadrado(self, obj):
        return obj.cuadrado
    mostrar_cuadrado.short_description = "Cuadrado"
    mostrar_cuadrado.boolean = True


@admin.register(LineaAsiento)
class LineaAsientoAdmin(admin.ModelAdmin):
    list_display = ("asiento", "cuenta", "centro_costo", "debe", "haber", "glosa")
    list_filter = ("cuenta", "centro_costo")
