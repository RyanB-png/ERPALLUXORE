"""
Documentos y respaldos (seccion 15 del esquema).

El esquema pide "archivos adjuntos vinculados a cada operacion". En vez de
agregar un FileField a cada modelo del sistema (compra, venta, lote,
exportacion, activo...), se usa una relacion generica de Django: un solo
modelo Documento puede apuntar a CUALQUIER registro del ERP.

Asi, adjuntar una factura a una compra o un certificado a una exportacion
usa la misma tabla y la misma pantalla, y agregar un modulo nuevo no obliga
a tocar nada aqui.
"""

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from core.models import BaseModel


class TipoDocumento(BaseModel):
    """Catalogo flexible: factura, recibo, contrato, nota de venta, etc."""

    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)

    class Meta:
        verbose_name = "Tipo de Documento"
        verbose_name_plural = "Tipos de Documento"
        ordering = ["codigo"]

    def __str__(self):
        return self.nombre


class Documento(BaseModel):
    """
    Archivo adjunto vinculado a cualquier operacion del sistema.

    `content_type` + `object_id` forman la relacion generica: content_type
    dice a que modelo apunta (Compra, Lote, Exportacion...) y object_id al
    registro concreto. `contenido` los combina para poder hacer
    `documento.contenido` y obtener el objeto directamente.
    """

    tipo = models.ForeignKey(
        TipoDocumento, on_delete=models.PROTECT, related_name="documentos",
    )
    nombre = models.CharField(max_length=255)
    numero = models.CharField(
        max_length=60, blank=True,
        help_text="Numero de factura, recibo o contrato, si corresponde.",
    )
    archivo = models.FileField(upload_to="documentos/%Y/%m/")
    fecha = models.DateField()
    observaciones = models.TextField(blank=True)

    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True,
        related_name="documentos",
        help_text="Modelo al que se adjunta el documento.",
    )
    object_id = models.UUIDField(null=True, blank=True)
    contenido = GenericForeignKey("content_type", "object_id")

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        if self.contenido:
            return f"{self.tipo} {self.nombre} ({self.contenido})"
        return f"{self.tipo} {self.nombre}"
