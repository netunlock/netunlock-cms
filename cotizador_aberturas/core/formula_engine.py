"""
Motor de fórmulas paramétricas seguro.

Permite evaluar expresiones de despiece cargadas por el usuario en la base de
datos (ej.: ``(A + 26) / N``, ``H - 48``, ``si(N > 2, 3, 2)``) sin exponer
``eval()`` al usuario final: se recorre el AST y sólo se permiten nodos de una
lista blanca.

Variables disponibles en el contexto de despiece
------------------------------------------------
    A      Ancho nominal de la abertura, en mm
    H      Alto nominal de la abertura, en mm
    N      Cantidad de hojas
    AH     Ancho de hoja resultante (disponible en fórmulas de vidrio)
    HH     Alto de hoja resultante (disponible en fórmulas de vidrio)
    PERIM  Perímetro de la abertura en mm -> 2 * (A + H)
    M2     Superficie de la abertura en m2 -> A * H / 1_000_000
"""

from __future__ import annotations

import ast
import math
import operator

__all__ = ["FormulaError", "evaluar", "evaluar_entero", "validar", "FUNCIONES", "AYUDA_VARIABLES"]


class FormulaError(ValueError):
    """La fórmula no se puede interpretar o evaluar."""


_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}

_CMP_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


def _si(condicion, valor_si, valor_no):
    """Equivalente a la función SI() de Excel, para que el usuario no cambie de idioma."""
    return valor_si if condicion else valor_no


def _techo(valor, multiplo=1):
    return math.ceil(valor / multiplo) * multiplo


def _piso(valor, multiplo=1):
    return math.floor(valor / multiplo) * multiplo


FUNCIONES = {
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "redondear": round,
    "ceil": math.ceil,
    "floor": math.floor,
    "techo": _techo,
    "piso": _piso,
    "sqrt": math.sqrt,
    "raiz": math.sqrt,
    "si": _si,
    "if": _si,
}

AYUDA_VARIABLES = (
    "A = ancho (mm) · H = alto (mm) · N = cantidad de hojas · "
    "AH = ancho de hoja · HH = alto de hoja · PERIM = 2*(A+H) · M2 = A*H/1e6\n"
    "Funciones: min, max, abs, redondear, techo, piso, raiz, si(cond, a, b)"
)


def _evaluar_nodo(nodo, ctx):
    if isinstance(nodo, ast.Expression):
        return _evaluar_nodo(nodo.body, ctx)

    if isinstance(nodo, ast.Constant):
        if isinstance(nodo.value, (int, float, bool)):
            return nodo.value
        raise FormulaError(f"Constante no permitida: {nodo.value!r}")

    if isinstance(nodo, ast.Name):
        nombre = nodo.id
        if nombre in ctx:
            return ctx[nombre]
        # Se acepta minúscula por comodidad: a, h, n
        if nombre.upper() in ctx:
            return ctx[nombre.upper()]
        raise FormulaError(f"Variable desconocida: '{nombre}'")

    if isinstance(nodo, ast.BinOp):
        op = _BIN_OPS.get(type(nodo.op))
        if op is None:
            raise FormulaError("Operador no permitido")
        izq = _evaluar_nodo(nodo.left, ctx)
        der = _evaluar_nodo(nodo.right, ctx)
        if op in (operator.truediv, operator.floordiv, operator.mod) and der == 0:
            raise FormulaError("División por cero")
        return op(izq, der)

    if isinstance(nodo, ast.UnaryOp):
        op = _UNARY_OPS.get(type(nodo.op))
        if op is None:
            raise FormulaError("Operador unario no permitido")
        return op(_evaluar_nodo(nodo.operand, ctx))

    if isinstance(nodo, ast.Compare):
        izq = _evaluar_nodo(nodo.left, ctx)
        for op_nodo, comp in zip(nodo.ops, nodo.comparators):
            op = _CMP_OPS.get(type(op_nodo))
            if op is None:
                raise FormulaError("Comparación no permitida")
            der = _evaluar_nodo(comp, ctx)
            if not op(izq, der):
                return False
            izq = der
        return True

    if isinstance(nodo, ast.BoolOp):
        valores = [_evaluar_nodo(v, ctx) for v in nodo.values]
        if isinstance(nodo.op, ast.And):
            return all(valores)
        return any(valores)

    if isinstance(nodo, ast.IfExp):
        return (
            _evaluar_nodo(nodo.body, ctx)
            if _evaluar_nodo(nodo.test, ctx)
            else _evaluar_nodo(nodo.orelse, ctx)
        )

    if isinstance(nodo, ast.Call):
        if not isinstance(nodo.func, ast.Name):
            raise FormulaError("Llamada a función no permitida")
        fn = FUNCIONES.get(nodo.func.id.lower())
        if fn is None:
            raise FormulaError(f"Función desconocida: '{nodo.func.id}'")
        if nodo.keywords:
            raise FormulaError("No se admiten argumentos con nombre")
        args = [_evaluar_nodo(a, ctx) for a in nodo.args]
        return fn(*args)

    raise FormulaError(f"Expresión no permitida: {type(nodo).__name__}")


def evaluar(formula, contexto, por_defecto=None):
    """Evalúa ``formula`` y devuelve un float.

    Si la fórmula está vacía se devuelve ``por_defecto`` (o 0.0).
    """
    if formula is None or str(formula).strip() == "":
        return float(por_defecto or 0.0)

    texto = str(formula).strip()
    # Tolerancia de tipeo: coma decimal y símbolos de Excel
    texto = texto.replace("^", "**").lstrip("=")

    try:
        arbol = ast.parse(texto, mode="eval")
    except SyntaxError as exc:
        raise FormulaError(f"Sintaxis inválida en '{formula}': {exc.msg}") from exc

    resultado = _evaluar_nodo(arbol, contexto)
    if isinstance(resultado, bool):
        return 1.0 if resultado else 0.0
    if not isinstance(resultado, (int, float)):
        raise FormulaError(f"La fórmula '{formula}' no devolvió un número")
    return float(resultado)


def evaluar_entero(formula, contexto, por_defecto=1):
    """Igual que :func:`evaluar` pero redondeando hacia arriba (cantidades de piezas)."""
    valor = evaluar(formula, contexto, por_defecto)
    return max(0, int(math.ceil(round(valor, 6))))


def validar(formula, variables=("A", "H", "N", "AH", "HH", "PERIM", "M2")):
    """Verifica que la fórmula compile y evalúe con valores de prueba.

    Devuelve ``(True, resultado)`` o ``(False, mensaje_de_error)``.
    """
    ctx = {v: 1000.0 for v in variables}
    ctx["N"] = 2.0
    ctx["M2"] = 1.0
    try:
        return True, evaluar(formula, ctx)
    except FormulaError as exc:
        return False, str(exc)
