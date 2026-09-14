from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from core.models import BaseModel
from terceros.models import Tercero


class TipoMaterial(BaseModel):
    """
    Catálogo de tipos de material que puede declararse en un lote
    (Zinc, Plomo, Plata, Otro). Un lote puede tener uno o varios
    tipos a la vez (mineral complejo/polimetálico).
    """
    codigo = models.CharField(max_length=10, unique=True)
    nombre = models.CharField(max_length=50)

    class Meta:
        verbose_name = "Tipo de Material"
        verbose_name_plural = "Tipos de Material"

    def __str__(self):
        return self.nombre


class LoteComercial(BaseModel):
    """
    Código comercial/exportación generado cuando se mezclan
    uno o más lotes internos (sección 7 del esquema).
    El código se define manualmente, caso por caso.
    """
    ESTADO_CHOICES = [
        ("ABIERTO", "Abierto"),
        ("CERRADO", "Cerrado"),
    ]

    codigo = models.CharField(max_length=30, unique=True)
    fecha_creacion = models.DateField()
    peso_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default="ABIERTO")
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Lote Comercial"
        verbose_name_plural = "Lotes Comerciales"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return self.codigo


class Lote(BaseModel):
    """
    Cada entrega individual de mineral de un proveedor.
    El código se genera automáticamente con el formato LOT-YYYY-NNNN,
    reiniciando la numeración cada año.
    """
    ESTADO_CHOICES = [
        ("RECIBIDO", "Recibido"),
        ("EN_MUESTREO", "En Muestreo"),
        ("EN_ANALISIS", "En Análisis"),
        ("NEGOCIACION", "En Negociación"),
        ("LIQUIDADO", "Liquidado"),
        ("CERRADO", "Cerrado"),
    ]

    codigo = models.CharField(max_length=30, unique=True, blank=True, editable=False)

    proveedor = models.ForeignKey(
        Tercero, on_delete=models.PROTECT, related_name="lotes",
    )

    tipo_material = models.ManyToManyField(
        TipoMaterial, related_name="lotes",
    )

    fecha_recepcion = models.DateField()
    fecha_entrega = models.DateField(null=True, blank=True)

    peso_bruto = models.DecimalField(max_digits=12, decimal_places=2)
    tara = models.DecimalField(max_digits=12, decimal_places=2)
    peso_neto = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    placa_vehiculo = models.CharField(max_length=20, blank=True)

    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default="RECIBIDO")

    lote_comercial = models.ForeignKey(
        LoteComercial, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="lotes_internos",
    )

    observaciones = models.TextField(blank=True)

    documento_liquidacion=models.FileField(
        upload_to="liquidaciones/%Y/%m/",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Lote"
        verbose_name_plural = "Lotes"
        ordering = ["-fecha_recepcion"]

    def clean(self):
        if self.tara >= self.peso_bruto:
            raise ValidationError("La tara no puede ser mayor o igual al peso bruto.")

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self._generar_codigo()
        self.peso_neto = self.peso_bruto - self.tara
        super().save(*args, **kwargs)

    def _generar_codigo(self):
        anio = timezone.now().year
        ultimo = Lote.objects.filter(codigo__startswith=f"LOT-{anio}-").order_by("-codigo").first()

        if ultimo:
            ultimo_numero = int(ultimo.codigo.split("-")[-1])
            nuevo_numero = ultimo_numero + 1
        else:
            nuevo_numero = 1

        return f"LOT-{anio}-{nuevo_numero:04d}"

    def __str__(self):
        if not self.pk:
            return "Lote (sin guardar)"
        materiales = ", ".join(t.nombre for t in self.tipo_material.all())
        return f"{self.codigo} - {materiales} ({self.peso_neto} kg)"