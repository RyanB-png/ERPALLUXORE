from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import MovimientoFinanciero, TransferenciaEntreCuentas
from organizacion.models import Caja, CuentaBancaria


def _actualizar_saldo(cuenta_modelo, cuenta_id, delta):
    """Actualiza el saldo de forma atómica usando F() para evitar condiciones de carrera."""
    cuenta_modelo.objects.filter(id=cuenta_id).update(saldo_actual=F("saldo_actual") + delta)


@receiver(post_save, sender=MovimientoFinanciero)
def actualizar_saldo_movimiento(sender, instance, created, **kwargs):
    if not created:
        return

    signo = 1 if instance.tipo == "INGRESO" else -1
    delta = instance.monto * signo

    with transaction.atomic():
        if instance.caja:
            _actualizar_saldo(Caja, instance.caja_id, delta)
        elif instance.cuenta_bancaria:
            _actualizar_saldo(CuentaBancaria, instance.cuenta_bancaria_id, delta)


@receiver(post_save, sender=TransferenciaEntreCuentas)
def actualizar_saldo_transferencia(sender, instance, created, **kwargs):
    if not created:
        return

    with transaction.atomic():
        if instance.origen_caja:
            _actualizar_saldo(Caja, instance.origen_caja_id, -instance.monto)
        elif instance.origen_cuenta:
            _actualizar_saldo(CuentaBancaria, instance.origen_cuenta_id, -instance.monto)

        if instance.destino_caja:
            _actualizar_saldo(Caja, instance.destino_caja_id, instance.monto)
        elif instance.destino_cuenta:
            _actualizar_saldo(CuentaBancaria, instance.destino_cuenta_id, instance.monto)