from django.db import models
from core.models import BaseModel


class Tercero(BaseModel):
    TIPO_CHOICES = [
        ("PROVEEDOR", "Proveedor"),
        ("COMPRADOR", "Comprador"),
        ("LABORATORIO", "Laboratorio"),
        ("TRANSPORTISTA", "Transportista"),
        ("OTRO", "Otro"),
    ]

    TIPO_PERSONA_CHOICES = [
        ("NATURAL", "Natural"),
        ("JURIDICA", "Jurídica"),
    ]

    codigo = models.CharField(max_length=20, unique=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    tipo_persona = models.CharField(max_length=20, choices=TIPO_PERSONA_CHOICES)
    razon_social = models.CharField(max_length=255, blank=True)
    nombre_completo = models.CharField(max_length=255, blank=True)
    documento = models.CharField(max_length=50, blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    direccion = models.TextField(blank=True)
    observaciones = models.TextField(blank=True)

    def __str__(self):
        if self.tipo_persona == "JURIDICA":
            return self.razon_social
        return self.nombre_completo