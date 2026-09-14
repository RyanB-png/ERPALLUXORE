from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    """
    Modelo de usuario personalizado para Alluxore Metals ERP.
    Extiende AbstractUser (login por username, igual que Django por defecto)
    agregando datos propios del negocio: rol, teléfono, cargo, sucursal.
    """

    ROL_CHOICES = [
        ("admin", "Administrador"),
        ("operativo", "Usuario Operativo"),
        ("contabilidad", "Contabilidad"),
        ("finanzas", "Finanzas"),
        ("laboratorio", "Laboratorio"),
        ("ventas", "Ventas"),
    ]

    email = models.EmailField(unique=True, blank=True)
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default="operativo")
    telefono = models.CharField(max_length=20, blank=True)
    cargo = models.CharField(max_length=100, blank=True)

    sucursal = models.ForeignKey(
        "organizacion.Sucursal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usuarios",
    )
    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_rol_display()})"