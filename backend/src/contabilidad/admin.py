from django.contrib import admin
from .models import CuentaContable,PeriodoContable, Asiento, LineaAsiento
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

@admin.register(CuentaContable)
class CuentaContableAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre","tipo", "cuenta_padre", "permite_movimiento")
    list_filter = ("tipo","permite_movimiento")
    search_fields=("codigo","nombre")

@admin.register(PeriodoContable)
class PeriodoContableAdmin(admin.ModelAdmin):
    list_display=("anio","mes","fecha_inicio","fecha_fin","estado")
    list_filter= ("estado","anio")

class LineaAsientoFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

        total_debe=0
        total_haber=0
        lineas_vlidas=0

        for form in self.forms:
            if not hasattr(form, "clenaed_data"):
                continue
            if  form.clenaed_data.get("DELETE"):
                continue

            debe = form.cleaned_data.get("debe") or 0
            haber = form.cleaned_data.get("haber") or 0

            if debe or haber:
                lineas_vlidas+=1

            total_debe+=debe
            total_haber+=haber
        if lienas_validas <2:
            raise ValidationError("Un asiento debe tener al menos 2 lineas  (una en Debe y otra en Haber)")

        if total_debe !=total_haber:
            raise ValidationError(
                f"El asiento no cuadra: Debe= {total_debe}, Haber={total_haber}, Deben ser iguales "
            )

class LineaAsientoInline(admin.TabularInline):
    model=LineaAsiento
    formset= LineaAsientoFormSet
    extra=2
    fields=("cuenta","debe","haber","glosa")


@admin.register(Asiento)
class AsientoAdmin(admin.ModelAdmin):
    list_display=(
        "numero", "fecha", "periodo", "concepto",
        "mostrar_total_debe", "mostrar_total_haber", "mostrar_cuadrado",
    )
    list_filter=("periodo",)
    search_fields=("numero", "concepto")
    readonly_fields=("numero","periodo")
    date_hierarchy="fecha"
    inlines=[LineaAsientoInline]

    def mostrar_total_debe(self,obj):
        return obj.total_debe
    mostrar_total_debe.short_description="Total Debe"

    def mostrar_total_haber(self,obj):
        return obj.total_haber
    mostrar_total_haber.short_description= "Total Haber"

    def mostrar_cuadrado (self, obj):
        return obj.cuadrado
    mostrar_cuadrado.short_description = "Cuadrado"
    mostrar_cuadrado.boolean=True

@admin.register(LineaAsiento)
class LineaAsientoAdmin(admin.ModelAdmin):
    list_display = ("asiento", "cuenta", "debe", "haber", "glosa")
    list_filter = ("cuenta",)