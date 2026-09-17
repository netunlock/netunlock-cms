"""
Variables por tipología: opciones tipadas que alimentan el despiece.

El problema que resuelve
------------------------
El motor de fórmulas conoce tres medidas: ancho, alto y cantidad de hojas. Todo
lo demás —si lleva premarco, si el cierre es simple o multipunto, cuánto mide el
paño fijo de abajo— había que resolverlo creando una tipología nueva por cada
combinación. Con diez opciones binarias eso son mil tipologías.

Acá una tipología **declara** sus opciones, cada abertura **elige** sus valores,
y esos valores entran al contexto del motor junto a A, H y N. El despiece se
vuelve condicional sin tocar el motor:

    MT-0205   si(PREMARCO, H + 36, 0)      si(PREMARCO, 2, 0)
    MT-0212   si(ALTO_FIJO > 0, A - 100, 0)

Una pieza de largo cero ya se descarta en :func:`despiece.despiece_aluminio`, así
que "no lleva premarco" no necesita ningún caso especial.

Tipos
-----
``bool``      casilla de verificación         -> 1 / 0
``numero``    campo numérico, con mín. y máx. -> el número
``opcion``    lista de opciones               -> el número asociado a la elegida
``accesorio`` lista del catálogo              -> el **id** del accesorio elegido

El contexto del motor es **numérico**: toda variable termina siendo un float. El
tipo ``accesorio`` no rompe eso porque lo que guarda es el id, que también es un
número. No sirve dentro de una fórmula de largo —nadie corta un perfil a "id 47"
milímetros— pero es lo que lee el kit para saber qué rueda o qué cierre poner:

    R48 / R49     rodamiento simple o doble, según el peso de la hoja
    H123 / H130   cierre de embutir o multipunto

Antes eso obligaba a tener dos kits casi iguales, o dos tipologías. Ahora es una
opción del ítem, y el kit apunta a la variable en vez de a un accesorio fijo
(``kit_items.variable_clave``).

Dos capas separadas
-------------------
``tipologia_variables``            la declaración: qué opciones tiene la tipología
``presupuesto_items.variables_json``  la elección: qué valores tiene ESTA abertura

Están separadas a propósito. Agregarle una variable a una tipología no puede
romper los presupuestos ya guardados: lo que el ítem no tenga elegido toma el
valor por defecto de la declaración.
"""

from __future__ import annotations

import json
import re
import sqlite3

from .despiece import RESERVADAS

#: Tipos admitidos. El orden es el que se ofrece en el alta.
#:
#: 'accesorio' guarda el **id** del accesorio elegido. Es un número, así que
#: entra al contexto del motor como cualquier otra variable; no sirve en una
#: fórmula de largo, pero es lo que lee el kit para saber qué rueda o qué cierre
#: poner. Así una corrediza es una sola tipología con una opción, en vez de dos
#: kits que hay que mantener en paralelo.
TIPOS = ("bool", "numero", "opcion", "accesorio")

#: Una clave válida es un identificador de Python en mayúsculas: es lo que el
#: motor va a resolver como nombre dentro de la fórmula.
_CLAVE_VALIDA = re.compile(r"^[A-Z][A-Z0-9_]*$")


# ---------------------------------------------------------------------------
# Validación del alta
# ---------------------------------------------------------------------------

def normalizar_clave(clave: str) -> str:
    """``  alto fijo `` -> ``ALTO_FIJO``. Devuelve '' si no se puede."""
    limpio = (clave or "").strip().upper().replace(" ", "_").replace("-", "_")
    limpio = re.sub(r"[^A-Z0-9_]", "", limpio)
    return limpio


def validar_clave(clave: str) -> tuple[bool, str]:
    """¿Sirve como nombre de variable en una fórmula?"""
    if not clave:
        return False, "La clave no puede estar vacía."
    if clave in RESERVADAS:
        return False, (f"'{clave}' es una variable del motor "
                       f"({', '.join(sorted(RESERVADAS))}) y no se puede reusar.")
    if not _CLAVE_VALIDA.match(clave):
        return False, ("La clave tiene que empezar con una letra y llevar sólo "
                       "letras, números y guión bajo. Ej.: ALTO_FIJO")
    return True, ""


def parsear_opciones(texto: str) -> list[tuple[str, float]]:
    """Lee el JSON de opciones. Devuelve [] si está vacío o mal formado.

    Formato: ``[["Cierre simple", 0], ["Multipunto", 1]]``
    """
    if not texto:
        return []
    try:
        crudo = json.loads(texto)
    except (TypeError, ValueError):
        return []
    salida = []
    for fila in crudo if isinstance(crudo, list) else []:
        if isinstance(fila, (list, tuple)) and len(fila) >= 2:
            try:
                salida.append((str(fila[0]), float(fila[1])))
            except (TypeError, ValueError):
                continue
    return salida


def serializar_opciones(opciones) -> str:
    return json.dumps([[str(e), float(v)] for e, v in opciones], ensure_ascii=False)


def opciones_de_accesorio(db, filtro: str) -> list[tuple[str, float]]:
    """Los accesorios elegibles para una variable de tipo ``accesorio``.

    ``filtro`` es lo que se guarda en la columna ``opciones`` de la declaración:
    una lista de códigos separados por coma —``"R48, R49"``— que acota la lista a
    las variantes que tienen sentido para esa opción. Vacío significa todo el
    catálogo, que sirve mientras se carga pero es incómodo con 300 accesorios.

    Devuelve ``[(etiqueta, id)]``, el mismo par que ``parsear_opciones``, así el
    control de la interfaz y la lectura del valor no se enteran de la diferencia.
    """
    codigos = [c.strip().upper() for c in (filtro or "").replace(";", ",").split(",")
               if c.strip()]
    if codigos:
        marcas = ",".join("?" * len(codigos))
        filas = db.query(
            f"SELECT id, codigo, descripcion FROM accesorios "
            f"WHERE UPPER(codigo) IN ({marcas}) ORDER BY codigo", tuple(codigos))
    else:
        filas = db.query("SELECT id, codigo, descripcion FROM accesorios "
                         "ORDER BY codigo")
    return [(f"{f['codigo']} — {f['descripcion']}", float(f["id"])) for f in filas]


# ---------------------------------------------------------------------------
# Declaración
# ---------------------------------------------------------------------------

def declaradas(db, tipologia_codigo: str, linea_id: int | None = None) -> list[sqlite3.Row]:
    """Variables de la tipología para esa línea; si no hay, las genéricas.

    Mismo criterio de resolución que ``db.formulas_despiece()``: lo específico
    de la línea pisa a lo genérico, y no se mezclan. Si una línea define sus
    propias variables, manda esa lista entera.
    """
    if not tipologia_codigo:
        return []

    if linea_id:
        propias = db.query(
            "SELECT * FROM tipologia_variables "
            "WHERE tipologia_codigo = ? AND linea_id = ? AND activo = 1 "
            "ORDER BY orden, id",
            (tipologia_codigo, linea_id))
        if propias:
            return propias

    return db.query(
        "SELECT * FROM tipologia_variables "
        "WHERE tipologia_codigo = ? AND linea_id IS NULL AND activo = 1 "
        "ORDER BY orden, id",
        (tipologia_codigo,))


def nombres(db, tipologia_codigo: str, linea_id: int | None = None) -> tuple[str, ...]:
    """Claves disponibles, para pasarle a ``formula_engine.validar()``.

    Sin esto la pantalla de fórmulas rechazaría ``si(PREMARCO, H+36, 0)`` con
    "Variable desconocida", porque validar() prueba contra una lista fija.
    """
    return tuple(RESERVADAS) + tuple(v["clave"] for v in declaradas(db, tipologia_codigo, linea_id))


def ayuda(db, tipologia_codigo: str, linea_id: int | None = None) -> str:
    """Línea de ayuda con las variables de esta tipología, para la UI."""
    filas = declaradas(db, tipologia_codigo, linea_id)
    if not filas:
        return ""
    partes = [f"{v['clave']} = {v['etiqueta']}" for v in filas]
    return "Variables de la tipología:  " + "  ·  ".join(partes)


# ---------------------------------------------------------------------------
# Valores
# ---------------------------------------------------------------------------

def _a_numero(valor, por_defecto: float = 0.0) -> float:
    if isinstance(valor, bool):
        return 1.0 if valor else 0.0
    try:
        return float(valor)
    except (TypeError, ValueError):
        return por_defecto


def valores_por_defecto(db, tipologia_codigo: str,
                        linea_id: int | None = None) -> dict[str, float]:
    return {v["clave"]: _a_numero(v["valor_default"])
            for v in declaradas(db, tipologia_codigo, linea_id)}


#: Variables que no se eligen en el bloque de opciones sino con una casilla que
#: la abertura ya tenía: ``{clave: atributo del Item}``.
#:
#: «Incluye premarco» e «Incluye mosquitero» existían antes que las variables, y
#: son lo que imprimen el PDF ("Con premarco", "Con mosquitero") y la orden de
#: trabajo. Si la tipología declara PREMARCO —las de MDT Actual lo hacen— o
#: MOSQUITERO —las corredizas MDT de las dos líneas—, la casilla es la que decide
#: si se corta: no hay dos controles para lo mismo que puedan decir cosas
#: distintas.
VINCULADAS = {"PREMARCO": "incluye_premarco", "MOSQUITERO": "incluye_mosquitero"}


def resolver(db, item) -> dict[str, float]:
    """Contexto de variables de UNA abertura, listo para el motor.

    Parte de la declaración y le superpone lo que el ítem tenga elegido. Lo que
    no esté elegido queda en su valor por defecto, y lo que el ítem traiga de más
    —una variable que se borró de la tipología— se descarta: el contexto siempre
    refleja la declaración vigente, no lo que se guardó hace seis meses.

    Una variable de :data:`VINCULADAS` que el ítem no traiga elegida toma el
    valor de su casilla en lugar del valor por defecto. Si la trae —una abertura
    guardada cuando la opción todavía se elegía aparte— se respeta: esa abertura
    sigue cortando lo mismo que cortaba.
    """
    filas = declaradas(db, item.tipologia_codigo, item.linea_id)
    if not filas:
        return {}

    elegidos = getattr(item, "variables", None) or {}
    contexto: dict[str, float] = {}

    for fila in filas:
        clave = fila["clave"]
        campo = VINCULADAS.get(clave)
        if clave in elegidos:
            valor = _a_numero(elegidos[clave], _a_numero(fila["valor_default"]))
        elif campo and hasattr(item, campo):
            valor = 1.0 if getattr(item, campo) else 0.0
        else:
            valor = _a_numero(fila["valor_default"])

        # El mínimo y el máximo del alta son un contrato: una abertura vieja con
        # un valor fuera de rango se recorta en vez de propagar un corte absurdo.
        if fila["tipo"] == "numero":
            minimo, maximo = fila["minimo"] or 0.0, fila["maximo"] or 0.0
            if minimo and valor < minimo:
                valor = float(minimo)
            if maximo and valor > maximo:
                valor = float(maximo)

        contexto[clave] = valor

    return contexto


# ---------------------------------------------------------------------------
# Persistencia en el ítem
# ---------------------------------------------------------------------------

def leer_json(texto: str) -> dict:
    """Lee ``presupuesto_items.variables_json`` sin romper por datos raros."""
    if not texto:
        return {}
    try:
        datos = json.loads(texto)
    except (TypeError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def escribir_json(valores: dict | None) -> str:
    """Serializa los valores del ítem, descartando lo que no sea una clave válida.

    No normaliza a la fuerza: si algo no pasa :func:`validar_clave` se descarta,
    en vez de convertirlo en una clave parecida que nadie declaró. Lo que se
    guarda siempre puede volver a leerse como lo que era.
    """
    if not valores:
        return "{}"
    limpio = {}
    for clave, valor in valores.items():
        clave = str(clave).strip().upper()
        ok, _ = validar_clave(clave)
        if ok:
            limpio[clave] = _a_numero(valor)
    return json.dumps(limpio, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Alta y baja
# ---------------------------------------------------------------------------

class ClaveEnUso(ValueError):
    """Se quiere renombrar una clave que las fórmulas están usando.

    Lleva los datos necesarios para que la interfaz ofrezca renombrarla también
    ahí, en vez de dejar las fórmulas apuntando a un nombre que ya no existe.
    """

    def __init__(self, clave_vieja: str, clave_nueva: str, usos: list):
        self.clave_vieja = clave_vieja
        self.clave_nueva = clave_nueva
        self.usos = usos
        super().__init__(
            f"«{clave_vieja}» se usa en {len(usos)} fórmula(s) de despiece.")


def guardar(db, datos: dict, id_: int | None = None,
            renombrar_formulas: bool = False) -> int:
    """Alta o edición de una variable, con la clave ya validada.

    Levanta ``ValueError`` con un mensaje mostrable si la clave no sirve o si
    ya existe otra variable con ese nombre en la misma tipología.

    Si se está **cambiando la clave** de una variable que las fórmulas usan,
    levanta :class:`ClaveEnUso` en lugar de guardar: renombrar sin más dejaría
    las fórmulas evaluando un nombre inexistente, y el error recién aparecería
    la próxima vez que alguien cotice. Con ``renombrar_formulas=True`` se
    renombra en los dos lados.
    """
    datos = dict(datos)
    datos["clave"] = normalizar_clave(datos.get("clave", ""))

    ok, detalle = validar_clave(datos["clave"])
    if not ok:
        raise ValueError(detalle)

    if id_:
        anterior = db.query_one("SELECT * FROM tipologia_variables WHERE id = ?", (id_,))
        if anterior and anterior["clave"] != datos["clave"]:
            usos = en_uso(db, anterior["tipologia_codigo"], anterior["clave"])
            if usos and not renombrar_formulas:
                raise ClaveEnUso(anterior["clave"], datos["clave"], usos)
            if usos:
                renombrar_en_formulas(db, anterior["tipologia_codigo"],
                                      anterior["clave"], datos["clave"])

    if datos.get("tipo") not in TIPOS:
        datos["tipo"] = "bool"

    if datos["tipo"] == "opcion" and not parsear_opciones(datos.get("opciones", "")):
        raise ValueError(
            "Una variable de tipo 'opcion' necesita su lista de opciones.\n\n"
            'Formato:  [["Cierre simple", 0], ["Multipunto", 1]]')

    if datos["tipo"] == "accesorio":
        elegibles = opciones_de_accesorio(db, datos.get("opciones", ""))
        if not elegibles:
            raise ValueError(
                "Ninguno de esos códigos existe en el catálogo de accesorios.\n\n"
                "Escribí los códigos elegibles separados por coma (R48, R49), o "
                "dejá el campo vacío para ofrecer todo el catálogo.")
        # El valor por defecto de una variable de accesorio es un id, no un 0.
        # Si el alta lo dejó en cero, queda el primero de la lista: así el kit
        # siempre resuelve a algo aunque nadie toque la opción al cotizar.
        if _a_numero(datos.get("valor_default")) not in {v for _e, v in elegibles}:
            datos["valor_default"] = f"{elegibles[0][1]:g}"

    try:
        if id_:
            db.actualizar("tipologia_variables", id_, datos)
            return id_
        return db.insertar("tipologia_variables", datos)
    except sqlite3.IntegrityError as exc:
        raise ValueError(
            f"Ya existe una variable «{datos['clave']}» en esa tipología."
        ) from exc


def _menciona(formula: str, clave: str) -> bool:
    """¿La fórmula usa esta variable como nombre completo?

    Con un ``LIKE '%ALTO%'`` a secas, ``ALTO_FIJO`` daría positivo al buscar
    ``ALTO``, y renombrar una rompería la otra. Se compara contra el nombre
    entero, que es como lo lee el motor.
    """
    return re.search(rf"\b{re.escape(clave)}\b", formula or "") is not None


def en_uso(db, tipologia_codigo: str, clave: str) -> list[sqlite3.Row]:
    """Fórmulas que mencionan la variable. Para avisar antes de tocarla."""
    if not clave:
        return []
    # El LIKE filtra en la base y el regex descarta las coincidencias parciales
    patron = f"%{clave}%"
    candidatas = db.query(
        "SELECT * FROM tipologia_formulas WHERE tipologia_codigo = ? "
        "AND (formula_largo LIKE ? OR cantidad_piezas LIKE ?)",
        (tipologia_codigo, patron, patron))
    return [f for f in candidatas
            if _menciona(f["formula_largo"], clave)
            or _menciona(f["cantidad_piezas"], clave)]


def renombrar_en_formulas(db, tipologia_codigo: str, vieja: str, nueva: str) -> int:
    """Cambia el nombre de la variable dentro de las fórmulas. Devuelve cuántas tocó.

    Reemplaza sólo el nombre completo: ``ALTO`` no puede pisar a ``ALTO_FIJO``.
    """
    patron = re.compile(rf"\b{re.escape(vieja)}\b")
    tocadas = 0
    for fila in en_uso(db, tipologia_codigo, vieja):
        db.actualizar("tipologia_formulas", fila["id"], {
            "formula_largo": patron.sub(nueva, fila["formula_largo"] or ""),
            "cantidad_piezas": patron.sub(nueva, fila["cantidad_piezas"] or "")})
        tocadas += 1

    # Las fórmulas de vidrio también pueden usar variables
    for fila in db.query("SELECT * FROM vidrio_formulas WHERE tipologia_codigo = ?",
                         (tipologia_codigo,)):
        campos = {}
        for columna in ("formula_ancho", "formula_alto", "formula_cantidad"):
            if _menciona(fila[columna], vieja):
                campos[columna] = patron.sub(nueva, fila[columna])
        if campos:
            db.actualizar("vidrio_formulas", fila["id"], campos)
            tocadas += 1
    return tocadas
