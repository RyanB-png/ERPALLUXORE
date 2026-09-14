"""
Liquidaciones (seccion 9 del esquema).

Calcula cuanto vale comercialmente un lote de mineral y deja registrado COMO
se llego a ese numero: que cotizacion se uso, que porcentaje pagable se aplico
y que deducciones se descontaron. Esa trazabilidad es el punto: dentro de seis
meses tiene que poder justificarse por que se le pago X a un proveedor.

FORMULA IMPLEMENTADA (verificar contra la practica real de Alluxore):

    peso seco      = peso humedo * (1 - humedad/100)
    contenido fino = peso seco (TM) * ley, convertida segun la unidad del elemento
    valor elemento = contenido fino * cotizacion * (% pagable / 100)
    valor bruto    = suma de los valores por elemento
    valor neto     = valor bruto - deducciones

Las escalas por rango de ley, castigos por impurezas y formulas de maquila
especificas de cada contrato NO estan modeladas: se registran como deducciones.
"""

from decimal import Decimal

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.models import BaseModel
from lotes.models import Lote
from laboratorio.models import Elemento, Muestra
from terceros.models import Tercero

# Factores de conversion
GRAMOS_POR_ONZA_TROY = Decimal("31.1034768")
LIBRAS_POR_TONELADA = Decimal("2204.62262")
KG_POR_TONELADA = Decimal("1000")


class CotizacionMineral(BaseModel):
    """Precio de mercado de un elemento en una fecha determinada."""

    UNIDAD_CHOICES = [
        ("USD_TM", "USD por tonelada métrica"),
        ("USD_OZT", "USD por onza troy"),
        ("USD_LB", "USD por libra"),
    ]

    elemento = models.ForeignKey(
        Elemento, on_delete=models.PROTECT, related_name="cotizaciones",
    )
    fecha = models.DateField()
    precio = models.DecimalField(max_digits=14, decimal_places=4)
    unidad = models.CharField(max_length=10, choices=UNIDAD_CHOICES, default="USD_TM")
    fuente = models.CharField(
        max_length=100, blank=True,
        help_text="De donde salio el precio (LME, London Fix, contrato, etc.)",
    )

    class Meta:
        verbose_name = "Cotización de Mineral"
        verbose_name_plural = "Cotizaciones de Minerales"
        ordering = ["-fecha", "elemento"]
        unique_together = [("elemento", "fecha", "unidad")]

    def __str__(self):
        return f"{self.elemento.simbolo} {self.precio} {self.get_unidad_display()} ({self.fecha})"


class ReglaLiquidacion(BaseModel):
    """
    Regla configurable de cuanto se paga de un elemento.

    Puede ser general (aplica a todos los proveedores) o especifica de un
    proveedor. Si hay varias vigentes, gana la mas especifica y mas reciente.
    """

    elemento = models.ForeignKey(
        Elemento, on_delete=models.PROTECT, related_name="reglas_liquidacion",
    )
    proveedor = models.ForeignKey(
        Tercero, on_delete=models.PROTECT, null=True, blank=True,
        related_name="reglas_liquidacion",
        help_text="Vacio = regla general para todos los proveedores.",
    )

    porcentaje_pagable = models.DecimalField(
        max_digits=6, decimal_places=3,
        help_text="Porcentaje del contenido fino que se paga (ej. 85.000 para 85%).",
    )
    ley_minima = models.DecimalField(
        max_digits=10, decimal_places=4, default=0,
        help_text="Por debajo de esta ley el elemento no se paga.",
    )

    vigente_desde = models.DateField()
    vigente_hasta = models.DateField(null=True, blank=True)
    descripcion = models.TextField(blank=True)

    class Meta:
        verbose_name = "Regla de Liquidación"
        verbose_name_plural = "Reglas de Liquidación"
        ordering = ["-vigente_desde"]

    def clean(self):
        if self.vigente_hasta and self.vigente_desde and self.vigente_hasta < self.vigente_desde:
            raise ValidationError("La fecha final de vigencia es anterior a la inicial.")
        if self.porcentaje_pagable is None:
            return
        if self.porcentaje_pagable < 0 or self.porcentaje_pagable > 100:
            raise ValidationError("El porcentaje pagable debe estar entre 0 y 100.")

    @classmethod
    def vigente_para(cls, elemento, proveedor, fecha):
        """Devuelve la regla aplicable, priorizando la especifica del proveedor."""
        base = cls.objects.filter(
            elemento=elemento, is_active=True, vigente_desde__lte=fecha,
        ).filter(models.Q(vigente_hasta__isnull=True) | models.Q(vigente_hasta__gte=fecha))

        especifica = base.filter(proveedor=proveedor).order_by("-vigente_desde").first()
        if especifica:
            return especifica
        return base.filter(proveedor__isnull=True).order_by("-vigente_desde").first()

    def __str__(self):
        alcance = self.proveedor or "General"
        return f"{self.elemento.simbolo} {self.porcentaje_pagable}% ({alcance})"


class ConceptoDeduccion(BaseModel):
    """Catalogo de cargos que se descuentan del valor bruto."""

    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)

    class Meta:
        verbose_name = "Concepto de Deducción"
        verbose_name_plural = "Conceptos de Deducción"
        ordering = ["codigo"]

    def __str__(self):
        return self.nombre


class Liquidacion(BaseModel):
    """
    Cabecera del calculo. Se genera a partir de un lote y de la muestra cuyos
    resultados de laboratorio se toman como validos.
    """

    ESTADO_CHOICES = [
        ("BORRADOR", "Borrador"),
        ("APROBADA", "Aprobada"),
        ("ANULADA", "Anulada"),
    ]
    MONEDA_CHOICES = [
        ("USD", "Dólares"),
        ("BOB", "Bolivianos"),
    ]

    numero = models.CharField(max_length=30, unique=True, blank=True, editable=False)

    lote = models.ForeignKey(
        Lote, on_delete=models.PROTECT, related_name="liquidaciones",
    )
    muestra = models.ForeignKey(
        Muestra, on_delete=models.PROTECT, related_name="liquidaciones",
        help_text="Muestra cuyos resultados de ley se usan para el calculo.",
    )

    fecha = models.DateField()
    moneda = models.CharField(max_length=3, choices=MONEDA_CHOICES, default="USD")
    tipo_cambio = models.DecimalField(max_digits=8, decimal_places=4, default=1)

    peso_humedo = models.DecimalField(
        max_digits=12, decimal_places=2, editable=False, default=0,
        help_text="Kilos. Se copia del peso neto del lote.",
    )
    humedad = models.DecimalField(
        max_digits=5, decimal_places=2, editable=False, default=0,
        help_text="Porcentaje. Se copia de la muestra.",
    )
    peso_seco = models.DecimalField(
        max_digits=12, decimal_places=2, editable=False, default=0,
    )

    valor_bruto = models.DecimalField(
        max_digits=14, decimal_places=2, editable=False, default=0,
    )
    total_deducciones = models.DecimalField(
        max_digits=14, decimal_places=2, editable=False, default=0,
    )
    valor_neto = models.DecimalField(
        max_digits=14, decimal_places=2, editable=False, default=0,
    )

    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default="BORRADOR")
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Liquidación"
        verbose_name_plural = "Liquidaciones"
        ordering = ["-fecha", "-numero"]

    def clean(self):
        if self.muestra_id and self.lote_id and self.muestra.lote_id != self.lote_id:
            raise ValidationError(
                "La muestra seleccionada pertenece a otro lote."
            )

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self._generar_numero()

        if self.muestra_id and self.lote_id:
            self.peso_humedo = self.lote.peso_neto or Decimal("0")
            self.humedad = self.muestra.humedad or Decimal("0")
            self.peso_seco = self.peso_humedo * (
                Decimal("1") - self.humedad / Decimal("100")
            )

        super().save(*args, **kwargs)

    def _generar_numero(self):
        anio = (self.fecha or timezone.now().date()).year
        ultimo = (
            Liquidacion.objects.filter(numero__startswith=f"LIQ-{anio}-")
            .order_by("-numero")
            .first()
        )
        nuevo = int(ultimo.numero.split("-")[-1]) + 1 if ultimo else 1
        return f"LIQ-{anio}-{nuevo:04d}"

    @property
    def peso_seco_tm(self):
        return (self.peso_seco or Decimal("0")) / KG_POR_TONELADA

    def generar_detalles(self):
        """
        Crea una linea por cada resultado de laboratorio de la muestra,
        buscando la cotizacion mas reciente y la regla vigente de cada elemento.
        Reemplaza los detalles anteriores.
        """
        self.detalles.all().delete()

        for resultado in self.muestra.resultados.select_related("elemento"):
            elemento = resultado.elemento

            cotizacion = (
                CotizacionMineral.objects.filter(
                    elemento=elemento, fecha__lte=self.fecha, is_active=True
                )
                .order_by("-fecha")
                .first()
            )
            regla = ReglaLiquidacion.vigente_para(
                elemento, self.lote.proveedor, self.fecha
            )

            DetalleLiquidacion.objects.create(
                liquidacion=self,
                elemento=elemento,
                ley=resultado.valor,
                unidad_ley=elemento.unidad_ley,
                cotizacion=cotizacion,
                precio_unitario=cotizacion.precio if cotizacion else Decimal("0"),
                unidad_precio=cotizacion.unidad if cotizacion else "USD_TM",
                porcentaje_pagable=regla.porcentaje_pagable if regla else Decimal("0"),
                ley_minima=regla.ley_minima if regla else Decimal("0"),
            )

        self.recalcular()

    def recalcular(self):
        """Recalcula cada detalle, las deducciones y los totales."""
        bruto = Decimal("0")
        for detalle in self.detalles.all():
            detalle.calcular()
            detalle.save()
            bruto += detalle.valor

        deducciones = Decimal("0")
        for deduccion in self.deducciones.all():
            deduccion.calcular(bruto)
            deduccion.save()
            deducciones += deduccion.monto

        self.valor_bruto = bruto
        self.total_deducciones = deducciones
        self.valor_neto = bruto - deducciones
        super().save(update_fields=["valor_bruto", "total_deducciones", "valor_neto"])

    def __str__(self):
        return f"{self.numero} - {self.lote.codigo} ({self.valor_neto} {self.moneda})"


class DetalleLiquidacion(BaseModel):
    """
    Una linea por elemento pagado. Guarda copia del precio y del porcentaje
    usados: si manana cambia la cotizacion, esta liquidacion no se altera.
    """

    liquidacion = models.ForeignKey(
        Liquidacion, on_delete=models.CASCADE, related_name="detalles",
    )
    elemento = models.ForeignKey(
        Elemento, on_delete=models.PROTECT, related_name="detalles_liquidacion",
    )

    ley = models.DecimalField(max_digits=10, decimal_places=4)
    unidad_ley = models.CharField(max_length=20, default="PORCENTAJE")

    cotizacion = models.ForeignKey(
        CotizacionMineral, on_delete=models.PROTECT, null=True, blank=True,
        related_name="detalles_liquidacion",
    )
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    unidad_precio = models.CharField(max_length=10, default="USD_TM")

    porcentaje_pagable = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    ley_minima = models.DecimalField(max_digits=10, decimal_places=4, default=0)

    contenido_fino = models.DecimalField(
        max_digits=16, decimal_places=6, default=0, editable=False,
        help_text="En TM finas, u onzas troy si el elemento se mide en g/t u oz/t.",
    )
    valor = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, editable=False,
    )

    class Meta:
        verbose_name = "Detalle de Liquidación"
        verbose_name_plural = "Detalles de Liquidación"
        unique_together = [("liquidacion", "elemento")]

    def calcular(self):
        """Calcula contenido fino y valor. No guarda: eso lo hace quien llama."""
        peso_tm = self.liquidacion.peso_seco_tm

        if self.ley < self.ley_minima:
            self.contenido_fino = Decimal("0")
            self.valor = Decimal("0")
            return

        if self.unidad_ley == "PORCENTAJE":
            fino_tm = peso_tm * self.ley / Decimal("100")
            fino_ozt = Decimal("0")
        elif self.unidad_ley == "GRAMO_TONELADA":
            fino_tm = Decimal("0")
            fino_ozt = peso_tm * self.ley / GRAMOS_POR_ONZA_TROY
        else:  # ONZA_TONELADA
            fino_tm = Decimal("0")
            fino_ozt = peso_tm * self.ley

        self.contenido_fino = fino_tm if self.unidad_ley == "PORCENTAJE" else fino_ozt

        if self.unidad_precio == "USD_TM":
            base = fino_tm * self.precio_unitario
        elif self.unidad_precio == "USD_LB":
            base = fino_tm * LIBRAS_POR_TONELADA * self.precio_unitario
        else:  # USD_OZT
            base = fino_ozt * self.precio_unitario

        self.valor = (base * self.porcentaje_pagable / Decimal("100")).quantize(
            Decimal("0.01")
        )

    def __str__(self):
        return f"{self.elemento.simbolo}: {self.valor}"


class DeduccionLiquidacion(BaseModel):
    """Cargo descontado del valor bruto: maquila, flete, refinacion, castigos."""

    TIPO_CALCULO_CHOICES = [
        ("MONTO_FIJO", "Monto fijo"),
        ("PORCENTAJE", "Porcentaje del valor bruto"),
    ]

    liquidacion = models.ForeignKey(
        Liquidacion, on_delete=models.CASCADE, related_name="deducciones",
    )
    concepto = models.ForeignKey(
        ConceptoDeduccion, on_delete=models.PROTECT, related_name="deducciones",
    )
    tipo_calculo = models.CharField(
        max_length=12, choices=TIPO_CALCULO_CHOICES, default="MONTO_FIJO",
    )
    valor = models.DecimalField(
        max_digits=14, decimal_places=4,
        help_text="Monto en la moneda de la liquidacion, o porcentaje segun el tipo.",
    )
    monto = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, editable=False,
    )
    observaciones = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Deducción de Liquidación"
        verbose_name_plural = "Deducciones de Liquidación"

    def clean(self):
        if self.valor is None:
            return
        if self.tipo_calculo == "PORCENTAJE" and (self.valor < 0 or self.valor > 100):
            raise ValidationError("Un porcentaje debe estar entre 0 y 100.")

    def calcular(self, valor_bruto):
        if self.tipo_calculo == "PORCENTAJE":
            self.monto = (valor_bruto * self.valor / Decimal("100")).quantize(
                Decimal("0.01")
            )
        else:
            self.monto = Decimal(self.valor).quantize(Decimal("0.01"))

    def __str__(self):
        return f"{self.concepto} - {self.monto}"
