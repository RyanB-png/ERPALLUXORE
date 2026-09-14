

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)

GRIS = colors.HexColor("#4a4a4a")
GRIS_CLARO = colors.HexColor("#ededed")


def _dinero(valor, moneda=""):
    if valor is None:
        return "-"
    return f"{valor:,.2f} {moneda}".strip()


def _tabla(datos, anchos, alinear_derecha_desde=1):
    tabla = Table(datos, colWidths=anchos, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GRIS),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (alinear_derecha_desde, 1), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS_CLARO]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tabla


def construir_pdf_liquidacion(liquidacion):
    """Devuelve los bytes del PDF. No lo guarda: de eso se encarga el modelo."""
    from organizacion.models import Empresa

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"Liquidacion {liquidacion.numero}",
    )

    estilos = getSampleStyleSheet()
    normal = estilos["Normal"]
    normal.fontSize = 8.5
    titulo = ParagraphStyle(
        "titulo", parent=estilos["Title"], fontSize=15, spaceAfter=2,
    )
    subtitulo = ParagraphStyle(
        "subtitulo", parent=estilos["Normal"], fontSize=9,
        textColor=GRIS, alignment=1, spaceAfter=10,
    )
    seccion = ParagraphStyle(
        "seccion", parent=estilos["Heading3"], fontSize=10,
        textColor=GRIS, spaceBefore=10, spaceAfter=4,
    )

    lote = liquidacion.lote
    moneda = liquidacion.moneda
    empresa = Empresa.objects.filter(is_active=True).first()

    story = []

    if empresa:
        story.append(Paragraph(empresa.razon_social, titulo))
        story.append(Paragraph(f"NIT {empresa.nit}", subtitulo))
    story.append(Paragraph("LIQUIDACIÓN DE COMPRA DE MINERAL", titulo))
    story.append(Paragraph(liquidacion.numero, subtitulo))

    # --- Datos generales -------------------------------------------------
    story.append(Paragraph("Datos del lote", seccion))
    story.append(_tabla([
        ["Lote", "Proveedor", "Recepción", "Peso neto (kg)"],
        [
            lote.codigo,
            str(lote.proveedor),
            lote.fecha_recepcion.strftime("%d/%m/%Y") if lote.fecha_recepcion else "-",
            f"{lote.peso_neto:,.2f}" if lote.peso_neto is not None else "-",
        ],
    ], [35 * mm, 65 * mm, 30 * mm, 44 * mm], alinear_derecha_desde=3))

    story.append(Paragraph("Datos de la liquidación", seccion))
    story.append(_tabla([
        ["Fecha", "Laboratorio", "Humedad", "P. húmedo (kg)", "P. seco (kg)"],
        [
            liquidacion.fecha.strftime("%d/%m/%Y") if liquidacion.fecha else "-",
            str(liquidacion.muestra.laboratorio),
            f"{liquidacion.humedad:,.2f} %",
            f"{liquidacion.peso_humedo:,.2f}",
            f"{liquidacion.peso_seco:,.2f}",
        ],
    ], [26 * mm, 58 * mm, 24 * mm, 33 * mm, 33 * mm], alinear_derecha_desde=2))

    # --- Elementos pagables ----------------------------------------------
    story.append(Paragraph("Contenido pagable", seccion))
    filas = [["Elemento", "Ley", "Contenido fino", "Cotización", "% pagable", f"Valor ({moneda})"]]
    for d in liquidacion.detalles.select_related("elemento"):
        filas.append([
            f"{d.elemento.simbolo} - {d.elemento.nombre}",
            f"{d.ley:,.4f}",
            f"{d.contenido_fino:,.6f}",
            f"{d.precio_unitario:,.4f}",
            f"{d.porcentaje_pagable:,.3f} %",
            f"{d.valor:,.2f}",
        ])
    if len(filas) == 1:
        filas.append(["Sin elementos registrados", "", "", "", "", ""])
    story.append(_tabla(filas, [48 * mm, 22 * mm, 30 * mm, 26 * mm, 24 * mm, 24 * mm]))

    # --- Deducciones ------------------------------------------------------
    deducciones = list(liquidacion.deducciones.select_related("concepto"))
    if deducciones:
        story.append(Paragraph("Deducciones", seccion))
        filas = [["Concepto", "Tipo", "Valor", f"Monto ({moneda})"]]
        for d in deducciones:
            filas.append([
                str(d.concepto),
                d.get_tipo_calculo_display(),
                f"{d.valor:,.4f}",
                f"{d.monto:,.2f}",
            ])
        story.append(_tabla(filas, [74 * mm, 40 * mm, 30 * mm, 30 * mm]))

    # --- Totales ----------------------------------------------------------
    story.append(Spacer(1, 8))
    totales = Table([
        ["Valor bruto", _dinero(liquidacion.valor_bruto, moneda)],
        ["Deducciones", f"- {_dinero(liquidacion.total_deducciones, moneda)}"],
        ["VALOR NETO A PAGAR", _dinero(liquidacion.valor_neto, moneda)],
    ], colWidths=[100 * mm, 74 * mm], hAlign="RIGHT")
    totales.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LINEABOVE", (0, 2), (-1, 2), 0.8, GRIS),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("FONTSIZE", (0, 2), (-1, 2), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(totales)

    # --- Firmas y pie -----------------------------------------------------
    story.append(Spacer(1, 26))
    firmas = Table([
        ["_______________________", "_______________________"],
        ["Proveedor", "Alluxore Metals S.R.L."],
    ], colWidths=[87 * mm, 87 * mm])
    firmas.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 1), (-1, 1), GRIS),
    ]))
    story.append(firmas)

    story.append(Spacer(1, 12))
    story.append(Paragraph(
        f"Documento generado por el sistema el "
        f"{liquidacion.updated_at.strftime('%d/%m/%Y %H:%M')} — estado: "
        f"{liquidacion.get_estado_display()}.",
        ParagraphStyle("pie", parent=normal, fontSize=7, textColor=GRIS, alignment=1),
    ))

    doc.build(story)
    return buffer.getvalue()