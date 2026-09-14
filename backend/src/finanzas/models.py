from django.db import models
from django.core.exceptions import ValidationError
from core.models import BaseModel
from organizacion.models import Caja, CuentaBancaria
from terceros.models import Tercero


class MovimientoFinanciero(BaseModel):
    TIPO_CHOICES = [
        ("INGRESO", "Ingreso"),
        ("EGRESO", "Egreso"),
    ]
    ORIGEN_CHOICES = [
        ("CAJA", "Caja"),
        ("BANCO", "Cuenta Bancaria"),
    ]
    MONEDA_CHOICES = [
        ("BOB", "Bolivianos"),
        ("USD", "Dólares"),
    ]

    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    origen = models.CharField(max_length=10, choices=ORIGEN_CHOICES)

    caja = models.ForeignKey(
        Caja, on_delete=models.PROTECT, null=True, blank=True,
        related_name="movimientos",
    )
    cuenta_bancaria = models.ForeignKey(
        CuentaBancaria, on_delete=models.PROTECT, null=True, blank=True,
        related_name="movimientos",
    )

    tercero = models.ForeignKey(
        Tercero, on_delete=models.PROTECT, null=True, blank=True,
        related_name="movimientos_financieros",
    )

    concepto = models.CharField(max_length=255)
    monto = models.DecimalField(max_digits=14, decimal_places=2)
    moneda = models.CharField(max_length=3, choices=MONEDA_CHOICES, default="BOB")
    tipo_cambio = models.DecimalField(max_digits=8, decimal_places=4, default=1)

    fecha = models.DateField()

    class Meta:
        verbose_name = "Movimiento Financiero"
        verbose_name_plural = "Movimientos Financieros"
        ordering = ["-fecha", "-created_at"]

    def clean(self):
        if self.origen == "CAJA" and not self.caja:
            raise ValidationError("Debe seleccionar una caja.")
        if self.origen == "BANCO" and not self.cuenta_bancaria:
            raise ValidationError("Debe seleccionar una cuenta bancaria.")
        if self.caja and self.cuenta_bancaria:
            raise ValidationError("Un movimiento no puede tener caja y cuenta bancaria a la vez.")

        cuenta_origen = self.caja or self.cuenta_bancaria
        if cuenta_origen and cuenta_origen.moneda != self.moneda:
            raise ValidationError(
                f"La moneda del movimiento ({self.moneda}) no coincide con la de "
                f"la cuenta/caja ({cuenta_origen.moneda})."
            )

        if self.tipo == "EGRESO" and cuenta_origen and self.monto is not None:
            if self.monto > cuenta_origen.saldo_actual:
                raise ValidationError(
                    f"Saldo insuficiente. Disponible: {cuenta_origen.saldo_actual} {cuenta_origen.moneda}"
                )

    def __str__(self):
        return f"{self.tipo} - {self.concepto} - {self.monto} {self.moneda}"


class TransferenciaEntreCuentas(BaseModel):
    ORIGEN_CHOICES = [
        ("CAJA", "Caja"),
        ("BANCO", "Cuenta Bancaria"),
    ]

    origen_tipo = models.CharField(max_length=10, choices=ORIGEN_CHOICES)
    origen_caja = models.ForeignKey(
        Caja, on_delete=models.PROTECT, null=True, blank=True,
        related_name="transferencias_salida",
    )
    origen_cuenta = models.ForeignKey(
        CuentaBancaria, on_delete=models.PROTECT, null=True, blank=True,
        related_name="transferencias_salida",
    )

    destino_tipo = models.CharField(max_length=10, choices=ORIGEN_CHOICES)
    destino_caja = models.ForeignKey(
        Caja, on_delete=models.PROTECT, null=True, blank=True,
        related_name="transferencias_entrada",
    )
    destino_cuenta = models.ForeignKey(
        CuentaBancaria, on_delete=models.PROTECT, null=True, blank=True,
        related_name="transferencias_entrada",
    )

    monto = models.DecimalField(max_digits=14, decimal_places=2)
    fecha = models.DateField()
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Transferencia entre Cuentas"
        verbose_name_plural = "Transferencias entre Cuentas"
        ordering = ["-fecha", "-created_at"]

    def clean(self):
        if self.origen_tipo == "CAJA" and not self.origen_caja:
            raise ValidationError("Debe seleccionar una caja de origen.")
        if self.origen_tipo == "BANCO" and not self.origen_cuenta:
            raise ValidationError("Debe seleccionar una cuenta bancaria de origen.")
        if self.destino_tipo == "CAJA" and not self.destino_caja:
            raise ValidationError("Debe seleccionar una caja de destino.")
        if self.destino_tipo == "BANCO" and not self.destino_cuenta:
            raise ValidationError("Debe seleccionar una cuenta bancaria de destino.")

        origen = self.origen_caja or self.origen_cuenta
        if origen and self.monto is not None and self.monto > origen.saldo_actual:
            raise ValidationError(
                f"Saldo insuficiente en origen. Disponible: {origen.saldo_actual} {origen.moneda}"
            )

    def __str__(self):
        return f"Transferencia {self.monto} - {self.fecha}"


class Anticipo(BaseModel):
    ESTADO_CHOICES = [
        ("PENDIENTE", "Pendiente"),
        ("PARCIAL", "Aplicado Parcialmente"),
        ("APLICADO", "Aplicado Totalmente"),
        ("ANULADO", "Anulado"),
    ]
    MONEDA_CHOICES = [
        ("BOB", "Bolivianos"),
        ("USD", "Dólares"),
    ]

    tercero = models.ForeignKey(
        Tercero, on_delete=models.PROTECT, related_name="anticipos",
    )
    monto_total = models.DecimalField(max_digits=14, decimal_places=2)
    moneda = models.CharField(max_length=3, choices=MONEDA_CHOICES, default="BOB")
    fecha = models.DateField()
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default="PENDIENTE")
    observaciones = models.TextField(blank=True)

    movimiento = models.OneToOneField(
        MovimientoFinanciero, on_delete=models.PROTECT,
        related_name="anticipo",
    )

    class Meta:
        verbose_name = "Anticipo"
        verbose_name_plural = "Anticipos"
        ordering = ["-fecha", "-created_at"]

    def clean(self):
        if self.tercero.tipo != "PROVEEDOR":
            raise ValidationError("Los anticipos solo se pueden registrar a proveedores.")

    @property
    def monto_aplicado(self):
        return sum(a.monto for a in self.aplicaciones.all())

    @property
    def saldo_disponible(self):
        return self.monto_total - self.monto_aplicado

    def __str__(self):
        return f"Anticipo {self.tercero} - {self.monto_total} {self.moneda}"


class AplicacionAnticipo(BaseModel):
    anticipo = models.ForeignKey(
        Anticipo, on_delete=models.PROTECT, related_name="aplicaciones",
    )
    monto = models.DecimalField(max_digits=14, decimal_places=2)
    fecha = models.DateField()
    referencia = models.CharField(
        max_length=255, blank=True,
        help_text="Referencia a la compra/lote donde se aplicó (se vinculará formalmente en Fase 3)",
    )

    class Meta:
        verbose_name = "Aplicación de Anticipo"
        verbose_name_plural = "Aplicaciones de Anticipo"
        ordering = ["-fecha", "-created_at"]

    def clean(self):
        if self.monto is None or not self.anticipo_id:
            return
        if self.monto > self.anticipo.saldo_disponible:
            raise ValidationError("El monto a aplicar supera el saldo disponible del anticipo.")

    def __str__(self):
        return f"Aplicación {self.monto} sobre {self.anticipo}"