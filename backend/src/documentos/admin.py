from django.contrib import admin

from .models import TipoDocumento, Documento


@admin.register(TipoDocumento)
class TipoDocumentoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "descripcion")
    search_fields = ("codigo", "nombre")


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "numero", "fecha", "mostrar_vinculo")
    list_filter = ("tipo", "fecha", "content_type")
    search_fields = ("nombre", "numero", "observaciones")
    date_hierarchy = "fecha"

    def mostrar_vinculo(self, obj):
        if obj.contenido:
            return f"{obj.content_type.model}: {obj.contenido}"
        return "—"
    mostrar_vinculo.short_description = "Vinculado a"
