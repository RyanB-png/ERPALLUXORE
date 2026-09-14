"""
Migracion de datos: tipos de documento que enumera la seccion 15 del esquema.
"""

from django.db import migrations

TIPOS = [
    ("FACTURA", "Factura", "Factura de compra o de venta."),
    ("RECIBO", "Recibo", "Recibo de pago o cobro."),
    ("CONTRATO", "Contrato", "Contrato comercial o de servicios."),
    ("NOTA_VENTA", "Nota de venta", "Nota de venta o remision."),
    ("COMPROBANTE", "Comprobante", "Comprobante contable o bancario."),
    ("LABORATORIO", "Resultado de laboratorio", "Certificado o reporte de ensaye."),
    ("IDENTIDAD", "Documento de identidad", "Carnet, NIT u otro documento del tercero."),
    ("EXPORTACION", "Documentacion de exportacion", "DUE, packing list, BL, certificados."),
    ("OTRO", "Otro", "Cualquier otro respaldo."),
]


def crear_tipos(apps, schema_editor):
    TipoDocumento = apps.get_model("documentos", "TipoDocumento")
    for codigo, nombre, descripcion in TIPOS:
        TipoDocumento.objects.get_or_create(
            codigo=codigo,
            defaults={"nombre": nombre, "descripcion": descripcion},
        )


def eliminar_tipos(apps, schema_editor):
    TipoDocumento = apps.get_model("documentos", "TipoDocumento")
    TipoDocumento.objects.filter(codigo__in=[c for c, _, _ in TIPOS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("documentos", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(crear_tipos, eliminar_tipos),
    ]
