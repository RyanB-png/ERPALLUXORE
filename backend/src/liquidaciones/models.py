"""
Liquidaciones (seccion 9 del esquema).

REPARTO DE RESPONSABILIDADES
----------------------------
El CALCULO vive en el frontend (React): es donde se negocia con el proveedor y
donde tiene sentido ver el efecto de cada cambio al instante, sin migraciones
de por medio.

El BACKEND no calcula: registra. Guarda el resultado Y el desglose de como se
llego a el —que cotizacion se uso, que porcentaje pagable, que deducciones—
para que dentro de seis meses se pueda justificar por que se le pago X a un
proveedor. Sin ese desglose, el numero final no seria auditable.

Lo unico que el backend si hace con los numeros es VERIFICAR que sean
coherentes entre si (ver `Liquidacion.clean` y `verificar_consistencia`).
Guardar importes que llegan del cliente sin comprobar que cuadren seria
confiar ciegamente en el navegador.

`CotizacionMineral` y `ReglaLiquidacion` siguen siendo configuracion del
sistema: el frontend las lee para calcular, y el detalle guarda copia de los
valores que efectivamente uso (si manana cambia la cotizacion, la liquidacion
vieja no se altera).
"""

from decimal import Decimal

from django.core.files.base import ContentFile
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.models import BaseModel
from lotes.models import Lote
from laboratorio.models import Elemento, Muestra
from terceros.models import Tercero

# Tolerancia al comparar importes: evita falsos errores por redondeo decimal.
TOLERANCIA = Decimal("0.01")


class CotizacionMineral(BaseModel):
    """Precio de mercado de un elemento en una fecha. Lo consume el frontend."""

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
    Regla configurable de cuanto se paga de un elemento. La aplica el frontend
    al calcular; aqui solo se define y se consulta.
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
        """
        Regla aplicable, priorizando la especifica del proveedor sobre la
        general. Pensada para que la exponga la API y el frontend la use.
        """
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


def ruta_pdf_liquidacion(instance, filename):
    """
    Guarda el PDF dentro de la carpeta del lote:
        media/lotes/LOT-2026-0001/liquidaciones/LIQ-2026-0001.pdf

    Es una funcion y no un string fijo porque la ruta depende del lote, que
    solo se conoce en tiempo de ejecucion.
    """
    return f"lotes/{instance.lote.codigo}/liquidaciones/{filename}"


class Liquidacion(BaseModel):
    """
    Registro de una liquidacion calculada en el frontend.

    Todos los importes llegan ya calculados. El backend no los recalcula:
    solo comprueba que cuadren entre si antes de aceptarlos.
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
        help_text="Muestra cuyos resultados de ley se usaron para el calculo.",
    )

    fecha = models.DateField()
    moneda = models.CharField(max_length=3, choices=MONEDA_CHOICES, default="USD")
    tipo_cambio = models.DecimalField(max_digits=8, decimal_places=4, default=1)

    peso_humedo = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Kilos, tal como se uso en el calculo.",
    )
    humedad = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Porcentaje de humedad aplicado.",
    )
    peso_seco = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Kilos secos resultantes.",
    )

    valor_bruto = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text="Suma del valor de todos los elementos pagables.",
    )
    total_deducciones = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
    )
    valor_neto = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text="Valor bruto menos deducciones. Es lo que se paga al proveedor.",
    )

    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default="BORRADOR")
    observaciones = models.TextField(blank=True)

    archivo_pdf = models.FileField(
        upload_to=ruta_pdf_liquidacion,
        null=True, blank=True, editable=False,
        help_text="PDF generado por el sistema a partir de este registro.",
    )

    class Meta:
        verbose_name = "Liquidación"
        verbose_name_plural = "Liquidaciones"
        ordering = ["-fecha", "-numero"]

    def clean(self):
        # Recordar: Django llama a clean() aunque falten campos obligatorios.
        if self.muestra_id and self.lote_id and self.muestra.lote_id != self.lote_id:
            raise ValidationError("La muestra seleccionada pertenece a otro lote.")

        if self.peso_humedo is not None and self.peso_seco is not None:
            if self.peso_seco > self.peso_humedo:
                raise ValidationError(
                    "El peso seco no puede ser mayor que el peso humedo."
                )

        # El backend no calcula, pero si verifica que los importes cuadren.
        if (
            self.valor_bruto is not None
            and self.total_deducciones is not None
            and self.valor_neto is not None
        ):
            esperado = self.valor_bruto - self.total_deducciones
            if abs(self.valor_neto - esperado) > TOLERANCIA:
                raise ValidationError(
                    f"Los importes no cuadran: valor bruto ({self.valor_bruto}) "
                    f"menos deducciones ({self.total_deducciones}) da {esperado}, "
                    f"pero el valor neto recibido es {self.valor_neto}."
                )

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self._generar_numero()
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

    def verificar_consistencia(self):
        """
        Contrasta los totales de la cabecera contra la suma de sus lineas.

        Devuelve una lista de discrepancias (vacia si todo cuadra). No lanza
        excepcion ni corrige nada: sirve para que la API responda con avisos y
        para mostrarlos en el admin. Se separa de `clean()` porque las lineas
        se guardan despues de la cabecera y ahi todavia no existen.
        """
        problemas = []

        suma_detalles = sum(
            (d.valor for d in self.detalles.all()), Decimal("0")
        )
        if abs(suma_detalles - (self.valor_bruto or 0)) > TOLERANCIA:
            problemas.append(
                f"El valor bruto ({self.valor_bruto}) no coincide con la suma "
                f"de los elementos ({suma_detalles})."
            )

        suma_deducciones = sum(
            (d.monto for d in self.deducciones.all()), Decimal("0")
        )
        if abs(suma_deducciones - (self.total_deducciones or 0)) > TOLERANCIA:
            problemas.append(
                f"El total de deducciones ({self.total_deducciones}) no coincide "
                f"con la suma de las lineas ({suma_deducciones})."
            )

        return problemas

    def generar_pdf(self):
        """
        Construye el PDF y lo guarda en la carpeta del lote.

        Si ya existia uno se borra primero: sin eso Django no sobrescribe, le
        agrega un sufijo aleatorio al nombre, y terminarias acumulando
        LIQ-2026-0001.pdf, LIQ-2026-0001_a8Fk2.pdf, LIQ-2026-0001_p0Zx9.pdf.
        """
        from .pdf import construir_pdf_liquidacion

        contenido = construir_pdf_liquidacion(self)

        if self.archivo_pdf:
            self.archivo_pdf.delete(save=False)

        self.archivo_pdf.save(
            f"{self.numero}.pdf", ContentFile(contenido), save=True,
        )
        return self.archivo_pdf

    @property
    def cuadra(self):
        return not self.verificar_consistencia()

    def __str__(self):
        return f"{self.numero} - {self.lote.codigo} ({self.valor_neto} {self.moneda})"


class DetalleLiquidacion(BaseModel):
    """
    Una linea por elemento pagado, tal como la calculo el frontend.

    Guarda copia del precio y del porcentaje usados: si manana cambia la
    cotizacion o la regla, esta liquidacion sigue diciendo con que numeros
    se hizo.
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
        help_text="Cotizacion concreta que se uso, si salio del catalogo.",
    )
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    unidad_precio = models.CharField(max_length=10, default="USD_TM")

    porcentaje_pagable = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    ley_minima = models.DecimalField(max_digits=10, decimal_places=4, default=0)

    contenido_fino = models.DecimalField(
        max_digits=16, decimal_places=6, default=0,
        help_text="Calculado por el frontend. En TM finas, u onzas troy segun el elemento.",
    )
    valor = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text="Calculado por el frontend: lo que se paga por este elemento.",
    )

    class Meta:
        verbose_name = "Detalle de Liquidación"
        verbose_name_plural = "Detalles de Liquidación"
        unique_together = [("liquidacion", "elemento")]

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
        help_text="El porcentaje aplicado, o el monto fijo pactado.",
    )
    monto = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text="Importe resultante, calculado por el frontend.",
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

    def __str__(self):
        return f"{self.concepto} - {self.monto}"