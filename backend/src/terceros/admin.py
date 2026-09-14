from django.contrib import admin
from .models import Tercero


@admin.register(Tercero)
class TerceroAdmin(admin.ModelAdmin):
    list_display = ("codigo", "tipo", "tipo_persona", "razon_social", "nombre_completo", "is_active")
    list_filter = ("tipo", "tipo_persona", "is_active")
    search_fields = ("codigo", "razon_social", "nombre_completo", "documento")