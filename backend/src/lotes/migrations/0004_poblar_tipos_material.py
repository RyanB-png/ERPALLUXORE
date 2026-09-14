from django.db import migrations


def crear_tipos_material(apps, schema_editor):
    TipoMaterial = apps.get_model('lotes', 'TipoMaterial')
    tipos = [
        ('ZN', 'Zinc'),
        ('PB', 'Plomo'),
        ('AG', 'Plata'),
        ('OTRO', 'Otro'),
    ]
    for codigo, nombre in tipos:
        TipoMaterial.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})


def eliminar_tipos_material(apps, schema_editor):
    TipoMaterial = apps.get_model('lotes', 'TipoMaterial')
    TipoMaterial.objects.filter(codigo__in=['ZN', 'PB', 'AG', 'OTRO']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('lotes', '0003_remove_lote_tipo_material_tipomaterial_and_more'),
    ]

    operations = [
        migrations.RunPython(crear_tipos_material, eliminar_tipos_material),
    ]