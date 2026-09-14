"""
Ventas y comercializacion (seccion 10 del esquema).

Es el espejo de `compras`: alli se compra mineral a proveedores y se paga;
aqui se vende a clientes y se cobra. Un cobro no mueve dinero por si mismo:
se apoya en un MovimientoFinanciero de tipo INGRESO, que ya suma el saldo de
caja/banco a traves de la señal de finanzas.
"""

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.models import BaseModel
from terceros.models import Tercero
from lotes.models import Lote, LoteComercial


class ContratoComercial(BaseModel):
    """Condiciones pactadas con un cliente, que luego heredan sus ventas."""

    ESTADO_CHOICES = [
        ("VIGENTE", "Vigente"),
        ("VENCIDO", "Vencido"),
        ("ANULADO", "Anulado"),
    ]

    numero = models.CharField(max_length=30, unique=True)
    cliente = models.ForeignKey(
        Tercero, on_delete=models.PROTECT, related_name="contratos",
    )
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default="VIGENTE")
    condiciones = models.TextField(blank=True)
    documento = models.FileField(
        upload_to="contratos/%Y/%m/", null=True, blank=True,
    )

    class Meta:
        verbose_name = "Contrato Comercial"
        verbose_name_plural = "Contratos Comerciales"
        ordering = ["-fecha_inicio"]

    def clean(self):
        if self.cliente_id and self.cliente.tipo != "COMPRADOR":
            raise ValidationError("El contrato debe asociarse a un tercero de tipo COMPRADOR.")
        if self.fecha_fin and self.fecha_inicio and self.fecha_fin < self.fecha_inicio:
            raise ValidationError("La fecha de fin es anterior a la de inicio.")

    def __str__(self):
        return f"{self.numero} - {self.cliente}"


class Venta(BaseModel):
    """
    Venta local o reventa de material. Las exportaciones se registran en la
    app `exportaciones`, que tiene documentacion y costos propios.
    """

    TIPO_CHOICES = [
        ("LOCAL", "Venta Local"),
        ("REVENTA", "Reventa de Material"),
    ]
    ESTADO_CHOICES = [
        ("NEGOCIACION", "En Negociación"),
        ("CONFIRMADA", "Confirmada"),
        ("COBRO_PARCIAL", "Con Cobro Parcial"),
        ("COBRADA", "Cobrada Totalmente"),
        ("CERRADA", "Cerrada"),
    ]
    MONEDA_CHOICES = [
        ("BOB", "Bolivianos"),
        ("USD", "Dólares"),
    ]

    numero = models.CharField(max_length=30, unique=True, blank=True, editable=False)

    cliente = models.ForeignKey(
        Tercero, on_delete=models.PROTECT, related_name="ventas",
    )
    contrato = models.ForeignKey(
        ContratoComercial, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ventas",
    )

    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default="LOCAL")
    fecha = models.DateField()

    lote = models.ForeignKey(
        Lote, on_delete=models.PROTECT, null=True, blank=True,
        related_name="ventas",
    )
    lote_comercial = models.ForeignKey(
        LoteComercial, on_delete=models.PROTECT, null=True, blank=True,
        related_name="ventas",
    )

    peso = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Kilos vendidos.",
    )

    moneda = models.CharField(max_length=3, choices=MONEDA_CHOICES, default="BOB")
    tipo_cambio = models.DecimalField(max_digits=8, decimal_places=4, default=1)
    valor_bruto = models.DecimalField(max_digits=14, decimal_places=2)
    deducciones = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    valor_neto = models.DecimalField(
        max_digits=14, decimal_places=2, editable=False, default=0,
    )

    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default="NEGOCIACION")
    condiciones = models.TextField(blank=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ["-fecha", "-numero"]

    def clean(self):
        if self.cliente_id and self.cliente.tipo != "COMPRADOR":
            raise ValidationError("Las ventas solo se registran a terceros de tipo COMPRADOR.")
        if not self.lote_id and not self.lote_comercial_id:
            raise ValidationError("Debe indicar un lote o un lote comercial.")
        if self.lote_id and self.lote_comercial_id:
            raise ValidationError("Indique un lote o un lote comercial, no ambos.")
        if self.deducciones and self.valor_bruto is not None and self.deducciones > self.valor_bruto:
            raise ValidationError("Las deducciones superan el valor bruto.")

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self._generar_numero()
        self.valor_neto = (self.valor_bruto or 0) - (self.deducciones or 0)
        super().save(*args, **kwargs)

    def _generar_numero(self):
        anio = (self.fecha or timezone.now().date()).year
        ultimo = (
            Venta.objects.filter(numero__startswith=f"VTA-{anio}-")
            .order_by("-numero")
            .first()
        )
        nuevo = int(ultimo.numero.split("-")[-1]) + 1 if ultimo else 1
        return f"VTA-{anio}-{nuevo:04d}"

    @property
    def monto_cobrado(self):
        return sum(c.monto for c in self.cobros.all())

    @property
    def saldo_pendiente(self):
        return self.valor_neto - self.monto_cobrado

    def __str__(self):
        return f"{self.numero} - {self.cliente} ({self.valor_neto} {self.moneda})"


class CobroVenta(BaseModel):
    """Cobro recibido por una venta, respaldado por un ingreso en finanzas."""

    venta = models.ForeignKey(
        Venta, on_delete=models.PROTECT, related_name="cobros",
    )
    movimiento = models.OneToOneField(
        "finanzas.MovimientoFinanciero",
        on_delete=models.PROTECT,
        related_name="cobro_venta",
    )
    monto = models.DecimalField(max_digits=14, decimal_places=2)
    fecha = models.DateField()
    observaciones = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Cobro de Venta"
        verbose_name_plural = "Cobros de Venta"
        ordering = ["-fecha"]

    def clean(self):
        if self.movimiento_id and self.movimiento.tipo != "INGRESO":
            raise ValidationError(
                "El movimiento vinculado a un cobro debe ser un INGRESO."
            )
        if self.venta_id and self.monto is not None:
            # El pk ya existe antes de guardar (BaseModel usa uuid4 por defecto),
            # asi que excluirse a si mismo funciona tanto al crear como al editar.
            otros = sum(
                c.monto for c in self.venta.cobros.exclude(pk=self.pk)
            )
            if otros + self.monto > self.venta.valor_neto:
                raise ValidationError(
                    f"El cobro supera el saldo pendiente. Ya cobrado: {otros}, "
                    f"valor neto de la venta: {self.venta.valor_neto}."
                )

    def __str__(self):
        return f"Cobro {self.monto} - {self.venta}"
