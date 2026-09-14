"""
Mantiene actualizadas las existencias por lote/almacen.

Mismo criterio que las señales de `finanzas`: solo reaccionan a la creacion
(`created`), nunca a ediciones, porque un movimiento de inventario ya
registrado no deberia modificarse — se corrige con un movimiento de ajuste.
"""

from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ExistenciaLote, MovimientoInventario, TransferenciaAlmacen


def _aplicar_delta(almacen_id, lote_id, delta):
    """Suma (o resta) kilos a la existencia, creandola si no existe."""
    existencia, creada = ExistenciaLote.objects.get_or_create(
        almacen_id=almacen_id, lote_id=lote_id, defaults={"peso_actual": 0},
    )
    ExistenciaLote.objects.filter(pk=existencia.pk).update(
        peso_actual=F("peso_actual") + delta
    )


@receiver(post_save, sender=MovimientoInventario)
def actualizar_existencia_movimiento(sender, instance, created, **kwargs):
    if not created:
        return

    if instance.tipo == "ENTRADA":
        delta = instance.peso
    elif instance.tipo == "SALIDA":
        delta = -instance.peso
    else:  # AJUSTE: el peso indica la correccion con su signo ya resuelto
        delta = instance.peso

    with transaction.atomic():
        _aplicar_delta(instance.almacen_id, instance.lote_id, delta)


@receiver(post_save, sender=TransferenciaAlmacen)
def generar_movimientos_transferencia(sender, instance, created, **kwargs):
    """
    Una transferencia se materializa como dos movimientos reales, para que el
    historial del almacen quede completo y auditable desde un solo lugar.
    """
    if not created:
        return

    with transaction.atomic():
        MovimientoInventario.objects.create(
            tipo="SALIDA",
            motivo="TRANSFERENCIA",
            almacen_id=instance.almacen_origen_id,
            lote_id=instance.lote_id,
            peso=instance.peso,
            fecha=instance.fecha,
            referencia=f"Transferencia {instance.pk}",
        )
        MovimientoInventario.objects.create(
            tipo="ENTRADA",
            motivo="TRANSFERENCIA",
            almacen_id=instance.almacen_destino_id,
            lote_id=instance.lote_id,
            peso=instance.peso,
            fecha=instance.fecha,
            referencia=f"Transferencia {instance.pk}",
        )
