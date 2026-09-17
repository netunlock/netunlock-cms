"""
PDF de la orden de trabajo: la hoja que baja al taller.

Es deliberadamente distinto del presupuesto. Acá no hay precios ni totales:
sólo lo que hace falta para fabricar la abertura —medidas de corte, paños de
vidrio, accesorios y barras a preparar— más un recuadro grande arriba con la
identificación, para que se lea de lejos apoyada en la mesa de corte.

Todo sale del ``snapshot_json`` congelado al emitir la orden, no de un cálculo
nuevo: la hoja que está en el taller no puede cambiar porque alguien tocó una
fórmula en la oficina.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from core import formato as F

from .esquemas import dibujo_de_abertura

AZUL = colors.HexColor("#1B3A57")
GRIS_FONDO = colors.HexColor("#F4F6F8")
GRIS_LINEA = colors.HexColor("#C7D0D8")
MARGEN = 14 * mm
ANCHO_UTIL = A4[0] - 2 * MARGEN

_BASE = getSampleStyleSheet()
EST = {
    "titulo": ParagraphStyle("ot_titulo", parent=_BASE["Normal"], fontName="Helvetica-Bold",
                             fontSize=20, textColor=colors.white, leading=23),
    "sub": ParagraphStyle("ot_sub", parent=_BASE["Normal"], fontName="Helvetica",
                          fontSize=9, textColor=colors.white, leading=12),
    "seccion": ParagraphStyle("ot_seccion", parent=_BASE["Normal"],
                              fontName="Helvetica-Bold", fontSize=11, textColor=AZUL,
                              spaceBefore=8, spaceAfter=4),
    "celda": ParagraphStyle("ot_celda", parent=_BASE["Normal"], fontName="Helvetica",
                            fontSize=9, leading=11),
    "celda_b": ParagraphStyle("ot_celda_b", parent=_BASE["Normal"],
                              fontName="Helvetica-Bold", fontSize=9, leading=11),
    "celda_c": ParagraphStyle("ot_celda_c", parent=_BASE["Normal"], fontName="Helvetica",
                              fontSize=9, leading=11, alignment=TA_CENTER),
    "grande": ParagraphStyle("ot_grande", parent=_BASE["Normal"],
                             fontName="Helvetica-Bold", fontSize=13, leading=16),
    "pie": ParagraphStyle("ot_pie", parent=_BASE["Normal"], fontName="Helvetica",
                          fontSize=7.5, textColor=colors.HexColor("#6B7A88")),
}


def _p(texto, estilo="celda"):
    return Paragraph(str(texto if texto is not None else ""), EST[estilo])


def _tabla(filas, anchos, alineaciones=None):
    t = Table(filas, colWidths=anchos, repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, GRIS_LINEA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS_FONDO]),
    ]
    if alineaciones:
        for col, alineacion in alineaciones.items():
            estilo.append(("ALIGN", (col, 1), (col, -1), alineacion))
    t.setStyle(TableStyle(estilo))
    return t


# ---------------------------------------------------------------------------
# Bloques
# ---------------------------------------------------------------------------

def _cabecera(orden, datos, emp):
    """Recuadro azul con el número de orden bien grande y la identificación."""
    izquierda = [
        _p(f"ORDEN DE TRABAJO {orden['numero']}", "titulo"),
        _p(f"{emp['razon_social'] or ''}", "sub"),
    ]
    abertura = datos.get("abertura", {})
    derecha = [
        _p(f"Cliente: {orden['cliente'] or '—'}", "sub"),
        _p(f"Obra: {orden['obra'] or '—'}", "sub"),
        _p(f"Presupuesto: {orden['presupuesto_numero'] or '—'}"
           f"  ·  Ítem {orden['item_orden']}", "sub"),
        _p(f"Emitida: {orden['fecha']}"
           + (f"  ·  Entrega: {orden['entrega']}" if orden["entrega"] else ""), "sub"),
    ]

    t = Table([[izquierda, derecha]], colWidths=[ANCHO_UTIL * 0.5, ANCHO_UTIL * 0.5])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), AZUL),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    return t


def _ficha(datos, orden, dibujo):
    """Qué hay que fabricar: dibujo + medidas, en letra grande."""
    a = datos.get("abertura", {})
    izquierda = [
        _p(a.get("tipologia_nombre") or a.get("tipologia_codigo", ""), "grande"),
        Spacer(1, 3),
        _p(f"<b>{a.get('ancho_mm', 0):.0f} x {a.get('alto_mm', 0):.0f} mm</b>"
           f"   ·   <b>{orden['cantidad']} unidad(es)</b>", "grande"),
        Spacer(1, 4),
        _p(f"Línea: {a.get('linea', '—')}   ·   Color: {a.get('color', '—')}"),
        _p(f"Hojas: {a.get('hojas', '—')}   ·   Vidrio: {a.get('vidrio', '—')}"),
        _p(f"Medida de hoja: {a.get('ancho_hoja_mm', 0):.0f} x "
           f"{a.get('alto_hoja_mm', 0):.0f} mm"),
        _p("Premarco: " + ("SÍ" if a.get("premarco") else "no")
           + "   ·   Mosquitero: " + ("SÍ" if a.get("mosquitero") else "no")),
    ]

    t = Table([[izquierda, dibujo]], colWidths=[ANCHO_UTIL - 62 * mm, 62 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (0, 0), "TOP"),
        ("VALIGN", (1, 0), (1, 0), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("BOX", (0, 0), (-1, -1), 0.6, GRIS_LINEA),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _tabla_cortes(datos, unidades: int):
    filas = [[_p(h, "celda_b") for h in
              ("Perfil", "Descripción", "Detalle", "Largo (mm)", "Piezas", "✓")]]
    for corte in datos.get("cortes", []):
        filas.append([
            _p(corte["perfil"], "celda_b"),
            _p(corte.get("descripcion", "")),
            _p(corte.get("detalle", "")),
            _p(F.milimetros_corte(corte["largo_mm"]), "celda_c"),
            _p(corte["cantidad"] * unidades, "celda_c"),
            _p("", "celda_c"),          # casillero para tildar en el taller
        ])
    return _tabla(filas, [22 * mm, 46 * mm, 46 * mm, 24 * mm, 16 * mm, 12 * mm],
                  {3: "CENTER", 4: "CENTER"})


def _tabla_barras(datos, unidades: int):
    filas = [[_p(h, "celda_b") for h in
              ("Perfil", "Largo de barra", "Barras a preparar")]]
    for barra in datos.get("barras", []):
        filas.append([
            _p(barra["perfil"], "celda_b"),
            _p(F.milimetros_corte(barra["largo_barra_mm"]), "celda_c"),
            _p(barra["barras"] * unidades, "celda_c"),
        ])
    return _tabla(filas, [40 * mm, 40 * mm, 40 * mm], {1: "CENTER", 2: "CENTER"})


def _tabla_vidrios(datos, unidades: int):
    filas = [[_p(h, "celda_b") for h in ("Tipo", "Medida del paño", "Paños", "✓")]]
    for pano in datos.get("vidrios", []):
        filas.append([
            _p(pano.get("tipo", "")),
            _p(f"{pano['ancho_mm']:.0f} x {pano['alto_mm']:.0f} mm", "celda_c"),
            _p(pano["cantidad"] * unidades, "celda_c"),
            _p("", "celda_c"),
        ])
    return _tabla(filas, [60 * mm, 45 * mm, 20 * mm, 12 * mm], {1: "CENTER", 2: "CENTER"})


def _tabla_accesorios(datos, unidades: int):
    filas = [[_p(h, "celda_b") for h in ("Código", "Descripción", "Cantidad", "✓")]]
    for acc in datos.get("accesorios", []):
        filas.append([
            _p(acc["codigo"], "celda_b"),
            _p(acc.get("descripcion", "")),
            _p(F.cantidad(acc["cantidad"] * unidades, acc.get("unidad", "u")), "celda_c"),
            _p("", "celda_c"),
        ])
    return _tabla(filas, [26 * mm, 76 * mm, 30 * mm, 12 * mm], {2: "CENTER"})


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def generar_ot(db, orden, destino: str | Path) -> Path:
    """Escribe el PDF de UNA orden de trabajo y devuelve la ruta."""
    from core.ordenes import snapshot

    datos = snapshot(orden)
    if not datos:
        raise ValueError(
            f"La orden {orden['numero']} no tiene despiece guardado. "
            "Volvé a emitirla desde el presupuesto.")

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    unidades = orden["cantidad"] or 1
    emp = db.empresa()

    doc = SimpleDocTemplate(
        str(destino), pagesize=A4,
        leftMargin=MARGEN, rightMargin=MARGEN, topMargin=MARGEN, bottomMargin=MARGEN,
        title=f"Orden de trabajo {orden['numero']}",
        author=emp["razon_social"] or "Cotizador de Aberturas")

    a = datos.get("abertura", {})
    dibujo = dibujo_de_abertura(db, a.get("tipologia_codigo", ""),
                                a.get("ancho_mm", 0), a.get("alto_mm", 0),
                                a.get("hojas", 2), ancho_max=150, alto_max=110)

    historia = [
        _cabecera(orden, datos, emp),
        Spacer(1, 8),
        _ficha(datos, orden, dibujo),
    ]

    if datos.get("cortes"):
        historia += [Paragraph("Corte de perfiles", EST["seccion"]),
                     _tabla_cortes(datos, unidades)]
    if datos.get("barras"):
        historia += [Paragraph("Barras a preparar", EST["seccion"]),
                     _tabla_barras(datos, unidades)]
    if datos.get("vidrios"):
        historia += [Paragraph("Vidrios", EST["seccion"]),
                     _tabla_vidrios(datos, unidades)]
    if datos.get("accesorios"):
        historia += [Paragraph(f"Accesorios — {datos.get('kit', '')}", EST["seccion"]),
                     _tabla_accesorios(datos, unidades)]

    if orden["notas"]:
        historia += [Paragraph("Observaciones", EST["seccion"]), _p(orden["notas"])]

    if datos.get("advertencias"):
        historia += [Paragraph("Avisos del despiece", EST["seccion"])]
        for aviso in datos["advertencias"]:
            historia.append(_p(f"⚠ {aviso}"))

    historia += [
        Spacer(1, 14),
        _tabla([[_p("Cortó", "celda_b"), _p("Armó", "celda_b"),
                 _p("Controló", "celda_b"), _p("Fecha", "celda_b")],
                [_p(""), _p(""), _p(""), _p("")]],
               [ANCHO_UTIL / 4] * 4),
        Spacer(1, 6),
        Paragraph(
            f"Emitida el {orden['fecha']} · Estado: {orden['estado']} · "
            f"Impresa el {date.today().isoformat()}", EST["pie"]),
    ]

    doc.build(historia)
    return destino


def generar_lote(db, ordenes, carpeta: str | Path) -> list[Path]:
    """Un PDF por orden. Devuelve las rutas generadas."""
    carpeta = Path(carpeta)
    return [generar_ot(db, orden, carpeta / f"{orden['numero']}.pdf")
            for orden in ordenes]
