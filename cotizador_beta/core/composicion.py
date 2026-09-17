"""
Tipologías compuestas: una abertura formada por otras.

El problema que resuelve
------------------------
La ventana con paño fijo abajo, la corrediza con banderola arriba, el paño fijo
partido en tres. Hasta acá había que cargarlas como dos ítems separados y
aclarar en observaciones que iban acopladas: dos marcos completos donde va uno,
el perfil de acople sin contar, y dos renglones en el presupuesto para algo que
el cliente ve como una sola ventana.

Cómo funciona
-------------
Una tipología declara de qué paños está hecha. Cada paño recibe su medida por
**fórmula**, evaluada en el contexto de la compuesta:

    orden 1   FIJO   ancho = A   alto = ALTO_FIJO
    orden 2   COR2   ancho = A   alto = H - ALTO_FIJO - 45

Las medidas cierran por construcción. No hay dos aberturas negociando entre
ellas: hay un hueco que se reparte, que es como lo piensa el carpintero.

Los perfiles propios de la compuesta —el marco perimetral que rodea todo y el
perfil de acople entre paños— van en ``tipologia_formulas`` como los de
cualquier tipología. El motor de fórmulas y las variables funcionan igual.

Anidamiento
-----------
Un paño puede a su vez ser compuesto. Está permitido y se resuelve solo, pero
con dos límites: una tipología no puede contenerse a sí misma —ni directa ni
indirectamente— y hay un tope de profundidad. Sin eso, un ciclo cuelga el
programa en un bucle infinito mientras el usuario mira una ventana congelada.
"""

from __future__ import annotations

import sqlite3  # noqa: F401  (se usa en los except de renombrar/duplicar)

#: Hasta dónde se baja anidando compuestas. Tres niveles cubren cualquier
#: abertura real (un conjunto de conjuntos ya es una fachada, no una ventana) y
#: el tope evita que un error de carga se convierta en un cuelgue.
PROFUNDIDAD_MAXIMA = 3


def panos(db, tipologia_codigo: str, linea_id: int | None = None) -> list[sqlite3.Row]:
    """Paños que forman la tipología; vacío si no es compuesta.

    Mismo criterio de resolución que el resto: lo específico de la línea pisa a
    lo genérico, y no se mezclan.
    """
    if not tipologia_codigo:
        return []

    if linea_id:
        propios = db.query(
            "SELECT * FROM tipologia_composicion "
            "WHERE tipologia_codigo = ? AND linea_id = ? AND activo = 1 "
            "ORDER BY orden, id",
            (tipologia_codigo, linea_id))
        if propios:
            return propios

    return db.query(
        "SELECT * FROM tipologia_composicion "
        "WHERE tipologia_codigo = ? AND linea_id IS NULL AND activo = 1 "
        "ORDER BY orden, id",
        (tipologia_codigo,))


def es_compuesta(db, tipologia_codigo: str, linea_id: int | None = None) -> bool:
    return bool(panos(db, tipologia_codigo, linea_id))


def hijos_directos(db, tipologia_codigo: str) -> set[str]:
    """Todas las tipologías que aparecen como paño, en cualquier línea."""
    return {f["tipologia_hijo"] for f in db.query(
        "SELECT DISTINCT tipologia_hijo FROM tipologia_composicion "
        "WHERE tipologia_codigo = ?", (tipologia_codigo,))}


def crearia_ciclo(db, compuesta: str, hijo: str) -> list[str] | None:
    """¿Agregar ``hijo`` dentro de ``compuesta`` cerraría un ciclo?

    Devuelve el camino que lo cierra, o ``None`` si no hay ciclo. Se llama antes
    de guardar: un ciclo no se detecta cotizando, se cuelga cotizando.
    """
    if hijo == compuesta:
        return [compuesta, hijo]

    # Se busca si desde 'hijo' se puede llegar de vuelta a 'compuesta'
    pendientes = [(hijo, [compuesta, hijo])]
    vistos = set()
    while pendientes:
        actual, camino = pendientes.pop()
        if actual in vistos:
            continue
        vistos.add(actual)
        for siguiente in hijos_directos(db, actual):
            if siguiente == compuesta:
                return camino + [siguiente]
            pendientes.append((siguiente, camino + [siguiente]))
    return None


def guardar_pano(db, datos: dict, id_: int | None = None) -> int:
    """Alta o edición de un paño, validando que no se arme un ciclo."""
    datos = dict(datos)
    compuesta = (datos.get("tipologia_codigo") or "").strip()
    hijo = (datos.get("tipologia_hijo") or "").strip()

    if not compuesta or not hijo:
        raise ValueError("Faltan la tipología compuesta y la del paño.")

    camino = crearia_ciclo(db, compuesta, hijo)
    if camino:
        raise ValueError(
            "Esa composición se contiene a sí misma:\n\n    "
            + "  →  ".join(camino)
            + "\n\nUna tipología no puede ser paño de sí misma, ni directa ni "
              "indirectamente: el despiece no terminaría nunca.")

    if id_:
        db.actualizar("tipologia_composicion", id_, datos)
        return id_
    return db.insertar("tipologia_composicion", datos)


def usada_en(db, tipologia_codigo: str) -> list[sqlite3.Row]:
    """Compuestas que usan esta tipología como paño. Para avisar antes de borrar."""
    return db.query(
        "SELECT DISTINCT tipologia_codigo FROM tipologia_composicion "
        "WHERE tipologia_hijo = ?", (tipologia_codigo,))


#: Tablas que apuntan a una tipología por su código, no por id. Renombrar el
#: código sin tocarlas deja todo huérfano: las fórmulas siguen existiendo pero
#: apuntan a una tipología que ya no se llama así, y desde la interfaz parece
#: que se borraron.
DEPENDIENTES = (
    ("tipologia_formulas", "tipologia_codigo", "fórmulas de despiece"),
    ("vidrio_formulas", "tipologia_codigo", "fórmulas de vidrio"),
    ("tipologia_variables", "tipologia_codigo", "variables"),
    ("tipologia_composicion", "tipologia_codigo", "paños de composición"),
    ("tipologia_composicion", "tipologia_hijo", "usos como paño de otra"),
    ("kits", "tipologia_codigo", "kits de accesorios"),
    ("presupuesto_items", "tipologia_codigo", "aberturas ya presupuestadas"),
)


def dependencias(db, codigo: str) -> list[tuple[str, int]]:
    """Qué cuelga de una tipología, por su código. Devuelve [(qué es, cuántos)]."""
    salida = []
    for tabla, columna, etiqueta in DEPENDIENTES:
        try:
            fila = db.query_one(
                f"SELECT COUNT(*) AS c FROM {tabla} WHERE {columna} = ?", (codigo,))
        except Exception:
            continue                       # la tabla puede no existir todavía
        if fila and fila["c"]:
            salida.append((etiqueta, fila["c"]))
    return salida


def renombrar_codigo(db, viejo: str, nuevo: str) -> int:
    """Lleva todo lo que cuelga de una tipología al código nuevo.

    Se hace en una sola transacción: si se cortara a la mitad, quedarían
    fórmulas apuntando a un código y variables a otro, que es peor que el
    problema original.
    """
    tocados = 0
    # Se usa la conexión directa porque db.execute() devuelve lastrowid, que en
    # un UPDATE no dice nada, y porque hay que confirmar una sola vez al final.
    try:
        for tabla, columna, _etiqueta in DEPENDIENTES:
            try:
                cur = db.cx.execute(
                    f"UPDATE {tabla} SET {columna} = ? WHERE {columna} = ?",
                    (nuevo, viejo))
                tocados += cur.rowcount or 0
            except sqlite3.OperationalError:
                continue                   # la tabla puede no existir todavía
        db.cx.commit()
    except Exception:
        db.cx.rollback()
        raise
    return tocados


def duplicar_tipologia(db, codigo: str, codigo_nuevo: str,
                       nombre_nuevo: str = "") -> str:
    """Clona una tipología con todo lo que cuelga de ella.

    Es lo que se hace todo el tiempo: una corrediza igual a otra pero con el
    perfil de hoja para DVH, o una variante con premarco. Copiar a mano
    veinte fórmulas para cambiar dos es donde aparecen los errores.

    Se copian fórmulas, fórmulas de vidrio, variables, composición y kits. **No**
    se copian los presupuestos ya hechos, por razones evidentes.
    """
    original = db.tipologia(codigo)
    if original is None:
        raise ValueError(f"No existe la tipología «{codigo}».")

    codigo_nuevo = (codigo_nuevo or "").strip().upper()
    if not codigo_nuevo:
        raise ValueError("Hay que darle un código a la tipología nueva.")
    if db.query_one("SELECT 1 FROM tipologias WHERE codigo = ?", (codigo_nuevo,)):
        raise ValueError(f"Ya existe una tipología con el código «{codigo_nuevo}».")

    datos = {c: original[c] for c in original.keys() if c not in ("id", "codigo", "nombre")}
    datos["codigo"] = codigo_nuevo
    datos["nombre"] = nombre_nuevo or f"{original['nombre']} (copia)"
    db.insertar("tipologias", datos)

    # Cada tabla se copia entera cambiando sólo el código. Se listan a mano y no
    # con SELECT *: así, si mañana alguna gana una columna, esto sigue andando.
    copias = (
        ("tipologia_formulas", "tipologia_codigo",
         ("linea_id", "perfil_codigo", "funcion", "formula_largo",
          "cantidad_piezas", "peso_kg_m", "nota", "orden")),
        ("vidrio_formulas", "tipologia_codigo",
         ("linea_id", "formula_ancho", "formula_alto", "formula_cantidad")),
        ("tipologia_variables", "tipologia_codigo",
         ("linea_id", "clave", "etiqueta", "tipo", "opciones", "valor_default",
          "minimo", "maximo", "ayuda", "activo", "orden")),
        ("tipologia_composicion", "tipologia_codigo",
         ("linea_id", "orden", "tipologia_hijo", "etiqueta", "formula_ancho",
          "formula_alto", "formula_hojas", "activo")),
        ("kits", "tipologia_codigo",
         ("nombre", "linea_id", "descripcion", "activo")),
    )

    for tabla, columna, campos in copias:
        try:
            filas = db.query(f"SELECT * FROM {tabla} WHERE {columna} = ?", (codigo,))
        except sqlite3.OperationalError:
            continue
        for fila in filas:
            nuevo = {c: fila[c] for c in campos if c in fila.keys()}
            nuevo[columna] = codigo_nuevo
            if tabla == "kits":
                # El kit clonado necesita nombre propio: hay un UNIQUE por
                # (línea, tipología, nombre) y además conviene distinguirlos.
                nuevo["nombre"] = f"{fila['nombre']} ({codigo_nuevo})"
                kit_nuevo = db.insertar("kits", nuevo)
                for item in db.query("SELECT * FROM kit_items WHERE kit_id = ?",
                                     (fila["id"],)):
                    db.insertar("kit_items", {
                        "kit_id": kit_nuevo, "accesorio_id": item["accesorio_id"],
                        "cantidad_formula": item["cantidad_formula"]})
            else:
                db.insertar(tabla, nuevo)

    return codigo_nuevo


def resumen_de_tipologia(db, codigo: str) -> str:
    """Una línea con lo que cuelga de la tipología, para mostrar antes de copiar."""
    partes = [f"{n} {etiqueta}" for etiqueta, n in dependencias(db, codigo)
              if etiqueta != "aberturas ya presupuestadas"]
    return " · ".join(partes) or "sin nada cargado todavía"


def describir(db, tipologia_codigo: str, linea_id: int | None = None) -> str:
    """Resumen legible de la composición, para la interfaz."""
    filas = panos(db, tipologia_codigo, linea_id)
    if not filas:
        return ""
    partes = []
    for f in filas:
        etiqueta = f["etiqueta"] or f["tipologia_hijo"]
        partes.append(f"{etiqueta} ({f['formula_ancho']} × {f['formula_alto']})")
    return "  +  ".join(partes)
