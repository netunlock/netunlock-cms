"""
Formateo estricto de unidades — única fuente de verdad para pantalla, tablas y PDF.

Convención argentina: miles con punto, decimales con coma.

    moneda(125400.5)      -> '$ 125.400,50'
    horas(8)              -> '8 hrs'
    horas(2.5)            -> '2,5 hrs'
    kilos(14.2)           -> '14,2 Kgs'
    unidades(4)           -> '4 uds.'
    milimetros(1200)      -> '1200 mm'
    medida(1200, 1500)    -> '1200 x 1500 mm'
    superficie(2.4567)    -> '2,46 m²'
    porcentaje(0.21)      -> '21 %'

Toda cifra que se muestre al usuario debe pasar por acá. Los sufijos de unidad
que se ven dentro de los campos de carga salen de :data:`UNIDADES`.
"""

from __future__ import annotations

import math
import re

#: '1.500', '1.234.567' — puntos usados como separador de miles, sin decimales
_SOLO_MILES = re.compile(r"^-?\d{1,3}(\.\d{3})+$")

__all__ = [
    "moneda", "horas", "kilos", "unidades", "milimetros", "medida", "superficie",
    "metros", "porcentaje", "numero", "a_float", "a_int", "pct_desde_texto",
    "UNIDADES", "SIMBOLO_MONEDA",
]

SIMBOLO_MONEDA = "$"

#: Sufijo/prefijo que se muestra dentro de cada campo de carga.
UNIDADES = {
    "moneda": "$",
    "moneda_kg": "$ / Kg",
    "moneda_m2": "$ / m²",
    "moneda_ml": "$ / ml",
    "moneda_ud": "$ / ud.",
    "moneda_hora": "$ / hora",
    "horas": "hrs",
    "kilos": "Kgs",
    "kilos_metro": "Kg / m",
    "unidades": "uds.",
    "operarios": "operarios",
    "milimetros": "mm",
    "metros": "m",
    "superficie": "m²",
    "porcentaje": "%",
    "dias": "días",
}


# ---------------------------------------------------------------------------
# Núcleo de formateo
# ---------------------------------------------------------------------------

def numero(valor, decimales: int = 2, quitar_ceros: bool = False,
           miles: bool = True) -> str:
    """Formatea un número con separador de miles '.' y decimal ','.

    ``quitar_ceros`` recorta los ceros sobrantes de la derecha::

        8.0  -> '8'      2.5  -> '2,5'      14.20 -> '14,2'

    ``miles=False`` omite el separador de miles. Se usa en las medidas: en un
    plano de carpintería ``1500 mm`` se lee mejor que ``1.500 mm``.
    """
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        valor = 0.0
    if not math.isfinite(valor):
        valor = 0.0

    texto = f"{valor:,.{decimales}f}" if miles else f"{valor:.{decimales}f}"

    if quitar_ceros and decimales:
        entera, _, decimal = texto.partition(".")
        decimal = decimal.rstrip("0")
        texto = f"{entera}.{decimal}" if decimal else entera

    if not miles:
        return texto.replace(".", ",")
    # Intercambia los separadores anglosajones por los locales
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


# ---------------------------------------------------------------------------
# Unidades del dominio
# ---------------------------------------------------------------------------

def moneda(valor, con_simbolo: bool = True) -> str:
    """``$ 125.400,50`` — siempre con dos decimales."""
    texto = numero(valor, 2)
    if texto.startswith("-"):
        return f"-{SIMBOLO_MONEDA} {texto[1:]}" if con_simbolo else texto
    return f"{SIMBOLO_MONEDA} {texto}" if con_simbolo else texto


def horas(valor) -> str:
    """``8 hrs`` · ``2,5 hrs``"""
    return f"{numero(valor, 2, quitar_ceros=True)} hrs"


def kilos(valor, decimales: int = 2) -> str:
    """``14,2 Kgs``"""
    return f"{numero(valor, decimales, quitar_ceros=True)} Kgs"


def kilos_metro(valor) -> str:
    """``0,850 Kg / m`` — peso nominal de perfil, con 3 decimales."""
    return f"{numero(valor, 3)} Kg / m"


def unidades(valor) -> str:
    """``4 uds.`` — enteras. Para consumos fraccionados usá :func:`cantidad`."""
    return f"{numero(valor, 0)} uds."


def cantidad(valor, unidad: str = "u") -> str:
    """Cantidad con la unidad del accesorio.

    ``4 uds.`` · ``3,25 ml`` · ``1,4 m²`` · ``2,45 Kgs``

    Un accesorio cargado como ``kg/m`` se consume en **kilos**: la fórmula del
    kit da metros y el despiece los multiplica por el peso lineal antes de
    llegar acá. Por eso 'kg/m' y 'kg' se muestran igual — es la unidad en la que
    se factura, no la que se usó para cargarlo.
    """
    unidad = (unidad or "u").lower()
    if unidad in ("u", "ud", "uds", "jgo"):
        return unidades(valor)
    if unidad == "ml":
        return f"{numero(valor, 2)} ml"
    if unidad in ("m2", "m²"):
        return superficie(valor)
    if unidad in ("kg", "kg/m", "kgs"):
        return kilos(valor)
    return f"{numero(valor, 2)} {unidad}"


def milimetros(valor) -> str:
    """``1200 mm`` — sin decimales ni separador de miles."""
    return f"{numero(valor, 0, miles=False)} mm"


def milimetros_corte(valor) -> str:
    """``1052,5 mm`` — largo de pieza con décima de mm."""
    return f"{numero(valor, 1, quitar_ceros=True, miles=False)} mm"


def medida(ancho, alto) -> str:
    """``1200 x 1500 mm``"""
    return f"{numero(ancho, 0, miles=False)} x {numero(alto, 0, miles=False)} mm"


def superficie(valor) -> str:
    """``2,46 m²``"""
    return f"{numero(valor, 2)} m²"


def metros(valor) -> str:
    """``12,46 m`` — metros lineales de perfil."""
    return f"{numero(valor, 2)} m"


def porcentaje(valor, decimales: int = 0) -> str:
    """Recibe la fracción (0.21) y devuelve ``21 %``."""
    return f"{numero((valor or 0.0) * 100.0, decimales, quitar_ceros=True)} %"


def operarios(valor) -> str:
    n = int(a_float(valor, 1))
    return f"{n} operario" if n == 1 else f"{n} operarios"


# ---------------------------------------------------------------------------
# Lectura: de texto escrito por el usuario a número
# ---------------------------------------------------------------------------

def a_float(texto, por_defecto: float = 0.0) -> float:
    """Lee un número tolerando '$', '%', 'mm', 'Kgs', espacios y coma decimal."""
    if texto is None:
        return por_defecto
    if isinstance(texto, (int, float)):
        return float(texto)

    limpio = str(texto).strip()
    for basura in ("$", "%", "mm", "m²", "m2", "Kgs", "Kg", "kg", "hrs", "hs",
                   "uds.", "uds", "ud.", "ml", " ", " "):
        limpio = limpio.replace(basura, "")
    if not limpio or limpio in ("-", ",", "."):
        return por_defecto

    if "," in limpio:
        # Con coma presente, la coma es el decimal y el punto separa miles.
        limpio = limpio.replace(".", "").replace(",", ".")
    elif _SOLO_MILES.match(limpio):
        # '1.500' o '1.234.567': puntos cada 3 dígitos y ningún decimal.
        # Sin esta regla, quien escribe '1.500' pensando en mil quinientos
        # obtendría 1,5 — un error de tres órdenes de magnitud en un precio.
        limpio = limpio.replace(".", "")

    try:
        return float(limpio)
    except ValueError:
        return por_defecto


def a_int(texto, por_defecto: int = 0) -> int:
    return int(round(a_float(texto, por_defecto)))


def pct_desde_texto(texto, por_defecto: float = 0.0) -> float:
    """El usuario escribe porcentajes en escala 0-100; el motor los usa como fracción.

    ``'21'`` o ``'21 %'`` -> ``0.21``
    """
    return a_float(texto, por_defecto * 100.0) / 100.0
