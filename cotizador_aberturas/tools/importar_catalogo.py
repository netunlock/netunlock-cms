"""
Importador genérico de catálogos de perfiles desde Excel.

A diferencia de :mod:`tools.importar_excel`, que lee la planilla propia del
cotizador, este módulo está pensado para la lista de perfiles que publica
*cualquier* extrusora (Aluar, Hydro, Alcemar…) en *cualquier* línea. No exige un
layout: busca la fila de encabezados y deduce qué columna es cada cosa a partir
del texto del título.

Lo que necesita el programa de cada perfil es poco:

    código · descripción · peso (kg/m) · largo de barra (mm)

y opcionalmente familia, notas y el nombre de un archivo de imagen.

El flujo es en dos pasos a propósito, para que el usuario vea qué se va a
importar **antes** de tocar la base:

    analisis = analizar("catalogo.xlsx")      # no escribe nada
    resumen  = importar(db, linea_id, analisis.filas)

Requiere ``openpyxl`` (``pip install openpyxl``).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

#: Cuántas filas se miran, desde arriba, buscando los encabezados.
MAX_FILAS_ENCABEZADO = 30

#: Cuántas filas vacías seguidas cortan la lectura de datos.
VACIAS_PARA_CORTAR = 15

#: Largo de barra que se asume cuando la planilla no trae la columna.
LARGO_BARRA_DEFECTO = 6000


def _normalizar(texto) -> str:
    """Minúsculas, sin acentos y sin superíndices (NFKD convierte '²' en '2')."""
    if texto is None:
        return ""
    texto = str(texto).strip().lower()
    return "".join(c for c in unicodedata.normalize("NFKD", texto)
                   if unicodedata.category(c) != "Mn")


# ---------------------------------------------------------------------------
# Detección de columnas
# ---------------------------------------------------------------------------

#: campo -> (fragmentos que lo identifican, fragmentos que lo descartan)
#:
#: Se busca por *fragmento* porque los títulos reales son cosas como
#: "Peso Kg/m (aleación 6063)" o "Código de perfil".
ALIAS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "codigo": (
        ("codigo", "cod.", "cod ", "n° perfil", "nro perfil", "articulo", "artic",
         "referencia", "sap", "item", "perfil n", "n de perfil"),
        ("descripcion", "familia", "color"),
    ),
    "descripcion": (
        ("descripcion", "denominacion", "designacion", "detalle", "nombre",
         "producto"),
        (),
    ),
    "peso_kg_m": (
        ("kg/m", "kg / m", "kg x m", "kg por metro", "kgm", "kg/ml", "peso lineal",
         "peso teorico", "peso", "gr/m", "g/m", "grs/m"),
        ("kg/m2", "kg/barra", "peso barra", "peso de barra"),
    ),
    "largo_barra_mm": (
        ("largo de barra", "largo barra", "largo de la barra", "longitud de barra",
         "largo", "longitud", "barra"),
        ("peso", "kg"),
    ),
    "familia": (
        ("familia", "grupo", "rubro", "seccion", "categoria", "conjunto"),
        (),
    ),
    "notas": (
        ("nota", "observacion", "comentario", "aplicacion", "uso"),
        (),
    ),
    "imagen": (
        ("imagen", "dibujo", "foto", "croquis", "archivo", "figura"),
        (),
    ),
}

#: Orden de prioridad: si dos campos reclaman la misma columna, gana el primero.
PRIORIDAD = ("codigo", "peso_kg_m", "largo_barra_mm", "descripcion",
             "familia", "imagen", "notas")


def _campo_de(titulo: str) -> str | None:
    """Qué campo representa un título de columna, o ``None``."""
    t = _normalizar(titulo)
    if not t:
        return None
    candidatos = []
    for campo in PRIORIDAD:
        incluye, excluye = ALIAS[campo]
        if any(mal in t for mal in excluye):
            continue
        for frag in incluye:
            if frag in t:
                # Un título más específico ("largo de barra") debe ganarle al
                # genérico ("largo"), así que se ordena por largo del fragmento.
                candidatos.append((len(frag), -PRIORIDAD.index(campo), campo))
                break
    if not candidatos:
        return None
    return max(candidatos)[2]


def _mapear_fila(fila: list) -> dict[str, int]:
    """Título de columna -> índice, para una fila candidata a encabezado."""
    mapa: dict[str, int] = {}
    for i, celda in enumerate(fila):
        campo = _campo_de(celda)
        if campo and campo not in mapa:
            mapa[campo] = i
    return mapa


# ---------------------------------------------------------------------------
# Lectura y conversión de valores
# ---------------------------------------------------------------------------

_NUMERO = re.compile(r"-?\d+(?:[.,]\d+)?")


def _numero(valor) -> float | None:
    """Convierte a float tolerando '1,266', '0.675 kg', ' 6000 mm '."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip()
    if not texto:
        return None
    m = _NUMERO.search(texto.replace(" ", ""))
    if not m:
        return None
    crudo = m.group(0)
    # '1.234,56' (miles con punto) vs '1,266' (decimal con coma): en un catálogo
    # de perfiles ningún peso ni largo llega a los miles con decimales, así que
    # alcanza con tratar la coma como separador decimal.
    return float(crudo.replace(",", "."))


def _texto(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


@dataclass
class FilaCatalogo:
    """Un perfil leído de la planilla, ya normalizado."""

    codigo: str = ""
    descripcion: str = ""
    peso_kg_m: float = 0.0
    largo_barra_mm: int = LARGO_BARRA_DEFECTO
    familia: str = ""
    notas: str = ""
    imagen: str = ""
    fila_excel: int = 0
    #: Motivo por el que la fila no se puede importar (vacío = está bien).
    problema: str = ""

    @property
    def valida(self) -> bool:
        return not self.problema


@dataclass
class Analisis:
    """Resultado de leer la planilla, sin haber tocado la base."""

    ruta: str = ""
    hoja: str = ""
    hojas_disponibles: list[str] = field(default_factory=list)
    fila_encabezado: int = 0
    columnas: dict[str, str] = field(default_factory=dict)  # campo -> título hallado
    filas: list[FilaCatalogo] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    @property
    def validas(self) -> list[FilaCatalogo]:
        return [f for f in self.filas if f.valida]

    @property
    def descartadas(self) -> list[FilaCatalogo]:
        return [f for f in self.filas if not f.valida]


def hojas_de(ruta_excel: str | Path) -> list[str]:
    """Nombres de las hojas, para que la UI ofrezca elegir."""
    from openpyxl import load_workbook

    wb = load_workbook(Path(ruta_excel), data_only=True, read_only=True)
    try:
        return list(wb.sheetnames)
    finally:
        wb.close()


def analizar(ruta_excel: str | Path, hoja: str | None = None) -> Analisis:
    """Lee la planilla y devuelve lo que se importaría. **No escribe nada.**"""
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # el llamador muestra el mensaje al usuario
        raise ImportError("openpyxl no está instalado") from exc

    ruta = Path(ruta_excel)
    wb = load_workbook(ruta, data_only=True, read_only=True)
    try:
        nombres = list(wb.sheetnames)
        ws = wb[hoja] if hoja in nombres else wb[nombres[0]]
        titulo_hoja = ws.title
        crudo = [[c.value for c in fila] for fila in ws.iter_rows()]
    finally:
        wb.close()

    res = Analisis(ruta=str(ruta), hoja=titulo_hoja, hojas_disponibles=nombres)

    # -- 1. encontrar la fila de encabezados ---------------------------------
    mejor_i, mejor_mapa = -1, {}
    for i, fila in enumerate(crudo[:MAX_FILAS_ENCABEZADO]):
        mapa = _mapear_fila(fila)
        if "codigo" not in mapa:
            continue
        if len(mapa) > len(mejor_mapa):
            mejor_i, mejor_mapa = i, mapa

    if not mejor_mapa:
        res.avisos.append(
            "No se encontró una fila de encabezados con una columna de código. "
            "Revisá que la primera fila de la tabla diga, por ejemplo, "
            "'Código  Descripción  Peso Kg/m  Largo de barra'.")
        return res

    res.fila_encabezado = mejor_i + 1  # 1-based, como lo ve el usuario en Excel
    res.columnas = {campo: _texto(crudo[mejor_i][idx]) for campo, idx in mejor_mapa.items()}

    if "peso_kg_m" not in mejor_mapa:
        res.avisos.append(
            "La planilla no tiene columna de peso (kg/m). Sin peso el programa no "
            "puede costear por kilo: vas a tener que cargarlo a mano.")
    if "largo_barra_mm" not in mejor_mapa:
        res.avisos.append(
            f"No hay columna de largo de barra: se asume {LARGO_BARRA_DEFECTO} mm "
            "para todos los perfiles.")

    # ¿el peso viene en gramos?
    titulo_peso = _normalizar(res.columnas.get("peso_kg_m", ""))
    en_gramos = bool(re.search(r"\b(gr?s?|gramos)\s*/\s*m", titulo_peso))

    # -- 2. leer los datos ----------------------------------------------------
    col = mejor_mapa
    familia_actual = ""
    vacias = 0
    vistos: set[str] = set()

    for i in range(mejor_i + 1, len(crudo)):
        fila = crudo[i]
        no_vacias = [c for c in fila if _texto(c)]
        if not no_vacias:
            vacias += 1
            if vacias >= VACIAS_PARA_CORTAR:
                break
            continue
        vacias = 0

        codigo = _texto(fila[col["codigo"]] if col["codigo"] < len(fila) else None)

        # Muchos catálogos separan secciones con una fila de un solo texto
        # ("MARCOS", "HOJAS"). Se toma como familia de lo que viene abajo.
        if len(no_vacias) == 1 and codigo and not _numero(codigo):
            familia_actual = codigo
            continue

        def celda(campo: str):
            idx = col.get(campo)
            if idx is None or idx >= len(fila):
                return None
            return fila[idx]

        if not codigo:
            continue
        # Repetición del encabezado en planillas paginadas.
        if _campo_de(codigo) == "codigo":
            continue

        f = FilaCatalogo(
            codigo=codigo,
            descripcion=_texto(celda("descripcion")),
            familia=_texto(celda("familia")) or familia_actual,
            notas=_texto(celda("notas")),
            imagen=_texto(celda("imagen")),
            fila_excel=i + 1,
        )

        peso = _numero(celda("peso_kg_m"))
        if peso is not None:
            f.peso_kg_m = round(peso / 1000.0, 4) if en_gramos else round(peso, 4)

        largo = _numero(celda("largo_barra_mm"))
        if largo is None:
            f.largo_barra_mm = LARGO_BARRA_DEFECTO
        elif largo <= 30:
            f.largo_barra_mm = int(round(largo * 1000))   # venía en metros
        else:
            f.largo_barra_mm = int(round(largo))

        if f.peso_kg_m <= 0:
            f.problema = "sin peso kg/m"
        elif f.peso_kg_m > 20:
            f.problema = f"peso fuera de rango ({f.peso_kg_m} kg/m)"
        elif f.largo_barra_mm < 500 or f.largo_barra_mm > 20000:
            f.problema = f"largo de barra fuera de rango ({f.largo_barra_mm} mm)"
        elif codigo in vistos:
            f.problema = "código repetido en la planilla"

        vistos.add(codigo)
        res.filas.append(f)

    if not res.filas:
        res.avisos.append("No se leyó ninguna fila de datos debajo de los encabezados.")

    return res


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------


def importar(db, linea_id: int, filas: list[FilaCatalogo],
             sobrescribir: bool = True) -> dict:
    """Alta/actualización de perfiles en una línea. Devuelve un conteo.

    Nunca borra perfiles que no estén en la planilla: si un código deja de
    figurar puede seguir usándose en fórmulas ya cargadas.

    ``sobrescribir=False`` sólo da de alta los códigos nuevos y deja intactos
    los que ya existen (útil para completar un catálogo sin pisar pesos
    corregidos a mano).
    """
    nuevos = actualizados = sin_cambios = omitidos = 0

    for f in filas:
        if not f.valida:
            omitidos += 1
            continue

        existente = db.perfil(linea_id, f.codigo)
        datos = {
            "descripcion": f.descripcion,
            "peso_kg_m": f.peso_kg_m,
            "largo_barra_mm": f.largo_barra_mm,
            "familia": f.familia,
            "notas": f.notas,
        }
        # La imagen sólo se pisa si la planilla trae una: un import posterior no
        # tiene por qué borrar el dibujo que el usuario ya cargó.
        if f.imagen:
            datos["imagen"] = f.imagen

        if existente is None:
            db.insertar("perfiles", {"linea_id": linea_id, "codigo": f.codigo, **datos})
            nuevos += 1
        elif not sobrescribir:
            sin_cambios += 1
        else:
            cambio = any(_texto(existente[c]) != _texto(v) for c, v in datos.items())
            if cambio:
                db.actualizar("perfiles", existente["id"], datos)
                actualizados += 1
            else:
                sin_cambios += 1

    return {"nuevos": nuevos, "actualizados": actualizados,
            "sin_cambios": sin_cambios, "omitidos": omitidos}


def resumen_texto(analisis: Analisis, resultado: dict | None = None) -> str:
    """Texto listo para mostrar en un cuadro de diálogo."""
    partes = [f"Hoja: {analisis.hoja}   (encabezados en la fila {analisis.fila_encabezado})"]
    if analisis.columnas:
        detectadas = ", ".join(f"{campo} ← «{titulo}»"
                               for campo, titulo in analisis.columnas.items())
        partes.append(f"Columnas detectadas: {detectadas}")
    partes.append(f"Perfiles válidos: {len(analisis.validas)}   "
                  f"Descartados: {len(analisis.descartadas)}")
    for f in analisis.descartadas[:8]:
        partes.append(f"   · fila {f.fila_excel}  {f.codigo}: {f.problema}")
    if len(analisis.descartadas) > 8:
        partes.append(f"   · … y {len(analisis.descartadas) - 8} más")
    partes.extend(analisis.avisos)
    if resultado:
        partes.append("")
        partes.append(f"Nuevos: {resultado['nuevos']}   "
                      f"Actualizados: {resultado['actualizados']}   "
                      f"Sin cambios: {resultado['sin_cambios']}   "
                      f"Omitidos: {resultado['omitidos']}")
    return "\n".join(partes)


# ---------------------------------------------------------------------------
# Uso desde la consola (para probar sin abrir la interfaz)
# ---------------------------------------------------------------------------


def _main(argv: list[str]) -> int:
    import sys

    if not argv:
        print(__doc__)
        print("Uso: python -m tools.importar_catalogo <archivo.xlsx> [hoja]")
        return 2

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    analisis = analizar(argv[0], argv[1] if len(argv) > 1 else None)
    print(resumen_texto(analisis))
    print()
    for f in analisis.validas[:20]:
        print(f"  {f.codigo:<12} {f.descripcion[:40]:<42} "
              f"{f.peso_kg_m:>7.3f} kg/m   {f.largo_barra_mm:>6} mm   {f.familia}")
    if len(analisis.validas) > 20:
        print(f"  … y {len(analisis.validas) - 20} más")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_main(sys.argv[1:]))
