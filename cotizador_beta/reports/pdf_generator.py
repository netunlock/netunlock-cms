"""
Generación del presupuesto en PDF (ReportLab / Platypus).

Estructura del documento:
    1. Encabezado: logo + datos del emisor + recuadro con N° de presupuesto
    2. Datos del cliente y de la obra
    3. Detalle ítem por ítem, con esquema, descripción técnica y observaciones
    4. Cuadro de Observaciones Generales
    5. Resumen económico desglosado
    6. Términos y condiciones + firmas
    7. (Opcional) Anexo de despiece y consolidado de materiales
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.calculo import resumen_materiales
from core import formato as F
from .esquemas import dibujo_de_abertura, esquema
from . import marca_prueba

# --- Paleta -----------------------------------------------------------------
AZUL = colors.HexColor("#1B3A57")
AZUL_CLARO = colors.HexColor("#E7EEF4")
GRIS = colors.HexColor("#6B7A88")
GRIS_LINEA = colors.HexColor("#C7D0D8")
GRIS_FONDO = colors.HexColor("#F4F6F8")

MARGEN = 16 * mm
ANCHO_UTIL = A4[0] - 2 * MARGEN


# --- Estilos ----------------------------------------------------------------

def _estilos():
    base = getSampleStyleSheet()
    e = {
        "titulo": ParagraphStyle("titulo", parent=base["Normal"], fontName="Helvetica-Bold",
                                 fontSize=15, textColor=AZUL, leading=18),
        "empresa": ParagraphStyle("empresa", parent=base["Normal"], fontName="Helvetica",
                                  fontSize=7.5, textColor=GRIS, leading=10),
        "seccion": ParagraphStyle("seccion", parent=base["Normal"], fontName="Helvetica-Bold",
                                  fontSize=9, textColor=colors.white, leading=12),
        "celda": ParagraphStyle("celda", parent=base["Normal"], fontName="Helvetica",
                                fontSize=7.5, leading=9.5),
        "celda_b": ParagraphStyle("celda_b", parent=base["Normal"], fontName="Helvetica-Bold",
                                  fontSize=7.5, leading=9.5),
        "celda_der": ParagraphStyle("celda_der", parent=base["Normal"], fontName="Helvetica",
                                    fontSize=7.5, leading=9.5, alignment=TA_RIGHT),
        "item_titulo": ParagraphStyle("item_titulo", parent=base["Normal"],
                                      fontName="Helvetica-Bold", fontSize=8, leading=10),
        "item_detalle": ParagraphStyle("item_detalle", parent=base["Normal"], fontName="Helvetica",
                                       fontSize=7, textColor=GRIS, leading=9),
        "obs": ParagraphStyle("obs", parent=base["Normal"], fontName="Helvetica-Oblique",
                              fontSize=7, textColor=colors.HexColor("#7A5C1E"), leading=9),
        "obs_gral": ParagraphStyle("obs_gral", parent=base["Normal"], fontName="Helvetica",
                                   fontSize=8, leading=11, alignment=TA_LEFT),
        "nota": ParagraphStyle("nota", parent=base["Normal"], fontName="Helvetica", fontSize=6.5,
                               textColor=GRIS, leading=8.5),
        "firma": ParagraphStyle("firma", parent=base["Normal"], fontName="Helvetica", fontSize=7.5,
                                textColor=GRIS, alignment=TA_CENTER, leading=10),
    }
    return e


EST = _estilos()


def _p(texto, estilo="celda"):
    return Paragraph(str(texto or "").replace("\n", "<br/>"), EST[estilo])


def _banda(titulo: str) -> Table:
    t = Table([[Paragraph(titulo, EST["seccion"])]], colWidths=[ANCHO_UTIL])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), AZUL),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


# --- Encabezado / pie -------------------------------------------------------

def _encabezado(emp, pres) -> Table:
    bloque_emisor = []
    logo_path = Path(emp["logo_path"] or "")
    if logo_path.exists() and logo_path.is_file():
        try:
            bloque_emisor.append(Image(str(logo_path), width=38 * mm, height=18 * mm,
                                       kind="proportional"))
        except Exception:  # logo ilegible: se sigue sin él
            pass

    datos = [emp["razon_social"] or "—"]
    if emp["cuit"]:
        datos.append(f"CUIT: {emp['cuit']}")
    if emp["direccion"]:
        datos.append(emp["direccion"])
    contacto = " · ".join(x for x in (emp["telefono"], emp["email"], emp["web"]) if x)
    if contacto:
        datos.append(contacto)

    izquierda = [Paragraph(f"<b>{emp['razon_social'] or 'Carpintería de Aluminio'}</b>",
                           EST["item_titulo"]),
                 Paragraph("<br/>".join(datos[1:]), EST["empresa"])]
    if bloque_emisor:
        izquierda = bloque_emisor + izquierda

    vence = pres.fecha + timedelta(days=pres.validez_dias or 0)
    caja = Table(
        [[Paragraph("PRESUPUESTO", EST["seccion"])],
         [Paragraph(f"<b>N°</b> {pres.numero}", EST["celda"])],
         [Paragraph(f"<b>Fecha:</b> {pres.fecha.strftime('%d/%m/%Y')}", EST["celda"])],
         [Paragraph(f"<b>Válido hasta:</b> {vence.strftime('%d/%m/%Y')}", EST["celda"])]],
        colWidths=[52 * mm],
    )
    caja.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), AZUL),
        ("BACKGROUND", (0, 1), (0, -1), AZUL_CLARO),
        ("BOX", (0, 0), (-1, -1), 0.6, AZUL),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    t = Table([[izquierda, caja]], colWidths=[ANCHO_UTIL - 52 * mm, 52 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
    ]))
    return t


def _pie(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(GRIS_LINEA)
    canvas.setLineWidth(0.4)
    canvas.line(MARGEN, 12 * mm, A4[0] - MARGEN, 12 * mm)
    canvas.setFont("Helvetica", 6.5)
    canvas.setFillColor(GRIS)
    canvas.drawString(MARGEN, 8.5 * mm, doc.pie_texto)
    canvas.drawRightString(A4[0] - MARGEN, 8.5 * mm, f"Página {canvas.getPageNumber()}")
    canvas.restoreState()


# --- Bloques ----------------------------------------------------------------

def _bloque_cliente(pres) -> Table:
    c = pres.cliente
    filas = [
        [_p("Cliente / Razón Social", "celda_b"), _p(c.razon_social or "—"),
         _p("DNI / CUIT", "celda_b"), _p(c.documento or "—")],
        [_p("Contacto", "celda_b"), _p(c.contacto or "—"),
         _p("Localidad", "celda_b"), _p(c.localidad or "—")],
        [_p("Obra / Dirección", "celda_b"), _p(c.obra or "—"),
         _p("Forma de pago", "celda_b"), _p(c.forma_pago or "—")],
    ]
    anchos = [32 * mm, ANCHO_UTIL / 2 - 32 * mm, 28 * mm, ANCHO_UTIL / 2 - 28 * mm]
    t = Table(filas, colWidths=anchos)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), GRIS_FONDO),
        ("BACKGROUND", (2, 0), (2, -1), GRIS_FONDO),
        ("GRID", (0, 0), (-1, -1), 0.4, GRIS_LINEA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _detalle_tecnico(db, res) -> list:
    it = res.item
    partes = [Paragraph(f"{it.tipologia_nombre or it.tipologia_codigo}", EST["item_titulo"])]

    detalle = [f"Línea {it.linea_nombre} · Color {it.color or 's/d'}"]
    if it.vidrio_nombre:
        detalle.append(f"Vidrio: {it.vidrio_nombre}")
    detalle.append(f"Hojas: {it.hojas}")

    opcionales = []
    opcionales.append("Con premarco" if it.incluye_premarco else "Sin premarco")
    if db.tipologia(it.tipologia_codigo) and db.tipologia(it.tipologia_codigo)["admite_mosquitero"]:
        opcionales.append("Con mosquitero" if it.incluye_mosquitero else "Sin mosquitero")
    detalle.append(" · ".join(opcionales))

    # El consumo de material es información de taller: le dice al cliente final
    # cuánto aluminio y vidrio lleva la abertura, que es justo el dato con el que
    # puede ir a pedir el mismo trabajo a otro lado. Por eso viene apagado y se
    # enciende desde Costos operativos.
    d = res.despiece
    if d.aluminio.peso_total_kg and db.parametro_int("mostrar_consumo_pdf", 0):
        detalle.append(
            f"Aluminio: {F.kilos(d.aluminio.peso_total_kg)}  ·  "
            f"Vidrio: {F.superficie(d.vidrio.m2_total)}"
        )
    partes.append(Paragraph("<br/>".join(detalle), EST["item_detalle"]))
    return partes




def _tabla_items(db, pres) -> Table:
    anchos = [12 * mm, 30 * mm, 58 * mm, 21 * mm, 10 * mm, 22 * mm, 12 * mm, 23 * mm]
    ancho_total = sum(anchos)
    # Ajuste fino para ocupar exactamente el ancho útil
    anchos[2] += ANCHO_UTIL - ancho_total

    encabezado = ["Ít.", "Esquema", "Descripción técnica", "Medidas", "Cant.",
                  "P. Unitario", "Bonif.", "Importe"]
    filas = [[Paragraph(f"<b>{h}</b>", EST["celda"]) for h in encabezado]]
    estilos = [
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, GRIS_LINEA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (4, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]

    r = 1
    for res in pres.resultados:
        it = res.item
        tip = db.tipologia(it.tipologia_codigo)
        dibujo = dibujo_de_abertura(db, it.tipologia_codigo, it.ancho_mm, it.alto_mm,
                                    it.hojas, ancho_max=anchos[1] - 4, alto_max=52)

        filas.append([
            _p(it.orden, "celda_b"),
            dibujo,
            _detalle_tecnico(db, res),
            _p(it.medida_texto),
            _p(F.unidades(it.cantidad)),
            _p(F.moneda(res.precio_unitario), "celda_der"),
            _p(F.porcentaje(it.descuento_pct) if it.descuento_pct else "—", "celda_der"),
            _p(F.moneda(res.neto), "celda_der"),
        ])
        estilos.append(("BACKGROUND", (0, r), (-1, r),
                        colors.white if r % 2 else GRIS_FONDO))
        r += 1

        if it.observaciones.strip():
            filas.append(["", "", Paragraph(f"<b>Observaciones:</b> {it.observaciones}", EST["obs"]),
                          "", "", "", "", ""])
            estilos.append(("SPAN", (2, r), (7, r)))
            estilos.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#FFF8E7")))
            estilos.append(("TOPPADDING", (0, r), (-1, r), 1))
            r += 1

    t = Table(filas, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle(estilos))
    return t


def _bloque_observaciones(pres) -> list:
    texto = (pres.observaciones_generales or "").strip()
    if not texto:
        return []
    cuerpo = Table([[_p(texto, "obs_gral")]], colWidths=[ANCHO_UTIL])
    cuerpo.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, GRIS_LINEA),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FCFCF7")),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return [_banda("OBSERVACIONES GENERALES"), Spacer(1, 2), cuerpo, Spacer(1, 8)]


def _bloque_totales(pres) -> Table:
    r = pres.resumen
    filas = [("Subtotal ítems", r.subtotal_items_bruto, False)]
    if r.descuentos_items:
        filas.append(("Descuentos por ítem", -r.descuentos_items, False))
        filas.append(("Subtotal ítems neto", r.subtotal_items, False))
    if r.mano_obra:
        mo = pres.mano_obra
        filas.append((
            f"Mano de obra ({F.horas(mo.horas)} × {F.operarios(mo.operarios)} × "
            f"{F.moneda(mo.valor_hora)})",
            r.mano_obra, False))
    if r.logistica:
        filas.append(("Logística (flete + colocación)", r.logistica, False))
    filas.append(("Subtotal general", r.subtotal_general, True))
    if r.descuento_global:
        etiqueta = (f"Descuento global ({F.porcentaje(pres.descuento_global_valor, 1)})"
                    if pres.descuento_global_tipo == "porcentaje" else "Descuento global")
        filas.append((etiqueta, -r.descuento_global, False))
        filas.append(("Neto", r.neto, False))
    if pres.aplica_iva:
        filas.append((f"IVA {F.porcentaje(r.iva_pct)}", r.iva, False))
    else:
        filas.append(("Operación sin IVA discriminado", 0.0, False))

    datos = [[_p(txt, "celda_b" if fuerte else "celda"),
              _p(F.moneda(val), "celda_der")] for txt, val, fuerte in filas]
    datos.append([Paragraph("<b>TOTAL</b>", EST["seccion"]),
                  Paragraph(f"<b>{F.moneda(r.total)}</b>", EST["seccion"])])

    ancho = ANCHO_TOTALES
    t = Table(datos, colWidths=[ancho - 34 * mm, 34 * mm], hAlign="RIGHT")
    t.spaceBefore = 0
    estilos = [
        ("GRID", (0, 0), (-1, -1), 0.4, GRIS_LINEA),
        ("BACKGROUND", (0, -1), (-1, -1), AZUL),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for i, (_txt, _v, fuerte) in enumerate(filas):
        if fuerte:
            estilos.append(("BACKGROUND", (0, i), (-1, i), AZUL_CLARO))
    t.setStyle(TableStyle(estilos))
    return t


ANCHO_TOTALES = 88 * mm


def _bloque_cierre(pres) -> list:
    """Observaciones generales y cuadro de totales, en dos columnas.

    Apilados verticalmente, en un presupuesto de varios ítems el cuadro de
    totales se parte y el TOTAL queda huérfano en la página siguiente. Lado a
    lado entran juntos y el documento cierra en una sola página.
    """
    totales = _bloque_totales(pres)
    texto = (pres.observaciones_generales or "").strip()

    if not texto:
        return [totales, Spacer(1, 4)]

    ancho_obs = ANCHO_UTIL - ANCHO_TOTALES - 6 * mm
    columna_obs = [
        _banda_ancho("OBSERVACIONES GENERALES", ancho_obs),
        Spacer(1, 2),
        _caja_observaciones(texto, ancho_obs),
    ]

    cierre = Table([[columna_obs, totales]],
                   colWidths=[ancho_obs, ANCHO_TOTALES + 6 * mm])
    cierre.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [cierre]


def _banda_ancho(titulo: str, ancho: float) -> Table:
    t = Table([[Paragraph(titulo, EST["seccion"])]], colWidths=[ancho])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), AZUL),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _caja_observaciones(texto: str, ancho: float) -> Table:
    cuerpo = Table([[_p(texto, "obs_gral")]], colWidths=[ancho])
    cuerpo.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, GRIS_LINEA),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FCFCF7")),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return cuerpo


def _bloque_firmas(emp) -> list:
    terminos = (emp["terminos"] or "").strip()
    bloques = []
    if terminos:
        bloques += [Spacer(1, 8), _p("<b>Términos y condiciones</b>", "celda_b"),
                    _p(terminos, "nota")]

    # La columna del medio es un separador: sin ella las dos rayas de firma se
    # tocan y se leen como una sola línea continua.
    ancho_firma = (ANCHO_UTIL - 30 * mm) / 2
    firma = Table(
        [["", "", ""],
         [Paragraph("Firma y aclaración del cliente", EST["firma"]), "",
          Paragraph("Por la empresa", EST["firma"])]],
        colWidths=[ancho_firma, 30 * mm, ancho_firma],
        rowHeights=[16 * mm, 8 * mm],
    )
    firma.setStyle(TableStyle([
        ("LINEABOVE", (0, 1), (0, 1), 0.5, GRIS),
        ("LINEABOVE", (2, 1), (2, 1), 0.5, GRIS),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    bloques += [Spacer(1, 14), firma]
    return bloques


# --- Anexo de despiece ------------------------------------------------------

def _anexo_despiece(db, pres) -> list:
    bloques = [PageBreak(), _banda("ANEXO TÉCNICO · DESPIECE DE CORTE"), Spacer(1, 6)]

    for res in pres.resultados:
        it = res.item
        cab = _p(f"<b>Ítem {it.orden}</b> — {it.descripcion} · {it.medida_texto} · "
                 f"{F.unidades(it.cantidad)} · {it.hojas} hoja(s)", "celda_b")

        filas = [[_p(h, "celda_b") for h in
                  ("Perfil", "Función", "Largo (mm)", "Piezas", "Kg/m", "Peso (kg)")]]
        for p in res.despiece.aluminio.piezas:
            filas.append([
                _p(p.perfil_codigo), _p(p.funcion_legible),
                _p(F.milimetros_corte(p.largo_mm), "celda_der"), _p(F.unidades(p.cantidad), "celda_der"),
                _p(F.kilos_metro(p.peso_kg_m), "celda_der"), _p(F.kilos(p.peso_kg), "celda_der"),
            ])
        filas.append([_p("TOTAL", "celda_b"), _p(""), _p(""),
                      _p(F.unidades(sum(p.cantidad for p in res.despiece.aluminio.piezas)), "celda_der"),
                      _p(""), _p(F.kilos(res.despiece.aluminio.peso_total_kg), "celda_der")])

        for pano in res.despiece.vidrio.panos:
            filas.append([_p("VIDRIO", "celda_b"), _p(pano.descripcion),
                          _p(F.medida(pano.ancho_mm, pano.alto_mm), "celda_der"),
                          _p(F.unidades(pano.cantidad), "celda_der"), _p("m²"),
                          _p(F.superficie(pano.m2_total), "celda_der")])

        anchos = [26 * mm, 46 * mm, 24 * mm, 18 * mm, 20 * mm, 24 * mm]
        anchos[1] += ANCHO_UTIL - sum(anchos)
        t = Table(filas, colWidths=anchos)
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.3, GRIS_LINEA),
            ("BACKGROUND", (0, 0), (-1, 0), AZUL_CLARO),
            ("BACKGROUND", (0, -1), (-1, -1), GRIS_FONDO),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        bloques.append(KeepTogether([cab, Spacer(1, 2), t, Spacer(1, 8)]))

    # Consolidado para compras
    cons = resumen_materiales(pres)
    bloques += [Spacer(1, 4), _banda("CONSOLIDADO DE MATERIALES (COMPRAS)"), Spacer(1, 4)]

    filas = [[_p(h, "celda_b") for h in ("Perfil", "Descripción", "Largo (mm)", "Piezas", "Peso (kg)")]]
    for reg in cons["perfiles"]:
        filas.append([_p(reg["perfil"]), _p(reg["descripcion"]),
                      _p(F.milimetros_corte(reg["largo_mm"]), "celda_der"),
                      _p(F.unidades(reg["cantidad"]), "celda_der"),
                      _p(F.kilos(reg["peso_kg"]), "celda_der")])
    anchos = [26 * mm, 70 * mm, 24 * mm, 18 * mm, 24 * mm]
    anchos[1] += ANCHO_UTIL - sum(anchos)
    t = Table(filas, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, GRIS_LINEA),
                           ("BACKGROUND", (0, 0), (-1, 0), AZUL_CLARO),
                           ("TOPPADDING", (0, 0), (-1, -1), 2),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    bloques += [t, Spacer(1, 8)]

    filas = [[_p(h, "celda_b") for h in ("Accesorio", "Descripción", "Un.", "Cantidad", "Importe")]]
    for reg in cons["accesorios"]:
        filas.append([_p(reg["codigo"]), _p(reg["descripcion"]), _p(reg["unidad"]),
                      _p(F.cantidad(reg["cantidad"], reg["unidad"]), "celda_der"),
                      _p(F.moneda(reg["total"]), "celda_der")])
    for reg in cons["vidrios"]:
        filas.append([_p("VIDRIO"), _p(reg["tipo"]), _p("m²"),
                      _p(F.superficie(reg["m2"]), "celda_der"), _p("")])
    anchos = [26 * mm, 70 * mm, 14 * mm, 24 * mm, 28 * mm]
    anchos[1] += ANCHO_UTIL - sum(anchos)
    t = Table(filas, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, GRIS_LINEA),
                           ("BACKGROUND", (0, 0), (-1, 0), AZUL_CLARO),
                           ("TOPPADDING", (0, 0), (-1, -1), 2),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    bloques.append(t)
    return bloques


# --- API pública ------------------------------------------------------------

def generar_pdf(db, pres, ruta_salida: str | Path, incluir_despiece: bool = False) -> Path:
    """Escribe el presupuesto en ``ruta_salida`` y devuelve la ruta."""
    ruta = Path(ruta_salida)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    emp = db.empresa()

    doc = SimpleDocTemplate(
        str(ruta), pagesize=A4,
        leftMargin=MARGEN, rightMargin=MARGEN, topMargin=14 * mm, bottomMargin=18 * mm,
        title=f"Presupuesto {pres.numero}",
        author=emp["razon_social"] or "Cotizador de Aberturas",
        subject=f"Presupuesto para {pres.cliente.razon_social}",
    )
    doc.pie_texto = " · ".join(
        x for x in (emp["razon_social"], emp["telefono"], emp["email"]) if x
    ) or "Cotizador de Aberturas de Aluminio"

    story = [
        _encabezado(emp, pres), Spacer(1, 8),
        _banda("DATOS DEL CLIENTE"), Spacer(1, 2), _bloque_cliente(pres), Spacer(1, 8),
        _banda("DETALLE DE ABERTURAS"), Spacer(1, 2), _tabla_items(db, pres), Spacer(1, 10),
    ]
    story += _bloque_cierre(pres)
    story += _bloque_firmas(emp)
    if incluir_despiece:
        story += _anexo_despiece(db, pres)

    # canvasmaker cruza cada hoja con el sello de prueba mientras no haya
    # licencia. No toca el armado: los pies de página siguen siendo los de acá.
    doc.build(story, onFirstPage=_pie, onLaterPages=_pie,
              canvasmaker=marca_prueba.lienzo())
    return ruta


def nombre_sugerido(pres) -> str:
    cliente = "".join(ch for ch in (pres.cliente.razon_social or "cliente")
                      if ch.isalnum() or ch in " -_").strip().replace(" ", "_")[:40]
    return f"{pres.numero}_{cliente or 'cliente'}.pdf"
