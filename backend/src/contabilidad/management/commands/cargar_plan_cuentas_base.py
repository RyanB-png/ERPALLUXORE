"""
Siembra un plan de cuentas inicial y deja la contabilidad automatica lista.

IMPORTANTE: este plan es un PUNTO DE PARTIDA con la estructura que este ERP
necesita para funcionar (inventario de mineral, cuentas por pagar, anticipos,
ventas...). NO es un plan de cuentas normativo boliviano ni esta adaptado al
rubro de Alluxore. Reviselo con su contador antes de operar en serio: los
codigos, los nombres y el desglose son suyos para cambiar.

Lo que hace:
  1. Crea las cuentas que no existan (por codigo, nunca pisa las existentes).
  2. Crea la Configuracion Contable apuntando a las cuentas correctas.
  3. Asigna cuenta contable a las cajas, cuentas bancarias y categorias de
     gasto que todavia no la tengan.
  4. Crea el periodo contable del mes en curso si no existe (sin periodo
     abierto no se genera ningun asiento).

Uso:
    docker compose exec backend python manage.py cargar_plan_cuentas_base --simular
    docker compose exec backend python manage.py cargar_plan_cuentas_base
"""

from datetime import date
from calendar import monthrange

from django.core.management.base import BaseCommand
from django.db import transaction

# (codigo, nombre, tipo, permite_movimiento)
PLAN = [
    ("1",          "ACTIVO",                          "ACTIVO",     False),
    ("1.1",        "ACTIVO CORRIENTE",                "ACTIVO",     False),
    ("1.1.1",      "Caja y Bancos",                   "ACTIVO",     False),
    ("1.1.1.01",   "Caja General",                    "ACTIVO",     True),
    ("1.1.1.02",   "Bancos Moneda Nacional",          "ACTIVO",     True),
    ("1.1.1.03",   "Bancos Moneda Extranjera",        "ACTIVO",     True),
    ("1.1.2",      "Cuentas por Cobrar",              "ACTIVO",     False),
    ("1.1.2.01",   "Cuentas por Cobrar Comerciales",  "ACTIVO",     True),
    ("1.1.3",      "Anticipos Otorgados",             "ACTIVO",     False),
    ("1.1.3.01",   "Anticipos a Proveedores",         "ACTIVO",     True),
    ("1.1.4",      "Inventarios",                     "ACTIVO",     False),
    ("1.1.4.01",   "Inventario de Mineral",           "ACTIVO",     True),
    ("1.2",        "ACTIVO NO CORRIENTE",             "ACTIVO",     False),
    ("1.2.1",      "Activo Fijo",                     "ACTIVO",     False),
    ("1.2.1.01",   "Vehiculos",                       "ACTIVO",     True),
    ("1.2.1.02",   "Maquinaria y Equipo",             "ACTIVO",     True),
    ("1.2.1.03",   "Muebles y Enseres",               "ACTIVO",     True),
    ("1.2.2",      "Depreciacion Acumulada",          "ACTIVO",     False),
    ("1.2.2.01",   "Depreciacion Acumulada Activo Fijo", "ACTIVO",  True),

    ("2",          "PASIVO",                          "PASIVO",     False),
    ("2.1",        "PASIVO CORRIENTE",                "PASIVO",     False),
    ("2.1.1",      "Cuentas por Pagar",               "PASIVO",     False),
    ("2.1.1.01",   "Cuentas por Pagar Comerciales",   "PASIVO",     True),
    ("2.1.2",      "Impuestos por Pagar",             "PASIVO",     False),
    ("2.1.2.01",   "Impuestos por Pagar",             "PASIVO",     True),

    ("3",          "PATRIMONIO",                      "PATRIMONIO", False),
    ("3.1",        "Capital",                         "PATRIMONIO", False),
    ("3.1.01",     "Capital Social",                  "PATRIMONIO", True),
    ("3.2",        "Resultados",                      "PATRIMONIO", False),
    ("3.2.01",     "Resultados Acumulados",           "PATRIMONIO", True),
    ("3.2.02",     "Resultado del Ejercicio",         "PATRIMONIO", True),

    ("4",          "INGRESOS",                        "INGRESO",    False),
    ("4.1",        "Ingresos Operativos",             "INGRESO",    False),
    ("4.1.01",     "Ventas de Mineral",               "INGRESO",    True),
    ("4.1.02",     "Ventas de Exportacion",           "INGRESO",    True),
    ("4.2",        "Otros Ingresos",                  "INGRESO",    False),
    ("4.2.01",     "Ingresos Varios",                 "INGRESO",    True),

    ("5",          "GASTOS",                          "GASTO",      False),
    ("5.1",        "Costo de Ventas",                 "GASTO",      False),
    ("5.1.01",     "Costo de Mineral Vendido",        "GASTO",      True),
    ("5.2",        "Gastos Operativos",               "GASTO",      False),
    ("5.2.01",     "Combustible",                     "GASTO",      True),
    ("5.2.02",     "Transporte y Fletes",             "GASTO",      True),
    ("5.2.03",     "Mantenimiento de Vehiculos",      "GASTO",      True),
    ("5.2.04",     "Alimentacion",                    "GASTO",      True),
    ("5.2.05",     "Logistica",                       "GASTO",      True),
    ("5.2.06",     "Otros Gastos Operativos",         "GASTO",      True),
    ("5.3",        "Gastos Administrativos",          "GASTO",      False),
    ("5.3.01",     "Sueldos y Salarios",              "GASTO",      True),
    ("5.3.02",     "Servicios Basicos",               "GASTO",      True),
    ("5.3.03",     "Otros Gastos Administrativos",    "GASTO",      True),
    ("5.4",        "Gastos Financieros",              "GASTO",      False),
    ("5.4.01",     "Comisiones e Intereses Bancarios", "GASTO",     True),
    ("5.5",        "Otros Gastos",                    "GASTO",      False),
    ("5.5.01",     "Egresos Varios",                  "GASTO",      True),
    ("5.5.02",     "Depreciacion del Ejercicio",      "GASTO",      True),
]

# Mapeo de la Configuracion Contable
CONFIGURACION = {
    "inventario_mineral": "1.1.4.01",
    "cuentas_por_pagar": "2.1.1.01",
    "cuentas_por_cobrar": "1.1.2.01",
    "ventas": "4.1.01",
    "anticipos_proveedores": "1.1.3.01",
    "ingresos_varios": "4.2.01",
    "egresos_varios": "5.5.01",
}

# Categoria de gasto (por nombre, en minusculas) -> cuenta
CATEGORIAS = {
    "combustible": "5.2.01",
    "transporte": "5.2.02",
    "mantenimiento de vehiculos": "5.2.03",
    "alimentacion": "5.2.04",
    "logistica": "5.2.05",
    "gastos operativos": "5.2.06",
    "servicios": "5.3.02",
    "gastos administrativos": "5.3.03",
    "gastos financieros": "5.4.01",
}


class Command(BaseCommand):
    help = "Siembra un plan de cuentas inicial y configura la contabilidad automatica."

    def add_arguments(self, parser):
        parser.add_argument(
            "--simular",
            action="store_true",
            help="Muestra que haria, sin escribir nada.",
        )

    def handle(self, *args, **opciones):
        from contabilidad.models import (
            ConfiguracionContable,
            CuentaContable,
            PeriodoContable,
        )
        from gastos.models import CategoriaGasto
        from organizacion.models import Caja, CuentaBancaria

        simular = opciones["simular"]

        self.stdout.write(self.style.WARNING(
            "\nEste plan de cuentas es un PUNTO DE PARTIDA, no una plantilla "
            "normativa.\nRevise codigos y nombres con su contador antes de "
            "operar en serio.\n"
        ))

        if simular:
            self.stdout.write("--- SIMULACION: no se escribe nada ---\n")

        with transaction.atomic():
            # 1. Cuentas
            creadas = existentes = 0
            cuentas = {}
            for codigo, nombre, tipo, imputable in PLAN:
                cuenta = CuentaContable.objects.filter(codigo=codigo).first()
                if cuenta:
                    cuentas[codigo] = cuenta
                    existentes += 1
                    continue
                if simular:
                    self.stdout.write(f"  crearia  {codigo:<12} {nombre}")
                    creadas += 1
                    continue
                padre_codigo = codigo.rsplit(".", 1)[0] if "." in codigo else None
                cuenta = CuentaContable.objects.create(
                    codigo=codigo,
                    nombre=nombre,
                    tipo=tipo,
                    permite_movimiento=imputable,
                    cuenta_padre=cuentas.get(padre_codigo),
                )
                cuentas[codigo] = cuenta
                creadas += 1

            self.stdout.write(
                f"\nCuentas: {creadas} nueva(s), {existentes} ya existian."
            )

            if simular:
                self.stdout.write("\n--- fin de la simulacion ---")
                transaction.set_rollback(True)
                return

            # 2. Configuracion contable
            config = ConfiguracionContable.vigente()
            if config:
                self.stdout.write("Configuracion contable: ya existia, no se toca.")
            else:
                config = ConfiguracionContable(generar_asientos_automaticos=True)
                for campo, codigo in CONFIGURACION.items():
                    setattr(config, campo, cuentas.get(codigo))
                config.save()
                self.stdout.write(self.style.SUCCESS("Configuracion contable creada."))

            # 3. Cajas y cuentas bancarias
            n = 0
            for caja in Caja.objects.filter(cuenta_contable__isnull=True):
                caja.cuenta_contable = cuentas.get("1.1.1.01")
                caja.save(update_fields=["cuenta_contable"])
                n += 1
            for cb in CuentaBancaria.objects.filter(cuenta_contable__isnull=True):
                codigo = "1.1.1.02" if cb.moneda == "BOB" else "1.1.1.03"
                cb.cuenta_contable = cuentas.get(codigo)
                cb.save(update_fields=["cuenta_contable"])
                n += 1
            self.stdout.write(f"Cajas/bancos vinculados a su cuenta: {n}")

            # 4. Categorias de gasto
            n = 0
            for cat in CategoriaGasto.objects.filter(cuenta_contable__isnull=True):
                codigo = CATEGORIAS.get(cat.nombre.strip().lower())
                if not codigo:
                    continue
                cat.cuenta_contable = cuentas.get(codigo)
                cat.save(update_fields=["cuenta_contable"])
                n += 1
            self.stdout.write(f"Categorias de gasto vinculadas: {n}")

            sin_cuenta = CategoriaGasto.objects.filter(
                cuenta_contable__isnull=True
            ).count()
            if sin_cuenta:
                self.stdout.write(self.style.WARNING(
                    f"  {sin_cuenta} categoria(s) sin cuenta: asignelas a mano "
                    f"en el admin o sus gastos no generaran asiento."
                ))

            # 5. Periodo contable del mes en curso
            hoy = date.today()
            periodo = PeriodoContable.objects.filter(
                anio=hoy.year, mes=hoy.month
            ).first()
            if periodo:
                self.stdout.write(f"Periodo {periodo}: ya existia.")
            else:
                ultimo_dia = monthrange(hoy.year, hoy.month)[1]
                periodo = PeriodoContable.objects.create(
                    anio=hoy.year,
                    mes=hoy.month,
                    fecha_inicio=date(hoy.year, hoy.month, 1),
                    fecha_fin=date(hoy.year, hoy.month, ultimo_dia),
                    estado="ABIERTO",
                )
                self.stdout.write(self.style.SUCCESS(f"Periodo {periodo} creado."))

        self.stdout.write(self.style.SUCCESS(
            "\nListo. La contabilidad automatica ya puede generar asientos.\n"
            "Siguiente paso sugerido: registre un movimiento de caja y revise\n"
            "que aparezca su asiento en Contabilidad > Asientos Contables."
        ))
