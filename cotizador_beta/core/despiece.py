"""
Motor de despiece paramétrico.

A partir de las dimensiones nominales (A x H en mm), la cantidad de hojas (N),
la tipología y la línea, resuelve:

  * el listado de piezas de perfil a cortar y su peso,
  * las medidas y superficie de los paños de vidrio,
  * el consumo de accesorios según el kit asociado.
"""

from __future__ import annotations

from dataclasses import replace

from . import avisos as av
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

#: Tope del optimizador de corte, que es cuadrático. Por encima de esto se
#: estima por metros: sigue sirviendo para comprar y el programa no se cuelga.
MAX_PIEZAS_A_EMPAQUETAR = 20_000

FUNCIONES_CONOCIDAS = [
    "MARCO_HORIZONTAL",
    "MARCO_VERTICAL",
    "HOJA_HORIZONTAL",
    "HOJA_VERTICAL",
    "CONTRAVIDRIO",
    "REFUERZO",
    "PREMARCO",
    # Piezas del mosquitero de una corrediza. No son HOJA_*, así que no cuentan
    # para AH ni HH: el vidrio sale de la hoja y no del mosquitero, que tiene el
    # zócalo más largo. Si el despiece las trae, calculo.costo_mosquitero() no
    # vuelve a cobrar el mosquitero entero por m².
    "MOSQUITERO",
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


#: Nombres que define el propio motor. Una variable de tipología nunca los pisa:
#: si alguien llamara "A" a una variable, el ancho de la abertura dejaría de ser
#: el ancho y el despiece entero mentiría en silencio.
RESERVADAS = frozenset({"A", "H", "N", "AH", "HH", "PERIM", "M2"})


def _tiene_catalogo(db, linea_id) -> bool:
    """¿La línea tiene perfiles propios cargados?

    Distingue a quien armó su sistema —y por lo tanto espera que se use— de una
    línea recién creada, donde caer en las fórmulas genéricas es lo esperable.
    """
    if not linea_id:
        return False
    return bool(db.query_one("SELECT 1 FROM perfiles WHERE linea_id = ? LIMIT 1",
                             (linea_id,)))


def contexto_base(ancho_mm: float, alto_mm: float, hojas: int,
                  variables: dict | None = None) -> dict[str, float]:
    """Contexto con el que se evalúan todas las fórmulas de la abertura.

    ``variables`` son las opciones declaradas por la tipología (premarco sí o
    no, alto del paño fijo, tipo de cierre…). Entran como una clave más: el
    motor de fórmulas las resuelve igual que a A o H, así que no hay nada que
    enseñarle. Con ``variables=None`` el contexto es idéntico al de siempre.
    """
    ctx = {
        "A": float(ancho_mm),
        "H": float(alto_mm),
        "N": float(max(1, hojas)),
        "AH": float(ancho_mm),
        "HH": float(alto_mm),
        "PERIM": 2.0 * (ancho_mm + alto_mm),
        "M2": ancho_mm * alto_mm / 1_000_000.0,
    }

    for clave, valor in (variables or {}).items():
        clave = str(clave).strip().upper()
        if not clave or clave in RESERVADAS:
            continue
        try:
            ctx[clave] = float(valor)
        except (TypeError, ValueError):
            # Una variable rota vale 0 y el despiece sigue: es preferible una
            # pieza de menos que un presupuesto que no se puede abrir.
            ctx[clave] = 0.0

    return ctx


# ---------------------------------------------------------------------------
# Aluminio
# ---------------------------------------------------------------------------


def despiece_aluminio(db, tipologia_codigo, linea_id, color, ancho_mm, alto_mm, hojas,
                      variables=None):
    """Devuelve un :class:`DespieceAluminio` con las piezas de corte."""
    ctx = contexto_base(ancho_mm, alto_mm, hojas, variables)
    avisos: list = []

    linea = db.linea(linea_id)
    linea_nombre = linea["nombre"] if linea else "?"
    modo = (linea["modo_costeo"] if linea else None) or db.parametro("modo_costeo_default", "kg")

    precio = db.precio_linea(linea_id, color)
    precio_kg = precio["precio_kg"] if precio else 0.0
    precio_m2 = precio["precio_m2_perfil"] if precio else 0.0
    if precio is None:
        avisos.append(av.linea_sin_precio(linea_id, linea_nombre, color))

    filas = db.formulas_despiece(tipologia_codigo, linea_id)
    if not filas:
        avisos.append(av.sin_formulas(tipologia_codigo, linea_id, linea_nombre))
    elif all(f["linea_id"] is None for f in filas) and _tiene_catalogo(db, linea_id):
        # Se cayó en las fórmulas genéricas teniendo la línea su propio catálogo:
        # el usuario cargó perfiles esperando usarlos y el despiece los ignora.
        # Sin este aviso, lo único que se ve son los perfiles inventados de las
        # genéricas, y el problema parece estar donde no está.
        tipologia = db.tipologia(tipologia_codigo)
        avisos.append(av.despiece_generico(
            tipologia_codigo, tipologia["nombre"] if tipologia else "",
            linea_id, linea_nombre))

    piezas: list[PiezaCorte] = []
    for fila in filas:
        try:
            largo = evaluar(fila["formula_largo"], ctx)
            cantidad = evaluar_entero(fila["cantidad_piezas"], ctx, 1)
        except FormulaError as exc:
            avisos.append(av.formula_invalida(
                fila["perfil_codigo"], fila["funcion"], str(exc),
                tipologia_codigo, linea_id, linea_nombre))
            continue

        if largo <= 0 or cantidad <= 0:
            continue

        # Freno antes de que una fórmula equivocada cuelgue el programa.
        if cantidad > av.MAX_PIEZAS_POR_FORMULA:
            avisos.append(av.demasiadas_piezas(
                fila["perfil_codigo"], _clave(fila, "nota", "") or fila["funcion"],
                cantidad, tipologia_codigo, linea_id, linea_nombre))
            cantidad = av.MAX_PIEZAS_POR_FORMULA

        # Una medida positiva pero absurda es peor que una en cero: la pieza
        # entra al despiece, suma peso y precio, y nadie se entera de que la
        # abertura no se puede armar.
        if largo < av.CORTE_MINIMO_PLAUSIBLE:
            avisos.append(av.corte_muy_corto(
                fila["perfil_codigo"], _clave(fila, "nota", "") or fila["funcion"],
                largo, tipologia_codigo, linea_id, linea_nombre))

        perfil = db.perfil(linea_id, fila["perfil_codigo"])
        peso_kg_m = perfil["peso_kg_m"] if perfil and perfil["peso_kg_m"] else fila["peso_kg_m"]
        descripcion = perfil["descripcion"] if perfil else fila["funcion"].replace("_", " ").title()

        if perfil is None:
            avisos.append(av.perfil_fuera_catalogo(
                fila["perfil_codigo"], linea_id, linea_nombre))
        if not peso_kg_m:
            avisos.append(av.perfil_sin_peso(
                perfil["id"] if perfil else 0, fila["perfil_codigo"],
                linea_id, linea_nombre))
        elif not (av.PESO_MINIMO_PLAUSIBLE <= peso_kg_m <= av.PESO_MAXIMO_PLAUSIBLE):
            # Un peso ausente se nota enseguida; uno mil veces más grande no, y
            # el costo del aluminio sale justamente de ahí.
            avisos.append(av.peso_sospechoso(
                perfil["id"] if perfil else 0, fila["perfil_codigo"],
                float(peso_kg_m), linea_id, linea_nombre))

        largo_barra = (perfil["largo_barra_mm"] if perfil and perfil["largo_barra_mm"]
                       else 6000)
        if largo > largo_barra:
            avisos.append(av.corte_excede_barra(
                fila["perfil_codigo"], largo, int(largo_barra), linea_id, linea_nombre))

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
        avisos=avisos,
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
        linea = db.linea(linea_id)
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
            avisos=[av.sin_kit(linea_id, linea["nombre"] if linea else "?",
                               tipologia_codigo)],
        )

    lineas: list[LineaAccesorio] = []
    avisos: list = []
    for fila in db.items_de_kit(kit["id"]):
        try:
            cantidad = evaluar(fila["cantidad_formula"], ctx, 1)
        except FormulaError as exc:
            avisos.append(av.accesorio_formula(fila["codigo"], str(exc)))
            continue
        if cantidad <= 0:
            continue

        # Si el renglón apunta a una variable, el accesorio lo elige quien carga
        # la abertura: la rueda simple o la doble según el peso de la hoja.
        clave = _clave(fila, "variable_clave", "") or ""
        if clave and clave in ctx:
            elegido = db.query_one("SELECT * FROM accesorios WHERE id = ?",
                                   (int(ctx[clave]),))
            if elegido is not None:
                fila = dict(fila)
                fila.update({"accesorio_id": elegido["id"], "codigo": elegido["codigo"],
                             "descripcion": elegido["descripcion"],
                             "unidad": elegido["unidad"], "precio": elegido["precio"],
                             "peso_kg_m": elegido["peso_kg_m"]})
            else:
                avisos.append(av.accesorio_no_elegido(clave, fila["codigo"]))

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
                avisos.append(av.accesorio_sin_peso(
                    _clave(fila, "accesorio_id", 0) or 0, fila["codigo"]))
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

    return DespieceAccesorios(kit_nombre=kit["nombre"], lineas=lineas, avisos=avisos)


# ---------------------------------------------------------------------------
# Orquestador
# ---------------------------------------------------------------------------


def calcular_despiece(db, tipologia_codigo, linea_id, color, ancho_mm, alto_mm, hojas, vidrio_id,
                      variables=None, _profundidad=0):
    """Despiece completo de UNA unidad de abertura.

    Si la tipología es **compuesta** (una corrediza con paño fijo abajo, por
    ejemplo) se despieza cada paño con su propia tipología y medida, y todo se
    suma al despiece propio de la compuesta: su marco perimetral y el perfil de
    acople entre paños.
    """
    from . import composicion

    panos = composicion.panos(db, tipologia_codigo, linea_id)
    if panos and _profundidad < composicion.PROFUNDIDAD_MAXIMA:
        return _despiece_compuesto(db, tipologia_codigo, linea_id, color,
                                   ancho_mm, alto_mm, hojas, vidrio_id,
                                   variables, panos, _profundidad)

    aluminio = despiece_aluminio(db, tipologia_codigo, linea_id, color, ancho_mm, alto_mm, hojas,
                                 variables)
    ancho_hoja, alto_hoja = medidas_de_hoja(aluminio, ancho_mm, alto_mm)

    ctx = contexto_base(ancho_mm, alto_mm, hojas, variables)
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


def _despiece_compuesto(db, tipologia_codigo, linea_id, color, ancho_mm, alto_mm,
                        hojas, vidrio_id, variables, panos, profundidad):
    """Despiece de una tipología formada por otras.

    Cada paño se resuelve con su propia tipología y con la medida que le toca,
    calculada en el contexto de la compuesta. Al resultado se le suma el
    despiece propio de la compuesta —marco perimetral y acople—, que se carga
    en ``tipologia_formulas`` como el de cualquier tipología.
    """
    # Import diferido: variables.py toma RESERVADAS de este módulo, así que
    # traerlo arriba cerraría un ciclo de importación.
    from . import variables as variables_mod

    ctx = contexto_base(ancho_mm, alto_mm, hojas, variables)

    # Lo propio de la compuesta: el marco que rodea todo y los acoples
    propio = despiece_aluminio(db, tipologia_codigo, linea_id, color,
                               ancho_mm, alto_mm, hojas, variables)
    piezas = list(propio.piezas)
    avisos = list(propio.avisos)
    panos_vidrio = []
    accesorios = []
    kit_nombres = []
    ancho_hoja = alto_hoja = 0.0

    for fila in panos:
        etiqueta = fila["etiqueta"] or fila["tipologia_hijo"]
        try:
            ancho_pano = evaluar(fila["formula_ancho"], ctx, ancho_mm)
            alto_pano = evaluar(fila["formula_alto"], ctx, alto_mm)
            hojas_pano = evaluar_entero(fila["formula_hojas"], ctx, 1)
        except FormulaError as exc:
            avisos.append(av.formula_invalida(
                fila["tipologia_hijo"], f"paño «{etiqueta}»", str(exc),
                tipologia_codigo, linea_id, ""))
            continue

        # Un paño de medida imposible no se despieza: se avisa y se sigue, para
        # que el resto del conjunto se pueda seguir cotizando.
        if ancho_pano <= 0 or alto_pano <= 0:
            avisos.append(av.pano_imposible(
                etiqueta, fila["tipologia_hijo"], ancho_pano, alto_pano,
                tipologia_codigo, linea_id))
            continue

        # Cada paño resuelve SUS PROPIAS variables, con sus valores por defecto.
        # Las de la compuesta no se heredan a propósito: dos tipologías pueden
        # usar el mismo nombre para cosas distintas. Acá, ALTO_FIJO significa
        # "alto del paño fijo del conjunto" para la compuesta y "alto del paño
        # fijo interno" para la corrediza; heredarlo le hacía generar un paño
        # fijo adentro del suyo.
        #
        # El conjunto gobierna a sus paños por donde corresponde: las fórmulas
        # de ancho, alto y hojas de la composición, que sí ven sus variables.
        vars_hijo = variables_mod.valores_por_defecto(
            db, fila["tipologia_hijo"], linea_id)

        hijo = calcular_despiece(
            db, fila["tipologia_hijo"], linea_id, color,
            ancho_pano, alto_pano, hojas_pano, vidrio_id, vars_hijo,
            _profundidad=profundidad + 1)

        # Cada pieza recuerda de qué paño salió: sin eso la lista de corte de
        # una compuesta es una pila de largos sin decir a qué parte va cada uno.
        for pieza in hijo.aluminio.piezas:
            piezas.append(replace(pieza, origen=etiqueta))
        for aviso in hijo.avisos:
            aviso.item = f"{etiqueta}: {aviso.item}" if aviso.item else etiqueta
            avisos.append(aviso)

        panos_vidrio.extend(hijo.vidrio.panos)
        accesorios.extend(hijo.accesorios.lineas)
        if hijo.accesorios.kit_nombre:
            kit_nombres.append(f"{etiqueta}: {hijo.accesorios.kit_nombre}")

        # La medida de hoja del conjunto es la mayor de sus paños: es la que
        # usan las fórmulas de vidrio de la compuesta, si tuviera.
        ancho_hoja = max(ancho_hoja, hijo.ancho_hoja_mm)
        alto_hoja = max(alto_hoja, hijo.alto_hoja_mm)

    aluminio = DespieceAluminio(
        piezas=piezas,
        desperdicio_pct=propio.desperdicio_pct,
        precio_kg=propio.precio_kg,
        precio_m2_perfil=propio.precio_m2_perfil,
        modo_costeo=propio.modo_costeo,
        m2_abertura=ctx["M2"],
        avisos=avisos,
    )

    # El vidrio se toma de los paños: la compuesta no tiene vidrio propio, el
    # vidrio está en cada abertura que la forma.
    vidrio = despiece_vidrio(db, tipologia_codigo, linea_id, vidrio_id, ctx)
    vidrio.panos = panos_vidrio

    return Despiece(
        aluminio=aluminio,
        vidrio=vidrio,
        accesorios=DespieceAccesorios(
            kit_nombre=" · ".join(kit_nombres) or "Sin kit",
            lineas=accesorios),
        ancho_hoja_mm=ancho_hoja or ancho_mm,
        alto_hoja_mm=alto_hoja or alto_mm,
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

    # El empaquetado es cuadrático. Con decenas de miles de piezas —una obra
    # enorme, o una cantidad de ítem cargada de más— dejaría de responder, así
    # que a partir de cierto volumen se estima por metros en vez de acomodar
    # pieza por pieza. El número sirve igual para comprar; lo que se pierde es
    # el detalle de qué se corta de cada barra.
    if len(largos) > MAX_PIEZAS_A_EMPAQUETAR:
        import math
        total_mm = sum(largos)
        cantidad_barras = max(1, math.ceil(total_mm / max(1, largo_barra_mm)))
        return cantidad_barras, [[largo_barra_mm]] * cantidad_barras

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


def _clave_de_perfil(pieza: PiezaCorte) -> tuple:
    """Dos piezas comparten barra sólo si son **el mismo perfil del mismo catálogo**.

    Se agrupa por id y no sólo por código: dos líneas distintas pueden usar el
    mismo código para perfiles distintos, y mezclarlos haría comprar barras que
    no existen. Cuando el perfil no está en el catálogo (fórmula genérica) el id
    es 0 y se cae al código, que es lo único que hay.
    """
    return (pieza.perfil_id, pieza.perfil_codigo)


def escalar(piezas: list[PiezaCorte], veces: int) -> list[PiezaCorte]:
    """Las mismas piezas para ``veces`` unidades de la abertura.

    No duplica objetos: multiplica la cantidad, que es lo que después consume el
    optimizador.
    """
    veces = max(1, int(veces))
    if veces == 1:
        return list(piezas)
    return [replace(p, cantidad=p.cantidad * veces) for p in piezas]


def optimizar_por_perfil(piezas: list[PiezaCorte],
                         largo_barra_default: int = 6000) -> list[BarrasPerfil]:
    """Cuántas barras hay que comprar, **perfil por perfil**.

    Un 6200 y un 6201 son extrusiones distintas: no se pueden cortar de la misma
    barra. Por eso se agrupa por perfil y cada grupo se empaqueta sobre el largo
    comercial de *ese* perfil (``perfiles.largo_barra_mm``).
    """
    grupos: dict[tuple, list[PiezaCorte]] = {}
    for pieza in piezas:
        grupos.setdefault(_clave_de_perfil(pieza), []).append(pieza)

    resultado: list[BarrasPerfil] = []
    for del_perfil in grupos.values():
        largo_barra = next((p.largo_barra_mm for p in del_perfil if p.largo_barra_mm),
                           largo_barra_default) or largo_barra_default
        _, barras = optimizar_barras(del_perfil, largo_barra)
        resultado.append(BarrasPerfil(
            perfil_codigo=del_perfil[0].perfil_codigo,
            descripcion=del_perfil[0].descripcion,
            largo_barra_mm=largo_barra,
            barras=barras,
            peso_kg_m=del_perfil[0].peso_kg_m,
        ))

    resultado.sort(key=lambda b: b.perfil_codigo)
    return resultado


def optimizar_conjunto(grupos, largo_barra_default: int = 6000) -> list[BarrasPerfil]:
    """Barras a comprar para VARIAS aberturas juntas.

    ``grupos`` es un iterable de ``(piezas, unidades)``.

    Optimizar abertura por abertura y después sumar es comprar de más, y no por
    poco: tres ventanas iguales cuyo parante mide 1 m gastan **una** barra de 6,
    no tres. El recorte de una abertura sirve para la siguiente siempre que sea
    el mismo perfil, así que hay que juntar todas las piezas antes de empaquetar.

    Es la diferencia entre el material que se compra y el que se paga.
    """
    todas: list[PiezaCorte] = []
    for piezas, unidades in grupos:
        todas.extend(escalar(piezas, unidades))
    return optimizar_por_perfil(todas, largo_barra_default)


def barras_de_presupuesto(resultados, largo_barra_default: int = 6000) -> list[BarrasPerfil]:
    """Barras a comprar para un presupuesto entero, con sus cantidades."""
    return optimizar_conjunto(
        ((r.despiece.aluminio.piezas, r.item.cantidad) for r in resultados),
        largo_barra_default)
