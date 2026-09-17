"""
Motor de despiece paramétrico.

A partir de las dimensiones nominales (A x H en mm), la cantidad de hojas (N),
la tipología y la línea, resuelve:

  * el listado de piezas de perfil a cortar y su peso,
  * las medidas y superficie de los paños de vidrio,
  * el consumo de accesorios según el kit asociado.
"""

from __future__ import annotations

from .formula_engine import FormulaError, evaluar, evaluar_entero
from .models import (
    BarrasPerfil,
    Despiece,
    DespieceAccesorios,
    DespieceAluminio,
    DespieceVidrio,
    LineaAccesorio,
    PanoVidrio,
    PiezaCorte,
)

# Funciones cuyo largo representa la medida de hoja (se exponen como AH / HH)
FUNCION_ANCHO_HOJA = "HOJA_HORIZONTAL"
FUNCION_ALTO_HOJA = "HOJA_VERTICAL"

FUNCIONES_CONOCIDAS = [
    "MARCO_HORIZONTAL",
    "MARCO_VERTICAL",
    "HOJA_HORIZONTAL",
    "HOJA_VERTICAL",
    "CONTRAVIDRIO",
    "REFUERZO",
    "PREMARCO",
    "OTRO",
]


def _clave(fila, nombre: str, por_defecto=None):
    """Lee una columna de un ``sqlite3.Row`` que puede no existir.

    Una base todavía sin migrar no tiene las columnas nuevas, y ``Row`` levanta
    ``IndexError`` en vez de devolver None. Esto evita que el despiece explote
    mientras la migración no corrió.
    """
    try:
        return fila[nombre]
    except (IndexError, KeyError):
        return por_defecto


def contexto_base(ancho_mm: float, alto_mm: float, hojas: int) -> dict[str, float]:
    return {
        "A": float(ancho_mm),
        "H": float(alto_mm),
        "N": float(max(1, hojas)),
        "AH": float(ancho_mm),
        "HH": float(alto_mm),
        "PERIM": 2.0 * (ancho_mm + alto_mm),
        "M2": ancho_mm * alto_mm / 1_000_000.0,
    }


# ---------------------------------------------------------------------------
# Aluminio
# ---------------------------------------------------------------------------


def despiece_aluminio(db, tipologia_codigo, linea_id, color, ancho_mm, alto_mm, hojas):
    """Devuelve un :class:`DespieceAluminio` con las piezas de corte."""
    ctx = contexto_base(ancho_mm, alto_mm, hojas)
    advertencias: list[str] = []

    linea = db.linea(linea_id)
    modo = (linea["modo_costeo"] if linea else None) or db.parametro("modo_costeo_default", "kg")

    precio = db.precio_linea(linea_id, color)
    precio_kg = precio["precio_kg"] if precio else 0.0
    precio_m2 = precio["precio_m2_perfil"] if precio else 0.0
    if precio is None:
        advertencias.append(
            f"No hay precio cargado para la línea seleccionada en color '{color}'."
        )

    filas = db.formulas_despiece(tipologia_codigo, linea_id)
    if not filas:
        advertencias.append(
            f"No hay fórmulas de despiece para la tipología '{tipologia_codigo}'. "
            "Cargalas en Materiales > Fórmulas de despiece."
        )

    piezas: list[PiezaCorte] = []
    for fila in filas:
        try:
            largo = evaluar(fila["formula_largo"], ctx)
            cantidad = evaluar_entero(fila["cantidad_piezas"], ctx, 1)
        except FormulaError as exc:
            advertencias.append(f"{fila['perfil_codigo']} ({fila['funcion']}): {exc}")
            continue

        if largo <= 0 or cantidad <= 0:
            continue

        perfil = db.perfil(linea_id, fila["perfil_codigo"])
        peso_kg_m = perfil["peso_kg_m"] if perfil and perfil["peso_kg_m"] else fila["peso_kg_m"]
        descripcion = perfil["descripcion"] if perfil else fila["funcion"].replace("_", " ").title()
        if not peso_kg_m:
            advertencias.append(
                f"El perfil '{fila['perfil_codigo']}' no tiene peso (kg/m) cargado."
            )

        largo_barra = (perfil["largo_barra_mm"] if perfil and perfil["largo_barra_mm"]
                       else 6000)
        if largo > largo_barra:
            advertencias.append(
                f"El perfil '{fila['perfil_codigo']}' requiere un corte de "
                f"{largo:.0f} mm y la barra es de {largo_barra} mm."
            )

        piezas.append(
            PiezaCorte(
                perfil_codigo=fila["perfil_codigo"],
                descripcion=descripcion,
                funcion=fila["funcion"],
                largo_mm=round(largo, 1),
                cantidad=cantidad,
                peso_kg_m=peso_kg_m or 0.0,
                largo_barra_mm=int(largo_barra),
                nota=_clave(fila, "nota", "") or "",
                perfil_id=perfil["id"] if perfil else 0,
            )
        )

    resultado = DespieceAluminio(
        piezas=piezas,
        desperdicio_pct=db.parametro_float("desperdicio_aluminio_pct", 0.05),
        precio_kg=precio_kg,
        precio_m2_perfil=precio_m2,
        modo_costeo=modo,
        m2_abertura=ctx["M2"],
        advertencias=advertencias,
    )
    return resultado


def medidas_de_hoja(despiece_al: DespieceAluminio, ancho_mm: float, alto_mm: float):
    """Extrae AH / HH del despiece para alimentar las fórmulas de vidrio."""
    anchos = [p.largo_mm for p in despiece_al.piezas if p.funcion == FUNCION_ANCHO_HOJA]
    altos = [p.largo_mm for p in despiece_al.piezas if p.funcion == FUNCION_ALTO_HOJA]
    ancho_hoja = max(anchos) if anchos else float(ancho_mm)
    alto_hoja = max(altos) if altos else float(alto_mm)
    return ancho_hoja, alto_hoja


# ---------------------------------------------------------------------------
# Vidrio
# ---------------------------------------------------------------------------


def despiece_vidrio(db, tipologia_codigo, linea_id, vidrio_id, ctx) -> DespieceVidrio:
    vidrio = db.vidrio(vidrio_id)
    if vidrio is None:
        return DespieceVidrio()

    fila = db.formula_vidrio(tipologia_codigo, linea_id)
    f_ancho = fila["formula_ancho"] if fila else "AH - 60"
    f_alto = fila["formula_alto"] if fila else "HH - 60"
    f_cant = fila["formula_cantidad"] if fila else "N"

    try:
        ancho = evaluar(f_ancho, ctx)
        alto = evaluar(f_alto, ctx)
        cantidad = evaluar_entero(f_cant, ctx, 1)
    except FormulaError:
        ancho, alto, cantidad = ctx["AH"] - 60, ctx["HH"] - 60, int(ctx["N"])

    panos = []
    if ancho > 0 and alto > 0 and cantidad > 0:
        panos.append(
            PanoVidrio(
                ancho_mm=round(ancho, 1),
                alto_mm=round(alto, 1),
                cantidad=cantidad,
                descripcion=vidrio["nombre"],
            )
        )

    desperdicio = vidrio["desperdicio_pct"]
    if desperdicio is None:
        desperdicio = db.parametro_float("desperdicio_vidrio_pct", 0.10)

    return DespieceVidrio(
        panos=panos,
        tipo=vidrio["nombre"],
        precio_m2=vidrio["precio_m2"],
        desperdicio_pct=desperdicio,
        plancha_ancho_mm=vidrio["plancha_ancho_mm"],
        plancha_alto_mm=vidrio["plancha_alto_mm"],
        vidrio_id=vidrio["id"],
    )


# ---------------------------------------------------------------------------
# Accesorios
# ---------------------------------------------------------------------------


def despiece_accesorios(db, tipologia_codigo, linea_id, ctx, hojas) -> DespieceAccesorios:
    kit = db.kit_para(linea_id, tipologia_codigo)
    if kit is None:
        precio_hoja = db.parametro_float("accesorios_por_hoja", 12000)
        return DespieceAccesorios(
            kit_nombre="Estimación por hoja (sin kit definido)",
            lineas=[
                LineaAccesorio(
                    codigo="ACC-EST",
                    descripcion="Accesorios estimados por hoja",
                    unidad="u",
                    cantidad=float(max(1, hojas)),
                    precio_unitario=precio_hoja,
                )
            ],
        )

    lineas: list[LineaAccesorio] = []
    advertencias: list[str] = []
    for fila in db.items_de_kit(kit["id"]):
        try:
            cantidad = evaluar(fila["cantidad_formula"], ctx, 1)
        except FormulaError as exc:
            advertencias.append(f"Accesorio {fila['codigo']}: {exc}")
            continue
        if cantidad <= 0:
            continue

        unidad = (fila["unidad"] or "u").lower()

        # Las unidades discretas se redondean hacia arriba; ml / m2 quedan fraccionadas.
        if unidad in ("u", "jgo"):
            cantidad = float(int(cantidad + 0.999))
        elif unidad == "kg/m":
            # Accesorio extruido que el proveedor vende por peso: la fórmula da
            # METROS y el precio es $/kg. Se pasa a kilos acá para que el
            # renglón cierre como todos los demás (cantidad x precio = importe)
            # y para que el listado de compras hable en la unidad de la factura.
            peso_lineal = _clave(fila, "peso_kg_m") or 0.0
            if not peso_lineal:
                advertencias.append(
                    f"El accesorio '{fila['codigo']}' está en kg/m pero no tiene "
                    "peso lineal cargado: se cotiza en 0.")
            cantidad = cantidad * peso_lineal
            unidad = "kg"

        lineas.append(
            LineaAccesorio(
                codigo=fila["codigo"],
                descripcion=fila["descripcion"],
                unidad=unidad,
                cantidad=round(cantidad, 3),
                precio_unitario=fila["precio"],
                accesorio_id=_clave(fila, "accesorio_id", 0) or 0,
            )
        )

    return DespieceAccesorios(kit_nombre=kit["nombre"], lineas=lineas, advertencias=advertencias)


# ---------------------------------------------------------------------------
# Orquestador
# ---------------------------------------------------------------------------


def calcular_despiece(db, tipologia_codigo, linea_id, color, ancho_mm, alto_mm, hojas, vidrio_id):
    """Despiece completo de UNA unidad de abertura."""
    aluminio = despiece_aluminio(db, tipologia_codigo, linea_id, color, ancho_mm, alto_mm, hojas)
    ancho_hoja, alto_hoja = medidas_de_hoja(aluminio, ancho_mm, alto_mm)

    ctx = contexto_base(ancho_mm, alto_mm, hojas)
    ctx["AH"] = ancho_hoja
    ctx["HH"] = alto_hoja

    vidrio = despiece_vidrio(db, tipologia_codigo, linea_id, vidrio_id, ctx)
    accesorios = despiece_accesorios(db, tipologia_codigo, linea_id, ctx, hojas)

    return Despiece(
        aluminio=aluminio,
        vidrio=vidrio,
        accesorios=accesorios,
        ancho_hoja_mm=ancho_hoja,
        alto_hoja_mm=alto_hoja,
    )


def optimizar_barras(piezas: list[PiezaCorte], largo_barra_mm: int = 6000):
    """Optimización de corte *first-fit decreasing* sobre barras de largo fijo.

    Devuelve ``(cantidad_de_barras, lista_de_barras)`` donde cada barra es la
    lista de largos que se cortan de ella. Es una heurística: sirve para estimar
    material a comprar, no reemplaza a un optimizador de producción.

    **Todas las piezas que se pasen deben ser del mismo perfil**: dos perfiles
    distintos son dos barras distintas y no se pueden mezclar. Para un despiece
    completo usá :func:`optimizar_por_perfil`.
    """
    largos: list[float] = []
    for p in piezas:
        largos.extend([p.largo_mm] * p.cantidad)
    largos.sort(reverse=True)

    barras: list[list[float]] = []
    restos: list[float] = []
    for largo in largos:
        if largo > largo_barra_mm:
            barras.append([largo])
            restos.append(0.0)
            continue
        for i, resto in enumerate(restos):
            if resto >= largo:
                barras[i].append(largo)
                restos[i] = resto - largo
                break
        else:
            barras.append([largo])
            restos.append(largo_barra_mm - largo)
    return len(barras), barras


def optimizar_por_perfil(piezas: list[PiezaCorte],
                         largo_barra_default: int = 6000) -> list[BarrasPerfil]:
    """Cuántas barras hay que comprar, **perfil por perfil**.

    Un 6200 y un 6201 son extrusiones distintas: no se pueden cortar de la misma
    barra. Por eso se agrupa por código de perfil y cada grupo se empaqueta sobre
    el largo comercial de *ese* perfil (``perfiles.largo_barra_mm``).
    """
    grupos: dict[str, list[PiezaCorte]] = {}
    for pieza in piezas:
        grupos.setdefault(pieza.perfil_codigo, []).append(pieza)

    resultado: list[BarrasPerfil] = []
    for codigo, del_perfil in grupos.items():
        largo_barra = next((p.largo_barra_mm for p in del_perfil if p.largo_barra_mm),
                           largo_barra_default) or largo_barra_default
        _, barras = optimizar_barras(del_perfil, largo_barra)
        resultado.append(BarrasPerfil(
            perfil_codigo=codigo,
            descripcion=del_perfil[0].descripcion,
            largo_barra_mm=largo_barra,
            barras=barras,
            peso_kg_m=del_perfil[0].peso_kg_m,
        ))

    resultado.sort(key=lambda b: b.perfil_codigo)
    return resultado
