"""
Migracion de datos: corrige la unidad de ley de los metales preciosos.

El campo `unidad_ley` se agrego con default PORCENTAJE, que es correcto para
Zn y Pb pero no para Ag y Au, cuya ley se reporta en gramos por tonelada.
Sin esto, el calculo de liquidacion tratatia 150 g/t de plata como 150%.
"""

from django.db import migrations


def ajustar_unidades(apps, schema_editor):
    Elemento = apps.get_model("laboratorio", "Elemento")
    Elemento.objects.filter(simbolo__iexact="Ag").update(unidad_ley="GRAMO_TONELADA")
    Elemento.objects.filter(simbolo__iexact="Au").update(unidad_ley="GRAMO_TONELADA")


def revertir(apps, schema_editor):
    Elemento = apps.get_model("laboratorio", "Elemento")
    Elemento.objects.filter(simbolo__iexact="Ag").update(unidad_ley="PORCENTAJE")
    Elemento.objects.filter(simbolo__iexact="Au").update(unidad_ley="PORCENTAJE")


class Migration(migrations.Migration):

    dependencies = [
        ("laboratorio", "0003_elemento_unidad_ley"),
    ]

    operations = [
        migrations.RunPython(ajustar_unidades, revertir),
    ]
