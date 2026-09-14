"""
Migracion de datos: crea las categorias de gasto que lista la seccion 13
del esquema, para no tener que cargarlas a mano desde el admin.

Usa get_or_create, asi que es segura de correr mas de una vez (por ejemplo,
si se resetea la base de datos y se vuelve a migrar desde cero).
"""

from django.db import migrations

CATEGORIAS = [
    ("Gastos operativos", "Gastos ligados directamente a la operacion minera."),
    ("Gastos administrativos", "Gastos de oficina y administracion general."),
    ("Gastos financieros", "Intereses, comisiones bancarias y similares."),
    ("Combustible", "Diesel, gasolina y lubricantes."),
    ("Alimentacion", "Alimentacion de personal y viaticos."),
    ("Mantenimiento de vehiculos", "Reparaciones y mantenimiento de la flota."),
    ("Servicios", "Luz, agua, internet, telefonia y otros servicios."),
    ("Logistica", "Gastos de logistica y manipuleo."),
    ("Transporte", "Fletes y transporte de mineral o personal."),
]


def crear_categorias(apps, schema_editor):
    CategoriaGasto = apps.get_model("gastos", "CategoriaGasto")
    for nombre, descripcion in CATEGORIAS:
        CategoriaGasto.objects.get_or_create(
            nombre=nombre, defaults={"descripcion": descripcion},
        )


def eliminar_categorias(apps, schema_editor):
    CategoriaGasto = apps.get_model("gastos", "CategoriaGasto")
    CategoriaGasto.objects.filter(
        nombre__in=[n for n, _ in CATEGORIAS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("gastos", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(crear_categorias, eliminar_categorias),
    ]
