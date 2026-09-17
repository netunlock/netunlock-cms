"""
Papeles de taller: diagramas de corte y etiquetas de pieza.

Hasta acá el programa decía *cuántas* barras comprar. El que corta necesita otra
cosa: **de dónde sale cada pieza**. Un diagrama de corte dibuja cada barra con
sus piezas ubicadas y el recorte que sobra al final, que es como se trabaja
frente a la sierra.

Las etiquetas son el otro papel que falta: un rótulo por pieza con la obra, la
posición y la medida. Es lo que evita que se mezclen dos trabajos en el mismo
caballete, y lo que permite que alguien que no cortó la pieza sepa dónde va.

Los dos salen del mismo optimizador que usa el presupuesto, así que el taller y
la compra nunca dicen números distintos.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)
from reportlab.graphics.shapes import Drawing, Line, Rect, String

from core import formato as F
from core.despiece import barras_de_presupuesto, optimizar_conjunto

from . import marca_prueba

AZUL = colors.HexColor("#1B3A57")
GRIS_LINEA = colors.HexColor("#C7D0D8")
GRIS_FONDO = colors.HexColor("#F4F6F8")
PIEZA = colors.HexColor("#D8E6EE")
RECORTE = colors.HexColor("#F0D9D2")
#: Las etiquetas de vidrio van de otro color para separarlas de un vistazo
VIDRIO_FONDO = colors.HexColor("#DCEFE8")
VIDRIO_BORDE = colors.HexColor("#2F6B57")

MARGEN = 14 * mm
ANCHO_UTIL = A4[0] - 2 * MARGEN

_BASE = getSampleStyleSheet()
# OJO con el interlineado: el estilo Normal trae leading=12, así que una letra
# de 17 puntos sin leading propio se encima con el renglón siguiente. Cada
# estilo fija el suyo, holgado respecto del cuerpo.
EST = {
    "titulo": ParagraphStyle("t_titulo", parent=_BASE["Normal"],
                             fontName="Helvetica-Bold", fontSize=17, leading=21,
                             textColor=AZUL, spaceAfter=6),
    "sub": ParagraphStyle("t_sub", parent=_BASE["Normal"], fontName="Helvetica",
                          fontSize=9.5, leading=13, spaceAfter=2,
                          textColor=colors.HexColor("#48565F")),
    "perfil": ParagraphStyle("t_perfil", parent=_BASE["Normal"],
                             fontName="Helvetica-Bold", fontSize=11, leading=14,
                             textColor=AZUL, spaceBefore=12, spaceAfter=4),
    "celda": ParagraphStyle("t_celda", parent=_BASE["Normal"], fontName="Helvetica",
                            fontSize=8.5, leading=10),
    "celda_b": ParagraphStyle("t_celda_b", parent=_BASE["Normal"],
                              fontName="Helvetica-Bold", fontSize=8.5, leading=10),
    "pie": ParagraphStyle("t_pie", parent=_BASE["Normal"], fontName="Helvetica",
                          fontSize=7.5, leading=10,
                          textColor=colors.HexColor("#78868D")),
}


def _p(texto, estilo="celda"):
    return Paragraph(str(texto if texto is not None else ""), EST[estilo])


# ---------------------------------------------------------------------------
# Diagrama de una barra
# ---------------------------------------------------------------------------

def _dibujo_barra(cortes: list[float], largo_barra: int, ancho: float,
                  alto: float = 15) -> Drawing:
    """Una barra dibujada a escala, con sus cortes y el recorte final.

    La escala es la real: una pieza que ocupa media barra se ve ocupando media
    barra. Es lo que permite mirar la hoja y entender el aprovechamiento sin
    leer ningún número.
    """
    d = Drawing(ancho, alto)
    escala = ancho / max(1, largo_barra)

    d.add(Rect(0, 0, ancho, alto, fillColor=colors.white,
               strokeColor=AZUL, strokeWidth=0.8))

    x = 0.0
    for largo in cortes:
        w = largo * escala
        d.add(Rect(x, 0, w, alto, fillColor=PIEZA, strokeColor=AZUL, strokeWidth=0.5))
        # La medida sólo entra si la pieza es suficientemente ancha; si no, el
        # número se superpone con el de al lado y no se lee ninguno.
        if w > 26:
            d.add(String(x + w / 2, alto / 2 - 2.6, f"{largo:.0f}",
                         fontName="Helvetica", fontSize=6.5,
                         fillColor=AZUL, textAnchor="middle"))
        x += w

    if x < ancho - 1:
        d.add(Rect(x, 0, ancho - x, alto, fillColor=RECORTE,
                   strokeColor=GRIS_LINEA, strokeWidth=0.5))
        sobra = largo_barra - sum(cortes)
        if ancho - x > 30:
            d.add(String(x + (ancho - x) / 2, alto / 2 - 2.6, f"sobra {sobra:.0f}",
                         fontName="Helvetica-Oblique", fontSize=6.5,
                         fillColor=colors.HexColor("#A64B31"), textAnchor="middle"))
    return d


def _seccion_perfil(barras) -> list:
    """Todas las barras de un perfil, una debajo de otra."""
    partes = [Paragraph(
        f"{barras.perfil_codigo} &nbsp;&nbsp;<font size=9 color='#48565F'>"
        f"{barras.descripcion or ''} · barra de {barras.largo_barra_mm} mm · "
        f"{barras.cantidad} barra(s) · {F.porcentaje(barras.desperdicio_pct)} de recorte"
        f"</font>", EST["perfil"])]

    ancho_dibujo = ANCHO_UTIL - 24 * mm
    filas = []
    for i, cortes in enumerate(barras.barras, start=1):
        filas.append([
            _p(f"#{i}", "celda_b"),
            _dibujo_barra(cortes, barras.largo_barra_mm, ancho_dibujo),
        ])

    tabla = Table(filas, colWidths=[14 * mm, ancho_dibujo + 6])
    tabla.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (1, 0), (1, -1), 0),
    ]))
    partes.append(tabla)
    return partes


# ---------------------------------------------------------------------------
# Diagramas de corte
# ---------------------------------------------------------------------------

def _panos_de_presupuesto(pres) -> dict[tuple, dict]:
    """Paños de vidrio a cortar, agrupados por tipo y medida.

    Devuelve {(tipo, ancho, alto): {cantidad, posiciones}}.
    """
    panos: dict[tuple, dict] = {}
    for res in pres.resultados:
        for pano in res.despiece.vidrio.panos:
            clave = (res.despiece.vidrio.tipo, pano.ancho_mm, pano.alto_mm)
            reg = panos.setdefault(clave, {"cantidad": 0, "posiciones": []})
            reg["cantidad"] += pano.cantidad * res.item.cantidad
            reg["posiciones"].append(f"P{res.item.orden}")
    return panos


def _dibujo_plancha(plancha, ancho_dibujo: float) -> Drawing:
    """Una plancha con sus paños ubicados, a escala.

    Se dibuja tal como queda sobre la mesa: cada paño en su lugar, con su medida
    adentro si entra, y lo que sobra sin pintar. La escala es la real, así que
    el aprovechamiento se ve sin leer ningún número.
    """
    escala = ancho_dibujo / max(1.0, plancha.ancho)
    alto_dibujo = plancha.alto * escala
    d = Drawing(ancho_dibujo, alto_dibujo)

    d.add(Rect(0, 0, ancho_dibujo, alto_dibujo, fillColor=RECORTE,
               strokeColor=AZUL, strokeWidth=0.9))

    for pano in plancha.panos:
        w = pano.ancho * escala
        h = pano.alto * escala
        # El origen del dibujo está abajo y el del plan arriba: se invierte la
        # Y para que la hoja se lea como se apoya la plancha.
        y = alto_dibujo - (pano.y + pano.alto) * escala
        x = pano.x * escala
        d.add(Rect(x, y, w, h, fillColor=VIDRIO_FONDO,
                   strokeColor=VIDRIO_BORDE, strokeWidth=0.6))
        if w > 44 and h > 16:
            d.add(String(x + w / 2, y + h / 2 + 1,
                         f"{pano.ancho:.0f} × {pano.alto:.0f}",
                         fontName="Helvetica", fontSize=6.5,
                         fillColor=AZUL, textAnchor="middle"))
            # Se marca con "90°" y no con una flecha de giro: las fuentes base
            # del PDF no la tienen y en el papel sale un cuadradito negro.
            etiqueta = pano.posicion + ("  · 90°" if pano.rotado else "")
            if etiqueta and h > 26:
                d.add(String(x + w / 2, y + h / 2 - 7, etiqueta,
                             fontName="Helvetica-Oblique", fontSize=6,
                             fillColor=VIDRIO_BORDE, textAnchor="middle"))
    return d


def _seccion_planchas(db, pres) -> list:
    """Planos de corte de vidrio: qué sale de cada plancha."""
    from core.optimizar_vidrio import planes_de_presupuesto

    planes = [p for p in planes_de_presupuesto(db, pres) if p.planchas]
    if not planes:
        return []

    partes = [
        Paragraph("Corte de vidrio", EST["titulo"]),
        Paragraph(
            "El vidrio se corta con guillotina: cada raya atraviesa la plancha "
            "entera, así que los paños van en franjas. Los que dicen «90°» hay "
            "que cortarlos girados.", EST["sub"]),
        Spacer(1, 6),
    ]

    ancho_dibujo = ANCHO_UTIL - 26 * mm
    for plan in planes:
        partes.append(Paragraph(
            f"{plan.tipo} &nbsp;&nbsp;<font size=9 color='#48565F'>"
            f"{plan.cantidad} plancha(s) de "
            f"{plan.planchas[0].ancho:.0f} × {plan.planchas[0].alto:.0f} mm · "
            f"{F.superficie(plan.m2_compradas)} compradas · "
            f"{F.porcentaje(plan.aprovechamiento)} aprovechado</font>",
            EST["perfil"]))

        for i, plancha in enumerate(plan.planchas, start=1):
            bloque = [
                Paragraph(
                    f"<font size=8><b>Plancha #{i}</b> · {len(plancha.panos)} paño(s) · "
                    f"{F.porcentaje(plancha.aprovechamiento)} aprovechado</font>",
                    EST["celda"]),
                Spacer(1, 2),
                _dibujo_plancha(plancha, ancho_dibujo),
                Spacer(1, 8),
            ]
            partes.append(KeepTogether(bloque))

        if plan.sin_ubicar:
            partes.append(Paragraph(
                f"<font color='#A64B31'>⚠ {len(plan.sin_ubicar)} paño(s) no entran "
                "en la plancha ni girados: hay que pedirlos en medida especial.</font>",
                EST["sub"]))

    return partes


def _seccion_vidrios(pres) -> list:
    """Lista de medidas de vidrio, que es lo que se le pide a la vidriería."""
    panos = _panos_de_presupuesto(pres)
    if not panos:
        return []

    filas = [[_p(h, "celda_b") for h in
              ("Tipo de vidrio", "Medida del paño", "Paños", "Posiciones", "m²")]]
    total_m2 = 0.0
    for (tipo, ancho, alto), reg in sorted(panos.items()):
        m2 = ancho * alto / 1_000_000 * reg["cantidad"]
        total_m2 += m2
        filas.append([
            _p(tipo or "—"),
            _p(f"<b>{ancho:.0f} × {alto:.0f} mm</b>", "celda_b"),
            _p(reg["cantidad"], "celda_b"),
            _p(" ".join(sorted(set(reg["posiciones"])))),
            _p(F.superficie(m2)),
        ])
    filas.append([_p("TOTAL", "celda_b"), _p(""), _p(""), _p(""),
                  _p(F.superficie(total_m2), "celda_b")])

    t = Table(filas, colWidths=[54 * mm, 40 * mm, 18 * mm, 34 * mm, 26 * mm],
              repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, GRIS_LINEA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, GRIS_FONDO]),
        ("BACKGROUND", (0, -1), (-1, -1), GRIS_FONDO),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    return [
        Paragraph("Vidrios a cortar", EST["perfil"]),
        Paragraph("Medidas del paño terminado. El plano de cada plancha va al final.",
                  EST["sub"]),
        Spacer(1, 4),
        t,
    ]


def generar_diagramas(db, pres, destino: str | Path) -> Path:
    """PDF con el diagrama de corte de todas las barras del presupuesto."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    emp = db.empresa()

    doc = SimpleDocTemplate(
        str(destino), pagesize=A4, leftMargin=MARGEN, rightMargin=MARGEN,
        topMargin=MARGEN, bottomMargin=MARGEN,
        title=f"Diagramas de corte {pres.numero}",
        author=emp["razon_social"] or "Cotizador de Aberturas")

    barras = barras_de_presupuesto(pres.resultados)
    total = sum(b.cantidad for b in barras)
    metros = sum(b.metros_comprados for b in barras)
    recorte = sum(b.recorte_mm for b in barras) / 1000.0

    historia = [
        Paragraph("Diagramas de corte", EST["titulo"]),
        Paragraph(
            f"Presupuesto {pres.numero} · {pres.cliente.razon_social or '—'}"
            + (f" · {pres.cliente.obra}" if pres.cliente.obra else ""), EST["sub"]),
        Paragraph(
            f"{total} barra(s) en {len(barras)} perfil(es) · "
            f"{F.metros(metros)} comprados · {F.metros(recorte)} de recorte",
            EST["sub"]),
        Spacer(1, 4),
        Paragraph(
            "Cada barra está dibujada a escala. Las piezas van en el orden en que "
            "conviene cortarlas, de mayor a menor, y lo pintado al final es lo que "
            "sobra.", EST["sub"]),
        Spacer(1, 8),
    ]

    for b in barras:
        # KeepTogether: un perfil no se parte entre dos hojas, porque la hoja se
        # apoya en la sierra y hay que verlo entero.
        historia.append(KeepTogether(_seccion_perfil(b)))

    vidrios = _seccion_vidrios(pres)
    if vidrios:
        historia.append(Spacer(1, 10))
        historia.extend(vidrios)

    planchas = _seccion_planchas(db, pres)
    if planchas:
        historia.append(PageBreak())
        historia.extend(planchas)

    historia += [
        Spacer(1, 12),
        Paragraph(f"Generado el {date.today().isoformat()}", EST["pie"]),
    ]
    doc.build(historia, canvasmaker=marca_prueba.lienzo())
    return destino


# ---------------------------------------------------------------------------
# Etiquetas
# ---------------------------------------------------------------------------

#: Grilla de etiquetas por hoja A4. Entran cómodas y se cortan con guillotina.
ETIQUETAS_COLUMNAS = 3
ETIQUETAS_FILAS = 8


def _etiqueta(datos: dict) -> Table:
    """Un rótulo: obra, posición, artículo, medida y un casillero para tildar.

    El vidrio lleva la cabecera pintada distinto: en la mesa se separan las
    etiquetas de aluminio de las de vidrio a simple vista, sin leerlas.
    """
    ancho = (ANCHO_UTIL - 8) / ETIQUETAS_COLUMNAS
    es_vidrio = datos.get("clase") == "vidrio"

    filas = [
        [_p(f"<b>{datos['perfil']}</b>", "celda_b"), _p(datos["posicion"], "celda_b")],
        [_p(datos["detalle"][:46], "celda"), _p("")],
        [_p(f"<b><font size=13>{datos['largo']}</font></b>", "celda_b"),
         _p(f"×{datos['cantidad']}", "celda_b")],
        [_p(f"<font size=7>{datos['obra'][:34]}</font>", "celda"),
         _p("<font size=7>☐</font>", "celda")],
    ]
    t = Table(filas, colWidths=[ancho * 0.72, ancho * 0.28],
              rowHeights=[10, 10, 16, 9])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.7, VIDRIO_BORDE if es_vidrio else AZUL),
        ("BACKGROUND", (0, 0), (-1, 0), VIDRIO_FONDO if es_vidrio else GRIS_FONDO),
        ("LINEBELOW", (0, 0), (-1, 0), 0.4, GRIS_LINEA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    return t


def _etiquetas_de_presupuesto(db, pres) -> list[dict]:
    """Una etiqueta por pieza de corte y por paño de vidrio, con su posición."""
    salida = []
    obra = pres.cliente.obra or pres.cliente.razon_social or pres.numero
    for res in pres.resultados:
        it = res.item
        posicion = f"P{it.orden}"
        for pieza in res.despiece.aluminio.piezas:
            salida.append({
                "clase": "perfil",
                "perfil": pieza.perfil_codigo,
                "posicion": posicion,
                "detalle": pieza.funcion_legible,
                "largo": F.milimetros_corte(pieza.largo_mm),
                "cantidad": pieza.cantidad * it.cantidad,
                "obra": obra,
            })
        # El vidrio también se rotula: llega de la vidriería sin identificar y
        # hay que saber a qué abertura va cada paño antes de armar.
        for pano in res.despiece.vidrio.panos:
            salida.append({
                "clase": "vidrio",
                "perfil": "VIDRIO",
                "posicion": posicion,
                "detalle": pano.descripcion or res.despiece.vidrio.tipo,
                "largo": f"{pano.ancho_mm:.0f} × {pano.alto_mm:.0f}",
                "cantidad": pano.cantidad * it.cantidad,
                "obra": obra,
            })
    return salida


def generar_etiquetas(db, pres, destino: str | Path) -> Path:
    """PDF de rótulos para pegar en las piezas cortadas."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    emp = db.empresa()

    doc = SimpleDocTemplate(
        str(destino), pagesize=A4, leftMargin=MARGEN, rightMargin=MARGEN,
        topMargin=MARGEN, bottomMargin=MARGEN,
        title=f"Etiquetas {pres.numero}",
        author=emp["razon_social"] or "Cotizador de Aberturas")

    etiquetas = _etiquetas_de_presupuesto(db, pres)
    de_vidrio = sum(1 for e in etiquetas if e.get("clase") == "vidrio")
    historia = [
        Paragraph("Etiquetas de corte", EST["titulo"]),
        Paragraph(f"Presupuesto {pres.numero} · {len(etiquetas)} rótulo(s): "
                  f"{len(etiquetas) - de_vidrio} de perfil y {de_vidrio} de vidrio "
                  "(en verde)", EST["sub"]),
        Spacer(1, 8),
    ]

    ancho = (ANCHO_UTIL - 8) / ETIQUETAS_COLUMNAS
    fila: list = []
    grilla: list = []
    for datos in etiquetas:
        fila.append(_etiqueta(datos))
        if len(fila) == ETIQUETAS_COLUMNAS:
            grilla.append(fila)
            fila = []
    if fila:
        # La última fila se completa con celdas vacías: si no, la tabla queda
        # con menos columnas y ReportLab la estira.
        fila += [""] * (ETIQUETAS_COLUMNAS - len(fila))
        grilla.append(fila)

    if grilla:
        t = Table(grilla, colWidths=[ancho + 4] * ETIQUETAS_COLUMNAS)
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        historia.append(t)

    doc.build(historia, canvasmaker=marca_prueba.lienzo())
    return destino


# ---------------------------------------------------------------------------
# Listas por rubro
# ---------------------------------------------------------------------------

def _tabla_simple(cabeceras, filas, anchos):
    datos = [[_p(h, "celda_b") for h in cabeceras]] + filas
    t = Table(datos, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, GRIS_LINEA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS_FONDO]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def generar_listas(db, pres, destino: str | Path) -> Path:
    """Un PDF con una lista por rubro: perfiles, vidrios y accesorios.

    Van separadas porque cada una se le manda a un proveedor distinto. Junto
    todo en una sola hoja, el vidriero tiene que buscar sus renglones entre los
    perfiles.
    """
    from core.calculo import resumen_materiales

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    emp = db.empresa()
    materiales = resumen_materiales(pres)

    doc = SimpleDocTemplate(
        str(destino), pagesize=A4, leftMargin=MARGEN, rightMargin=MARGEN,
        topMargin=MARGEN, bottomMargin=MARGEN,
        title=f"Listas de materiales {pres.numero}",
        author=emp["razon_social"] or "Cotizador de Aberturas")

    cabecera = [
        Paragraph("Materiales por rubro", EST["titulo"]),
        Paragraph(f"Presupuesto {pres.numero} · {pres.cliente.razon_social or '—'}"
                  + (f" · {pres.cliente.obra}" if pres.cliente.obra else ""),
                  EST["sub"]),
        Spacer(1, 10),
    ]

    # -- perfiles: lo que se le pide al extrusor son BARRAS
    barras = barras_de_presupuesto(pres.resultados)
    filas = [[_p(b.perfil_codigo, "celda_b"), _p(b.descripcion or ""),
              _p(F.milimetros_corte(b.largo_barra_mm)), _p(F.unidades(b.cantidad)),
              _p(F.kilos(b.peso_comprado_kg))] for b in barras]
    cabecera += [
        Paragraph("Perfiles — pedido al extrusor", EST["perfil"]),
        _tabla_simple(["Perfil", "Descripción", "Largo de barra", "Barras", "Peso"],
                      filas, [24 * mm, 74 * mm, 28 * mm, 20 * mm, 26 * mm]),
    ]

    # -- vidrios: lo que se le pide a la vidriería son MEDIDAS
    medidas: dict[tuple, int] = {}
    for res in pres.resultados:
        for pano in res.despiece.vidrio.panos:
            clave = (res.despiece.vidrio.tipo, pano.ancho_mm, pano.alto_mm)
            medidas[clave] = medidas.get(clave, 0) + pano.cantidad * res.item.cantidad
    filas = [[_p(tipo), _p(f"{a:.0f} × {h:.0f} mm"), _p(F.unidades(n)),
              _p(F.superficie(a * h / 1_000_000 * n))]
             for (tipo, a, h), n in sorted(medidas.items())]
    cabecera += [
        Paragraph("Vidrios — pedido a la vidriería", EST["perfil"]),
        _tabla_simple(["Tipo", "Medida del paño", "Paños", "m²"],
                      filas, [70 * mm, 46 * mm, 24 * mm, 32 * mm]),
    ]

    # -- accesorios
    filas = [[_p(a["codigo"], "celda_b"), _p(a["descripcion"]),
              _p(F.cantidad(a["cantidad"], a["unidad"]))]
             for a in materiales["accesorios"]]
    cabecera += [
        Paragraph("Accesorios y herrajes", EST["perfil"]),
        _tabla_simple(["Código", "Descripción", "Cantidad"],
                      filas, [26 * mm, 110 * mm, 36 * mm]),
        Spacer(1, 12),
        Paragraph(f"Generado el {date.today().isoformat()}", EST["pie"]),
    ]

    doc.build(cabecera, canvasmaker=marca_prueba.lienzo())
    return destino


def diagramas_de_orden(db, orden, destino: str | Path) -> Path:
    """Diagrama de corte de una sola orden de trabajo, desde su despiece congelado."""
    from core.models import PiezaCorte
    from core.ordenes import snapshot

    datos = snapshot(orden)
    if not datos.get("cortes"):
        raise ValueError(f"La orden {orden['numero']} no tiene despiece guardado.")

    # Se reconstruyen las piezas del snapshot para pasarlas por el mismo
    # optimizador: la OT no vuelve a calcular nada, sólo dibuja lo que congeló.
    piezas = [PiezaCorte(
        perfil_codigo=c["perfil"], descripcion=c.get("descripcion", ""),
        funcion=c.get("funcion", "OTRO"), largo_mm=c["largo_mm"],
        cantidad=c["cantidad"], peso_kg_m=c.get("peso_kg_m", 0.0),
        largo_barra_mm=int(c.get("largo_barra_mm", 6000) or 6000),
        nota=c.get("detalle", "")) for c in datos["cortes"]]

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(destino), pagesize=A4, leftMargin=MARGEN, rightMargin=MARGEN,
        topMargin=MARGEN, bottomMargin=MARGEN,
        title=f"Corte {orden['numero']}")

    abertura = datos.get("abertura", {})
    historia = [
        Paragraph(f"Corte — {orden['numero']}", EST["titulo"]),
        Paragraph(f"{orden['descripcion']} · {orden['cantidad']} unidad(es)"
                  + (f" · {orden['obra']}" if orden["obra"] else ""), EST["sub"]),
        Paragraph(f"Línea {abertura.get('linea', '—')} · "
                  f"Color {abertura.get('color', '—')}", EST["sub"]),
        Spacer(1, 8),
    ]
    for b in optimizar_conjunto([(piezas, orden["cantidad"] or 1)]):
        historia.append(KeepTogether(_seccion_perfil(b)))

    historia += [Spacer(1, 12),
                 Paragraph(f"Impreso el {date.today().isoformat()}", EST["pie"])]
    doc.build(historia, canvasmaker=marca_prueba.lienzo())
    return destino
