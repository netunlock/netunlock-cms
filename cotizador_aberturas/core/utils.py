"""Utilidades de formato (moneda y números en formato argentino)."""

from __future__ import annotations


def fmt_money(valor: float, simbolo: str = "$", decimales: int = 2) -> str:
    """1234567.5 -> '$ 1.234.567,50'"""
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        valor = 0.0
    signo = "-" if valor < 0 else ""
    texto = f"{abs(valor):,.{decimales}f}"
    texto = texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"{signo}{simbolo} {texto}".strip()


def fmt_num(valor: float, decimales: int = 2) -> str:
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        valor = 0.0
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def fmt_pct(valor: float, decimales: int = 1) -> str:
    """0.21 -> '21,0%'"""
    return fmt_num((valor or 0.0) * 100.0, decimales) + "%"


def a_float(texto, por_defecto: float = 0.0) -> float:
    """Lee un número escrito con coma o punto decimal, tolerando '$', '%' y espacios."""
    if texto is None:
        return por_defecto
    if isinstance(texto, (int, float)):
        return float(texto)
    limpio = str(texto).strip().replace("$", "").replace("%", "").replace(" ", "")
    if not limpio:
        return por_defecto
    if "," in limpio and "." in limpio:
        limpio = limpio.replace(".", "").replace(",", ".")
    else:
        limpio = limpio.replace(",", ".")
    try:
        return float(limpio)
    except ValueError:
        return por_defecto


def a_int(texto, por_defecto: int = 0) -> int:
    return int(round(a_float(texto, por_defecto)))


def pct_desde_texto(texto, por_defecto: float = 0.0) -> float:
    """Lee un porcentaje escrito en enteros: '10' o '10%' -> 0.10.

    Toda la GUI muestra y pide los porcentajes en escala 0-100; la base y el
    motor de cálculo los guardan siempre como fracción (0.10).
    """
    return a_float(texto, por_defecto * 100.0) / 100.0
