"""
Genera los asientos de operaciones que no lo tienen.

Sirve para dos casos:
  - Operaciones registradas ANTES de configurar el plan de cuentas.
  - Operaciones cuyo asiento no se genero porque el periodo estaba cerrado
    o faltaba alguna cuenta, y ahora ya se corrigio.

Uso:
    docker compose exec backend python manage.py generar_asientos_faltantes
    docker compose exec backend python manage.py generar_asientos_faltantes --simular
    docker compose exec backend python manage.py generar_asientos_faltantes --modelo compras.Compra
"""

from django.apps import apps as django_apps
from django.core.management.base import BaseCommand

from contabilidad.servicios import GENERADORES, asiento_existente, generar_asiento


class Command(BaseCommand):
    help = "Genera los asientos contables de operaciones que aun no tienen uno."

    def add_arguments(self, parser):
        parser.add_argument(
            "--simular",
            action="store_true",
            help="Muestra que se generaria, sin escribir nada.",
        )
        parser.add_argument(
            "--modelo",
            type=str,
            default=None,
            help="Procesar solo un modelo, ej. compras.Compra",
        )

    def handle(self, *args, **opciones):
        simular = opciones["simular"]
        solo = opciones["modelo"]

        claves = [solo] if solo else list(GENERADORES)
        desconocidas = [c for c in claves if c not in GENERADORES]
        if desconocidas:
            self.stderr.write(
                self.style.ERROR(
                    f"Modelo no soportado: {', '.join(desconocidas)}. "
                    f"Disponibles: {', '.join(GENERADORES)}"
                )
            )
            return

        total_generados = 0
        total_sin_poder = 0

        for clave in claves:
            app_label, nombre_modelo = clave.split(".")
            Modelo = django_apps.get_model(app_label, nombre_modelo)

            pendientes = [
                obj for obj in Modelo.objects.all() if asiento_existente(obj) is None
            ]

            if not pendientes:
                self.stdout.write(f"{clave}: sin pendientes.")
                continue

            self.stdout.write(
                self.style.WARNING(f"{clave}: {len(pendientes)} sin asiento.")
            )

            if simular:
                for obj in pendientes:
                    self.stdout.write(f"    [simulado] {obj}")
                continue

            for obj in pendientes:
                asiento = generar_asiento(obj)
                if asiento:
                    total_generados += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"    {asiento.numero}  <-  {obj}")
                    )
                else:
                    total_sin_poder += 1
                    self.stdout.write(
                        self.style.ERROR(f"    sin generar  <-  {obj}")
                    )

        if simular:
            self.stdout.write("\nSimulacion: no se escribio nada.")
            return

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Asientos generados: {total_generados}"))
        if total_sin_poder:
            self.stdout.write(
                self.style.ERROR(
                    f"No se pudieron generar: {total_sin_poder}. "
                    f"Causas habituales: falta la cuenta contable de la caja, del "
                    f"banco o de la categoria de gasto; falta una cuenta en la "
                    f"Configuracion Contable; o no existe el periodo contable de "
                    f"esa fecha (o esta cerrado)."
                )
            )
