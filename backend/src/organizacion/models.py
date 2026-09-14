from django.db import models
from core.models import BaseModel


class Empresa(BaseModel):
    razon_social = models.CharField(max_length=255)
    nit = models.CharField(max_length=30, unique=True)
    direccion = models.TextField(blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"

    def __str__(self):
        return self.razon_social


class Sucursal(BaseModel):
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        related_name="sucursales",
    )
    nombre = models.CharField(max_length=100)
    direccion = models.TextField(blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    es_principal = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Sucursal"
        verbose_name_plural = "Sucursales"


    def __str__(self):
        return f"{self.nombre} ({self.empresa.razon_social})"


class Caja(BaseModel):
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        related_name="cajas",
    )
    nombre = models.CharField(max_length=100)
    moneda = models.CharField(
        max_length=3,
        choices=[("BOB", "Bolivianos"), ("USD", "Dólares")],
        default="BOB",
    )
    saldo_actual = models.DecimalField(max_digits=14, decimal_places=2, default=0)


    class Meta:
        verbose_name = "Caja"
        verbose_name_plural = "Cajas"


    def __str__(self):
        return f"{self.nombre} ({self.moneda})"


class CuentaBancaria(BaseModel):
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        related_name="cuentas_bancarias",
    )
    banco = models.CharField(max_length=100)
    numero_cuenta = models.CharField(max_length=50, unique=True)
    moneda = models.CharField(
        max_length=3,
        choices=[("BOB", "Bolivianos"), ("USD", "Dólares")],
        default="BOB",
    )
    saldo_actual = models.DecimalField(max_digits=14, decimal_places=2, default=0)


    class Meta:
        verbose_name = "Cuenta Bancaria"
        verbose_name_plural = "Cuentas Bancarias"

    def __str__(self):
        return f"{self.banco} - {self.numero_cuenta}"