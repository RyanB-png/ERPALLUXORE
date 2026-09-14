from django.db import models
from django.core.exceptions import ValidationError
from core.models import BaseModel


class CuentaContable(BaseModel):
    TIPO_CHOICES = [
        ("ACTIVO", "Activo"),
        ("PASIVO", "Pasivo"),
        ("PATRIMONIO", "Patrimonio"),
        ("INGRESO", "Ingreso"),
        ("GASTO", "Gasto"),
    ]

    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=150)
    tipo = models.CharField(max_length=12, choices=TIPO_CHOICES)

    cuenta_padre = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="subcuentas",
    )

    permite_movimiento = models.BooleanField(
        default=True,
        help_text="Si está desmarcado, esta cuenta es solo un agrupador y no puede recibir movimientos directos.",
    )

    class Meta:
        verbose_name = "Cuenta Contable"
        verbose_name_plural = "Plan de Cuentas"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class PeriodoContable(BaseModel):
    ESTADO_CHOICES = [
        ("ABIERTO", "Abierto"),
        ("CERRADO", "Cerrado"),
    ]

    anio = models.PositiveIntegerField()
    mes = models.PositiveIntegerField()

    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()

    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default="ABIERTO")

    class Meta:
        verbose_name = "Periodo Contable"
        verbose_name_plural = "Periodos Contables"
        unique_together = [("anio", "mes")]
        ordering = ["-anio", "-mes"]

    def __str__(self):
        return f"{self.mes:02d}/{self.anio} ({self.get_estado_display()})"


class Asiento(BaseModel):
    numero = models.CharField(max_length=30, unique=True, blank=True, editable=False)
    fecha = models.DateField()
    periodo = models.ForeignKey(
        PeriodoContable, on_delete=models.PROTECT,
        related_name="asientos", editable=False,
    )
    concepto = models.CharField(max_length=255)
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Asiento Contable"
        verbose_name_plural = "Asientos Contables"
        ordering = ["-fecha", "-numero"]

    def clean(self):
        periodo = PeriodoContable.objects.filter(
            anio=self.fecha.year, mes=self.fecha.month
        ).first()
        if not periodo:
            raise ValidationError(
                f"No existe un periodo contable creado para {self.fecha.month}/{self.fecha.year}. Créelo primero."
            )
        if periodo.estado == "CERRADO":
            raise ValidationError(f"El periodo {periodo} está cerrado. No se pueden registrar asientos.")
        self.periodo = periodo

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self._generar_numero()
        super().save(*args, **kwargs)

    def _generar_numero(self):
        anio = self.fecha.year
        ultimo = Asiento.objects.filter(numero__startswith=f"ASN-{anio}-").order_by("-numero").first()
        if ultimo:
            nuevo_numero = int(ultimo.numero.split("-")[-1]) + 1
        else:
            nuevo_numero = 1
        return f"ASN-{anio}-{nuevo_numero:04d}"

    @property
    def total_debe(self):
        return sum(l.debe for l in self.lineas.all())

    @property
    def total_haber(self):
        return sum(l.haber for l in self.lineas.all())

    @property
    def cuadrado(self):
        return self.total_debe == self.total_haber

    def __str__(self):
        return f"{self.numero} - {self.concepto}"


class LineaAsiento(BaseModel):
    asiento = models.ForeignKey(
        Asiento, on_delete=models.CASCADE, related_name="lineas",
    )
    cuenta = models.ForeignKey(
        CuentaContable, on_delete=models.PROTECT, related_name="lineas_asiento",
    )
    debe = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    haber = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    glosa = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Línea de Asiento"
        verbose_name_plural = "Líneas de Asiento"

    def clean(self):
        if self.debe and self.haber:
            raise ValidationError("Una línea no puede tener valor en Debe y Haber a la vez.")
        if not self.debe and not self.haber:
            raise ValidationError("Debe ingresar un valor en Debe o en Haber.")
        if not self.cuenta.permite_movimiento:
            raise ValidationError(f"La cuenta {self.cuenta} no permite movimientos directos (es un agrupador).")

    def __str__(self):
        lado = "Debe" if self.debe else "Haber"
        monto = self.debe or self.haber
        return f"{self.cuenta.codigo} - {lado}: {monto}"