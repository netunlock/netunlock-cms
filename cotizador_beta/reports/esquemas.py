"""
Esquemas vectoriales de cada tipología para el PDF.

Se dibujan con ReportLab Graphics (sin imágenes externas), respetando la
proporción real A x H de la abertura, con la simbología habitual de plano de
carpintería: flechas para corredizas, diagonales hacia la bisagra para hojas de
abrir, triángulo para banderola.
"""

from __future__ import annotations

from reportlab.graphics.shapes import Drawing, Group, Line, PolyLine, Rect, String
from reportlab.lib import colors

TRAZO = colors.HexColor("#1F2933")
RELLENO_VIDRIO = colors.HexColor("#E8F1F5")
SIMBOLO = colors.HexColor("#5B6B7A")


def _encuadrar(ancho_mm: float, alto_mm: float, ancho_max: float, alto_max: float):
    """Devuelve (w, h) respetando la proporción real dentro del recuadro dado."""
    ancho_mm = max(1.0, float(ancho_mm))
    alto_mm = max(1.0, float(alto_mm))
    escala = min(ancho_max / ancho_mm, alto_max / alto_mm)
    return ancho_mm * escala, alto_mm * escala


def _flecha(d, x0, y0, x1, y1, color=SIMBOLO):
    d.add(Line(x0, y0, x1, y1, strokeColor=color, strokeWidth=0.8))
    dx = 3 if x1 > x0 else -3
    d.add(Line(x1, y1, x1 - dx, y1 + 2, strokeColor=color, strokeWidth=0.8))
    d.add(Line(x1, y1, x1 - dx, y1 - 2, strokeColor=color, strokeWidth=0.8))


def _corrediza(d, x, y, w, h, hojas):
    n = max(1, hojas)
    paso = w / n
    for i in range(n):
        px = x + i * paso
        d.add(Rect(px + 1.5, y + 1.5, paso - 3, h - 3, fillColor=RELLENO_VIDRIO,
                   strokeColor=TRAZO, strokeWidth=0.6))
        cy = y + h / 2
        # Las hojas pares corren hacia la izquierda, las impares hacia la derecha
        if i % 2 == 0:
            _flecha(d, px + paso * 0.65, cy, px + paso * 0.30, cy)
        else:
            _flecha(d, px + paso * 0.35, cy, px + paso * 0.70, cy)


def _fijo(d, x, y, w, h, hojas):
    d.add(Rect(x + 2, y + 2, w - 4, h - 4, fillColor=RELLENO_VIDRIO,
               strokeColor=TRAZO, strokeWidth=0.6))
    d.add(String(x + w / 2, y + h / 2 - 3, "FIJO", fontName="Helvetica", fontSize=6,
                 fillColor=SIMBOLO, textAnchor="middle"))


def _batiente(d, x, y, w, h, hojas):
    n = max(1, hojas)
    paso = w / n
    for i in range(n):
        px = x + i * paso
        d.add(Rect(px + 1.5, y + 1.5, paso - 3, h - 3, fillColor=RELLENO_VIDRIO,
                   strokeColor=TRAZO, strokeWidth=0.6))
        # Vértice de las diagonales del lado de la bisagra
        bisagra_izq = (i % 2 == 0 and n > 1) or n == 1
        vx = px + 2 if bisagra_izq else px + paso - 2
        d.add(PolyLine([px + paso - 2 if bisagra_izq else px + 2, y + h - 2,
                        vx, y + h / 2,
                        px + paso - 2 if bisagra_izq else px + 2, y + 2],
                       strokeColor=SIMBOLO, strokeWidth=0.7))


def _banderola(d, x, y, w, h, hojas):
    d.add(Rect(x + 2, y + 2, w - 4, h - 4, fillColor=RELLENO_VIDRIO,
               strokeColor=TRAZO, strokeWidth=0.6))
    d.add(PolyLine([x + 3, y + 3, x + w / 2, y + h - 3, x + w - 3, y + 3],
                   strokeColor=SIMBOLO, strokeWidth=0.7))


def _puerta_batiente(d, x, y, w, h, hojas):
    _batiente(d, x, y, w, h, max(1, hojas))
    # Manija indicativa
    d.add(Line(x + w - 8, y + h * 0.45, x + w - 8, y + h * 0.55,
               strokeColor=TRAZO, strokeWidth=1.4))


DIBUJANTES = {
    "corrediza": _corrediza,
    "fijo": _fijo,
    "batiente": _batiente,
    "banderola": _banderola,
    "puerta_batiente": _puerta_batiente,
}


def dibujo_de_abertura(db, tipologia_codigo: str, ancho_mm: float, alto_mm: float,
                       hojas: int = 2, ancho_max: float = 78, alto_max: float = 62,
                       con_cotas: bool = True):
    """Imagen cargada por el usuario si la hay; si no, el esquema vectorial.

    Es el punto único por el que pasan el PDF del presupuesto y el de la orden de
    trabajo, para que la abertura se vea igual en los dos papeles.

    La imagen se escala respetando su proporción —un dibujo apaisado no puede
    salir estirado— y si el archivo se perdió (se movió la base a otra PC, se
    borró la carpeta de datos) cae al esquema en vez de romper el PDF.
    """
    tip = db.tipologia(tipologia_codigo) if db and tipologia_codigo else None

    nombre = ""
    if tip is not None:
        try:
            nombre = tip["imagen"] or ""
        except (IndexError, KeyError):     # base todavía sin migrar a v4
            nombre = ""

    if nombre:
        from core import imagenes

        ruta = imagenes.ruta_de(nombre)
        if ruta:
            try:
                from reportlab.lib.utils import ImageReader
                from reportlab.platypus import Image

                ancho_px, alto_px = ImageReader(str(ruta)).getSize()
                escala = min(ancho_max / ancho_px, alto_max / alto_px)
                return Image(str(ruta), width=ancho_px * escala, height=alto_px * escala)
            except Exception:
                pass                        # formato ilegible: seguimos con el esquema

    clave = "corrediza"
    if tip is not None:
        clave = tip["esquema"] or "corrediza"
    return esquema(clave, ancho_mm, alto_mm, hojas,
                   ancho_max=ancho_max, alto_max=alto_max, con_cotas=con_cotas)


def esquema(tipo_esquema: str, ancho_mm: float, alto_mm: float, hojas: int = 2,
            ancho_max: float = 78, alto_max: float = 62, con_cotas: bool = True) -> Drawing:
    """Devuelve un ``Drawing`` de ReportLab listo para insertar en una tabla."""
    margen_cotas = 12 if con_cotas else 2
    w, h = _encuadrar(ancho_mm, alto_mm, ancho_max - margen_cotas, alto_max - margen_cotas)

    d = Drawing(ancho_max, alto_max)
    x = (ancho_max - w) / 2 + (margen_cotas / 2 if con_cotas else 0)
    y = (alto_max - h) / 2 + (margen_cotas / 2 if con_cotas else 0)

    # Marco exterior
    d.add(Rect(x, y, w, h, fillColor=colors.white, strokeColor=TRAZO, strokeWidth=1.1))

    dibujar = DIBUJANTES.get((tipo_esquema or "corrediza").lower(), _corrediza)
    dibujar(d, x, y, w, h, hojas)

    if con_cotas:
        d.add(String(x + w / 2, y - 8, f"{ancho_mm:.0f}", fontName="Helvetica", fontSize=5.5,
                     fillColor=SIMBOLO, textAnchor="middle"))
        # String no admite rotación propia: se envuelve en un Group transformado
        etiqueta_alto = Group(String(0, 0, f"{alto_mm:.0f}", fontName="Helvetica", fontSize=5.5,
                                     fillColor=SIMBOLO, textAnchor="middle"))
        etiqueta_alto.translate(x - 5, y + h / 2)
        etiqueta_alto.rotate(90)
        d.add(etiqueta_alto)

    return d
