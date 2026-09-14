from django.db import models
from django.core.exceptions import ValidationError
from core.models import BaseModel
from lotes.models import Lote


class Compra(BaseModel):
    """
    Compra de mineral a un proveedor (seccion 6 del esquema).

    Los valores monetarios pueden cargarse a mano o venir calculados desde
    una Liquidacion (app `liquidaciones`). Cuando hay liquidacion asociada,
    `save()` sincroniza los valores para que no existan dos verdades.
    """

    ESTADO_CHOICES = [
        ("NEGOCIACION", "En Negociacion"),
        ("LIQUIDADA", "Liquidada"),
        ("PAGO_PARCIAL", "Con Pago Parcial"),
        ("PAGADA", "Pagada Totalmente"),
        ("CERRADA", "Cerrada"),
    ]

    MONEDA_CHOICES = [
        ("BOB", "Bolivianos"),
        ("USD", "Dolares"),
    ]

    lote = models.OneToOneField(
        Lote,
        on_delete=models.PROTECT,
        related_name="compra",
    )

    liquidacion = models.OneToOneField(
        "liquidaciones.Liquidacion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="compra",
        help_text="Si se asocia una liquidacion, los valores se toman de ella.",
    )

    fecha_negociacion = models.DateField()
    moneda = models.CharField(max_length=3, choices=MONEDA_CHOICES, default="USD")
    tipo_cambio = models.DecimalField(max_digits=8, decimal_places=4, default=1)

    valor_bruto = models.DecimalField(max_digits=14, decimal_places=2)
    valor_neto = models.DecimalField(max_digits=14, decimal_places=2)
    monto_usd = models.DecimalField(max_digits=14, decimal_places=2)
    monto_bs = models.DecimalField(max_digits=14, decimal_places=2)

    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default="NEGOCIACION")
    condiciones = models.TextField(blank=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Compra"
        verbose_name_plural = "Compras"
        ordering = ["-fecha_negociacion"]

    def clean(self):
        if self.liquidacion and self.liquidacion.lote_id != self.lote_id:
            raise ValidationError(
                "La liquidacion asociada corresponde a un lote distinto al de esta compra."
            )

    def save(self, *args, **kwargs):
        if self.liquidacion_id:
            self.valor_bruto = self.liquidacion.valor_bruto
            self.valor_neto = self.liquidacion.valor_neto
            self.moneda = self.liquidacion.moneda
            self.tipo_cambio = self.liquidacion.tipo_cambio

        if self.moneda == "USD":
            self.monto_usd = self.valor_neto
            self.monto_bs = self.valor_neto * self.tipo_cambio
        else:
            self.monto_bs = self.valor_neto
            self.monto_usd = (
                self.valor_neto / self.tipo_cambio if self.tipo_cambio else 0
            )

        super().save(*args, **kwargs)

    @property
    def monto_pagado(self):
        return sum(p.monto for p in self.pagos_aplicados.all())

    @property
    def saldo_pendiente(self):
        return self.valor_neto - self.monto_pagado

    def __str__(self):
        return f"Compra {self.lote.codigo} - {self.valor_neto} {self.moneda}"


class PagoCompra(BaseModel):
    """
    Un pago aplicado a una compra. No mueve dinero por si mismo: se apoya en
    finanzas, sea aplicando un anticipo existente o vinculando un movimiento
    financiero real (que ya descuenta caja/banco via señal).
    """

    TIPO_ORIGEN_CHOICES = [
        ("ANTICIPO", "Aplicacion de Anticipo"),
        ("MOVIMIENTO", "Pago Directo (Movimiento Financiero)"),
    ]

    compra = models.ForeignKey(
        Compra,
        on_delete=models.PROTECT,
        related_name="pagos_aplicados",
    )

    tipo_origen = models.CharField(max_length=12, choices=TIPO_ORIGEN_CHOICES)

    aplicacion_anticipo = models.OneToOneField(
        "finanzas.AplicacionAnticipo",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pago_compra",
    )
    movimiento = models.OneToOneField(
        "finanzas.MovimientoFinanciero",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pago_compra",
    )

    monto = models.DecimalField(max_digits=14, decimal_places=2)
    fecha = models.DateField()

    class Meta:
        verbose_name = "Pago de Compra"
        verbose_name_plural = "Pagos de Compra"
        ordering = ["-fecha"]

    def clean(self):
        if self.tipo_origen == "ANTICIPO" and not self.aplicacion_anticipo:
            raise ValidationError(
                "Debe seleccionar la aplicacion de anticipo correspondiente."
            )
        if self.tipo_origen == "MOVIMIENTO" and not self.movimiento:
            raise ValidationError(
                "Debe seleccionar el movimiento financiero correspondiente."
            )
        if self.aplicacion_anticipo and self.movimiento:
            raise ValidationError(
                "Un pago no puede tener anticipo y movimiento a la vez."
            )
        if self.movimiento and self.movimiento.tipo != "EGRESO":
            raise ValidationError(
                "El movimiento vinculado a un pago de compra debe ser un EGRESO."
            )

    def __str__(self):
        return f"Pago {self.monto} - {self.compra}"
