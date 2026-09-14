"""
Generacion automatica de asientos contables (secciones 5 y 17 del esquema).

Cada operacion del ERP se traduce a un asiento de partida doble. El mapeo
operacion -> cuentas vive en `ConfiguracionContable` y en las cuentas
asignadas a cada Caja, CuentaBancaria y CategoriaGasto, no en el codigo:
el contador puede reconfigurarlo desde el admin sin tocar Python.

DOS REGLAS QUE GOBIERNAN TODO ESTE MODULO
-----------------------------------------

1. NUNCA bloquear la operacion. Si falta configuracion contable o el periodo
   esta cerrado, no se genera el asiento y la compra/venta/pago se guarda
   igual. Un ERP no puede impedirte registrar una venta real porque el plan
   de cuentas este incompleto. Lo que queda sin asiento se puede generar
   despues con la accion "Generar asientos faltantes" del admin.

2. NUNCA duplicar el movimiento de caja. Un MovimientoFinanciero que ya forma
   parte de un documento (pago de compra, cobro de venta, anticipo, gasto,
   costo de exportacion, mantenimiento) NO genera asiento propio: lo genera
   el documento, que conoce la contrapartida correcta. Solo los movimientos
   sueltos generan su propio asiento contra ingresos/egresos varios.
"""

import logging

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from .models import (
    Asiento,
    ConfiguracionContable,
    LineaAsiento,
    PeriodoContable,
)

logger = logging.getLogger(__name__)

# Documentos que "adoptan" un movimiento financiero y generan su propio asiento.
# Son los related_name de las relaciones uno-a-uno hacia MovimientoFinanciero.
DOCUMENTOS_QUE_ADOPTAN_MOVIMIENTO = (
    "pago_compra",
    "cobro_venta",
    "anticipo",
    "gasto",
    "costo_exportacion",
    "mantenimiento",
)


# ---------------------------------------------------------------- utilidades


def _periodo_abierto(fecha):
    """Periodo contable de esa fecha, solo si existe y esta abierto."""
    periodo = PeriodoContable.objects.filter(
        anio=fecha.year, mes=fecha.month
    ).first()
    if not periodo:
        logger.info("Sin asiento: no existe periodo contable para %s", fecha)
        return None
    if periodo.estado == "CERRADO":
        logger.info("Sin asiento: el periodo %s esta cerrado", periodo)
        return None
    return periodo


def _imputable(cuenta):
    """Una cuenta sirve para un asiento solo si existe y admite movimientos."""
    if cuenta is None:
        return None
    if not cuenta.permite_movimiento:
        logger.warning("Cuenta %s es agrupadora, no admite movimientos", cuenta)
        return None
    return cuenta


def _cuenta_de_origen(movimiento):
    """Cuenta contable de la caja o banco por donde paso el dinero."""
    if movimiento.caja_id:
        return _imputable(movimiento.caja.cuenta_contable)
    if movimiento.cuenta_bancaria_id:
        return _imputable(movimiento.cuenta_bancaria.cuenta_contable)
    return None


def _movimiento_tiene_documento(movimiento):
    """True si otro documento ya se hace cargo del asiento de este movimiento."""
    for rel in DOCUMENTOS_QUE_ADOPTAN_MOVIMIENTO:
        try:
            if getattr(movimiento, rel, None) is not None:
                return True
        except Exception:
            # La relacion inversa lanza ObjectDoesNotExist cuando no existe.
            continue
    return False


def asiento_existente(origen):
    """Asiento ya generado para esta operacion, si lo hay."""
    ct = ContentType.objects.get_for_model(type(origen))
    return Asiento.objects.filter(
        origen_content_type=ct, origen_object_id=origen.pk
    ).first()


@transaction.atomic
def _crear_asiento(origen, fecha, concepto, lineas, centro_costo=None):
    """
    Crea el asiento con sus lineas. `lineas` es una lista de tuplas
    (cuenta, debe, haber, glosa). Devuelve el Asiento o None.
    """
    periodo = _periodo_abierto(fecha)
    if not periodo:
        return None

    lineas_utiles = [
        (cuenta, debe, haber, glosa)
        for cuenta, debe, haber, glosa in lineas
        if cuenta is not None and (debe or haber)
    ]
    if len(lineas_utiles) < 2:
        logger.info(
            "Sin asiento para %s: faltan cuentas configuradas (%d lineas validas)",
            origen, len(lineas_utiles),
        )
        return None

    total_debe = sum(d for _, d, _, _ in lineas_utiles)
    total_haber = sum(h for _, _, h, _ in lineas_utiles)
    if total_debe != total_haber:
        logger.error(
            "Asiento descuadrado para %s: Debe %s, Haber %s. No se genera.",
            origen, total_debe, total_haber,
        )
        return None

    asiento = Asiento(
        fecha=fecha,
        concepto=concepto[:255],
        automatico=True,
        origen_content_type=ContentType.objects.get_for_model(type(origen)),
        origen_object_id=origen.pk,
    )
    asiento.periodo = periodo
    asiento.save()

    for cuenta, debe, haber, glosa in lineas_utiles:
        LineaAsiento.objects.create(
            asiento=asiento,
            cuenta=cuenta,
            centro_costo=centro_costo,
            debe=debe,
            haber=haber,
            glosa=glosa[:255],
        )

    return asiento


# ------------------------------------------------- generadores por operacion


def asiento_de_movimiento(movimiento):
    """
    Movimiento de caja/banco suelto (sin documento asociado).

    INGRESO -> Debe: caja/banco    Haber: ingresos varios
    EGRESO  -> Debe: egresos varios Haber: caja/banco
    """
    if _movimiento_tiene_documento(movimiento):
        return None

    config = ConfiguracionContable.vigente()
    if not config:
        return None

    cuenta_caja = _cuenta_de_origen(movimiento)
    monto = movimiento.monto

    if movimiento.tipo == "INGRESO":
        contrapartida = _imputable(config.ingresos_varios)
        lineas = [
            (cuenta_caja, monto, 0, movimiento.concepto),
            (contrapartida, 0, monto, movimiento.concepto),
        ]
    else:
        contrapartida = _imputable(config.egresos_varios)
        lineas = [
            (contrapartida, monto, 0, movimiento.concepto),
            (cuenta_caja, 0, monto, movimiento.concepto),
        ]

    return _crear_asiento(
        movimiento, movimiento.fecha,
        f"{movimiento.get_tipo_display()}: {movimiento.concepto}",
        lineas,
    )


def asiento_de_gasto(gasto):
    """
    Gasto clasificado.

    Debe : cuenta de la categoria de gasto
    Haber: caja/banco del movimiento
    """
    movimiento = gasto.movimiento
    cuenta_gasto = _imputable(gasto.categoria.cuenta_contable)
    cuenta_caja = _cuenta_de_origen(movimiento)
    monto = movimiento.monto

    concepto = gasto.descripcion or movimiento.concepto
    lineas = [
        (cuenta_gasto, monto, 0, concepto),
        (cuenta_caja, 0, monto, concepto),
    ]
    return _crear_asiento(
        gasto, movimiento.fecha,
        f"Gasto {gasto.categoria}: {concepto}",
        lineas,
        centro_costo=gasto.centro_costo,
    )


def asiento_de_anticipo(anticipo):
    """
    Anticipo entregado a un proveedor.

    Debe : anticipos a proveedores (es un derecho, un activo)
    Haber: caja/banco
    """
    config = ConfiguracionContable.vigente()
    if not config:
        return None

    movimiento = anticipo.movimiento
    lineas = [
        (_imputable(config.anticipos_proveedores), anticipo.monto_total, 0,
         f"Anticipo a {anticipo.tercero}"),
        (_cuenta_de_origen(movimiento), 0, anticipo.monto_total,
         f"Anticipo a {anticipo.tercero}"),
    ]
    return _crear_asiento(
        anticipo, anticipo.fecha,
        f"Anticipo a proveedor {anticipo.tercero}",
        lineas,
    )


def asiento_de_compra(compra):
    """
    Devengo de la compra de mineral (todavia no se paga).

    Debe : inventario de mineral
    Haber: cuentas por pagar
    """
    config = ConfiguracionContable.vigente()
    if not config:
        return None

    monto = compra.valor_neto
    concepto = f"Compra lote {compra.lote.codigo} - {compra.lote.proveedor}"
    lineas = [
        (_imputable(config.inventario_mineral), monto, 0, concepto),
        (_imputable(config.cuentas_por_pagar), 0, monto, concepto),
    ]
    return _crear_asiento(compra, compra.fecha_negociacion, concepto, lineas)


def asiento_de_pago_compra(pago):
    """
    Pago de una compra.

    Debe : cuentas por pagar (baja la deuda)
    Haber: caja/banco, o anticipos a proveedores si se aplico un anticipo
    """
    config = ConfiguracionContable.vigente()
    if not config:
        return None

    concepto = f"Pago compra {pago.compra.lote.codigo}"

    if pago.tipo_origen == "ANTICIPO":
        contrapartida = _imputable(config.anticipos_proveedores)
        concepto = f"Aplicacion de anticipo a compra {pago.compra.lote.codigo}"
    else:
        contrapartida = _cuenta_de_origen(pago.movimiento) if pago.movimiento_id else None

    lineas = [
        (_imputable(config.cuentas_por_pagar), pago.monto, 0, concepto),
        (contrapartida, 0, pago.monto, concepto),
    ]
    return _crear_asiento(pago, pago.fecha, concepto, lineas)


def asiento_de_venta(venta):
    """
    Devengo de la venta (todavia no se cobra).

    Debe : cuentas por cobrar
    Haber: ventas
    """
    config = ConfiguracionContable.vigente()
    if not config:
        return None

    concepto = f"Venta {venta.numero} - {venta.cliente}"
    lineas = [
        (_imputable(config.cuentas_por_cobrar), venta.valor_neto, 0, concepto),
        (_imputable(config.ventas), 0, venta.valor_neto, concepto),
    ]
    return _crear_asiento(venta, venta.fecha, concepto, lineas)


def asiento_de_cobro_venta(cobro):
    """
    Cobro de una venta.

    Debe : caja/banco
    Haber: cuentas por cobrar (baja el derecho)
    """
    config = ConfiguracionContable.vigente()
    if not config:
        return None

    concepto = f"Cobro venta {cobro.venta.numero}"
    lineas = [
        (_cuenta_de_origen(cobro.movimiento), cobro.monto, 0, concepto),
        (_imputable(config.cuentas_por_cobrar), 0, cobro.monto, concepto),
    ]
    return _crear_asiento(cobro, cobro.fecha, concepto, lineas)


# --------------------------------------------------------------- despachador

GENERADORES = {
    "finanzas.MovimientoFinanciero": asiento_de_movimiento,
    "gastos.Gasto": asiento_de_gasto,
    "finanzas.Anticipo": asiento_de_anticipo,
    "compras.Compra": asiento_de_compra,
    "compras.PagoCompra": asiento_de_pago_compra,
    "ventas.Venta": asiento_de_venta,
    "ventas.CobroVenta": asiento_de_cobro_venta,
}


def generar_asiento(origen, forzar=False):
    """
    Punto de entrada unico. Devuelve el Asiento generado, el que ya existia,
    o None si no se pudo (falta configuracion, periodo cerrado, etc.).

    Nunca lanza excepcion: generar contabilidad jamas debe tumbar la operacion
    que la origino.
    """
    config = ConfiguracionContable.vigente()
    if not config or not config.generar_asientos_automaticos:
        return None

    existente = asiento_existente(origen)
    if existente and not forzar:
        return existente

    clave = f"{origen._meta.app_label}.{type(origen).__name__}"
    generador = GENERADORES.get(clave)
    if not generador:
        return None

    try:
        if existente and forzar:
            existente.lineas.all().delete()
            existente.delete()
        return generador(origen)
    except Exception:
        logger.exception("Fallo al generar el asiento automatico de %s", origen)
        return None
