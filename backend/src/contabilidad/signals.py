"""
Conecta las operaciones del ERP con la generacion de asientos.

Se usa `transaction.on_commit` en vez de actuar dentro del post_save: asi el
asiento se genera cuando la operacion ya quedo confirmada en la base de datos.
Si la transaccion se revierte, no queda un asiento huerfano apuntando a una
compra que nunca existio.

Igual que en finanzas e inventarios, solo se reacciona a `created`: editar una
operacion ya registrada no regenera su asiento automaticamente. Para eso esta
la accion "Regenerar asiento contable" del admin, que es una decision
consciente del contador y no un efecto colateral de guardar un formulario.
"""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from compras.models import Compra, PagoCompra
from finanzas.models import Anticipo, MovimientoFinanciero
from gastos.models import Gasto
from ventas.models import CobroVenta, Venta

from .servicios import generar_asiento


def _programar(instance):
    transaction.on_commit(lambda: generar_asiento(instance))


@receiver(post_save, sender=MovimientoFinanciero)
def asiento_movimiento(sender, instance, created, **kwargs):
    if created:
        _programar(instance)


@receiver(post_save, sender=Gasto)
def asiento_gasto(sender, instance, created, **kwargs):
    if created:
        _programar(instance)


@receiver(post_save, sender=Anticipo)
def asiento_anticipo(sender, instance, created, **kwargs):
    if created:
        _programar(instance)


@receiver(post_save, sender=Compra)
def asiento_compra(sender, instance, created, **kwargs):
    if created:
        _programar(instance)


@receiver(post_save, sender=PagoCompra)
def asiento_pago_compra(sender, instance, created, **kwargs):
    if created:
        _programar(instance)


@receiver(post_save, sender=Venta)
def asiento_venta(sender, instance, created, **kwargs):
    if created:
        _programar(instance)


@receiver(post_save, sender=CobroVenta)
def asiento_cobro_venta(sender, instance, created, **kwargs):
    if created:
        _programar(instance)
