"""
Importador de catálogos completos en JSON.

Un único archivo puede traer líneas con sus perfiles y precios, tipologías,
fórmulas de corte, vidrios y accesorios. Es el camino para dar de alta un
sistema entero de una extrusora sin cargar nada a mano, y para actualizar
precios de vidrio y accesorios cuando el proveedor manda lista nueva.

    python -m tools.importar_json catalogo.json            # analiza, no escribe
    python -m tools.importar_json catalogo.json --aplicar  # importa

Formato
-------
Todas las secciones son **opcionales**: un archivo con sólo ``vidrios`` es
válido y es justamente el caso de "llegó lista de precios nueva".

    {
      "catalogo": "Metales del Talar — Sistema Actual",
      "version": "2026-07",
      "lineas": [
        {
          "nombre": "Actual",
          "extrusora": "Metales del Talar",
          "modo_costeo": "kg",
          "colores": [{"color": "Blanco", "precio_kg": 15300}],
          "perfiles": [
            {"codigo": "MT-0200", "descripcion": "Umbral y dintel corrediza",
             "peso_kg_m": 1.266, "largo_barra_mm": 6150, "familia": "Marcos",
             "imagen": "dibujos/MT-0200.jpg"}
          ],
          "formulas": [
            {"tipologia": "COR2", "perfil": "MT-0200", "funcion": "MARCO_HORIZONTAL",
             "largo": "A - 42", "cantidad": "2", "nota": ""}
          ],
          "formulas_vidrio": [
            {"tipologia": "COR2", "ancho": "AH + 15", "alto": "HH - 32", "cantidad": "N"}
          ],
          "kits": [
            {"nombre": "Kit corrediza Actual", "tipologia": "COR2",
             "items": [{"accesorio": "RUE-STD", "cantidad": "2*N"}]}
          ]
        }
      ],
      "tipologias": [
        {"codigo": "COR2", "nombre": "Ventana Corrediza 2 hojas", "hojas": 2,
         "esquema": "corrediza", "imagen": "dibujos/cor2.png"}
      ],
      "vidrios":    [{"nombre": "DVH 4/12/4", "tipo": "DVH", "precio_m2": 44516.77}],
      "accesorios": [{"codigo": "RUE-STD", "descripcion": "Rueda", "unidad": "u",
                      "precio": 2800}]
    }

Reglas
------
* **Nada se borra.** Lo que existe se actualiza por su clave natural (nombre de
  línea, código de perfil, código de accesorio); lo que no existe se crea.
* **Funciona sin catálogo asociado.** Si una fórmula nombra un perfil que no
  está en la línea, se importa igual y queda con el peso de respaldo: el
  despiece sigue costeando y el aviso queda en el informe. Lo mismo con los
  kits que nombran accesorios inexistentes.
* **Dos fases.** :func:`analizar` no escribe nada y devuelve el detalle de lo
  que va a pasar; :func:`importar` aplica. La interfaz muestra lo primero y
  pide confirmación antes de lo segundo.
* Las rutas de imagen se resuelven **relativas al propio JSON**, así el paquete
  del extrusor es una carpeta con el .json y los dibujos al lado.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: Claves aceptadas para cada campo. El JSON de un proveedor rara vez usa los
#: mismos nombres que el nuestro, y pelearse por eso no aporta nada.
ALIAS = {
    "codigo": ("codigo", "code", "articulo", "referencia", "sap"),
    "descripcion": ("descripcion", "description", "nombre", "detalle"),
    "peso_kg_m": ("peso_kg_m", "peso", "kg_m", "kgm", "peso_lineal"),
    "largo_barra_mm": ("largo_barra_mm", "largo_barra", "largo", "barra", "longitud"),
    "familia": ("familia", "family", "grupo", "rubro"),
    "imagen": ("imagen", "image", "dibujo", "foto"),
    "notas": ("notas", "nota", "observaciones"),
    "precio": ("precio", "price", "importe", "valor"),
    "precio_m2": ("precio_m2", "precio", "price", "importe"),
    "unidad": ("unidad", "unit", "um"),
}

UNIDADES_VALIDAS = ("u", "jgo", "ml", "m2", "kg", "kg/m")


def _campo(dic: dict, clave: str, por_defecto=None):
    """Lee un campo aceptando cualquiera de sus alias."""
    for nombre in ALIAS.get(clave, (clave,)):
        if nombre in dic and dic[nombre] not in (None, ""):
            return dic[nombre]
    return por_defecto


def _numero(valor, por_defecto: float = 0.0) -> float:
    if valor is None or valor == "":
        return por_defecto
    if isinstance(valor, (int, float)):
        return float(valor)
    limpio = str(valor).strip().replace("$", "").replace(" ", "")
    # "1.234,56" (locale argentino) y "1234.56" (JSON estándar) tienen que
    # dar lo mismo: si hay coma, la coma manda como decimal.
    if "," in limpio:
        limpio = limpio.replace(".", "").replace(",", ".")
    try:
        return float(limpio)
    except ValueError:
        return por_defecto


# ---------------------------------------------------------------------------
# Resultado del análisis
# ---------------------------------------------------------------------------

@dataclass
class Analisis:
    """Qué trae el archivo y qué va a pasar al aplicarlo."""

    catalogo: str = ""
    version: str = ""
    ruta: Path | None = None
    datos: dict = field(default_factory=dict)

    #: {seccion: (a_crear, a_actualizar)}
    conteo: dict[str, tuple[int, int]] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)

    @property
    def valido(self) -> bool:
        return not self.errores and bool(self.conteo)

    @property
    def total(self) -> int:
        return sum(a + b for a, b in self.conteo.values())


def resumen_texto(analisis: Analisis, resultado: dict | None = None) -> str:
    lineas = []
    if analisis.catalogo:
        lineas.append(f"Catálogo: {analisis.catalogo}"
                      + (f"  ·  versión {analisis.version}" if analisis.version else ""))
    for seccion, (nuevos, actualizados) in analisis.conteo.items():
        lineas.append(f"  {seccion:<18} {nuevos:>4} nuevos · {actualizados:>4} actualizados")
    if analisis.avisos:
        lineas.append("")
        lineas.append(f"Avisos ({len(analisis.avisos)}):")
        lineas += [f"  · {a}" for a in analisis.avisos[:8]]
        if len(analisis.avisos) > 8:
            lineas.append(f"  · … y {len(analisis.avisos) - 8} más")
    if analisis.errores:
        lineas.append("")
        lineas.append("ERRORES:")
        lineas += [f"  · {e}" for e in analisis.errores]
    if resultado:
        lineas.append("")
        lineas.append("Importado: " + " · ".join(f"{k}={v}" for k, v in resultado.items() if v))
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Fase 1: análisis (no escribe nada)
# ---------------------------------------------------------------------------

def analizar(db, ruta_json: str | Path) -> Analisis:
    ruta = Path(ruta_json)
    resultado = Analisis(ruta=ruta)

    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        resultado.errores.append(f"No se encuentra el archivo: {ruta}")
        return resultado
    except json.JSONDecodeError as exc:
        resultado.errores.append(f"El archivo no es un JSON válido (línea {exc.lineno}): {exc.msg}")
        return resultado
    except OSError as exc:
        resultado.errores.append(f"No se pudo leer el archivo: {exc}")
        return resultado

    if not isinstance(datos, dict):
        resultado.errores.append("El JSON tiene que ser un objeto, no una lista.")
        return resultado

    resultado.datos = datos
    resultado.catalogo = str(datos.get("catalogo", "") or "")
    resultado.version = str(datos.get("version", "") or "")

    _analizar_globales(db, datos, resultado)
    _analizar_lineas(db, datos, resultado)

    if not resultado.conteo:
        resultado.errores.append(
            "El archivo no trae ninguna sección conocida "
            "(lineas, tipologias, vidrios, accesorios).")
    return resultado


def _analizar_globales(db, datos: dict, res: Analisis) -> None:
    for seccion, tabla, clave in (("vidrios", "vidrios", "nombre"),
                                  ("accesorios", "accesorios", "codigo"),
                                  ("tipologias", "tipologias", "codigo")):
        filas = datos.get(seccion) or []
        if not filas:
            continue
        nuevos = actualizados = 0
        for fila in filas:
            valor = fila.get(clave) or _campo(fila, "codigo") or _campo(fila, "descripcion")
            if not valor:
                res.avisos.append(f"{seccion}: hay un registro sin «{clave}», se saltea.")
                continue
            existe = db.query_one(f"SELECT 1 FROM {tabla} WHERE {clave} = ?", (valor,))
            if existe:
                actualizados += 1
            else:
                nuevos += 1
            if seccion == "accesorios":
                unidad = str(_campo(fila, "unidad", "u")).lower()
                if unidad not in UNIDADES_VALIDAS:
                    res.avisos.append(
                        f"Accesorio {valor}: unidad «{unidad}» desconocida, se usa 'u'.")
                elif unidad == "kg/m" and not _numero(fila.get("peso_kg_m")):
                    res.avisos.append(
                        f"Accesorio {valor}: está en kg/m pero no trae peso lineal.")
        res.conteo[seccion] = (nuevos, actualizados)


def _analizar_lineas(db, datos: dict, res: Analisis) -> None:
    lineas = datos.get("lineas") or []
    if not lineas:
        return

    nuevas = actualizadas = 0
    perfiles_n = perfiles_a = 0
    formulas = formulas_v = kits = colores = 0

    for linea in lineas:
        nombre = linea.get("nombre") or linea.get("linea")
        if not nombre:
            res.avisos.append("Hay una línea sin nombre, se saltea.")
            continue

        fila = db.query_one("SELECT id FROM lineas WHERE nombre = ?", (nombre,))
        lid = fila["id"] if fila else 0
        if fila:
            actualizadas += 1
        else:
            nuevas += 1

        colores += len(linea.get("colores") or [])

        codigos_linea = set()
        for perfil in linea.get("perfiles") or []:
            codigo = _campo(perfil, "codigo")
            if not codigo:
                res.avisos.append(f"{nombre}: hay un perfil sin código, se saltea.")
                continue
            codigos_linea.add(str(codigo))
            existe = lid and db.query_one(
                "SELECT 1 FROM perfiles WHERE linea_id = ? AND codigo = ?", (lid, codigo))
            if existe:
                perfiles_a += 1
            else:
                perfiles_n += 1

        # Las fórmulas se importan aunque el perfil no exista: sin catálogo el
        # despiece igual cotiza con el peso de respaldo. Sólo se avisa.
        for formula in linea.get("formulas") or []:
            formulas += 1
            perfil = formula.get("perfil") or formula.get("perfil_codigo")
            if perfil and str(perfil) not in codigos_linea:
                existe = lid and db.query_one(
                    "SELECT 1 FROM perfiles WHERE linea_id = ? AND codigo = ?", (lid, perfil))
                if not existe:
                    res.avisos.append(
                        f"{nombre}: la fórmula usa el perfil «{perfil}», que no está "
                        "en el catálogo. Se importa igual, con peso de respaldo.")

        formulas_v += len(linea.get("formulas_vidrio") or [])
        kits += len(linea.get("kits") or [])

    res.conteo["lineas"] = (nuevas, actualizadas)
    if perfiles_n or perfiles_a:
        res.conteo["perfiles"] = (perfiles_n, perfiles_a)
    for etiqueta, cantidad in (("colores", colores), ("fórmulas", formulas),
                               ("fórmulas vidrio", formulas_v), ("kits", kits)):
        if cantidad:
            res.conteo[etiqueta] = (cantidad, 0)


# ---------------------------------------------------------------------------
# Fase 2: importación
# ---------------------------------------------------------------------------

def importar(db, analisis: Analisis) -> dict[str, int]:
    """Aplica el análisis. Nunca borra: crea lo que falta y actualiza lo que hay."""
    if not analisis.valido:
        raise ValueError("El análisis tiene errores; no se puede importar.")

    datos = analisis.datos
    base = analisis.ruta.parent if analisis.ruta else Path.cwd()
    hechos: dict[str, int] = {}

    hechos["vidrios"] = _importar_vidrios(db, datos.get("vidrios") or [])
    hechos["accesorios"] = _importar_accesorios(db, datos.get("accesorios") or [])
    hechos["tipologias"] = _importar_tipologias(db, datos.get("tipologias") or [], base)

    totales = _importar_lineas(db, datos.get("lineas") or [], base)
    hechos.update(totales)

    return {k: v for k, v in hechos.items() if v}


def _upsert(db, tabla: str, clave: str, valor, campos: dict) -> bool:
    """Inserta o actualiza por clave natural. Devuelve True si insertó."""
    fila = db.query_one(f"SELECT id FROM {tabla} WHERE {clave} = ?", (valor,))
    if fila:
        db.actualizar(tabla, fila["id"], campos)
        return False
    db.insertar(tabla, dict(campos, **{clave: valor}))
    return True


def _importar_vidrios(db, filas: list) -> int:
    hechos = 0
    for fila in filas:
        nombre = fila.get("nombre") or _campo(fila, "descripcion")
        if not nombre:
            continue
        campos = {
            "tipo": fila.get("tipo", "Float"),
            "espesor_mm": _numero(fila.get("espesor_mm"), 4),
            "precio_m2": _numero(_campo(fila, "precio_m2")),
            "plancha_ancho_mm": int(_numero(fila.get("plancha_ancho_mm"), 3600)),
            "plancha_alto_mm": int(_numero(fila.get("plancha_alto_mm"), 2500)),
            "desperdicio_pct": _numero(fila.get("desperdicio_pct"), 0.10),
            "activo": 1,
        }
        # El precio por plancha es informativo: si no viene, se deduce del m².
        area = campos["plancha_ancho_mm"] * campos["plancha_alto_mm"] / 1_000_000
        campos["precio_plancha"] = _numero(fila.get("precio_plancha"),
                                           round(campos["precio_m2"] * area, 2))
        _upsert(db, "vidrios", "nombre", nombre, campos)
        hechos += 1
    return hechos


def _importar_accesorios(db, filas: list) -> int:
    hechos = 0
    for fila in filas:
        codigo = _campo(fila, "codigo")
        if not codigo:
            continue
        unidad = str(_campo(fila, "unidad", "u")).lower()
        if unidad not in UNIDADES_VALIDAS:
            unidad = "u"
        _upsert(db, "accesorios", "codigo", str(codigo), {
            "descripcion": str(_campo(fila, "descripcion", "") or ""),
            "unidad": unidad,
            "precio": _numero(_campo(fila, "precio")),
            "peso_kg_m": _numero(fila.get("peso_kg_m")),
            "activo": 1,
        })
        hechos += 1
    return hechos


def _guardar_imagen(base: Path, valor, linea_nombre: str, codigo: str) -> str:
    """Copia la imagen referida por el JSON a la carpeta de datos.

    La ruta del JSON se interpreta relativa al propio archivo: el paquete que
    manda el extrusor es una carpeta con el .json y los dibujos al lado.
    """
    if not valor:
        return ""
    from core import imagenes

    origen = Path(str(valor))
    if not origen.is_absolute():
        origen = base / origen
    try:
        return imagenes.guardar(origen, linea_nombre, codigo)
    except (ValueError, OSError):
        return ""


def _importar_tipologias(db, filas: list, base: Path) -> int:
    hechos = 0
    for fila in filas:
        codigo = _campo(fila, "codigo")
        if not codigo:
            continue
        campos = {
            "nombre": str(_campo(fila, "descripcion", codigo) or codigo),
            "hojas_default": int(_numero(fila.get("hojas") or fila.get("hojas_default"), 2)),
            "admite_mosquitero": int(bool(fila.get("admite_mosquitero", 1))),
            "admite_premarco": int(bool(fila.get("admite_premarco", 1))),
            "esquema": fila.get("esquema", "corrediza"),
            "horas_por_m2": _numero(fila.get("horas_por_m2"), 0.85),
            "activo": 1,
        }
        imagen = _guardar_imagen(base, _campo(fila, "imagen"), "tipologia", str(codigo))
        if imagen:
            campos["imagen"] = imagen
        _upsert(db, "tipologias", "codigo", str(codigo), campos)
        hechos += 1
    return hechos


def _importar_lineas(db, filas: list, base: Path) -> dict[str, int]:
    totales = {"lineas": 0, "colores": 0, "perfiles": 0,
               "formulas": 0, "formulas_vidrio": 0, "kits": 0}

    for linea in filas:
        nombre = linea.get("nombre") or linea.get("linea")
        if not nombre:
            continue

        fila = db.query_one("SELECT id FROM lineas WHERE nombre = ?", (nombre,))
        campos = {
            "descripcion": linea.get("descripcion", ""),
            "modo_costeo": linea.get("modo_costeo", "kg"),
            "extrusora": linea.get("extrusora", ""),
            "activo": 1,
        }
        if fila:
            lid = fila["id"]
            db.actualizar("lineas", lid, campos)
        else:
            lid = db.insertar("lineas", dict(campos, nombre=nombre))
        totales["lineas"] += 1

        # -- colores y precios
        for color in linea.get("colores") or []:
            nombre_color = color.get("color") or color.get("nombre")
            if not nombre_color:
                continue
            existente = db.query_one(
                "SELECT id FROM linea_precios WHERE linea_id = ? AND color = ?",
                (lid, nombre_color))
            datos_color = {
                "precio_kg": _numero(color.get("precio_kg")),
                "precio_m2_perfil": _numero(color.get("precio_m2_perfil")),
                "activo": 1,
            }
            if existente:
                db.actualizar("linea_precios", existente["id"], datos_color)
            else:
                db.insertar("linea_precios",
                            dict(datos_color, linea_id=lid, color=nombre_color))
            totales["colores"] += 1

        # -- perfiles
        for perfil in linea.get("perfiles") or []:
            codigo = _campo(perfil, "codigo")
            if not codigo:
                continue
            datos_perfil = {
                "descripcion": str(_campo(perfil, "descripcion", "") or ""),
                "peso_kg_m": _numero(_campo(perfil, "peso_kg_m")),
                "largo_barra_mm": int(_numero(_campo(perfil, "largo_barra_mm"), 6000)),
                "familia": str(_campo(perfil, "familia", "") or ""),
                "notas": str(_campo(perfil, "notas", "") or ""),
            }
            imagen = _guardar_imagen(base, _campo(perfil, "imagen"), nombre, str(codigo))
            if imagen:
                datos_perfil["imagen"] = imagen

            existente = db.query_one(
                "SELECT id FROM perfiles WHERE linea_id = ? AND codigo = ?", (lid, codigo))
            if existente:
                db.actualizar("perfiles", existente["id"], datos_perfil)
            else:
                db.insertar("perfiles", dict(datos_perfil, linea_id=lid, codigo=str(codigo)))
            totales["perfiles"] += 1

        totales["formulas"] += _importar_formulas(db, lid, linea.get("formulas") or [])
        totales["formulas_vidrio"] += _importar_formulas_vidrio(
            db, lid, linea.get("formulas_vidrio") or [])
        totales["kits"] += _importar_kits(db, lid, linea.get("kits") or [])

    return totales


def _importar_formulas(db, lid: int, filas: list) -> int:
    """Reemplaza las fórmulas de las tipologías que el archivo trae.

    Se borran sólo las de (línea, tipología) presentes en el JSON: reimportar un
    catálogo corregido no puede dejar mezcladas las fórmulas viejas con las
    nuevas, pero tampoco tiene por qué tocar tipologías que el archivo no menciona.
    """
    tipologias = {f.get("tipologia") or f.get("tipologia_codigo") for f in filas}
    for codigo in tipologias:
        if codigo:
            db.execute("DELETE FROM tipologia_formulas WHERE linea_id = ? "
                       "AND tipologia_codigo = ?", (lid, codigo))

    hechos = 0
    for orden, formula in enumerate(filas, start=1):
        codigo = formula.get("tipologia") or formula.get("tipologia_codigo")
        perfil = formula.get("perfil") or formula.get("perfil_codigo")
        largo = formula.get("largo") or formula.get("formula_largo")
        if not (codigo and perfil and largo):
            continue
        db.insertar("tipologia_formulas", {
            "tipologia_codigo": str(codigo), "linea_id": lid,
            "perfil_codigo": str(perfil),
            "funcion": formula.get("funcion", "OTRO"),
            "formula_largo": str(largo),
            "cantidad_piezas": str(formula.get("cantidad")
                                   or formula.get("cantidad_piezas") or "1"),
            "peso_kg_m": _numero(formula.get("peso_kg_m")),
            "nota": str(formula.get("nota", "") or ""),
            "orden": int(_numero(formula.get("orden"), orden)),
        })
        hechos += 1
    return hechos


def _importar_formulas_vidrio(db, lid: int, filas: list) -> int:
    hechos = 0
    for formula in filas:
        codigo = formula.get("tipologia") or formula.get("tipologia_codigo")
        if not codigo:
            continue
        campos = {
            "formula_ancho": str(formula.get("ancho") or formula.get("formula_ancho")
                                 or "AH - 60"),
            "formula_alto": str(formula.get("alto") or formula.get("formula_alto")
                                or "HH - 60"),
            "formula_cantidad": str(formula.get("cantidad")
                                    or formula.get("formula_cantidad") or "N"),
        }
        existente = db.query_one(
            "SELECT id FROM vidrio_formulas WHERE tipologia_codigo = ? AND linea_id = ?",
            (codigo, lid))
        if existente:
            db.actualizar("vidrio_formulas", existente["id"], campos)
        else:
            db.insertar("vidrio_formulas",
                        dict(campos, tipologia_codigo=str(codigo), linea_id=lid))
        hechos += 1
    return hechos


def _importar_kits(db, lid: int, filas: list) -> int:
    hechos = 0
    for kit in filas:
        nombre = kit.get("nombre")
        if not nombre:
            continue
        tipologia = str(kit.get("tipologia") or kit.get("tipologia_codigo") or "")
        existente = db.query_one(
            "SELECT id FROM kits WHERE linea_id = ? AND nombre = ? AND tipologia_codigo = ?",
            (lid, nombre, tipologia))
        if existente:
            kid = existente["id"]
            # El kit se reemplaza entero: media composición vieja y media nueva
            # sería un consumo que no existe en ninguna versión del catálogo.
            db.execute("DELETE FROM kit_items WHERE kit_id = ?", (kid,))
        else:
            kid = db.insertar("kits", {
                "nombre": nombre, "linea_id": lid, "tipologia_codigo": tipologia,
                "descripcion": kit.get("descripcion", ""), "activo": 1})

        for item in kit.get("items") or []:
            codigo = item.get("accesorio") or _campo(item, "codigo")
            if not codigo:
                continue
            accesorio = db.query_one("SELECT id FROM accesorios WHERE codigo = ?",
                                     (str(codigo),))
            if accesorio is None:
                continue          # accesorio inexistente: el aviso ya salió en el análisis
            db.insertar("kit_items", {
                "kit_id": kid, "accesorio_id": accesorio["id"],
                "cantidad_formula": str(item.get("cantidad") or "1")})
        hechos += 1
    return hechos


# ---------------------------------------------------------------------------
# Uso desde la consola
# ---------------------------------------------------------------------------

def _main(argv: list[str]) -> int:
    from core.database import DB

    if not argv:
        print(__doc__)
        return 1

    aplicar = "--aplicar" in argv
    rutas = [a for a in argv if not a.startswith("--")]
    if not rutas:
        print("Falta el archivo .json")
        return 1

    db = DB()
    analisis = analizar(db, rutas[0])
    print(resumen_texto(analisis))

    if analisis.errores:
        return 1
    if not aplicar:
        print("\n(Sólo análisis. Agregá --aplicar para importar de verdad.)")
        return 0

    db.respaldar("antes_de_importar_json")
    resultado = importar(db, analisis)
    print("\n" + resumen_texto(analisis, resultado))
    db.cerrar()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
