"""
Genera el **Manual de Usuario** en PDF.

    python -m tools.generar_manual
    python -m tools.generar_manual --salida "C:/ruta/Manual.pdf"

Está escrito para el usuario final (el carpintero), no para el proveedor: no
menciona la emisión de licencias ni las herramientas internas.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    BaseDocTemplate, Frame, Image, KeepTogether, ListFlowable, ListItem,
    NextPageTemplate, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents  # noqa: E402

from core import rutas  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
IMAGENES = RAIZ / "recursos" / "manual"

AZUL = colors.HexColor("#1B3A57")
AZUL_CLARO = colors.HexColor("#E7EEF4")
GRIS = colors.HexColor("#5B6B7C")
GRIS_LINEA = colors.HexColor("#C7D0D8")
GRIS_FONDO = colors.HexColor("#F4F6F8")
VERDE = colors.HexColor("#0F766E")
VERDE_FONDO = colors.HexColor("#ECF6F4")
AMBAR = colors.HexColor("#B45309")
AMBAR_FONDO = colors.HexColor("#FEF6E7")

MARGEN = 20 * mm
ANCHO = A4[0] - 2 * MARGEN


# ---------------------------------------------------------------------------
# Estilos
# ---------------------------------------------------------------------------

def _estilos():
    base = getSampleStyleSheet()
    e = {}
    e["portada_titulo"] = ParagraphStyle(
        "pt", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=30,
        textColor=colors.white, leading=36, alignment=TA_CENTER)
    e["portada_sub"] = ParagraphStyle(
        "ps", parent=base["Normal"], fontName="Helvetica", fontSize=14,
        textColor=colors.HexColor("#C7D8E6"), leading=20, alignment=TA_CENTER)
    e["h1"] = ParagraphStyle(
        "h1", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=19,
        textColor=AZUL, leading=24, spaceBefore=0, spaceAfter=10)
    e["h2"] = ParagraphStyle(
        "h2", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=13,
        textColor=AZUL, leading=17, spaceBefore=14, spaceAfter=6)
    e["h3"] = ParagraphStyle(
        "h3", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=10.5,
        textColor=colors.HexColor("#26364A"), leading=14, spaceBefore=10, spaceAfter=4)
    e["p"] = ParagraphStyle(
        "p", parent=base["Normal"], fontName="Helvetica", fontSize=9.5,
        leading=14, alignment=TA_JUSTIFY, spaceAfter=6)
    e["li"] = ParagraphStyle(
        "li", parent=base["Normal"], fontName="Helvetica", fontSize=9.5, leading=13.5)
    e["celda"] = ParagraphStyle(
        "celda", parent=base["Normal"], fontName="Helvetica", fontSize=8.5, leading=11.5)
    e["celda_b"] = ParagraphStyle(
        "celdab", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8.5,
        leading=11.5, textColor=colors.white)
    e["aviso"] = ParagraphStyle(
        "aviso", parent=base["Normal"], fontName="Helvetica", fontSize=9,
        leading=13, textColor=colors.HexColor("#7A4A08"))
    e["tip"] = ParagraphStyle(
        "tip", parent=base["Normal"], fontName="Helvetica", fontSize=9,
        leading=13, textColor=colors.HexColor("#0B5D57"))
    e["pie_img"] = ParagraphStyle(
        "pieimg", parent=base["Normal"], fontName="Helvetica-Oblique", fontSize=8,
        textColor=GRIS, alignment=TA_CENTER, leading=11, spaceBefore=3)
    e["toc1"] = ParagraphStyle(
        "toc1", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=10.5,
        leading=20, textColor=AZUL)
    e["toc2"] = ParagraphStyle(
        "toc2", parent=base["Normal"], fontName="Helvetica", fontSize=9.5,
        leading=15, leftIndent=14, textColor=colors.HexColor("#33475B"))
    return e


EST = _estilos()
_contador = {"h1": 0, "h2": 0}


# ---------------------------------------------------------------------------
# Bloques
# ---------------------------------------------------------------------------

class Titulo(Paragraph):
    """Título visible que además se anota en el índice.

    Un único flowable hace las dos cosas: si se usara un marcador aparte para el
    índice más un párrafo visible, el título saldría impreso dos veces.
    """

    def __init__(self, texto, nivel=0, subrayado=False):
        self.nivel_toc = nivel
        self.texto_toc = texto
        self.subrayado = subrayado
        super().__init__(texto, EST["h1" if nivel == 0 else "h2"])

    def draw(self):
        super().draw()
        if self.subrayado:
            self.canv.saveState()
            self.canv.setStrokeColor(AZUL)
            self.canv.setLineWidth(1.2)
            self.canv.line(0, -5, ANCHO, -5)
            self.canv.restoreState()


def h1(texto):
    _contador["h1"] += 1
    _contador["h2"] = 0
    return [Titulo(f"{_contador['h1']}.  {texto}", 0, subrayado=True), Spacer(1, 14)]


def h2(texto):
    """Subtitulo numerado.

    El numero lo pone esta funcion y no el texto: con el numero escrito a mano,
    agregar un capitulo en el medio desfasaba todos los de abajo y habia que
    corregirlos de a uno.
    """
    _contador["h2"] += 1
    return [Titulo(f"{_contador['h1']}.{_contador['h2']}  {texto}", 1)]


def h3(texto):
    return [Paragraph(texto, EST["h3"])]


def p(texto):
    return [Paragraph(texto, EST["p"])]


def pasos(items, numerados=True):
    # Sin `value=`: ListFlowable numera solo. Pasarle un entero rompe el cálculo
    # de ancho del bullet dentro de ReportLab.
    return [ListFlowable(
        [ListItem(Paragraph(x, EST["li"]), leftIndent=16) for x in items],
        bulletType="1" if numerados else "bullet",
        bulletFormat="%s." if numerados else None,
        bulletFontSize=9, leftIndent=18, bulletDedent=13,
        spaceBefore=2, spaceAfter=8, bulletColor=AZUL), Spacer(1, 2)]


def vinetas(items):
    return pasos(items, numerados=False)


def _caja(texto, titulo, color_borde, color_fondo, estilo):
    contenido = Paragraph(f"<b>{titulo}</b>&nbsp;&nbsp;{texto}", estilo)
    t = Table([[contenido]], colWidths=[ANCHO])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color_fondo),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, color_borde),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return [t, Spacer(1, 8)]


def aviso(texto, titulo="Atención"):
    return _caja(texto, titulo, AMBAR, AMBAR_FONDO, EST["aviso"])


def tip(texto, titulo="Consejo"):
    return _caja(texto, titulo, VERDE, VERDE_FONDO, EST["tip"])


def tabla(encabezados, filas, anchos=None):
    datos = [[Paragraph(h, EST["celda_b"]) for h in encabezados]]
    datos += [[Paragraph(str(c), EST["celda"]) for c in fila] for fila in filas]
    if anchos is None:
        anchos = [ANCHO / len(encabezados)] * len(encabezados)
    else:
        total = sum(anchos)
        anchos = [a / total * ANCHO for a in anchos]

    t = Table(datos, colWidths=anchos, repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("GRID", (0, 0), (-1, -1), 0.4, GRIS_LINEA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for i in range(1, len(datos)):
        if i % 2 == 0:
            estilo.append(("BACKGROUND", (0, i), (-1, i), GRIS_FONDO))
    t.setStyle(TableStyle(estilo))
    return [t, Spacer(1, 10)]


def imagen(nombre, pie="", ancho_max=ANCHO):
    ruta = IMAGENES / nombre
    if not ruta.exists():
        return []
    from reportlab.lib.utils import ImageReader
    ancho_px, alto_px = ImageReader(str(ruta)).getSize()
    ancho = min(ancho_max, ANCHO)
    alto = ancho * alto_px / ancho_px

    marco = Table([[Image(str(ruta), width=ancho, height=alto)]], colWidths=[ancho])
    marco.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, GRIS_LINEA),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    marco.hAlign = "CENTER"

    bloque = [marco]
    if pie:
        bloque.append(Paragraph(pie, EST["pie_img"]))
    bloque.append(Spacer(1, 10))
    return [KeepTogether(bloque)]


def campos(filas):
    """Tabla de referencia campo -> qué hace."""
    return tabla(["Campo", "Para qué sirve"], filas, anchos=[30, 70])


# ---------------------------------------------------------------------------
# Plantillas de página
# ---------------------------------------------------------------------------

class Documento(BaseDocTemplate):
    def __init__(self, ruta, estilo_portada="vector", **kw):
        self.estilo_portada = estilo_portada
        super().__init__(str(ruta), pagesize=A4,
                         leftMargin=MARGEN, rightMargin=MARGEN,
                         topMargin=MARGEN + 6 * mm, bottomMargin=MARGEN,
                         title="Manual de Usuario — Cotizador de Aberturas",
                         author="Cotizador de Aberturas de Aluminio", **kw)
        marco = Frame(MARGEN, MARGEN, ANCHO,
                      A4[1] - 2 * MARGEN - 6 * mm, id="cuerpo")
        self.addPageTemplates([
            PageTemplate(id="portada", frames=[Frame(0, 0, A4[0], A4[1], id="p")],
                         onPage=self._portada),
            PageTemplate(id="normal", frames=[marco], onPage=self._encabezado),
        ])

    def _portada(self, canvas, doc):
        canvas.saveState()
        imagen_portada = IMAGENES / "portada.jpg"

        if self.estilo_portada == "imagen" and imagen_portada.exists():
            # A página completa. La proporción de la imagen difiere del A4 en un
            # 0,8 %: con preserveAspectRatio quedan dos franjas de menos de 3 pt
            # que se funden con el fondo del propio diseño.
            canvas.drawImage(str(imagen_portada), 0, 0, width=A4[0], height=A4[1],
                             preserveAspectRatio=True, anchor="c", mask="auto")
        else:
            from tools.portada import dibujar_portada
            dibujar_portada(canvas, rutas.version())
        canvas.restoreState()

    def _encabezado(self, canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(GRIS_LINEA)
        canvas.setLineWidth(0.4)
        y = A4[1] - MARGEN + 2 * mm
        canvas.line(MARGEN, y, A4[0] - MARGEN, y)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GRIS)
        canvas.drawString(MARGEN, y + 2.5 * mm, "Cotizador de Aberturas de Aluminio")
        canvas.drawRightString(A4[0] - MARGEN, y + 2.5 * mm, "Manual de Usuario")

        canvas.line(MARGEN, MARGEN - 4 * mm, A4[0] - MARGEN, MARGEN - 4 * mm)
        canvas.drawCentredString(A4[0] / 2, MARGEN - 9 * mm, str(canvas.getPageNumber() - 1))
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, Titulo):
            self.notify("TOCEntry", (flowable.nivel_toc, flowable.texto_toc, self.page - 1))


# ---------------------------------------------------------------------------
# Contenido
# ---------------------------------------------------------------------------

def construir() -> list:
    version = rutas.version()
    hoy = date.today().strftime("%d/%m/%Y")
    s: list = []

    # -------------------------------------------------- portada (imagen full page)
    s += [Spacer(1, 1), NextPageTemplate("normal"), PageBreak()]

    # ---------------------------------------------------------------- índice
    s += [Paragraph("Índice", EST["h1"])]
    s += [Spacer(1, 6)]
    toc = TableOfContents()
    toc.levelStyles = [EST["toc1"], EST["toc2"]]
    s += [toc, Spacer(1, 14)]

    ficha = Table([
        ["Versión del programa", version],
        ["Fecha del manual", hoy],
    ], colWidths=[55 * mm, 60 * mm])
    ficha.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (0, -1), AZUL),
        ("TEXTCOLOR", (1, 0), (1, -1), GRIS),
        ("LINEABOVE", (0, 0), (-1, 0), 0.4, GRIS_LINEA),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    ficha.hAlign = "LEFT"
    s += [ficha, Spacer(1, 14)]

    s += [Paragraph("Novedades de esta versión", EST["h2"]), Spacer(1, 4)]
    s += vinetas([
        "<b>Opciones de la tipología</b> — una misma tipología puede llevar "
        "rueda simple o doble, cierre de embutir o multipunto, paño fijo abajo "
        "o no. Se elige al cargar la abertura, sin tener que crear una "
        "tipología nueva por cada combinación (punto 3.4).",
        "<b>Panel de advertencias</b> — el contador al lado de la lista de "
        "aberturas avisa qué le falta al cálculo y lleva derecho al lugar "
        "donde se corrige (punto 3.5).",
        "<b>Papeles del taller</b> — diagramas de corte de cada barra, "
        "<b>plano de corte del vidrio sobre la plancha</b>, listas por rubro y "
        "etiquetas para pegar en las piezas (capítulo 5).",
        "<b>Barras a comprar</b> — el conteo optimiza todas las aberturas "
        "juntas: tres ventanas iguales cuyo parante mide un metro salen de una "
        "barra de seis, no de tres (punto 3.4).",
        "<b>Inventario</b> — qué hay en depósito, qué falta para una obra y qué "
        "se descuenta al mandar a fabricar (capítulo 8).",
        "<b>Órdenes de trabajo</b> — la hoja que baja al taller, con su propio "
        "estado y su diagrama de corte (capítulo 9).",
    ])
    s += [PageBreak()]

    # ================================================================ 1
    s += h1("Antes de empezar")
    s += p("El <b>Cotizador de Aberturas de Aluminio</b> arma presupuestos completos "
           "a partir de las medidas de cada abertura: calcula el despiece de perfiles, "
           "el vidrio y los accesorios, suma mano de obra y logística, aplica descuentos "
           "e IVA, y genera un PDF listo para enviar al cliente.")

    s += h2("Requisitos del sistema")
    s += p("El programa es liviano y funciona en cualquier computadora de oficina "
           "razonablemente moderna. <b>No necesita instalar Python, ni Office, ni ninguna "
           "otra cosa.</b>")
    s += tabla(["Requisito", "Mínimo", "Recomendado"], [
        ["<b>Sistema operativo</b>",
         "Windows 10 de 64 bits",
         "Windows 10 o 11 de 64 bits, actualizado"],
        ["<b>Procesador</b>",
         "Cualquier Intel o AMD de 64 bits",
         "Doble núcleo o superior"],
        ["<b>Memoria RAM</b>",
         "2 GB",
         "4 GB o más"],
        ["<b>Espacio en disco</b>",
         "150 MB libres",
         "500 MB, para presupuestos y respaldos"],
        ["<b>Resolución de pantalla</b>",
         "1024 × 600",
         "1366 × 768 o superior"],
        ["<b>Conexión a internet</b>",
         "No es necesaria",
         "Sólo para recibir la clave de activación"],
        ["<b>Permisos de Windows</b>",
         "Usuario común",
         "No hace falta ser administrador"],
    ], anchos=[30, 33, 37])

    s += h3("Un poco más de detalle")
    s += vinetas([
        "<b>El programa ocupa 42 MB</b> ya instalado. El resto del espacio es para tu "
        "base de datos, los PDF que generes y las copias de seguridad.",
        "<b>Usa unos 60 MB de memoria</b> mientras está abierto, así que convive sin "
        "problemas con el navegador y el resto de los programas.",
        "<b>Tarda unos 10 segundos en abrir</b> la primera vez que lo ejecutás en el día. "
        "Después arranca más rápido, porque Windows ya tiene los archivos en memoria.",
        "<b>No funciona en Windows 7 ni 8.</b> Tampoco en versiones de 32 bits.",
        "<b>Funciona sin internet.</b> Sólo hace falta conexión para que tu proveedor te "
        "haga llegar la clave de activación; el programa en sí trabaja sin red.",
    ])
    s += tip("Si tu pantalla es de 1366 × 768 (lo habitual en notebooks), la ventana se "
             "adapta sola al tamaño disponible. Si te queda chica la letra, agrandá la "
             "interfaz desde <b>Ajustes → Apariencia → Tamaño de la interfaz</b>.")

    s += h2("Instalación")
    s += pasos([
        "Descomprimí el archivo <b>.zip</b> que recibiste en una carpeta de tu PC "
        "(por ejemplo <font face='Courier'>C:\\Cotizador</font>).",
        "Entrá en la carpeta y hacé doble clic en "
        "<b><font face='Courier'>CotizadorAberturas.exe</font></b>.",
        "La primera vez Windows puede mostrar un aviso de seguridad: hacé clic en "
        "<b>Más información</b> y después en <b>Ejecutar de todas formas</b>.",
    ])
    s += tip("No hace falta instalar Python ni ningún otro programa. Para tenerlo a mano, "
             "hacé clic derecho sobre el .exe y elegí <b>Enviar a → Escritorio "
             "(crear acceso directo)</b>.")
    s += aviso("No muevas el archivo .exe fuera de su carpeta: necesita los archivos que "
               "están junto a él para funcionar. Movés la carpeta entera o creás un acceso "
               "directo.")

    s += h2("Los 3 días de prueba")
    s += p("La primera vez que abrís el programa arrancan <b>tres días de prueba "
           "gratuita</b>. Se activan solos: no hay que registrarse ni cargar ningún "
           "dato. Durante esos días el programa funciona completo, sin recortes.")
    s += p("Abajo a la izquierda, en la barra de estado, vas a ver cuántos días te "
           "quedan.")
    s += p("Una sola cosa cambia mientras dura la prueba: <b>todo lo que imprimás o "
           "exportes sale con la leyenda «VERSIÓN DE PRUEBA» cruzada en rojo</b>. "
           "Vale para los presupuestos, los diagramas de corte, las etiquetas, las "
           "listas de materiales, las órdenes de trabajo y también para el Excel. "
           "Es a propósito: la prueba es para que midas, cargues tus precios y veas "
           "si te sirve, no para mandar presupuestos con ella.")
    s += p("Apenas ponés la clave la marca desaparece, sin cerrar el programa. Los "
           "presupuestos que hayas hecho durante la prueba los volvés a generar "
           "limpios en un segundo, sin cargar nada de nuevo: quedaron guardados.")
    s += tip("Cuando se terminen, escribí a <b>cotizadoraberturas@gmail.com</b> con el "
             "código de equipo que muestra la pantalla y te llega la clave. <b>Lo que "
             "cargaste no se pierde</b>: los presupuestos, los precios y las fórmulas "
             "quedan donde están y siguen ahí cuando actives.")

    s += h2("Activación de la licencia")
    s += p("El sistema se licencia <b>por equipo</b>. La primera vez que lo abrís aparece "
           "la ventana de activación.")
    s += imagen("activacion.png", "Ventana de activación.", 118 * mm)
    s += pasos([
        "Hacé clic en <b>Copiar</b> para copiar el <b>código de equipo</b> "
        "(el número grande de 16 caracteres).",
        "Envialo a tu proveedor por WhatsApp.",
        "Te va a responder con una <b>clave de activación</b>, una línea larga que "
        "empieza con <font face='Courier'>COTIZ-</font>.",
        "Copiala completa, pegala en el recuadro <b>Clave de activación</b> y hacé clic "
        "en <b>Activar</b>.",
    ])
    s += tip("Al pegar la clave con <b>Ctrl+V</b>, el programa la valida solo: si está "
             "completa, se activa sin que tengas que apretar nada más. No importa si "
             "llega con espacios o cortada en varios renglones.")
    s += p("El código de equipo es distinto en cada PC, y la clave sirve <b>sólo para esa "
           "computadora</b>. Si cambiás de máquina, pedí una clave nueva con el código "
           "de la máquina nueva.")

    s += h2("Renovación de la suscripción")
    s += p("La licencia tiene fecha de vencimiento. Desde 7 días antes, el programa avisa "
           "al abrirse. Para renovar, mandale de nuevo el código de equipo a tu proveedor "
           "y cargá la clave en <b>Ajustes → Licencia → Activar / renovar suscripción</b>.")
    s += tip("Si renovás <b>antes</b> de que venza, los días nuevos se suman a los que te "
             "quedaban: no perdés nada por adelantarte.")
    s += aviso("Si el programa dice que la fecha del equipo está atrasada, corregí la fecha "
               "y hora de Windows (clic derecho en el reloj → <b>Ajustar fecha y hora</b> → "
               "activá <b>Establecer la hora automáticamente</b>) y volvé a abrirlo.")
    s += [PageBreak()]

    # ================================================================ 2
    s += h1("La pantalla principal")
    s += imagen("cotizacion.png", "Pantalla de Cotización, con las cinco secciones del menú "
                                  "a la izquierda.")
    s += p("A la izquierda está el menú con las cinco secciones del programa. "
           "Abajo de todo, el selector de tema.")
    s += tabla(["Sección", "Para qué se usa"], [
        ["<b>Cotización</b>", "Armar el presupuesto: cliente, aberturas, costos y PDF. "
                              "Es la pantalla de trabajo diaria."],
        ["<b>Presupuestos</b>", "Historial: buscar, reabrir, duplicar, cambiar de estado "
                                "y reimprimir presupuestos anteriores."],
        ["<b>Materiales y Costos</b>", "Precios del aluminio, vidrios, accesorios, "
                                       "tipologías y fórmulas de corte."],
        ["<b>Empresa</b>", "Tus datos, tu logo y la numeración de los presupuestos."],
        ["<b>Ajustes</b>", "Tema, licencia, copias de seguridad y actualizaciones."],
    ], anchos=[28, 72])

    s += h2("La barra inferior")
    s += p("Muestra en todo momento un resumen del presupuesto abierto: cantidad de ítems, "
           "metros cuadrados, kilos de aluminio y, a la derecha, el <b>total</b>. También "
           "aparecen ahí los avisos del sistema.")

    s += h2("Cambiar el tema")
    s += p("Abajo del menú hay dos botones: <b>Claro</b> y <b>Silver</b>. El cambio es "
           "inmediato, no hay que reiniciar.")
    s += tabla(["Tema", "Cuándo conviene"], [
        ["<b>Claro</b>", "Fondo blanco tradicional, máximo contraste. Para oficina "
                         "o lugares muy iluminados."],
        ["<b>Silver</b>", "Grises suaves de baja luminancia. Pensado para muchas horas "
                          "seguidas frente a la pantalla, sin llegar al negro."],
    ], anchos=[20, 80])
    s += imagen("cotizacion_silver.png", "La misma pantalla en Modo Silver.", 140 * mm)
    s += [PageBreak()]

    # ================================================================ 3
    s += h1("Armar un presupuesto")
    s += p("Todo el trabajo diario pasa por la pantalla <b>Cotización</b>.")

    s += h2("Encabezado")
    s += campos([
        ["<b>Número</b>", "Se completa solo con el siguiente de la serie. Se puede "
                          "escribir a mano. El botón <b>↻</b> vuelve a sugerir el "
                          "número correlativo."],
        ["<b>Fecha</b>", "Fecha del presupuesto, en formato día/mes/año."],
        ["<b>Días</b>", "Validez de la oferta. En el PDF se imprime la fecha hasta la "
                        "que el precio se mantiene."],
        ["<b>Estado</b>", "Borrador, Enviado, Aprobado, Rechazado o Facturado. Sirve para "
                          "el seguimiento comercial en el historial."],
    ])

    s += h2("Datos del cliente")
    s += p("Se cargan una sola vez y salen impresos en el PDF: <b>Cliente / Razón social</b>, "
           "<b>CUIT / DNI</b>, <b>Contacto</b>, <b>Obra / Dirección</b>, <b>Localidad</b> y "
           "<b>Forma de pago</b>.")
    s += tip("La <b>forma de pago</b> es una lista desplegable con las opciones más comunes "
             "(contado, 50 % anticipo, 30/30/40, cheque a 30 días…).")

    s += h2("Agregar una abertura")
    s += p("Hacé clic en <b>+ Agregar abertura</b>. Se abre una ventana con los datos de la "
           "abertura a la izquierda y el <b>costo calculado en vivo</b> a la derecha: cada "
           "vez que cambiás una medida, el precio se actualiza al instante.")
    s += campos([
        ["<b>Tipología</b>", "Tipo de abertura: ventana corrediza, puerta balcón, paño "
                             "fijo, batiente, banderola… Al elegirla se completa sola la "
                             "cantidad de hojas habitual."],
        ["<b>Línea</b>", "Línea de aluminio (Módena, Herrero, A30 New, Módena Plus…). "
                         "Determina los perfiles y las fórmulas de corte."],
        ["<b>Color / Terminación</b>", "Color de la línea elegida. Cada color tiene su "
                                       "propio precio."],
        ["<b>Vidrio</b>", "Tipo de vidrio: Float, Laminado, DVH, Esmerilado…"],
        ["<b>Ancho (A)</b>", "Ancho total del vano, en milímetros."],
        ["<b>Alto (H)</b>", "Alto total del vano, en milímetros."],
        ["<b>Hojas (N)</b>", "Cantidad de hojas. Entra en las fórmulas de corte."],
        ["<b>Cantidad</b>", "Cuántas aberturas iguales lleva el presupuesto."],
        ["<b>Incluye premarco</b>", "Si la línea corta el premarco con sus propios perfiles "
                                    "—como MDT Actual—, lo agrega al despiece y se cobra con "
                                    "el aluminio. Si no, suma el costo de premarco por m²."],
        ["<b>Incluye mosquitero</b>", "Si la línea corta el mosquitero con sus propios "
                                      "perfiles —las corredizas MDT—, lo agrega al despiece, "
                                      "se cobra con el aluminio y por m² se suma sólo la tela. "
                                      "Si no, suma el costo de mosquitero por m². Se desactiva "
                                      "solo en las tipologías que no lo admiten."],
        ["<b>Bonificación del ítem</b>", "Descuento en porcentaje aplicado sólo a este "
                                         "renglón."],
        ["<b>Observaciones</b>", "Texto libre que se imprime debajo del ítem en el PDF. "
                                 "Por ejemplo: “vidrio esmerilado”, “manijón especial”, "
                                 "“colocación en altura”."],
    ])
    s += tip("El botón <b>Ver despiece</b> muestra, antes de aceptar, todos los cortes de "
             "perfil con sus largos, el vidrio y los accesorios de esa abertura.")
    s += aviso("Si el programa avisa que <b>no hay fórmulas cargadas</b> para esa "
               "combinación de tipología y línea, el cálculo del aluminio va a quedar en "
               "cero. Hay que cargarlas en el capítulo <i>Materiales y Costos</i>.")

    s += h2("Opciones de la tipología")
    s += p("Debajo de las medidas puede aparecer un recuadro llamado <b>Opciones de la "
           "tipología</b>. Son las variantes que esa tipología admite, y salen de lo que "
           "vos hayas declarado en Materiales y Costos. Por ejemplo:")
    s += vinetas([
        "<b>Rodamiento</b> — rueda simple para una hoja liviana, doble reforzada "
        "para una hoja pesada. El kit descuenta y cobra <b>la que elegiste</b>.",
        "<b>Cierre</b> — de embutir para una ventana común, multipunto para una "
        "puerta balcón.",
        "<b>Lleva contramarco</b> — una casilla que agrega o saca los cortes de "
        "contramarco del despiece. El premarco no aparece acá: lo decide la casilla "
        "<b>Incluye premarco</b>.",
        "<b>Alto del paño fijo</b> — un número que entra en las fórmulas de corte.",
    ])
    s += p("Si la tipología no declara ninguna opción, el recuadro no aparece: no hay nada "
           "que completar.")
    s += tip("Antes había que crear una tipología distinta por cada combinación —corrediza "
             "con rueda simple, corrediza con rueda doble, corrediza con premarco…—. Con "
             "las opciones es <b>una sola tipología</b> y la variante se elige al cargar la "
             "abertura. En la lista de aberturas, la columna <b>Opcionales</b> muestra qué "
             "quedó elegido en cada renglón.")

    s += h2("El contador de advertencias")
    s += p("Al lado del título de la lista de aberturas puede aparecer un contador naranja "
           "con un símbolo de atención. Es lo que el cálculo tiene para decirte: no es un "
           "error del programa, es una falta de datos o algo que conviene mirar.")
    s += tabla(["Ejemplo de aviso", "Qué significa"], [
        ["<b>Sin fórmulas de despiece</b>",
         "Esa combinación de tipología y línea no tiene fórmulas cargadas. El aluminio "
         "va a dar cero."],
        ["<b>Despiece genérico</b>",
         "Se están usando fórmulas de ejemplo, no las de tu línea. Sirve para tener una "
         "cotización estimada, <b>no para cortar material</b>."],
        ["<b>Perfil sin peso por metro</b>",
         "Falta el kg/m del perfil, así que su costo por kilo no se puede calcular."],
        ["<b>Corte más largo que la barra</b>",
         "Una fórmula da un largo que no entra en una barra de 6 metros. Casi siempre es "
         "un error de la fórmula o una medida imposible."],
        ["<b>Paño de vidrio imposible</b>",
         "La fórmula del vidrio da una medida negativa o cero."],
    ], anchos=[34, 66])
    s += p("Hacé clic en el contador para ver la lista completa. Cada aviso tiene un botón "
           "que te lleva directo a la pantalla donde se corrige.")

    s += h2("Trabajar con la lista de aberturas")
    s += tabla(["Botón", "Qué hace"], [
        ["<b>Editar</b>", "Abre la abertura seleccionada para modificarla. También se "
                          "llega haciendo doble clic sobre la fila."],
        ["<b>Duplicar</b>", "Crea una copia idéntica. Práctico cuando hay varias aberturas "
                            "parecidas: se duplica y se cambia sólo la medida."],
        ["<b>Eliminar</b>", "Borra la abertura seleccionada. Pide confirmación."],
        ["<b>Ver despiece</b>", "Muestra el detalle de corte de la abertura seleccionada."],
        ["<b>Barras a comprar</b>", "Cuántas barras de cada perfil hay que comprar para "
                                    "<b>todo el presupuesto junto</b>. No es la suma de "
                                    "abertura por abertura: los cortes cortos de varias "
                                    "aberturas se acomodan en la misma barra, así que el "
                                    "número es bastante menor y es el que se le pide al "
                                    "proveedor."],
        ["<b>Papeles de taller</b>", "Genera los tres PDF que baja el taller. Ver el "
                                     "capítulo <i>Los papeles del taller</i>."],
        ["<b>Materiales a Excel</b>", "Exporta a una planilla el listado completo de "
                                      "perfiles, vidrios y accesorios del presupuesto, "
                                      "para mandársela al proveedor o cruzarla con una "
                                      "lista de precios."],
        ["<b>Emitir OT</b>", "Crea la orden de trabajo para mandar a fabricar. Ver el "
                             "capítulo <i>Órdenes de trabajo</i>."],
        ["<b>▲ ▼</b>", "Suben o bajan el renglón para cambiar el orden en que salen "
                       "impresos."],
    ], anchos=[22, 78])
    s += p("La tabla tiene más columnas de las que entran en pantalla (peso, vidrio, hojas, "
           "opcionales). Usá la <b>barra de desplazamiento horizontal</b> de abajo para "
           "verlas.")

    s += h2("Mano de obra y logística")
    s += campos([
        ["<b>Valor hora-hombre</b>", "Cuánto cuesta una hora de taller."],
        ["<b>Operarios</b>", "Cuántas personas trabajan en el pedido."],
        ["<b>Horas estimadas</b>", "Horas totales de fabricación."],
        ["<b>Flete / recepción</b>", "Costo de traer el material al taller."],
        ["<b>Envío / colocación</b>", "Costo de llevar y colocar en obra."],
    ])
    s += p("Con <b>Estimar horas por m² automáticamente</b> tildado, el programa calcula "
           "las horas a partir de los metros cuadrados del presupuesto y de las horas por "
           "m² de cada tipología. Destildalo para escribir las horas a mano.")
    s += p("El botón <b>Colocación por m²</b> completa el campo de envío multiplicando los "
           "m² del presupuesto por el precio de colocación configurado.")
    s += tip("<b>Mano de obra dentro de cada ítem</b> reparte la mano de obra dentro del "
             "precio unitario de cada abertura, en lugar de mostrarla como una línea "
             "aparte. Útil cuando no querés que el cliente vea ese costo por separado.")

    s += h2("Resumen, descuentos e IVA")
    s += campos([
        ["<b>Margen</b>", "Porcentaje de ganancia que se aplica sobre el costo para "
                          "obtener el precio de venta."],
        ["<b>Descuento global</b>", "Elegí si el descuento es en <b>porcentaje</b> o en "
                                    "un <b>monto</b> fijo en pesos."],
        ["<b>Descuento</b>", "El valor del descuento global."],
        ["<b>IVA</b>", "Alícuota a aplicar, normalmente 21 %."],
        ["<b>Facturar con IVA</b>", "Destildado, el total no lleva IVA y el PDF lo aclara."],
    ])
    s += p("Debajo aparece el desglose completo y el <b>TOTAL</b> destacado. El orden del "
           "cálculo es siempre este:")
    s += tabla(["Paso", "Concepto"], [
        ["1", "Subtotal de los ítems"],
        ["2", "− Descuentos por ítem (las bonificaciones de cada renglón)"],
        ["3", "+ Mano de obra"],
        ["4", "+ Logística (flete + colocación)"],
        ["5", "= Subtotal general"],
        ["6", "− Descuento global"],
        ["7", "= Neto"],
        ["8", "+ IVA"],
        ["9", "<b>= TOTAL</b>"],
    ], anchos=[10, 90])

    s += h2("Observaciones generales")
    s += p("Texto libre que se imprime en un recuadro del PDF: plazo de entrega, qué no "
           "incluye el precio, garantías. Se precarga con lo que hayas configurado en la "
           "sección Empresa, y se puede editar en cada presupuesto.")

    s += h2("Guardar y exportar")
    s += tabla(["Botón", "Qué hace"], [
        ["<b>Nuevo</b>", "Vacía la pantalla para empezar otro presupuesto. Si hay cambios "
                         "sin guardar, avisa antes."],
        ["<b>Guardar</b>", "Guarda el presupuesto en el historial. El número correlativo "
                           "avanza solo."],
        ["<b>Generar PDF</b>", "Pide dónde guardar el archivo y ofrece abrirlo al terminar."],
    ], anchos=[22, 78])
    s += [PageBreak()]

    # ================================================================ 4
    s += h1("Ver el despiece")
    s += p("La ventana de despiece muestra cómo se compone una abertura. Se abre desde "
           "<b>Ver despiece</b>, tanto en la lista de aberturas como dentro de la ventana "
           "de carga.")
    s += h2("Los cuatro recuadros de arriba")
    s += tabla(["Recuadro", "Qué informa"], [
        ["<b>Aluminio</b>", "Costo, metros lineales de perfil, kilos netos, kilos con "
                            "desperdicio y cuántas barras de 6 metros hacen falta."],
        ["<b>Vidrio</b>", "Costo, metros cuadrados netos y con desperdicio, tipo de vidrio "
                          "y planchas estimadas."],
        ["<b>Accesorios</b>", "Costo y qué kit se aplicó."],
        ["<b>Medida de hoja</b>", "Ancho y alto de hoja que resultan de las fórmulas. "
                                  "Es el dato que usa el vidriero."],
    ], anchos=[24, 76])
    s += h2("Las tres pestañas")
    s += vinetas([
        "<b>Perfiles</b> — cada corte con su código, función, largo en milímetros, "
        "cantidad de piezas y peso. Es la lista para la sierra.",
        "<b>Vidrios</b> — medida de cada paño, cantidad y metros cuadrados.",
        "<b>Accesorios</b> — cada accesorio con su cantidad y precio.",
    ])
    s += aviso("Los largos de corte salen de las fórmulas cargadas en el sistema. "
               "<b>Verificalos contra la tabla del fabricante de tu línea antes de cortar "
               "material.</b>")
    s += [PageBreak()]

    # ================================================================ 5
    s += h1("Los papeles del taller")
    s += p("El botón <b>Papeles de taller</b>, arriba de la lista de aberturas, genera de "
           "una vez los tres PDF que se imprimen y bajan al taller. Se guardan en una "
           "carpeta con el número del presupuesto, dentro de la carpeta de PDF, y el "
           "programa te ofrece abrirla.")
    s += tabla(["Archivo", "Qué trae"], [
        ["<b>Corte.pdf</b>", "El diagrama de corte de cada barra y el plano de corte del "
                             "vidrio sobre la plancha."],
        ["<b>Materiales.pdf</b>", "Todo lo que hay que tener a mano, separado por rubro: "
                                  "perfiles, vidrios y accesorios."],
        ["<b>Etiquetas.pdf</b>", "Rótulos para pegar en cada pieza cortada, con la "
                                 "posición, el código y la medida."],
    ], anchos=[24, 76])

    s += h2("Corte de perfiles")
    s += p("Cada barra está dibujada <b>a escala</b>. Las piezas van en el orden en que "
           "conviene cortarlas, de mayor a menor, y lo pintado al final es el recorte que "
           "sobra. Debajo de cada perfil dice cuántas barras hacen falta y qué porcentaje "
           "se tira.")
    s += p("Las aberturas se optimizan <b>todas juntas</b>, no una por una. Por eso el "
           "diagrama puede mostrar en la misma barra cortes de posiciones distintas: es "
           "justamente lo que hace que se compren menos barras.")
    s += aviso("Los largos salen de las fórmulas que vos cargaste. <b>Verificalos contra la "
               "tabla del fabricante de tu línea antes de cortar material.</b>")

    s += h2("Corte de vidrio")
    s += p("El vidrio no se compra por metro cuadrado suelto: viene en <b>planchas de "
           "medida fija</b>, y lo que se paga es la plancha entera. Esta sección acomoda "
           "los paños de todo el presupuesto adentro de las planchas y las dibuja a escala, "
           "una por una, con la medida escrita adentro de cada paño y la posición a la que "
           "pertenece.")
    s += vinetas([
        "Los paños se acomodan en <b>franjas horizontales</b>, porque el vidrio se corta de "
        "lado a lado: cada raya atraviesa la plancha entera. Un dibujo más apretado daría "
        "cortes que en la mesa no se pueden hacer.",
        "Los que dicen <b>«90°»</b> hay que cortarlos girados respecto de como figuran en "
        "la lista.",
        "Arriba de cada tipo de vidrio dice cuántas planchas hacen falta y qué porcentaje "
        "se aprovecha. Lo rosado es el sobrante.",
        "Cada tipo de vidrio va por separado: un float 4 y un DVH no se mezclan en la misma "
        "plancha, son productos distintos.",
    ])
    s += imagen("corte_vidrio.png",
                "Una plancha de 3210 × 2250 con diez paños acomodados: 72 % aprovechado. "
                "Lo rosado es el sobrante; los cuatro de la izquierda van girados.")
    s += p("La medida de la plancha de cada vidrio se carga en <b>Materiales y Costos → "
           "Vidrios</b>. Si un paño no entra ni girándolo, el PDF lo lista aparte: eso hay "
           "que pedirlo en medida especial.")
    s += tip("El porcentaje de aprovechamiento es la cuenta honesta de cuánto vidrio de lo "
             "que comprás termina en la obra. Con pocas aberturas va a ser bajo y no hay "
             "nada que arreglar: el sobrante de una plancha es sobrante real, y lo que "
             "queda sirve para el próximo trabajo.")

    s += h2("Materiales y etiquetas")
    s += p("<b>Materiales.pdf</b> es la lista de compras y de preparación: perfiles con sus "
           "cortes, vidrios con sus medidas y accesorios con sus cantidades, cada rubro en "
           "su propia sección.")
    s += p("<b>Etiquetas.pdf</b> trae un rótulo por pieza para pegar sobre el material "
           "cortado. Las de perfil van en gris y las de vidrio en verde, así no se mezclan "
           "en la mesa.")
    s += aviso("Los papeles se generan con lo que hay <b>en pantalla</b> en ese momento, "
               "esté guardado o no. Si después cambiás una medida, la hoja que ya está en "
               "el taller no se modifica sola: volvé a generarla.")
    s += [PageBreak()]

    # ================================================================ 6
    s += h1("Historial de presupuestos")
    s += imagen("presupuestos.png", "Pantalla de Presupuestos con el resumen comercial "
                                    "arriba.")
    s += p("Los cuatro recuadros superiores resumen la situación comercial: cuántos "
           "presupuestos hay listados, por cuánto dinero, cuántos fueron enviados y "
           "cuántos se aprobaron o facturaron.")
    s += h2("Buscar")
    s += p("El buscador filtra por número, cliente u obra mientras escribís. La lista "
           "desplegable de al lado filtra por estado.")
    s += h2("Acciones")
    s += tabla(["Botón", "Qué hace"], [
        ["<b>Abrir</b>", "Carga el presupuesto en la pantalla de Cotización. Los precios "
                         "se <b>recalculan con las listas vigentes</b>."],
        ["<b>Duplicar</b>", "Crea una copia con número nuevo y fecha de hoy, en estado "
                            "Borrador. Ideal para un cliente que vuelve."],
        ["<b>Cambiar estado</b>", "Marca el presupuesto como Enviado, Aprobado, Rechazado "
                                  "o Facturado."],
        ["<b>Reimprimir PDF</b>", "Vuelve a generar el PDF del presupuesto."],
        ["<b>Eliminar</b>", "Borra el presupuesto y sus ítems. No se puede deshacer."],
    ], anchos=[24, 76])
    s += aviso("Al reabrir un presupuesto viejo los precios se actualizan a los valores de "
               "hoy. Si subiste las listas, el total va a ser distinto del que le pasaste "
               "al cliente en su momento. La barra inferior te lo avisa.")
    s += [PageBreak()]

    # ================================================================ 6
    s += h1("Materiales y costos")
    s += imagen("materiales.png", "Pantalla de Materiales y Costos.")
    s += p("Acá se carga todo lo que el sistema usa para calcular. Está dividido en ocho "
           "pestañas. En todas se trabaja igual: <b>+ Nuevo</b> para agregar, "
           "<b>Editar</b> (o doble clic) para modificar y <b>Eliminar</b> para borrar.")

    s += h2("Los catálogos que vienen cargados")
    s += p("El programa trae adentro los dos catálogos de <b>MDT — Metales del Talar</b>, "
           "con la perfilería y las medidas de corte que publica el fabricante:")
    s += tabla(["", "Sistema Clásica", "Sistema Actual"], [
        ["<b>Perfiles con su peso por metro</b>", "142", "106"],
        ["<b>Tipologías listas para usar</b>", "14", "16"],
        ["<b>Medidas de corte</b>", "108", "255"],
    ], anchos=[46, 27, 27])
    s += p("Aparecen solos la primera vez que abrís el programa, y no pisan nada de lo que "
           "tengas cargado. Los perfiles salen del <i>Listado de Perfiles</i> de cada "
           "catálogo y las medidas de corte de las tablas <i>Dimensiones de corte de "
           "perfiles</i>, copiadas tal cual las publica el fabricante.")
    s += aviso("<b>Los precios vienen todos en $0.</b> El catálogo del fabricante no los "
               "publica y cada carpintería compra a su lista, así que lo primero es cargar "
               "el precio del kilo por color, el del m² de cada vidrio y el de cada "
               "accesorio. Los kits sí vienen completos: en cuanto pongas los precios, el "
               "presupuesto sale entero.")
    s += h3("Dos cosas sobre las medidas de corte")
    s += pasos([
        "Varias tablas del catálogo traen las <b>jambas con la medida del ancho</b> y el "
        "umbral con la del alto, al revés de como el mismo catálogo da el premarco dos "
        "filas más arriba. Están cargadas corregidas —jamba del alto, umbral y dintel del "
        "ancho— y el renglón lo dice en la columna Aclaración.",
        "El catálogo lista <b>alternativas en la misma tabla</b>: marco recto, curvo y de "
        "75 mm uno debajo del otro, o el perfil para vidrio simple junto al de DVH. Como "
        "se usa uno solo, queda activa la primera y las demás quedan con <b>cantidad 0</b> "
        "y una nota que dice de qué son alternativa. Si usás una de esas, ponele la "
        "cantidad en Fórmulas de despiece.",
    ])
    s += aviso("Verificá los largos contra la tabla del fabricante antes de cortar "
               "material. El programa calcula con lo que está cargado.", "Siempre")

    s += h2("Líneas y precios")
    s += p("A la izquierda, las líneas de aluminio. A la derecha, los colores y precios de "
           "la línea que tengas seleccionada.")
    s += campos([
        ["<b>Modo de costeo</b>", "<b>kg</b>: el aluminio se cobra por el peso real del "
                                  "despiece (recomendado). <b>m2</b>: se cobra por metro "
                                  "cuadrado de abertura."],
        ["<b>Precio del aluminio</b>", "Precio por kilo. Se usa en modo <b>kg</b>."],
        ["<b>Precio de perfil por m²</b>", "Se usa en modo <b>m2</b>."],
    ])
    s += tip("Podés tener unas líneas en modo <b>kg</b> y otras en <b>m2</b> al mismo "
             "tiempo. Sirve para ir migrando de a poco: mientras cargás los perfiles de "
             "una línea nueva, la dejás en m2 y ya podés cotizarla.")

    s += h2("Perfiles")
    s += p("Elegí primero la línea arriba. Cada perfil necesita su <b>peso nominal en "
           "Kg / m</b>, que es el dato del catálogo del extrusor y lo que define el costo "
           "del aluminio en modo kg.")

    s += h2("Vidrios")
    s += campos([
        ["<b>Denominación</b>", "Nombre visible: Float 4mm, DVH 4/9/4, Laminado 3+3…"],
        ["<b>Precio</b>", "Precio por metro cuadrado."],
        ["<b>Plancha base</b>", "Medidas de la plancha con la que trabajás."],
        ["<b>Desperdicio</b>", "Porcentaje de recorte que se suma al costo."],
    ])

    s += h2("Accesorios")
    s += p("Ruedas, cierres, felpas, burletes, escuadras. Cada uno con su unidad "
           "(<b>u</b> unidades, <b>jgo</b> juego, <b>ml</b> metro lineal, <b>m2</b>) y su "
           "precio unitario.")

    s += h2("Kits de accesorios")
    s += p("Un kit agrupa los accesorios que lleva una tipología en una línea. A la "
           "izquierda se crean los kits; a la derecha se carga su composición.")
    s += p("La <b>cantidad</b> de cada accesorio puede ser un número o una fórmula. Por "
           "ejemplo <font face='Courier'>2*N</font> significa “dos por cada hoja”.")

    s += h2("Tipologías")
    s += campos([
        ["<b>Código</b>", "Identificador corto (COR2, BAT1, FIJO). Vincula las fórmulas "
                          "y los kits."],
        ["<b>Hojas por defecto</b>", "Cuántas hojas propone al elegir esta tipología."],
        ["<b>Dibujo en el PDF</b>", "Qué esquema se dibuja: corrediza, fijo, batiente, "
                                    "banderola o puerta batiente."],
        ["<b>Fabricación por m²</b>", "Horas de taller por metro cuadrado. Se usa para "
                                      "estimar la mano de obra automáticamente."],
        ["<b>Admite mosquitero / premarco</b>", "Si está desactivado, esas opciones "
                                                "aparecen bloqueadas al cargar el ítem."],
    ])

    s += h2("Opciones de la tipología")
    s += p("A la derecha de la lista de tipologías hay un panel para declarar las "
           "<b>opciones</b> que esa tipología ofrece al cargar una abertura. Cada opción "
           "tiene una <b>clave</b>, que es el nombre con el que se la escribe en una "
           "fórmula, y un <b>tipo</b>:")
    s += tabla(["Tipo", "Qué muestra y qué vale"], [
        ["<b>bool</b>", "Una casilla. Vale 1 si está tildada y 0 si no. Para cosas que "
                        "están o no están: premarco, refuerzo, mosquitero."],
        ["<b>numero</b>", "Un campo numérico con mínimo y máximo. Para una medida que "
                          "cambia de obra en obra, como el alto de un paño fijo."],
        ["<b>opcion</b>", "Una lista desplegable. Cada opción tiene el texto que se lee y "
                          "el número que toma en la fórmula."],
        ["<b>accesorio</b>", "Una lista con accesorios del catálogo. Sirve para elegir "
                             "cuál entra al kit: rueda simple o doble, cierre de embutir o "
                             "multipunto."],
    ], anchos=[18, 82])
    s += h3("Cómo se usa una opción en una fórmula")
    s += p("La clave se escribe igual que <font face='Courier'>A</font>, "
           "<font face='Courier'>H</font> o <font face='Courier'>N</font>:")
    s += tabla(["Fórmula", "Qué hace"], [
        ["<font face='Courier'>si(PREMARCO, H + 36, 0)</font>",
         "Si la casilla está tildada corta el premarco; si no, el largo da cero y la pieza "
         "no aparece en el despiece."],
        ["<font face='Courier'>si(ALTO_FIJO &gt; 0, A - 100, 0)</font>",
         "El travesaño de división sólo se corta cuando hay paño fijo."],
        ["<font face='Courier'>H - ALTO_FIJO - 40</font>",
         "El alto de la hoja descuenta el paño fijo de abajo."],
    ], anchos=[36, 64])
    s += tip("Las opciones con clave <font face='Courier'>PREMARCO</font> y "
             "<font face='Courier'>MOSQUITERO</font> no aparecen en el recuadro de la abertura: "
             "las deciden las casillas <b>Incluye premarco</b> e <b>Incluye mosquitero</b>, que "
             "son las que imprimen el presupuesto y la orden de trabajo. Así no hay dos "
             "casillas para lo mismo.")
    s += h3("Cómo se usa una opción de tipo accesorio")
    s += pasos([
        "Declarás la opción con tipo <b>accesorio</b> y en el campo <b>Opciones</b> ponés "
        "los códigos elegibles separados por coma: <font face='Courier'>R48, R49</font>. "
        "Vacío ofrece todo el catálogo, que es incómodo con trescientos accesorios.",
        "Vas a <b>Kits de accesorios</b>, elegís el kit y el renglón de la rueda, y en "
        "<b>Lo elige la opción</b> ponés la clave que declaraste.",
        "Listo: al cargar la abertura aparece la lista, y el kit cobra y descuenta el "
        "accesorio que se haya elegido. El que quedó puesto en el renglón pasa a ser el "
        "valor por defecto.",
    ])
    s += aviso("Si cambiás la <b>clave</b> de una opción que ya se usa en fórmulas, el "
               "programa te avisa y te ofrece renombrarla también ahí. Si decís que no, no "
               "se guarda nada: renombrar de un solo lado dejaría las fórmulas apuntando a "
               "un nombre que ya no existe.")

    s += h2("Fórmulas de despiece")
    s += p("Es el corazón del cálculo: define, para cada tipología y línea, qué perfiles se "
           "cortan y de qué largo. Elegí arriba la <b>tipología</b> y la <b>línea</b>.")
    s += h3("Variables que se pueden usar")
    s += tabla(["Variable", "Significado"], [
        ["<font face='Courier'>A</font>", "Ancho de la abertura, en mm"],
        ["<font face='Courier'>H</font>", "Alto de la abertura, en mm"],
        ["<font face='Courier'>N</font>", "Cantidad de hojas"],
        ["<font face='Courier'>AH</font> / <font face='Courier'>HH</font>",
         "Ancho y alto de hoja (sólo en las fórmulas de vidrio)"],
        ["<font face='Courier'>PERIM</font>", "Perímetro: 2 × (A + H)"],
        ["<font face='Courier'>M2</font>", "Superficie en metros cuadrados"],
    ], anchos=[22, 78])
    s += h3("Ejemplos")
    s += tabla(["Fórmula", "Qué significa"], [
        ["<font face='Courier'>A</font>", "El largo del perfil es igual al ancho"],
        ["<font face='Courier'>H - 48</font>", "El alto menos 48 mm"],
        ["<font face='Courier'>(A + 26) / N</font>", "Ancho más 26, dividido por la "
                                                     "cantidad de hojas"],
        ["<font face='Courier'>2*N</font>", "En cantidad de piezas: dos por hoja"],
    ], anchos=[30, 70])
    s += h3("Botones de esta pestaña")
    s += tabla(["Botón", "Qué hace"], [
        ["<b>Probar despiece…</b>", "Calcula un ejemplo con las medidas que le des, sin "
                                    "tocar ningún presupuesto. Usalo siempre después de "
                                    "cambiar una fórmula."],
        ["<b>Fórmulas de vidrio…</b>", "Define cuánto se descuenta del ancho y alto de "
                                       "hoja para obtener la medida del vidrio."],
        ["<b>Copiar a otra línea…</b>", "Duplica todo el juego de fórmulas a otra línea, "
                                        "para después ajustar sólo las diferencias."],
    ], anchos=[26, 74])
    s += aviso("Después de tocar una fórmula, usá siempre <b>Probar despiece</b> y "
               "compará el resultado con la tabla de tu proveedor. Un error acá se "
               "traslada a todos los presupuestos.")

    s += h2("Costos operativos")
    s += p("Valores generales: hora-hombre, cantidad de operarios, costos de logística, "
           "premarco, mosquitero —y su tela, para las líneas que cortan el mosquitero con "
           "sus perfiles—, margen de ganancia, IVA y porcentajes de desperdicio. "
           "Son los valores que el programa propone al abrir un presupuesto nuevo.")
    s += tip("Poniendo el parámetro <font face='Courier'>incluir_despiece_pdf</font> en "
             "<b>1</b>, el PDF suma un anexo técnico con el corte de cada abertura y un "
             "consolidado de materiales para compras.")
    s += [PageBreak()]

    # ================================================================ 7
    s += h1("Inventario")
    s += p("La pestaña <b>Inventario</b> lleva la cuenta de lo que hay en depósito: barras "
           "de perfil, metros cuadrados de vidrio y accesorios. Sirve para saber, antes de "
           "prometer una entrega, qué hay que comprar.")
    s += aviso("El inventario viene <b>desactivado</b>. Mientras lo esté, la pantalla te "
               "muestra un botón <b>Activar ahora</b>; el resto del programa funciona "
               "igual, simplemente no lleva cuenta de las existencias.")

    s += h2("Dar de alta un artículo")
    s += p("El inventario no arranca con todo el catálogo adentro: se incorpora sólo lo que "
           "de verdad tenés en depósito. Con <b>Alta de artículo</b> elegís el tipo "
           "(perfil, vidrio o accesorio), escribís el código y ponés la cantidad inicial.")
    s += campos([
        ["<b>Cantidad</b>", "Lo que hay hoy. Los perfiles se cuentan en <b>barras</b> "
                            "enteras, el vidrio en <b>m²</b> y los accesorios en su propia "
                            "unidad (unidades, metros lineales)."],
        ["<b>Mínimo</b>", "Punto de reposición. Por debajo de ese valor el artículo queda "
                          "marcado y aparece con el filtro <b>Sólo bajo mínimo</b>."],
    ])

    s += h2("Movimientos")
    s += p("El saldo de un artículo no se edita a mano: se mueve con documentos, y cada "
           "movimiento queda asentado con su fecha, su motivo y su nota. Así siempre se "
           "puede reconstruir por qué el saldo es el que es.")
    s += tabla(["Botón", "Cuándo se usa"], [
        ["<b>Ingreso</b>", "Llegó material. Se anota el remito del proveedor."],
        ["<b>Egreso</b>", "Salió material por fuera de una orden de trabajo: una "
                          "reparación, una venta suelta, un descarte."],
        ["<b>Recuento</b>", "Contaste el depósito y no coincide. Se pone lo que contaste y "
                            "la diferencia queda asentada como ajuste."],
        ["<b>Mínimo</b>", "Cambia el punto de reposición del artículo seleccionado."],
        ["<b>Recalcular saldos</b>", "Reconstruye todos los saldos sumando los "
                                     "movimientos. Es una red de seguridad; normalmente no "
                                     "hace falta."],
    ], anchos=[24, 76])

    s += h2("Cuándo se descuenta")
    s += tip("El stock se descuenta al <b>emitir la orden de trabajo</b>, no al aprobar el "
             "presupuesto. Un presupuesto aprobado todavía no consumió nada; lo que saca "
             "material del depósito es mandar a fabricar.")
    s += p("Al emitir la OT el programa compara lo que hace falta contra lo que hay y te "
           "muestra el faltante artículo por artículo, antes de descontar. Los perfiles se "
           "descuentan en <b>barras enteras</b> —que es lo que sale del depósito— y el "
           "vidrio en m² con desperdicio, que es lo que factura la vidriería.")
    s += [PageBreak()]

    s += h1("Órdenes de trabajo")
    s += p("La orden de trabajo es la hoja que baja al taller: qué hay que fabricar, para "
           "qué cliente y para cuándo. Se emite desde el presupuesto con <b>Emitir OT</b> y "
           "después se sigue desde la pestaña <b>Órdenes de trabajo</b>.")

    s += h2("Emitir")
    s += pasos([
        "Abrí el presupuesto y hacé clic en <b>Emitir OT</b>.",
        "El programa te muestra qué material hace falta y qué hay en depósito. Si algo no "
        "alcanza, te lo dice antes de seguir.",
        "Al confirmar se crea la orden, se descuenta el stock y queda en estado "
        "<b>Producción</b>.",
    ])

    s += h2("Seguimiento")
    s += tabla(["Botón", "Qué hace"], [
        ["<b>Abrir carpeta</b>", "Abre la carpeta con los PDF de esa orden."],
        ["<b>Reimprimir</b>", "Vuelve a generar la hoja de la orden."],
        ["<b>Diagrama de corte</b>", "Genera el diagrama de corte de esa orden, con las "
                                     "barras y el plano de vidrio."],
        ["<b>En fabricación / Terminada / Entregada</b>",
         "Marcan el avance. El filtro de arriba deja ver sólo las de un estado."],
        ["<b>Anular</b>", "Da de baja la orden. El material descontado <b>vuelve al "
                          "depósito</b>."],
    ], anchos=[28, 72])
    s += aviso("La orden guarda las medidas y los precios <b>del momento en que se "
               "emitió</b>. Si después cambiás una fórmula o una lista de precios, la hoja "
               "que está en el taller no se modifica: es un documento de producción, no un "
               "cálculo en vivo.")
    s += [PageBreak()]

    s += h1("Datos de tu empresa")
    s += p("Lo que se carga acá sale impreso en el encabezado y el pie de todos los "
           "presupuestos.")
    s += h2("Datos del emisor")
    s += p("Nombre o razón social, CUIT, dirección, teléfono, email, sitio web y "
           "<b>logo</b>. El logo se busca con el botón <b>Buscar…</b> y conviene que sea "
           "un PNG o JPG horizontal.")
    s += h2("Numeración de presupuestos")
    s += campos([
        ["<b>Prefijo</b>", "Las letras del principio: PRES, PPTO, COT…"],
        ["<b>Próximo número</b>", "El número que va a llevar el siguiente presupuesto."],
        ["<b>Dígitos</b>", "Con cuántos ceros se rellena. Con 4: PRES-0001."],
        ["<b>Validez por defecto</b>", "Días de validez que se proponen."],
    ])
    s += p("Debajo se ve una <b>vista previa</b> de cómo va a quedar el número.")
    s += h2("Términos y condiciones")
    s += p("Se imprimen al pie del presupuesto, antes de las firmas: forma de pago, "
           "vigencia de los precios, plazos.")
    s += h2("Observaciones generales precargadas")
    s += p("Se cargan solas en cada presupuesto nuevo, y se pueden editar caso por caso.")
    s += aviso("Los cambios recién quedan guardados cuando hacés clic en "
               "<b>Guardar configuración</b>.")
    s += [PageBreak()]

    # ================================================================ 8
    s += h1("Ajustes")
    s += imagen("ajustes.png", "Pantalla de Ajustes.")
    s += h2("Apariencia")
    s += p("Elegí el tema (Claro o Silver) con el botón <b>Usar</b>. El "
           "<b>tamaño de la interfaz</b> (de 90 % a 125 %) agranda letras y controles, y "
           "se aplica al reiniciar. <b>Abrir maximizado</b> arranca a pantalla completa.")
    s += h2("Licencia")
    s += p("Muestra el estado de la suscripción, el código de este equipo y hasta cuándo "
           "está vigente.")
    s += tabla(["Botón", "Qué hace"], [
        ["<b>Activar / renovar suscripción…</b>", "Abre la ventana para pegar la clave "
                                                  "nueva o cargar un archivo .lic."],
        ["<b>Copiar código de equipo</b>", "Copia el código para mandárselo al proveedor."],
        ["<b>Datos para soporte</b>", "Copia un resumen técnico del equipo. Útil si tenés "
                                      "que reportar un problema."],
    ], anchos=[32, 68])

    s += h2("Datos y respaldos")
    s += p("Muestra dónde guarda el programa tu información. <b>Estas carpetas no se tocan "
           "nunca al instalar una actualización.</b>")
    s += tabla(["Botón", "Qué hace"], [
        ["<b>Crear copia de seguridad</b>", "Guarda una copia de la base de datos. "
                                            "Se conservan las últimas 10."],
        ["<b>Abrir carpeta de datos</b>", "Abre en el Explorador la carpeta con la base "
                                          "de datos y las copias."],
        ["<b>Abrir carpeta de PDF</b>", "Abre la carpeta donde se guardan los "
                                        "presupuestos exportados."],
        ["<b>Restaurar desde una copia…</b>", "Vuelve a un respaldo anterior. Antes guarda "
                                              "una copia del estado actual y cierra el "
                                              "programa."],
    ], anchos=[30, 70])
    s += tip("Hacé una copia de seguridad antes de una actualización masiva de precios o "
             "de cualquier cambio grande en las listas.")

    s += h2("Versión y actualizaciones")
    s += p("Muestra la versión instalada. Cuando tu proveedor te mande una versión nueva, "
           "usá <b>Instalar actualización desde archivo .zip</b>. El programa hace una "
           "copia de seguridad, reemplaza sólo el código y deja intactos tus "
           "presupuestos, listas de precios y configuración.")
    s += [PageBreak()]

    # ================================================================ 9
    s += h1("Cómo se muestran los números")
    s += p("Todas las cifras siguen la misma convención: <b>punto para los miles y coma "
           "para los decimales</b>. Cada campo muestra su unidad adentro, así no hay que "
           "adivinar en qué unidad se está cargando.")
    s += tabla(["Se muestra así", "Qué es"], [
        ["<font face='Courier'>$ 125.400,50</font>", "Dinero"],
        ["<font face='Courier'>8 hrs</font> · <font face='Courier'>2,5 hrs</font>",
         "Horas de trabajo"],
        ["<font face='Courier'>14,2 Kgs</font>", "Peso de material"],
        ["<font face='Courier'>0,850 Kg / m</font>", "Peso por metro de perfil"],
        ["<font face='Courier'>4 uds.</font>", "Cantidad de piezas"],
        ["<font face='Courier'>1200 x 1500 mm</font>", "Medidas (sin punto de miles)"],
        ["<font face='Courier'>2,46 m²</font>", "Superficie"],
        ["<font face='Courier'>21 %</font>", "Porcentajes"],
    ], anchos=[35, 65])
    s += tip("Al escribir podés usar el formato que te resulte cómodo: "
             "<font face='Courier'>1500</font>, <font face='Courier'>1.500</font> o "
             "<font face='Courier'>$ 1.500,00</font> se entienden todos como mil "
             "quinientos. Al salir del campo, el número se acomoda solo.")

    s += h2("Atajos de teclado")
    s += tabla(["Atajo", "Qué hace"], [
        ["<b>Ctrl + N</b>", "Nuevo presupuesto"],
        ["<b>Ctrl + S</b>", "Guardar"],
        ["<b>Ctrl + P</b>", "Exportar a PDF"],
        ["<b>Doble clic</b>", "Editar el ítem o abrir el presupuesto seleccionado"],
        ["<b>Enter</b>", "Confirmar el valor de un campo numérico"],
        ["<b>Esc</b>", "Cerrar la ventana que esté abierta"],
    ], anchos=[22, 78])
    s += [PageBreak()]

    # ================================================================ 10
    s += h1("Problemas frecuentes")
    s += tabla(["Situación", "Qué hacer"], [
        ["Windows muestra un aviso de seguridad al abrir",
         "Hacé clic en <b>Más información → Ejecutar de todas formas</b>. Pasa porque el "
         "programa no tiene firma digital comercial; no es un virus."],
        ["Dice que la licencia es de otro equipo",
         "La clave sirve sólo para la PC donde se generó. Mandale a tu proveedor el código "
         "que muestra <b>esta</b> computadora."],
        ["Dice que la fecha del equipo está atrasada",
         "Corregí la fecha y hora de Windows y activá <b>Establecer la hora "
         "automáticamente</b>. Después volvé a abrir el programa."],
        ["La clave no se acepta",
         "Copiala completa, desde <font face='Courier'>COTIZ-</font> hasta el último "
         "carácter. Si la mandaron por WhatsApp, fijate que no haya quedado cortada."],
        ["El costo del aluminio da cero",
         "Falta cargar las fórmulas de despiece de esa tipología y línea, o el peso por "
         "metro de los perfiles. Ver el capítulo <i>Materiales y Costos</i>."],
        ["Los precios de un presupuesto viejo cambiaron",
         "Es lo esperado: al reabrirlo se recalcula con las listas de hoy. Si necesitás el "
         "original, usá el PDF que habías generado."],
        ["No encuentro los PDF que generé",
         "<b>Ajustes → Abrir carpeta de PDF</b>."],
        ["Quiero volver atrás un cambio grande",
         "<b>Ajustes → Restaurar desde una copia…</b> y elegí un respaldo anterior."],
        ["Cambié de computadora",
         "Instalá el programa en la PC nueva, pedile a tu proveedor una clave para el "
         "código de equipo nuevo, y copiá la carpeta de datos de la PC vieja."],
    ], anchos=[32, 68])

    s += [Spacer(1, 10)]
    s += aviso("Antes de usar el sistema en producción, verificá contra el catálogo de tu "
               "proveedor los <b>precios por kilo</b>, los <b>pesos por metro</b> de cada "
               "perfil y las <b>deducciones de las fórmulas</b>. Los valores que vienen "
               "cargados de fábrica son orientativos.", "Importante")

    cierre = Table([[Paragraph(
        "<para align='center'><font size='9' color='#5B6B7C'>"
        f"Manual de Usuario · Cotizador de Aberturas de Aluminio · versión {version}<br/>"
        f"Generado el {hoy}"
        "</font></para>", EST["p"])]], colWidths=[ANCHO])
    cierre.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, -1), 0.6, GRIS_LINEA),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
    ]))
    s += [Spacer(1, 16), cierre]
    return s


def generar(ruta_salida: Path, estilo_portada: str = "vector") -> Path:
    _contador["h1"] = 0
    _contador["h2"] = 0
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    doc = Documento(ruta_salida, estilo_portada=estilo_portada)
    doc.multiBuild(construir())
    return ruta_salida


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera el manual de usuario en PDF")
    parser.add_argument("--salida", help="Ruta del PDF a generar")
    args = parser.parse_args()

    destino = Path(args.salida) if args.salida else \
        rutas.SALIDAS / "Manual_Cotizador_Aberturas.pdf"
    generar(destino)

    tam = destino.stat().st_size / 1024
    print(f"Manual generado:\n  {destino}\n  {tam:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
