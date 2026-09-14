from django.db import models
from django.core.exceptions import ValidationError
from core.models import BaseModel
from lotes.models import Lote


class CategoriaGasto(BaseModel):
    """
    Catalogo flexible de categorias (seccion 13 del esquema): operativos,
    administrativos, financieros, combustible, alimentacion, mantenimiento,
    servicios, logistica, transporte. Se administra desde el admin sin tocar codigo.
    """

    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    cuenta_contable = models.ForeignKey(
        "contabilidad.CuentaContable",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="categorias_gasto",
        help_text="Cuenta de gasto que se debita al registrar un gasto de esta "
                  "categoria. Necesaria para el asiento automatico.",
    )

    class Meta:
        verbose_name = "Categoría de Gasto"
        verbose_name_plural = "Categorías de Gasto"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Gasto(BaseModel):
    """
    Clasificacion de un egreso ya registrado en finanzas.

    No duplica el dinero: se vincula a un MovimientoFinanciero existente
    (que ya descuenta el saldo de caja/banco via señal) y le agrega la
    categoria, el centro de costo y, opcionalmente, el lote al que pertenece.
    El monto, la moneda y la fecha se leen del movimiento.
    """

    movimiento = models.OneToOneField(
        "finanzas.MovimientoFinanciero",
        on_delete=models.PROTECT,
        related_name="gasto",
    )
    categoria = models.ForeignKey(
        CategoriaGasto, on_delete=models.PROTECT, related_name="gastos",
    )
    centro_costo = models.ForeignKey(
        "contabilidad.CentroCosto",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="gastos",
    )
    lote = models.ForeignKey(
        Lote, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="gastos",
        help_text="Opcional: gasto atribuible a un lote concreto (ej. flete de ese lote).",
    )
    descripcion = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Gasto"
        verbose_name_plural = "Gastos"
        ordering = ["-created_at"]

    def clean(self):
        if self.movimiento and self.movimiento.tipo != "EGRESO":
            raise ValidationError(
                "Un gasto solo puede vincularse a un movimiento de tipo EGRESO."
            )
        if self.centro_costo and not self.centro_costo.permite_imputacion:
            raise ValidationError(
                f"El centro de costo {self.centro_costo} no permite imputacion directa."
            )

    @property
    def monto(self):
        return self.movimiento.monto

    @property
    def moneda(self):
        return self.movimiento.moneda

    @property
    def fecha(self):
        return self.movimiento.fecha

    def __str__(self):
        return f"{self.categoria} - {self.movimiento.monto} {self.movimiento.moneda}"
