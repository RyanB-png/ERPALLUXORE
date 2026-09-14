"""
Activos y bienes (seccion 14 del esquema).

Vehiculos, maquinaria, equipos y mobiliario, con su valor de adquisicion,
depreciacion acumulada e historial de mantenimientos.

La depreciacion se registra por periodo contable (no se calcula sola al
consultar): asi el valor en libros de un mes cerrado no cambia despues de
forma retroactiva, que es lo que exige la contabilidad.
"""

from decimal import Decimal

from django.db import models
from django.core.exceptions import ValidationError

from core.models import BaseModel
from terceros.models import Tercero
from organizacion.models import Sucursal


class Activo(BaseModel):
    TIPO_CHOICES = [
        ("VEHICULO", "Vehículo"),
        ("MAQUINARIA", "Maquinaria"),
        ("EQUIPO", "Equipo"),
        ("MOBILIARIO", "Mobiliario"),
        ("OFICINA", "Activo de Oficina"),
        ("OTRO", "Otro"),
    ]
    ESTADO_CHOICES = [
        ("ACTIVO", "En Uso"),
        ("MANTENIMIENTO", "En Mantenimiento"),
        ("BAJA", "Dado de Baja"),
    ]
    MONEDA_CHOICES = [
        ("BOB", "Bolivianos"),
        ("USD", "Dólares"),
    ]

    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=150)
    tipo = models.CharField(max_length=12, choices=TIPO_CHOICES)

    marca = models.CharField(max_length=100, blank=True)
    modelo = models.CharField(max_length=100, blank=True)
    numero_serie = models.CharField(max_length=100, blank=True)
    placa = models.CharField(
        max_length=20, blank=True,
        help_text="Solo para vehiculos.",
    )

    sucursal = models.ForeignKey(
        Sucursal, on_delete=models.PROTECT, null=True, blank=True,
        related_name="activos",
    )
    proveedor = models.ForeignKey(
        Tercero, on_delete=models.PROTECT, null=True, blank=True,
        related_name="activos_vendidos",
    )

    fecha_adquisicion = models.DateField()
    valor_adquisicion = models.DecimalField(max_digits=14, decimal_places=2)
    moneda = models.CharField(max_length=3, choices=MONEDA_CHOICES, default="BOB")
    valor_residual = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text="Valor estimado al final de la vida util.",
    )
    vida_util_anios = models.PositiveIntegerField(
        default=5,
        help_text="Años de vida util para la depreciacion lineal.",
    )

    estado = models.CharField(max_length=14, choices=ESTADO_CHOICES, default="ACTIVO")
    foto = models.ImageField(upload_to="activos/%Y/%m/", null=True, blank=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Activo"
        verbose_name_plural = "Activos"
        ordering = ["codigo"]

    def clean(self):
        if (
            self.valor_residual
            and self.valor_adquisicion is not None
            and self.valor_residual > self.valor_adquisicion
        ):
            raise ValidationError("El valor residual no puede superar al de adquisicion.")
        if self.vida_util_anios == 0:
            raise ValidationError("La vida util debe ser de al menos un año.")

    @property
    def depreciacion_mensual(self):
        """Cuota lineal: (valor - residual) / (años * 12)."""
        meses = (self.vida_util_anios or 0) * 12
        if not meses:
            return Decimal("0")
        base = (self.valor_adquisicion or Decimal("0")) - (self.valor_residual or Decimal("0"))
        return (base / Decimal(meses)).quantize(Decimal("0.01"))

    @property
    def depreciacion_acumulada(self):
        return sum(d.monto for d in self.depreciaciones.all())

    @property
    def valor_libros(self):
        return (self.valor_adquisicion or Decimal("0")) - self.depreciacion_acumulada

    @property
    def costo_mantenimiento_total(self):
        return sum(m.costo for m in self.mantenimientos.all())

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class DepreciacionActivo(BaseModel):
    """Cuota de depreciacion registrada para un periodo contable."""

    activo = models.ForeignKey(
        Activo, on_delete=models.PROTECT, related_name="depreciaciones",
    )
    periodo = models.ForeignKey(
        "contabilidad.PeriodoContable", on_delete=models.PROTECT,
        related_name="depreciaciones",
    )
    monto = models.DecimalField(max_digits=14, decimal_places=2)
    fecha = models.DateField()
    observaciones = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Depreciación"
        verbose_name_plural = "Depreciaciones"
        unique_together = [("activo", "periodo")]
        ordering = ["-fecha"]

    def clean(self):
        if self.periodo_id and self.periodo.estado == "CERRADO":
            raise ValidationError(
                f"El periodo {self.periodo} esta cerrado, no admite nuevas depreciaciones."
            )
        if self.activo_id and self.monto:
            restante = self.activo.valor_libros - (self.activo.valor_residual or 0)
            if self.monto > restante:
                raise ValidationError(
                    f"La cuota supera el valor depreciable restante ({restante})."
                )

    def __str__(self):
        return f"{self.activo.codigo} - {self.periodo}: {self.monto}"


class MantenimientoActivo(BaseModel):
    """Historial de mantenimientos, con su costo asociado."""

    TIPO_CHOICES = [
        ("PREVENTIVO", "Preventivo"),
        ("CORRECTIVO", "Correctivo"),
    ]

    activo = models.ForeignKey(
        Activo, on_delete=models.PROTECT, related_name="mantenimientos",
    )
    tipo = models.CharField(max_length=11, choices=TIPO_CHOICES, default="PREVENTIVO")
    fecha = models.DateField()
    descripcion = models.TextField()
    costo = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    proveedor = models.ForeignKey(
        Tercero, on_delete=models.PROTECT, null=True, blank=True,
        related_name="mantenimientos_realizados",
    )
    movimiento = models.OneToOneField(
        "finanzas.MovimientoFinanciero",
        on_delete=models.PROTECT, null=True, blank=True,
        related_name="mantenimiento",
        help_text="Egreso real que respalda el costo, si ya fue pagado.",
    )

    class Meta:
        verbose_name = "Mantenimiento"
        verbose_name_plural = "Mantenimientos"
        ordering = ["-fecha"]

    def clean(self):
        if self.movimiento_id and self.movimiento.tipo != "EGRESO":
            raise ValidationError("El movimiento vinculado debe ser un EGRESO.")

    def __str__(self):
        return f"{self.activo.codigo} - {self.get_tipo_display()} ({self.fecha})"
