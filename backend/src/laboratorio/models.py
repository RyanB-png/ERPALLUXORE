# backend/src/laboratorio/models.py

from django.db import models
from core.models import BaseModel
from lotes.models import Lote


class Laboratorio(BaseModel):
    TIPO_CHOICES = [
        ("RAPIDO", "Rápido"),
        ("ACREDITADO", "Acreditado"),
    ]

    nombre = models.CharField(max_length=150)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    contacto = models.CharField(max_length=150, blank=True)
    telefono = models.CharField(max_length=30, blank=True)

    class Meta:
        verbose_name = "Laboratorio"
        verbose_name_plural = "Laboratorios"

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()})"


class Elemento(BaseModel):
    UNIDAD_LEY_CHOICES = [
        ("PORCENTAJE", "Porcentaje (%)"),
        ("GRAMO_TONELADA", "Gramos por tonelada (g/t)"),
        ("ONZA_TONELADA", "Onzas troy por tonelada (oz/t)"),
    ]

    simbolo = models.CharField(max_length=10, unique=True)
    nombre = models.CharField(max_length=50)
    unidad_ley = models.CharField(
        max_length=20,
        choices=UNIDAD_LEY_CHOICES,
        default="PORCENTAJE",
        help_text="Unidad en que se reporta la ley de este elemento. "
                  "Zn/Pb suelen ir en %, Ag/Au en g/t u oz/t.",
    )

    class Meta:
        verbose_name = "Elemento"
        verbose_name_plural = "Elementos"

    def __str__(self):
        return f"{self.simbolo} - {self.nombre}"


class Muestra(BaseModel):
    ESTADO_CHOICES = [
        ("ENVIADA", "Enviada"),
        ("EN_ANALISIS", "En Análisis"),
        ("RESULTADO_RECIBIDO", "Resultado Recibido"),
    ]

    lote = models.ForeignKey(
        Lote, on_delete=models.PROTECT, related_name="muestras",
    )
    laboratorio = models.ForeignKey(
        Laboratorio, on_delete=models.PROTECT, related_name="muestras",
    )

    fecha_envio = models.DateField()
    fecha_resultado = models.DateField(null=True, blank=True)

    humedad = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text="Porcentaje de humedad (ej. 4.50 para 4.50%)",
    )

    foto = models.ImageField(upload_to="muestras/%Y/%m/", null=True, blank=True)

    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="ENVIADA")
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Muestra"
        verbose_name_plural = "Muestras"
        ordering = ["-fecha_envio"]

    def __str__(self):
        return f"Muestra {self.lote.codigo} - {self.laboratorio.nombre}"


class ResultadoElemento(BaseModel):
    muestra = models.ForeignKey(
        Muestra, on_delete=models.CASCADE, related_name="resultados",
    )
    elemento = models.ForeignKey(
        Elemento, on_delete=models.PROTECT, related_name="resultados",
    )
    valor = models.DecimalField(
        max_digits=10, decimal_places=4,
        help_text="Ley del elemento (unidad según el elemento: %, g/t, oz/t, etc.)",
    )

    class Meta:
        verbose_name = "Resultado de Elemento"
        verbose_name_plural = "Resultados de Elementos"
        unique_together = [("muestra", "elemento")]

    def __str__(self):
        return f"{self.elemento.simbolo}: {self.valor} ({self.muestra})"