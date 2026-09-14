# backend/src/laboratorio/admin.py

from django.contrib import admin
from django.utils.html import format_html
from .models import Laboratorio, Elemento, Muestra, ResultadoElemento


@admin.register(Laboratorio)
class LaboratorioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "contacto", "telefono")
    list_filter = ("tipo",)
    search_fields = ("nombre", "contacto")


@admin.register(Elemento)
class ElementoAdmin(admin.ModelAdmin):
    list_display = ("simbolo", "nombre")
    search_fields = ("simbolo", "nombre")


class ResultadoElementoInline(admin.TabularInline):
    model = ResultadoElemento
    extra = 1


@admin.register(Muestra)
class MuestraAdmin(admin.ModelAdmin):
    list_display = (
        "lote", "laboratorio", "fecha_envio", "fecha_resultado",
        "humedad", "estado", "previsualizar_foto",
    )
    list_filter = ("laboratorio", "estado", "fecha_envio")
    search_fields = ("lote__codigo",)
    date_hierarchy = "fecha_envio"
    readonly_fields = ("previsualizar_foto_grande",)
    inlines = [ResultadoElementoInline]

    class Media:
        css = {"all": ("laboratorio/css/lightbox.css",)}
        js = ("laboratorio/js/lightbox.js",)

    def previsualizar_foto(self, obj):
        if obj.foto:
            return format_html(
                '<img src="{}" data-full-src="{}" class="miniatura-clickeable, target=blank" '
                'style="height: 40px; border-radius: 4px;" />',
                obj.foto.url, obj.foto.url,
            )
        return "—"
    previsualizar_foto.short_description = "Foto"

    def previsualizar_foto_grande(self, obj):
        if obj.foto:
            return format_html(
                '<img src="{}" data-full-src="{}" class="miniatura-clickeable" '
                'style="max-height: 300px; border-radius: 8px;" />',
                obj.foto.url, obj.foto.url,
            )
        return "Sin foto"
    previsualizar_foto_grande.short_description = "Vista previa (clic para ampliar)"


@admin.register(ResultadoElemento)
class ResultadoElementoAdmin(admin.ModelAdmin):
    list_display = ("muestra", "elemento", "valor")
    list_filter = ("elemento",)