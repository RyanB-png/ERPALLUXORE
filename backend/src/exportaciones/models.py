"""
Exportaciones (seccion 11 del esquema).

Una exportacion parte de un LoteComercial (la mezcla de lotes internos que ya
modela la app `lotes`) y le agrega el cliente internacional, la documentacion,
los costos asociados y la liquidacion final de la operacion.
"""

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.models import BaseModel
from terceros.models import Tercero
from lotes.models import LoteComercial


class Exportacion(BaseModel):
    ESTADO_CHOICES = [
        ("PREPARACION", "En Preparación"),
        ("EMBARCADA", "Embarcada"),
        ("LIQUIDADA", "Liquidada"),
        ("COBRADA", "Cobrada"),
        ("CERRADA", "Cerrada"),
    ]
    INCOTERM_CHOICES = [
        ("EXW", "EXW - En fábrica"),
        ("FCA", "FCA - Franco transportista"),
        ("FOB", "FOB - Franco a bordo"),
        ("CFR", "CFR - Costo y flete"),
        ("CIF", "CIF - Costo, seguro y flete"),
        ("DAP", "DAP - Entregado en lugar"),
    ]

    numero = models.CharField(max_length=30, unique=True, blank=True, editable=False)

    lote_comercial = models.OneToOneField(
        LoteComercial, on_delete=models.PROTECT, related_name="exportacion",
    )
    cliente = models.ForeignKey(
        Tercero, on_delete=models.PROTECT, related_name="exportaciones",
        help_text="Cliente internacional (tercero de tipo COMPRADOR).",
    )

    fecha = models.DateField()
    fecha_embarque = models.DateField(null=True, blank=True)
    pais_destino = models.CharField(max_length=100)
    puerto_destino = models.CharField(max_length=150, blank=True)
    incoterm = models.CharField(max_length=3, choices=INCOTERM_CHOICES, default="FOB")

    peso_total = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Kilos embarcados.",
    )

    moneda = models.CharField(max_length=3, default="USD", editable=False)
    tipo_cambio = models.DecimalField(max_digits=8, decimal_places=4, default=1)

    valor_bruto = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    valor_neto = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, editable=False,
    )

    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default="PREPARACION")
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Exportación"
        verbose_name_plural = "Exportaciones"
        ordering = ["-fecha", "-numero"]

    def clean(self):
        if self.cliente_id and self.cliente.tipo != "COMPRADOR":
            raise ValidationError(
                "El cliente de una exportacion debe ser un tercero de tipo COMPRADOR."
            )
        if self.fecha_embarque and self.fecha and self.fecha_embarque < self.fecha:
            raise ValidationError("La fecha de embarque es anterior a la de la exportacion.")

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self._generar_numero()
        super().save(*args, **kwargs)
        self.recalcular()

    def _generar_numero(self):
        anio = (self.fecha or timezone.now().date()).year
        ultimo = (
            Exportacion.objects.filter(numero__startswith=f"EXP-{anio}-")
            .order_by("-numero")
            .first()
        )
        nuevo = int(ultimo.numero.split("-")[-1]) + 1 if ultimo else 1
        return f"EXP-{anio}-{nuevo:04d}"

    def recalcular(self):
        """Valor neto = valor bruto - costos de la operacion."""
        neto = (self.valor_bruto or 0) - self.total_costos
        if neto != self.valor_neto:
            Exportacion.objects.filter(pk=self.pk).update(valor_neto=neto)
            self.valor_neto = neto

    @property
    def total_costos(self):
        return sum(c.monto for c in self.costos.all())

    def __str__(self):
        return f"{self.numero} - {self.lote_comercial.codigo} ({self.pais_destino})"


class CostoExportacion(BaseModel):
    """
    Costo asociado a la operacion de exportacion: flete, seguro, aduana,
    inspeccion, analisis. Si ya se pago, se vincula al movimiento financiero
    correspondiente para no duplicar el dinero.
    """

    TIPO_CHOICES = [
        ("FLETE", "Flete"),
        ("SEGURO", "Seguro"),
        ("ADUANA", "Gastos de Aduana"),
        ("INSPECCION", "Inspección / Supervisión"),
        ("ANALISIS", "Análisis de Laboratorio"),
        ("PUERTO", "Gastos Portuarios"),
        ("REGALIA", "Regalías / Impuestos"),
        ("OTRO", "Otro"),
    ]

    exportacion = models.ForeignKey(
        Exportacion, on_delete=models.CASCADE, related_name="costos",
    )
    tipo = models.CharField(max_length=12, choices=TIPO_CHOICES)
    descripcion = models.CharField(max_length=255, blank=True)
    monto = models.DecimalField(max_digits=14, decimal_places=2)

    proveedor = models.ForeignKey(
        Tercero, on_delete=models.PROTECT, null=True, blank=True,
        related_name="costos_exportacion",
    )
    movimiento = models.OneToOneField(
        "finanzas.MovimientoFinanciero",
        on_delete=models.PROTECT, null=True, blank=True,
        related_name="costo_exportacion",
        help_text="Egreso real que respalda este costo, si ya fue pagado.",
    )
    centro_costo = models.ForeignKey(
        "contabilidad.CentroCosto",
        on_delete=models.PROTECT, null=True, blank=True,
        related_name="costos_exportacion",
    )

    fecha = models.DateField()

    class Meta:
        verbose_name = "Costo de Exportación"
        verbose_name_plural = "Costos de Exportación"
        ordering = ["-fecha"]

    def clean(self):
        if self.movimiento_id and self.movimiento.tipo != "EGRESO":
            raise ValidationError("El movimiento vinculado a un costo debe ser un EGRESO.")

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.monto} ({self.exportacion.numero})"
