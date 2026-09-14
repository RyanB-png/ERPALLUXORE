from django.db import migrations


def crear_elementos(apps, schema_editor):
    Elemento = apps.get_model('laboratorio', 'Elemento')
    elementos = [
        ('Ag', 'Plata'),
        ('Pb', 'Plomo'),
        ('Zn', 'Zinc'),
    ]
    for simbolo, nombre in elementos:
        Elemento.objects.get_or_create(simbolo=simbolo, defaults={'nombre': nombre})


def eliminar_elementos(apps, schema_editor):
    Elemento = apps.get_model('laboratorio', 'Elemento')
    Elemento.objects.filter(simbolo__in=['Ag', 'Pb', 'Zn']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('laboratorio', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_elementos, eliminar_elementos),
    ]