# -*- coding: utf-8 -*-
"""
Sello de "versión de prueba" sobre todo lo que el programa imprime.

Por qué esto y no más candados
-------------------------------
El período de prueba se puede reiniciar borrando la carpeta de datos del
usuario. Se podría esconder marcas por el registro y por medio disco para
impedirlo, y no se hace: eso es lo que hace un programa que uno no quiere tener
instalado, y además siempre pierde —quien sabe borrar una carpeta aprende a
borrar dos—.

El sello ataca el otro lado del problema, que es el que importa. A un
carpintero no le sirve **usar** el programa: le sirve **mandarle el presupuesto
a un cliente**. Un PDF cruzado de rojo con "VERSIÓN DE PRUEBA" no se le manda a
nadie. Así, reiniciar la prueba deja de tener sentido: se puede seguir abriendo
el programa para siempre y no sale un solo papel presentable.

Es también más honesto. No esconde nada, no rompe nada y no obliga a nadie a
confiar en que el programa no le dejó rastros raros en la máquina: se ve lo que
hace, y desaparece solo cuando entra la licencia.

Cómo está hecho
---------------
Un ``canvasmaker`` para ReportLab. Se pasa en ``doc.build(...)`` y estampa
**cada página**, sin tocar el armado del documento: los encabezados, los pies y
las tablas siguen exactamente igual. Y el texto va **repetido en diagonal por
toda la hoja**, no una sola vez en el medio: una marca única se recorta con
cualquier visor, catorce cruzadas sobre el contenido no.
"""

from __future__ import annotations

import time

from reportlab.lib import colors
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as rl_canvas

#: Lo que dice el sello.
TEXTO = "VERSIÓN DE PRUEBA"

#: Y la línea al pie, con el correo, porque el PDF puede terminar en manos de
#: alguien que no bajó el programa.
def _pie() -> str:
    from core.prueba import CONTACTO
    return (f"Documento generado con una versión de prueba del Cotizador de "
            f"Aberturas · {CONTACTO}")

ROJO = colors.Color(0.78, 0.09, 0.09, alpha=0.26)
ROJO_PIE = colors.Color(0.70, 0.08, 0.08, alpha=0.80)

#: Cómo se dibuja. Helvetica-Bold porque viene en todo lector de PDF: una
#: tipografía incrustada se puede quitar, ésta no molesta a nadie y se lee igual.
TIPOGRAFIA = "Helvetica-Bold"
CUERPO = 44
#: Grados. En diagonal cruza texto y tablas por igual; en horizontal se esconde
#: entre los renglones.
GIRO = 38
#: Aire entre una marca y la siguiente. Sin esto se pisan y no se lee ninguna.
SEPARACION = 70

#: Cuántos segundos se recuerda si hay licencia. Generar los tres papeles de
#: taller son tres documentos seguidos: no tiene sentido revisar la licencia
#: tres veces en el mismo segundo.
CACHE_S = 30.0
_cache: tuple[float, bool] = (0.0, False)


def hace_falta() -> bool:
    """¿Este equipo está sin licencia y hay que sellar lo que imprime?"""
    global _cache
    ahora = time.monotonic()
    if ahora - _cache[0] < CACHE_S:
        return _cache[1]

    try:
        from core import licencia
        # Sin red: esto corre al generar cada PDF y no puede quedarse esperando
        # a un servidor. La verificación de reloj con red ya se hizo al abrir.
        estado = licencia.estado_actual(consultar_red=False)
        falta = (not estado.valida) or bool(getattr(estado, "es_prueba", False))
    except Exception:
        # Si no se puede determinar, se sella. Es la opción que no regala nada
        # y el peor caso es un PDF marcado de más en una instalación rota.
        falta = True

    _cache = (ahora, falta)
    return falta


def limpiar_cache() -> None:
    """Se llama al activar una licencia, para que el sello se vaya en el acto."""
    global _cache
    _cache = (0.0, False)


class LienzoConSello(rl_canvas.Canvas):
    """Canvas que estampa el sello en cada página antes de cerrarla."""

    def showPage(self):
        self._sellar()
        super().showPage()

    # No se toca save(). ReportLab hace ``if self._code: self.showPage()`` antes
    # de guardar, así que si quedara una página a medio cerrar pasa igual por
    # showPage() y sale sellada. Sellar también en save() dibujaba sobre una
    # página ya vacía y eso mismo la volvía "con contenido": salía una hoja de
    # más al final, en blanco y cruzada de rojo.

    def _sellar(self):
        ancho, alto = self._pagesize
        self.saveState()
        try:
            self.setFont(TIPOGRAFIA, CUERPO)
            self.setFillColor(ROJO)
            self.translate(ancho / 2.0, alto / 2.0)
            self.rotate(GIRO)

            # Rejilla de repeticiones que cubre la hoja entera ya girada, así no
            # queda ninguna franja limpia por la que recortar. El paso horizontal
            # sale del ancho real del texto: si se pone a ojo, las repeticiones
            # se pisan entre ellas y no se lee ni la marca ni lo que hay debajo.
            paso_x = stringWidth(TEXTO, TIPOGRAFIA, CUERPO) + SEPARACION
            paso_y = CUERPO * 2.6
            # La diagonal es más larga que el lado de la hoja: hay que estirar
            # la rejilla más allá del papel o quedan las esquinas sin marcar.
            alcance = (ancho + alto) / 2.0
            filas = int(alcance / paso_y) + 1
            columnas = int(alcance / paso_x) + 1
            for i in range(-filas, filas + 1):
                # Filas alternadas corridas media marca: el ojo lee cada línea
                # entera en vez de una grilla de columnas.
                corrimiento = (paso_x / 2.0) if i % 2 else 0.0
                for j in range(-columnas, columnas + 1):
                    self.drawCentredString(j * paso_x + corrimiento, i * paso_y, TEXTO)
            self.restoreState()

            # El pie va derecho y bien legible: es el que lleva el correo.
            self.saveState()
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(ROJO_PIE)
            self.drawCentredString(ancho / 2.0, 16, _pie())
        finally:
            self.restoreState()


def lienzo():
    """El ``canvasmaker`` para ``doc.build()``.

    Devuelve el canvas normal de ReportLab cuando hay licencia, así un cliente
    que pagó no arrastra ni una línea de código de más en sus documentos.
    """
    return LienzoConSello if hace_falta() else rl_canvas.Canvas


def aviso_planilla() -> list[str]:
    """Las filas de encabezado que se le ponen a un Excel exportado.

    Una planilla no se puede cruzar en diagonal, así que el aviso va donde no
    se puede ignorar: las tres primeras filas, antes de cualquier dato.
    """
    if not hace_falta():
        return []
    return [f"{TEXTO} — este listado no sirve para presentarle a un cliente",
            _pie()]
