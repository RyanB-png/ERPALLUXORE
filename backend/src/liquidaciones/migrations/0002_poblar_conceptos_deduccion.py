"""
Migracion de datos: conceptos de deduccion habituales en la liquidacion de
mineral. Son un catalogo editable — se pueden agregar o desactivar desde el
admin sin tocar codigo.
"""

from django.db import migrations

CONCEPTOS = [
    ("MAQUILA", "Maquila / Tratamiento", "Cargo por tratamiento del concentrado."),
    ("REFINACION", "Refinacion", "Cargo por refinacion del metal contenido."),
    ("FLETE", "Flete", "Transporte del mineral hasta el punto de entrega."),
    ("ANALISIS", "Analisis de laboratorio", "Costo de ensayes y control de calidad."),
    ("CASTIGO", "Castigo por impurezas", "Penalizacion por elementos penalizables."),
    ("MERMA", "Merma", "Descuento por perdida de peso en el proceso."),
    ("OTRO", "Otras deducciones", "Cualquier otro cargo pactado."),
]


def crear_conceptos(apps, schema_editor):
    ConceptoDeduccion = apps.get_model("liquidaciones", "ConceptoDeduccion")
    for codigo, nombre, descripcion in CONCEPTOS:
        ConceptoDeduccion.objects.get_or_create(
            codigo=codigo,
            defaults={"nombre": nombre, "descripcion": descripcion},
        )


def eliminar_conceptos(apps, schema_editor):
    ConceptoDeduccion = apps.get_model("liquidaciones", "ConceptoDeduccion")
    ConceptoDeduccion.objects.filter(
        codigo__in=[c for c, _, _ in CONCEPTOS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("liquidaciones", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(crear_conceptos, eliminar_conceptos),
    ]
