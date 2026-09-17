"""
Portada del manual, dibujada en vectores.

Reproduce el diseño de cuaderno anillado con las maquetas de la interfaz, pero
trazado con primitivas de ReportLab en lugar de una imagen. Ventajas frente al
JPG original:

* **Nítida a cualquier resolución.** El JPG daba 87 DPI al imprimirse en A4, que
  en papel se ve blando. Un trazado vectorial se imprime a la resolución de la
  impresora.
* **Sin errores de tipeo.** La imagen generada decía "CUIT / ONI",
  "Obra / Diressión" y "50% anticpo".
* **Regenerable.** Al cambiar de versión, el número se actualiza solo.
* **Pesa nada:** unos pocos KB contra 116 KB del JPG.

Uso:
    from tools.portada import dibujar_portada
    dibujar_portada(canvas, "2.1.0")
"""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4

# --- Paleta (la misma que usa la aplicación) --------------------------------
AZUL = colors.HexColor("#1B3A57")
AZUL_HOVER = colors.HexColor("#2A5580")
TEXTO = colors.HexColor("#16202B")
TEXTO_SUAVE = colors.HexColor("#5B6B7C")
TEXTO_TENUE = colors.HexColor("#8A98A6")
BORDE = colors.HexColor("#D3DAE3")
BORDE_SUAVE = colors.HexColor("#E4E9EF")
SUPERFICIE_3 = colors.HexColor("#E8EDF3")
FONDO = colors.HexColor("#F1F3F6")
PAPEL = colors.HexColor("#FDFDFE")
SOMBRA = colors.HexColor("#D8DCE3")
METAL = colors.HexColor("#A9B2BD")
METAL_OSCURO = colors.HexColor("#7C8794")
VIDRIO = colors.HexColor("#D3E4F0")
VIDRIO_2 = colors.HexColor("#C2D6E6")
MARCO = colors.HexColor("#8FA3B5")

# --- Geometría de la hoja ---------------------------------------------------
HOJA_X, HOJA_Y = 62, 54
HOJA_W, HOJA_H = 476, 736
HOJA_X2 = HOJA_X + HOJA_W
HOJA_Y2 = HOJA_Y + HOJA_H

PAD = 26
COL_X = HOJA_X + PAD                      # inicio del contenido
COL_X2 = HOJA_X2 - PAD
LATERAL_W = 84                            # ancho de la maqueta de barra lateral
MAIN_X = COL_X + LATERAL_W + 16


# ---------------------------------------------------------------------------
# Primitivas
# ---------------------------------------------------------------------------

def _texto(c, x, y, txt, tam=8, color=TEXTO, negrita=False, centrado=False,
           derecha=False):
    c.setFont("Helvetica-Bold" if negrita else "Helvetica", tam)
    c.setFillColor(color)
    if centrado:
        c.drawCentredString(x, y, txt)
    elif derecha:
        c.drawRightString(x, y, txt)
    else:
        c.drawString(x, y, txt)


def _campo(c, x, y, w, h=13, etiqueta="", valor="", tam_etiqueta=5.2):
    """Campo de formulario con su etiqueta arriba."""
    if etiqueta:
        _texto(c, x, y + h + 3, etiqueta, tam_etiqueta, TEXTO_TENUE)
    c.setStrokeColor(BORDE)
    c.setFillColor(colors.white)
    c.setLineWidth(0.6)
    c.roundRect(x, y, w, h, 2.5, stroke=1, fill=1)
    if valor:
        _texto(c, x + 5, y + 4, valor, 5.6, TEXTO_SUAVE)


def _pastilla(c, x, y, w, h, txt, relleno=colors.white, texto_color=TEXTO,
              borde=BORDE, tam=6):
    c.setStrokeColor(borde)
    c.setFillColor(relleno)
    c.setLineWidth(0.6)
    c.roundRect(x, y, w, h, h / 2.6, stroke=1, fill=1)
    _texto(c, x + w / 2, y + h / 2 - tam * 0.35, txt, tam, texto_color, centrado=True)


def _boton(c, x, y, w, h, txt, tam=6):
    c.setStrokeColor(BORDE)
    c.setFillColor(SUPERFICIE_3)
    c.setLineWidth(0.6)
    c.roundRect(x, y, w, h, 2.5, stroke=1, fill=1)
    _texto(c, x + w / 2, y + h / 2 - tam * 0.35, txt, tam, TEXTO_SUAVE, centrado=True)


def _barra_lateral(c, x, y, activo_arriba=True):
    """Maqueta del menú lateral: 'Cotización' resaltado y 'Presupuestos'."""
    alto_item = 17
    c.setFillColor(AZUL)
    c.setStrokeColor(AZUL)
    c.roundRect(x, y, LATERAL_W, alto_item, 3, stroke=0, fill=1)
    _icono_hoja(c, x + 8, y + alto_item / 2, colors.white)
    _texto(c, x + 19, y + alto_item / 2 - 2.2, "Cotización", 6.4, colors.white)

    y2 = y - alto_item - 7
    _icono_hoja(c, x + 8, y2 + alto_item / 2, TEXTO_SUAVE)
    _texto(c, x + 19, y2 + alto_item / 2 - 2.2, "Presupuestos", 6.4, TEXTO_SUAVE)


def _icono_hoja(c, x, y, color):
    """Iconito de documento."""
    c.setStrokeColor(color)
    c.setLineWidth(0.7)
    c.setFillColor(colors.white if color != colors.white else AZUL)
    c.rect(x - 3, y - 4.2, 6, 8.4, stroke=1, fill=0)
    for i in range(3):
        yy = y + 1.8 - i * 2.1
        c.line(x - 1.6, yy, x + 1.6, yy)


# ---------------------------------------------------------------------------
# Bloques de la portada
# ---------------------------------------------------------------------------

def _hoja_y_anillado(c):
    """Pila de hojas, hoja principal y espiral metálica."""
    # Hojas de atrás, apiladas hacia abajo y a la derecha
    for i, desplazamiento in enumerate((16, 11, 6)):
        c.setFillColor(colors.HexColor("#E9EBEF") if i == 0 else colors.HexColor("#F4F5F8"))
        c.setStrokeColor(SOMBRA)
        c.setLineWidth(0.5)
        c.roundRect(HOJA_X + desplazamiento, HOJA_Y - desplazamiento,
                    HOJA_W, HOJA_H, 4, stroke=1, fill=1)

    # Hoja principal
    c.setFillColor(PAPEL)
    c.setStrokeColor(BORDE)
    c.setLineWidth(0.7)
    c.roundRect(HOJA_X, HOJA_Y, HOJA_W, HOJA_H, 4, stroke=1, fill=1)

    # Espiral: cada anillo es una elipse que cruza el borde izquierdo
    c.setLineWidth(2.2)
    paso = 25.5
    y = HOJA_Y2 - 20
    while y > HOJA_Y + 14:
        c.setStrokeColor(METAL_OSCURO)
        c.ellipse(HOJA_X - 17, y - 5.2, HOJA_X + 15, y + 5.2, stroke=1, fill=0)
        c.setStrokeColor(METAL)
        c.setLineWidth(1.1)
        c.ellipse(HOJA_X - 15, y - 3.6, HOJA_X + 13, y + 3.6, stroke=1, fill=0)
        c.setLineWidth(2.2)
        # Perforación de la hoja
        c.setFillColor(FONDO)
        c.setStrokeColor(BORDE)
        c.setLineWidth(0.4)
        c.circle(HOJA_X + 11, y, 2.1, stroke=1, fill=1)
        c.setLineWidth(2.2)
        y -= paso


def _bloque_superior(c, y):
    """Maqueta del encabezado del presupuesto y los datos del cliente."""
    _barra_lateral(c, COL_X, y - 30)

    x = MAIN_X
    _texto(c, x, y - 8, "PRESUPUESTO", 9.5, TEXTO, negrita=False)
    ancho_titulo = c.stringWidth("PRESUPUESTO", "Helvetica", 9.5)

    px = x + ancho_titulo + 10
    _pastilla(c, px, y - 12, 52, 12.5, "PRES-0001")
    _texto(c, px + 60, y - 8.5, "→", 8, TEXTO_TENUE)
    _pastilla(c, px + 70, y - 12, 54, 12.5, "11/08/2026")
    _pastilla(c, px + 129, y - 12, 34, 12.5, "15 días")
    _pastilla(c, px + 168, y - 12, 40, 12.5, "Borrador")

    # Datos del cliente
    yc = y - 34
    _texto(c, x, yc, "Datos del cliente", 7.6, TEXTO, negrita=True)

    yf = yc - 22
    _campo(c, x, yf, 118, etiqueta="Cliente / Razón social")
    _campo(c, x + 126, yf, 100, etiqueta="CUIT / DNI")
    _campo(c, x + 234, yf, 74, etiqueta="Contacto")

    yf2 = yf - 26
    _campo(c, x, yf2, 118, etiqueta="Obra / Dirección")
    _texto(c, x + 126, yf2 + 16, "Forma de pago", 5.2, TEXTO_TENUE)
    c.setStrokeColor(BORDE)
    c.setFillColor(colors.white)
    c.setLineWidth(0.6)
    c.roundRect(x + 126, yf2, 182, 13, 2.5, stroke=1, fill=1)
    _texto(c, x + 131, yf2 + 4, "50% anticipo / 50% contra entrega", 5.6, TEXTO_SUAVE)
    # Flechita del desplegable
    c.setStrokeColor(TEXTO_TENUE)
    c.setLineWidth(0.8)
    c.line(x + 300, yf2 + 8, x + 302.5, yf2 + 5)
    c.line(x + 302.5, yf2 + 5, x + 305, yf2 + 8)

    return yf2 - 16


def _titulo(c, y, version):
    _texto(c, A4[0] / 2, y, "COTIZADOR DE ABERTURAS", 25, AZUL, centrado=True)
    _texto(c, A4[0] / 2, y - 30, f"DE ALUMINIO v{version}", 25, AZUL, centrado=True)
    return y - 52


def _ventana_corrediza(c, x, y, w, h):
    """Dibujo de una ventana corrediza de dos hojas."""
    c.setFillColor(colors.white)
    c.setStrokeColor(MARCO)
    c.setLineWidth(1.6)
    c.rect(x, y, w, h, stroke=1, fill=1)

    m = 3.5
    mitad = (w - 2 * m) / 2
    for i in range(2):
        hx = x + m + i * mitad
        c.setFillColor(VIDRIO if i == 0 else VIDRIO_2)
        c.setStrokeColor(MARCO)
        c.setLineWidth(1.1)
        c.rect(hx, y + m, mitad, h - 2 * m, stroke=1, fill=1)

    # Reflejo diagonal en la hoja izquierda
    c.setStrokeColor(colors.white)
    c.setLineWidth(1.6)
    c.line(x + m + 4, y + m + 4, x + m + mitad - 6, y + h - m - 6)


def _puerta(c, x, y, w, h):
    """Dibujo de una puerta / paño con travesaños."""
    c.setFillColor(colors.white)
    c.setStrokeColor(MARCO)
    c.setLineWidth(1.6)
    c.rect(x, y, w, h, stroke=1, fill=1)

    m = 3.5
    c.setFillColor(VIDRIO_2)
    c.setStrokeColor(MARCO)
    c.setLineWidth(1.1)
    c.rect(x + m, y + m, w - 2 * m, h - 2 * m, stroke=1, fill=1)

    # Travesaños horizontales
    c.setStrokeColor(MARCO)
    c.setLineWidth(1.0)
    for i in (1, 2, 3):
        yy = y + m + (h - 2 * m) * i / 4
        c.line(x + m, yy, x + w - m, yy)

    # Manija
    c.setFillColor(METAL_OSCURO)
    c.setStrokeColor(METAL_OSCURO)
    c.rect(x + w - m - 4, y + h / 2 - 6, 1.8, 12, stroke=0, fill=1)


def _bloque_medio(c, y, alto=236):
    """Panel de aberturas a la izquierda y vista previa del PDF a la derecha."""
    _barra_lateral(c, COL_X, y - 58)

    x = MAIN_X
    _texto(c, x, y, "Aberturas", 9.5, TEXTO, negrita=True)

    _boton(c, x, y - 21, 42, 14, "Editar")
    _boton(c, x + 47, y - 21, 48, 14, "Duplicar")

    # Encabezado de la tabla
    tabla_y = y - 43
    c.setFillColor(SUPERFICIE_3)
    c.setStrokeColor(BORDE)
    c.setLineWidth(0.5)
    c.rect(x, tabla_y, 156, 15, stroke=1, fill=1)
    _texto(c, x + 7, tabla_y + 4.5, "#", 6.2, TEXTO_SUAVE, negrita=True)
    _texto(c, x + 26, tabla_y + 4.5, "Descripción", 6.2, TEXTO_SUAVE, negrita=True)

    # Filas: las primeras con contenido insinuado, el resto vacías. Una grilla
    # toda vacía se lee como una planilla sin usar.
    filas = 7
    for i in range(filas):
        fy = tabla_y - (i + 1) * 15
        c.setStrokeColor(BORDE_SUAVE)
        c.setFillColor(colors.HexColor("#FAFBFC") if i % 2 else colors.white)
        c.rect(x, fy, 156, 15, stroke=1, fill=1)
        if i < 4:
            _texto(c, x + 7, fy + 5, str(i + 1), 5.8, TEXTO_TENUE)
            c.setFillColor(BORDE_SUAVE)
            c.rect(x + 26, fy + 6, (96, 112, 74, 88)[i], 3.2, stroke=0, fill=1)

    # --- Tarjeta de vista previa del PDF
    tw = 146
    ty = y - 14 - alto
    tx = x + 172
    c.setFillColor(colors.white)
    c.setStrokeColor(BORDE)
    c.setLineWidth(0.9)
    c.rect(tx, ty, tw, alto, stroke=1, fill=1)

    _texto(c, tx + 11, ty + alto - 18, "Presupuesto", 8.4, TEXTO, negrita=True)
    c.setFillColor(SUPERFICIE_3)
    c.roundRect(tx + tw - 50, ty + alto - 19, 39, 7.5, 3.7, stroke=0, fill=1)
    _texto(c, tx + 11, ty + alto - 30, "PRES-0001", 6.6, TEXTO_SUAVE)
    _texto(c, tx + tw - 11, ty + alto - 30, "11/08/2026", 6.6, TEXTO_SUAVE, derecha=True)

    # Renglones de texto insinuados
    c.setFillColor(BORDE_SUAVE)
    c.rect(tx + 11, ty + alto - 45, 54, 3.2, stroke=0, fill=1)
    c.rect(tx + 81, ty + alto - 45, 54, 3.2, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#B9C9D8"))
    c.rect(tx + 11, ty + alto - 59, tw - 22, 6.5, stroke=0, fill=1)

    # Los dos dibujos de aberturas, centrados en el cuerpo de la tarjeta
    dib_y = ty + alto - 155
    _ventana_corrediza(c, tx + 17, dib_y, 56, 64)
    _puerta(c, tx + 83, dib_y - 6, 46, 76)

    # Pie de la tarjeta
    c.setFillColor(colors.HexColor("#B9C9D8"))
    c.rect(tx + 11, ty + 44, tw - 22, 6.5, stroke=0, fill=1)
    c.setFillColor(BORDE_SUAVE)
    for i in range(3):
        c.rect(tx + 11, ty + 32 - i * 9, 72, 3.2, stroke=0, fill=1)
    c.rect(tx + tw - 48, ty + 32, 15, 3.2, stroke=0, fill=1)
    c.rect(tx + tw - 27, ty + 32, 16, 3.2, stroke=0, fill=1)

    return ty - 20


def _bloque_inferior(c, y):
    """Las tres frases de características y otra maqueta de barra lateral."""
    x = COL_X
    lineas = ["Generación de Presupuestos Rápidos",
              "Gestión de Materiales y Costos",
              "Cálculo de Mano de Obra y Logística"]
    for i, linea in enumerate(lineas):
        _texto(c, x, y - i * 21, linea, 13, TEXTO)

    # Separador vertical y barra lateral a la derecha
    c.setStrokeColor(BORDE)
    c.setLineWidth(0.7)
    c.line(COL_X2 - 120, y - 46, COL_X2 - 120, y + 15)
    _barra_lateral(c, COL_X2 - 102, y - 6)

    return y - 60


def _pie(c, y, version):
    c.setStrokeColor(BORDE)
    c.setLineWidth(0.7)
    c.line(COL_X, y + 16, COL_X2, y + 16)
    _texto(c, A4[0] / 2, y, f"Manual de Instrucciones  •  Versión Impresa  •  A4  •  v{version}",
           9.5, TEXTO_SUAVE, centrado=True)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def dibujar_portada(c, version: str = "2.1.0") -> None:
    """Dibuja la portada completa sobre el canvas, a página entera."""
    c.saveState()

    # Fondo
    c.setFillColor(FONDO)
    c.rect(0, 0, A4[0], A4[1], stroke=0, fill=1)

    _hoja_y_anillado(c)

    # El reparto vertical se calcula desde el pie hacia arriba para que el
    # contenido llene la hoja: si se encadenan los bloques de arriba hacia abajo,
    # el sobrante se acumula todo junto al final.
    y = HOJA_Y2 - 34
    y = _bloque_superior(c, y)

    c.setStrokeColor(BORDE)
    c.setLineWidth(0.7)
    c.line(COL_X, y, COL_X2, y)

    y = _titulo(c, y - 66, version)

    c.setStrokeColor(BORDE)
    c.line(COL_X, y + 20, COL_X2, y + 20)

    y = _bloque_medio(c, y - 10, alto=236)

    c.setStrokeColor(BORDE)
    c.line(COL_X, y + 8, COL_X2, y + 8)

    _bloque_inferior(c, y - 26)
    _pie(c, HOJA_Y + 30, version)

    c.restoreState()


def _previsualizar(ruta="portada_vector.pdf", version="2.1.0"):
    """Genera un PDF de una sola página para revisar el diseño."""
    from reportlab.pdfgen import canvas as cv
    c = cv.Canvas(str(ruta), pagesize=A4)
    dibujar_portada(c, version)
    c.showPage()
    c.save()
    return ruta


if __name__ == "__main__":
    import sys
    destino = sys.argv[1] if len(sys.argv) > 1 else "portada_vector.pdf"
    print("Portada generada:", _previsualizar(destino))
