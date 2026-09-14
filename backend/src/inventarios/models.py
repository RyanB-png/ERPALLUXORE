"""
Inventarios y almacen (seccion 12 del esquema).

Sigue el mismo patron que los saldos de caja en `finanzas`: los movimientos
son el registro historico inmutable, y la existencia por lote/almacen es un
saldo que se actualiza solo a traves de señales (ver signals.py). Nunca se
edita `peso_actual` a mano.
"""

from django.db import models
from django.core.exceptions import ValidationError

from core.models import BaseModel
from lotes.models import Lote
from organizacion.models import Sucursal


class Almacen(BaseModel):
    """Galpon, cancha o deposito donde se acopia mineral."""

    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=150)
    sucursal = models.ForeignKey(
        Sucursal, on_delete=models.PROTECT, related_name="almacenes",
    )
    ubicacion = models.CharField(max_length=255, blank=True)
    descripcion = models.TextField(blank=True)

    class Meta:
        verbose_name = "Almacén"
        verbose_name_plural = "Almacenes"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class ExistenciaLote(BaseModel):
    """
    Stock actual de un lote en un almacen. Lo mantiene la señal de
    MovimientoInventario: no se edita manualmente.
    """

    almacen = models.ForeignKey(
        Almacen, on_delete=models.PROTECT, related_name="existencias",
    )
    lote = models.ForeignKey(
        Lote, on_delete=models.PROTECT, related_name="existencias",
    )
    peso_actual = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Kilos. Calculado por las señales de movimientos.",
    )

    class Meta:
        verbose_name = "Existencia de Lote"
        verbose_name_plural = "Existencias de Lotes"
        unique_together = [("almacen", "lote")]
        ordering = ["almacen", "lote"]

    def __str__(self):
        return f"{self.lote.codigo} en {self.almacen.codigo}: {self.peso_actual} kg"


class MovimientoInventario(BaseModel):
    """Entrada, salida o ajuste de mineral en un almacen."""

    TIPO_CHOICES = [
        ("ENTRADA", "Entrada"),
        ("SALIDA", "Salida"),
        ("AJUSTE", "Ajuste de Inventario"),
    ]
    MOTIVO_CHOICES = [
        ("RECEPCION", "Recepción de Lote"),
        ("VENTA", "Salida por Venta"),
        ("EXPORTACION", "Salida por Exportación"),
        ("TRANSFERENCIA", "Transferencia entre Almacenes"),
        ("CONCILIACION", "Ajuste por Inventario Físico"),
        ("OTRO", "Otro"),
    ]

    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    motivo = models.CharField(max_length=15, choices=MOTIVO_CHOICES, default="OTRO")

    almacen = models.ForeignKey(
        Almacen, on_delete=models.PROTECT, related_name="movimientos",
    )
    lote = models.ForeignKey(
        Lote, on_delete=models.PROTECT, related_name="movimientos_inventario",
    )

    peso = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Kilos. Siempre positivo: el signo lo determina el tipo.",
    )
    fecha = models.DateField()
    referencia = models.CharField(
        max_length=255, blank=True,
        help_text="Documento u operacion que origina el movimiento.",
    )
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Movimiento de Inventario"
        verbose_name_plural = "Movimientos de Inventario"
        ordering = ["-fecha", "-created_at"]

    def clean(self):
        if self.peso is not None and self.peso <= 0:
            raise ValidationError("El peso debe ser mayor a cero.")

        if self.tipo == "SALIDA" and self.almacen_id and self.lote_id and self.peso is not None:
            existencia = ExistenciaLote.objects.filter(
                almacen=self.almacen, lote=self.lote
            ).first()
            disponible = existencia.peso_actual if existencia else 0
            if self.peso > disponible:
                raise ValidationError(
                    f"Stock insuficiente. Disponible en {self.almacen.codigo}: {disponible} kg."
                )

    def __str__(self):
        return f"{self.tipo} {self.peso} kg - {self.lote.codigo} ({self.fecha})"


class TransferenciaAlmacen(BaseModel):
    """
    Mueve mineral de un almacen a otro. Al guardarse genera los dos
    movimientos correspondientes (salida en origen, entrada en destino).
    """

    almacen_origen = models.ForeignKey(
        Almacen, on_delete=models.PROTECT, related_name="transferencias_salida",
    )
    almacen_destino = models.ForeignKey(
        Almacen, on_delete=models.PROTECT, related_name="transferencias_entrada",
    )
    lote = models.ForeignKey(
        Lote, on_delete=models.PROTECT, related_name="transferencias",
    )
    peso = models.DecimalField(max_digits=12, decimal_places=2)
    fecha = models.DateField()
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Transferencia entre Almacenes"
        verbose_name_plural = "Transferencias entre Almacenes"
        ordering = ["-fecha", "-created_at"]

    def clean(self):
        if self.almacen_origen_id == self.almacen_destino_id:
            raise ValidationError("El almacen de origen y destino no pueden ser el mismo.")
        if self.peso is not None and self.peso <= 0:
            raise ValidationError("El peso debe ser mayor a cero.")
        if self.almacen_origen_id and self.lote_id and self.peso is not None:
            existencia = ExistenciaLote.objects.filter(
                almacen=self.almacen_origen, lote=self.lote
            ).first()
            disponible = existencia.peso_actual if existencia else 0
            if self.peso > disponible:
                raise ValidationError(
                    f"Stock insuficiente en origen. Disponible: {disponible} kg."
                )

    def __str__(self):
        return (
            f"{self.lote.codigo}: {self.almacen_origen.codigo} -> "
            f"{self.almacen_destino.codigo} ({self.peso} kg)"
        )


class InventarioFisico(BaseModel):
    """Conteo fisico de un almacen en una fecha, para conciliar contra el sistema."""

    ESTADO_CHOICES = [
        ("BORRADOR", "Borrador"),
        ("CERRADO", "Cerrado"),
        ("CONCILIADO", "Conciliado"),
    ]

    almacen = models.ForeignKey(
        Almacen, on_delete=models.PROTECT, related_name="inventarios_fisicos",
    )
    fecha = models.DateField()
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default="BORRADOR")
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Inventario Físico"
        verbose_name_plural = "Inventarios Físicos"
        ordering = ["-fecha"]

    @property
    def diferencia_total(self):
        return sum(d.diferencia for d in self.detalles.all())

    def __str__(self):
        return f"Inventario {self.almacen.codigo} - {self.fecha}"


class DetalleInventarioFisico(BaseModel):
    """Lo contado fisicamente para un lote, frente a lo que decia el sistema."""

    inventario = models.ForeignKey(
        InventarioFisico, on_delete=models.CASCADE, related_name="detalles",
    )
    lote = models.ForeignKey(
        Lote, on_delete=models.PROTECT, related_name="detalles_inventario",
    )
    peso_sistema = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    peso_fisico = models.DecimalField(max_digits=12, decimal_places=2)
    observaciones = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Detalle de Inventario Físico"
        verbose_name_plural = "Detalles de Inventario Físico"
        unique_together = [("inventario", "lote")]

    @property
    def diferencia(self):
        return (self.peso_fisico or 0) - (self.peso_sistema or 0)

    def __str__(self):
        return f"{self.lote.codigo}: sistema {self.peso_sistema} / fisico {self.peso_fisico}"
