from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.core.exceptions import ValidationError
from core.models import BaseModel


class CentroCosto(BaseModel):
    """
    Unidad a la que se imputan gastos e ingresos para saber donde se genera
    el costo (secciones 5 y 13 del esquema): una mina, un vehiculo, el area
    administrativa, una operacion de exportacion.

    Es jerarquico igual que el plan de cuentas: un centro puede agrupar otros
    (por ejemplo "Operaciones" agrupando "Transporte" y "Planta").
    """

    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)

    centro_padre = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="subcentros",
    )

    permite_imputacion = models.BooleanField(
        default=True,
        help_text="Si esta desmarcado, el centro solo agrupa y no recibe cargos directos.",
    )

    class Meta:
        verbose_name = "Centro de Costo"
        verbose_name_plural = "Centros de Costo"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class CuentaContable(BaseModel):
    TIPO_CHOICES = [
        ("ACTIVO", "Activo"),
        ("PASIVO", "Pasivo"),
        ("PATRIMONIO", "Patrimonio"),
        ("INGRESO", "Ingreso"),
        ("GASTO", "Gasto"),
    ]

    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=150)
    tipo = models.CharField(max_length=12, choices=TIPO_CHOICES)

    cuenta_padre = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="subcuentas",
    )

    permite_movimiento = models.BooleanField(
        default=True,
        help_text="Si está desmarcado, esta cuenta es solo un agrupador y no puede recibir movimientos directos.",
    )

    class Meta:
        verbose_name = "Cuenta Contable"
        verbose_name_plural = "Plan de Cuentas"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class PeriodoContable(BaseModel):
    ESTADO_CHOICES = [
        ("ABIERTO", "Abierto"),
        ("CERRADO", "Cerrado"),
    ]

    anio = models.PositiveIntegerField()
    mes = models.PositiveIntegerField()

    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()

    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default="ABIERTO")

    class Meta:
        verbose_name = "Periodo Contable"
        verbose_name_plural = "Periodos Contables"
        unique_together = [("anio", "mes")]
        ordering = ["-anio", "-mes"]

    def __str__(self):
        return f"{self.mes:02d}/{self.anio} ({self.get_estado_display()})"


class ConfiguracionContable(BaseModel):
    """
    Dice que cuenta usar en cada tipo de operacion, para poder generar los
    asientos solos. Sin esto, el sistema no tiene forma de saber que una compra
    de mineral va contra "Inventario" y "Cuentas por Pagar".

    Es un registro unico (singleton): se crea uno y se edita desde el admin.
    Las cuentas de caja y banco NO van aqui — cada Caja y CuentaBancaria tiene
    la suya, porque cada una es una cuenta contable distinta.
    """

    inventario_mineral = models.ForeignKey(
        CuentaContable, on_delete=models.PROTECT, null=True, blank=True,
        related_name="config_inventario",
        help_text="Activo. Se debita al registrar una compra de mineral.",
    )
    cuentas_por_pagar = models.ForeignKey(
        CuentaContable, on_delete=models.PROTECT, null=True, blank=True,
        related_name="config_cxp",
        help_text="Pasivo. Se acredita al comprar y se debita al pagar.",
    )
    cuentas_por_cobrar = models.ForeignKey(
        CuentaContable, on_delete=models.PROTECT, null=True, blank=True,
        related_name="config_cxc",
        help_text="Activo. Se debita al vender y se acredita al cobrar.",
    )
    ventas = models.ForeignKey(
        CuentaContable, on_delete=models.PROTECT, null=True, blank=True,
        related_name="config_ventas",
        help_text="Ingreso. Se acredita al registrar una venta.",
    )
    anticipos_proveedores = models.ForeignKey(
        CuentaContable, on_delete=models.PROTECT, null=True, blank=True,
        related_name="config_anticipos",
        help_text="Activo. Se debita al entregar un anticipo a un proveedor.",
    )
    ingresos_varios = models.ForeignKey(
        CuentaContable, on_delete=models.PROTECT, null=True, blank=True,
        related_name="config_ingresos_varios",
        help_text="Ingreso por defecto para movimientos de caja sin documento asociado.",
    )
    egresos_varios = models.ForeignKey(
        CuentaContable, on_delete=models.PROTECT, null=True, blank=True,
        related_name="config_egresos_varios",
        help_text="Gasto por defecto para egresos sin categoria ni documento.",
    )

    generar_asientos_automaticos = models.BooleanField(
        default=True,
        help_text="Si se desmarca, el sistema deja de generar asientos solo.",
    )

    class Meta:
        verbose_name = "Configuración Contable"
        verbose_name_plural = "Configuración Contable"

    @classmethod
    def vigente(cls):
        return cls.objects.filter(is_active=True).first()

    def __str__(self):
        return "Configuración contable"


class Asiento(BaseModel):
    numero = models.CharField(max_length=30, unique=True, blank=True, editable=False)
    fecha = models.DateField()
    periodo = models.ForeignKey(
        PeriodoContable, on_delete=models.PROTECT,
        related_name="asientos", editable=False,
    )
    concepto = models.CharField(max_length=255)
    observaciones = models.TextField(blank=True)

    automatico = models.BooleanField(
        default=False, editable=False,
        help_text="Generado por el sistema a partir de una operacion.",
    )
    origen_content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="asientos_originados",
    )
    origen_object_id = models.UUIDField(null=True, blank=True, editable=False)
    origen = GenericForeignKey("origen_content_type", "origen_object_id")

    class Meta:
        verbose_name = "Asiento Contable"
        verbose_name_plural = "Asientos Contables"
        ordering = ["-fecha", "-numero"]
        indexes = [
            models.Index(fields=["origen_content_type", "origen_object_id"]),
        ]

    def clean(self):
        # Django llama a clean() aunque la validacion de campos ya haya fallado,
        # asi que los campos obligatorios pueden venir vacios. Si falta la fecha,
        # se sale: el error de "campo obligatorio" ya lo reporta Django.
        if not self.fecha:
            return

        periodo = PeriodoContable.objects.filter(
            anio=self.fecha.year, mes=self.fecha.month
        ).first()
        if not periodo:
            raise ValidationError(
                f"No existe un periodo contable creado para {self.fecha.month}/{self.fecha.year}. Créelo primero."
            )
        if periodo.estado == "CERRADO":
            raise ValidationError(f"El periodo {periodo} está cerrado. No se pueden registrar asientos.")
        self.periodo = periodo

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self._generar_numero()
        super().save(*args, **kwargs)

    def _generar_numero(self):
        anio = self.fecha.year
        ultimo = Asiento.objects.filter(numero__startswith=f"ASN-{anio}-").order_by("-numero").first()
        if ultimo:
            nuevo_numero = int(ultimo.numero.split("-")[-1]) + 1
        else:
            nuevo_numero = 1
        return f"ASN-{anio}-{nuevo_numero:04d}"

    @property
    def total_debe(self):
        return sum(l.debe for l in self.lineas.all())

    @property
    def total_haber(self):
        return sum(l.haber for l in self.lineas.all())

    @property
    def cuadrado(self):
        return self.total_debe == self.total_haber

    def __str__(self):
        return f"{self.numero} - {self.concepto}"


class LineaAsiento(BaseModel):
    asiento = models.ForeignKey(
        Asiento, on_delete=models.CASCADE, related_name="lineas",
    )
    cuenta = models.ForeignKey(
        CuentaContable, on_delete=models.PROTECT, related_name="lineas_asiento",
    )
    centro_costo = models.ForeignKey(
        CentroCosto, on_delete=models.PROTECT, null=True, blank=True,
        related_name="lineas_asiento",
        help_text="Opcional. Necesario para los reportes por centro de costo.",
    )
    debe = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    haber = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    glosa = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Línea de Asiento"
        verbose_name_plural = "Líneas de Asiento"

    def clean(self):
        if self.debe and self.haber:
            raise ValidationError("Una línea no puede tener valor en Debe y Haber a la vez.")
        if not self.debe and not self.haber:
            raise ValidationError("Debe ingresar un valor en Debe o en Haber.")
        if not self.cuenta.permite_movimiento:
            raise ValidationError(f"La cuenta {self.cuenta} no permite movimientos directos (es un agrupador).")
        if self.centro_costo and not self.centro_costo.permite_imputacion:
            raise ValidationError(
                f"El centro de costo {self.centro_costo} no permite imputacion directa (es un agrupador)."
            )

    def __str__(self):
        lado = "Debe" if self.debe else "Haber"
        monto = self.debe or self.haber
        return f"{self.cuenta.codigo} - {lado}: {monto}"