# -*- coding: utf-8 -*-
"""
Arma un escenario de prueba para el control de stock.

Para qué sirve
--------------
El stock no se puede probar con la base vacía: hace falta que haya cantidades
cargadas, que algunas alcancen y otras no, y que exista un presupuesto que las
consuma. Cargar todo eso a mano lleva media hora y cada vez queda distinto, así
que no se puede comparar una corrida con la siguiente.

Este script deja la base en un estado **conocido**:

* **Aluminio**: barras de los perfiles que el presupuesto de prueba usa. A
  propósito, algunos con cantidad de sobra, uno justo y uno corto, para ver los
  tres colores del semáforo.
* **Vidrio**: planchas de los tipos que el presupuesto usa, en m², con el mismo
  criterio (sobra / justo / falta).
* **Accesorios**: unidades y metros lineales, incluyendo las dos variantes de
  rodamiento y de cierre, para probar que el kit descuenta el que se eligió y
  no el otro.

Cómo se usa
-----------
    python -m tools.escenario_stock              # ver qué haría, sin tocar nada
    python -m tools.escenario_stock --aplicar    # escribirlo en la base
    python -m tools.escenario_stock --limpiar    # borrar sólo lo que puso

Antes de escribir hace una copia de la base, igual que las migraciones.

Todo lo que carga va a un depósito aparte, ``PRUEBA``, y mientras el escenario
está puesto ese pasa a ser el depósito por defecto: el programa consulta y
descuenta contra **un solo** depósito a la vez, así que si el escenario dejara
las cantidades en otro lado el sistema no las vería. El stock verdadero que
tengas en ``Principal`` no se toca y vuelve a ser el que manda con ``--limpiar``.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import rutas
from core.database import DB

#: Todo lo que carga este script va a este depósito. Es la marca que permite
#: limpiarlo después sin tocar el stock verdadero.
DEPOSITO = "PRUEBA"

#: El programa lee y descuenta siempre contra el depósito por defecto. Mientras
#: el escenario está puesto, ese es PRUEBA; acá se recuerda cuál era el de antes
#: para poder devolverlo tal cual estaba.
PARAM_DEPOSITO = "stock_deposito_default"
PARAM_GUARDADO = "stock_deposito_antes_de_prueba"

#: Las variantes que el usuario relevó del catálogo de Aluar. Se dan de alta si
#: no existen, para poder probar la elección de accesorio en la tipología.
#:  (código, descripción, unidad, precio, cuánto stock dejar)
ACCESORIOS_PRUEBA = [
    # -- rodamientos: la variable RODAMIENTO elige entre estos dos ------------
    ("R48", "Rodamiento simple para hoja corrediza", "u", 2800.0, 200.0),
    ("R49", "Rodamiento doble reforzado para hoja pesada", "u", 4600.0, 12.0),
    # -- cierres: la variable CIERRE elige entre estos dos --------------------
    ("H123", "Cierre de embutir a uñeta", "u", 5200.0, 80.0),
    ("H130", "Cierre multipunto con manija", "u", 14500.0, 3.0),
    # -- escuadras de armado --------------------------------------------------
    ("E83", "Escuadra de armado para marco", "u", 900.0, 500.0),
    ("E97", "Escuadra de armado para hoja", "u", 950.0, 500.0),
    ("E98", "Escuadra de refuerzo de ángulo", "u", 1100.0, 40.0),
    # -- topes y desagües -----------------------------------------------------
    ("T89", "Tope de hoja corrediza", "u", 700.0, 300.0),
    ("T90", "Tope de hoja corrediza reforzado", "u", 850.0, 300.0),
    ("T126", "Tope antisalto superior", "u", 640.0, 300.0),
    ("T127", "Tope antisalto inferior", "u", 640.0, 300.0),
    ("T130", "Tapa de desagüe recta", "u", 480.0, 150.0),
    ("T131", "Tapa de desagüe curva", "u", 480.0, 150.0),
    ("T143", "Deflector de desagüe", "u", 520.0, 0.0),      # ← faltante a propósito
    # -- burletes y felpas (por metro lineal) ---------------------------------
    ("B60", "Burlete de vidrio EPDM", "ml", 1500.0, 400.0),
    ("C3", "Felpa 4,8 x 6 mm", "ml", 800.0, 250.0),
    ("C4", "Felpa 4,8 x 9 mm", "ml", 900.0, 250.0),
    ("C8", "Felpa siliconada 5 x 7 mm", "ml", 1050.0, 60.0),
    ("C14", "Burlete de encuentro de hojas", "ml", 1600.0, 120.0),
    ("C15", "Burlete de cierre lateral", "ml", 1600.0, 120.0),
    # -- premarco -------------------------------------------------------------
    ("E106", "Grapa de premarco", "u", 380.0, 400.0),
    ("E66", "Escuadra de premarco", "u", 640.0, 400.0),
    ("B57", "Burlete de premarco", "ml", 1200.0, 200.0),
    ("B69", "Sellador de premarco", "u", 3900.0, 25.0),
    ("S9", "Tornillo de fijación de premarco", "u", 120.0, 1000.0),
    ("T88", "Tapa de premarco", "u", 450.0, 200.0),
    # -- mosquitero -----------------------------------------------------------
    ("E73", "Escuadra de mosquitero", "u", 700.0, 200.0),
    ("B9", "Burlete de tela mosquitera", "ml", 900.0, 150.0),
    ("B70", "Perfil de cierre de mosquitero", "ml", 2400.0, 150.0),
    ("R43", "Rodamiento de mosquitero", "u", 1900.0, 100.0),
]

#: Las dos variables de elección que el usuario pidió, con sus códigos elegibles.
#:  (clave, etiqueta, códigos, ayuda)
VARIABLES_PRUEBA = [
    ("RODAMIENTO", "Rodamiento", "R48, R49",
     "Simple para hoja liviana, doble reforzado a partir de 40 kg de hoja."),
    ("CIERRE", "Cierre", "H123, H130",
     "De embutir para ventana común, multipunto para puerta balcón."),
]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _copia_de_seguridad(ruta: Path) -> Path:
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = ruta.parent / "copias" / f"antes_escenario_{marca}.db"
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ruta, destino)
    return destino


def _poner_stock(db, tipo: str, referencia_id: int, cantidad: float,
                 unidad: str, minimo: float = 0.0) -> None:
    """Deja esa cantidad en el depósito de prueba, sin duplicar el renglón."""
    fila = db.query_one(
        "SELECT id FROM stock WHERE tipo = ? AND referencia_id = ? AND deposito = ?",
        (tipo, referencia_id, DEPOSITO))
    ahora = datetime.now().isoformat(timespec="seconds")
    if fila:
        db.cx.execute(
            "UPDATE stock SET cantidad = ?, unidad = ?, minimo = ?, actualizado = ? "
            "WHERE id = ?", (cantidad, unidad, minimo, ahora, fila["id"]))
    else:
        db.cx.execute(
            "INSERT INTO stock (tipo, referencia_id, deposito, cantidad, unidad, "
            "minimo, actualizado) VALUES (?,?,?,?,?,?,?)",
            (tipo, referencia_id, DEPOSITO, cantidad, unidad, minimo, ahora))


def poner_deposito(db) -> str:
    """Deja PRUEBA como depósito por defecto y recuerda cuál era el anterior."""
    anterior = db.parametro(PARAM_DEPOSITO, "Principal") or "Principal"
    if anterior != DEPOSITO:
        db.set_parametro(PARAM_GUARDADO, anterior,
                         "Depósito real, guardado por tools.escenario_stock", "Técnico")
    db.set_parametro(PARAM_DEPOSITO, DEPOSITO,
                     "Depósito contra el que se consulta y descuenta", "Técnico")
    return anterior


def sacar_deposito(db) -> str:
    """Devuelve el depósito por defecto al que había antes del escenario."""
    anterior = db.parametro(PARAM_GUARDADO, "Principal") or "Principal"
    db.set_parametro(PARAM_DEPOSITO, anterior,
                     "Depósito contra el que se consulta y descuenta", "Técnico")
    db.cx.execute("DELETE FROM parametros WHERE clave = ?", (PARAM_GUARDADO,))
    return anterior


def _accesorio_por_codigo(db, codigo: str):
    return db.query_one("SELECT * FROM accesorios WHERE UPPER(codigo) = ?",
                        (codigo.upper(),))


# ---------------------------------------------------------------------------
# Las tres cargas
# ---------------------------------------------------------------------------

def cargar_accesorios(db, aplicar: bool) -> list[str]:
    """Da de alta las variantes del catálogo Aluar y les pone stock."""
    lineas = []
    for codigo, descripcion, unidad, precio, cantidad in ACCESORIOS_PRUEBA:
        acc = _accesorio_por_codigo(db, codigo)
        if acc is None:
            lineas.append(f"  alta  {codigo:<6} {descripcion}")
            if aplicar:
                db.cx.execute(
                    "INSERT INTO accesorios (codigo, descripcion, unidad, precio, activo) "
                    "VALUES (?,?,?,?,1)", (codigo, descripcion, unidad, precio))
                acc = _accesorio_por_codigo(db, codigo)
        else:
            lineas.append(f"  ok    {codigo:<6} ya existe")

        if acc is not None and aplicar:
            _poner_stock(db, "accesorio", acc["id"], cantidad, unidad,
                         minimo=10.0 if unidad == "u" else 20.0)
        estado = "FALTA" if cantidad == 0 else ("justo" if cantidad < 15 else "sobra")
        lineas.append(f"        stock {cantidad:g} {unidad}  ({estado})")

    # Los accesorios que los kits ya venían usando también necesitan stock. Si
    # se cargan sólo los códigos nuevos, cualquier presupuesto sale con veinte
    # renglones en rojo y no se distingue el faltante puesto a propósito del
    # que falta porque nadie lo cargó.
    nuevos = {c.upper() for c, *_ in ACCESORIOS_PRUEBA}
    otros = [a for a in db.query("SELECT id, codigo, unidad FROM accesorios "
                                 "ORDER BY codigo")
             if (a["codigo"] or "").upper() not in nuevos]
    if otros:
        lineas.append("")
        lineas.append("  -- los que ya estaban en los kits --")
    for i, acc in enumerate(otros):
        unidad = (acc["unidad"] or "u").lower()
        # Cantidades altas: son consumibles (felpa, escuadras, tornillería) y la
        # gracia es que no tapen los faltantes puestos a propósito.
        cantidad, estado = ((900.0, "sobra"), (900.0, "sobra"), (6.0, "justo"))[i % 3]
        lineas.append(f"  {acc['codigo']:<10} {cantidad:>6g} {unidad:<4} ({estado})")
        if aplicar:
            _poner_stock(db, "accesorio", acc["id"], cantidad, unidad, minimo=20.0)
    return lineas


def cargar_variables(db, aplicar: bool) -> list[str]:
    """Declara RODAMIENTO y CIERRE en las tipologías corredizas.

    Se declaran genéricas (sin línea) para que valgan en cualquier sistema: la
    elección de rodamiento depende del peso de la hoja, no de la línea.
    """
    from core import variables as V

    lineas = []
    # La corrediza y la puerta balcón son las que tienen rodamiento y cierre
    # variables. Una banderola no lleva rueda: declararle RODAMIENTO sería
    # ofrecerle al usuario una opción que no cambia nada.
    corredizas = db.query(
        "SELECT codigo, nombre FROM tipologias "
        "WHERE esquema = 'corrediza' AND activo = 1 ORDER BY codigo")
    if not corredizas:
        return ["  (no hay tipologías corredizas activas)"]

    for tip in corredizas:
        for orden, (clave, etiqueta, codigos, ayuda) in enumerate(VARIABLES_PRUEBA, 1):
            ya = db.query_one(
                "SELECT id FROM tipologia_variables "
                "WHERE tipologia_codigo = ? AND clave = ? AND linea_id IS NULL",
                (tip["codigo"], clave))
            if ya:
                lineas.append(f"  ok    {tip['codigo']:<10} {clave} ya declarada")
                continue
            lineas.append(f"  alta  {tip['codigo']:<10} {clave} -> {codigos}")
            if aplicar:
                V.guardar(db, {
                    "tipologia_codigo": tip["codigo"], "linea_id": None,
                    "clave": clave, "etiqueta": etiqueta, "tipo": "accesorio",
                    "opciones": codigos, "valor_default": "0",
                    "minimo": 0, "maximo": 0, "ayuda": ayuda,
                    "orden": 10 + orden, "activo": 1,
                })
    return lineas


def enganchar_kits(db, aplicar: bool) -> list[str]:
    """Hace que el renglón de rueda y el de cierre los elija la variable.

    Es el paso que convierte la declaración en algo que se ve en el presupuesto:
    hasta que el kit no apunta a la variable, elegir R49 no cambia nada.
    """
    lineas = []
    # Las tipologías que cargar_variables() declara o va a declarar.
    a_declarar = {t["codigo"] for t in db.query(
        "SELECT codigo FROM tipologias WHERE esquema = 'corrediza' AND activo = 1")}

    # El renglón a enganchar se reconoce por el accesorio que tiene puesto hoy.
    enganches = [("RODAMIENTO", ("RUE-STD", "RUE-REF", "R48", "R49")),
                 ("CIERRE", ("CIE-CRE", "CIE-EMB", "H123", "H130"))]

    for clave, codigos in enganches:
        marcas = ",".join("?" * len(codigos))
        filas = db.query(
            f"SELECT ki.id, ki.kit_id, a.codigo, k.nombre AS kit, "
            f"       k.tipologia_codigo "
            f"FROM kit_items ki "
            f"JOIN accesorios a ON a.id = ki.accesorio_id "
            f"JOIN kits k ON k.id = ki.kit_id "
            f"WHERE UPPER(a.codigo) IN ({marcas})",
            tuple(c.upper() for c in codigos))
        if not filas:
            lineas.append(f"  --    ningún kit tiene un renglón de {clave.lower()}")
            continue
        for fila in filas:
            # En la corrida seca todavía no hay nada escrito, así que se cuenta
            # también lo que el paso anterior va a declarar. Si no, informaría
            # "no declara" para todo y no se entendería qué va a pasar.
            declarada = db.query_one(
                "SELECT 1 FROM tipologia_variables "
                "WHERE tipologia_codigo = ? AND clave = ? AND activo = 1",
                (fila["tipologia_codigo"] or "", clave))
            if not declarada and fila["tipologia_codigo"] in a_declarar:
                declarada = True
            if not declarada:
                lineas.append(f"  --    kit «{fila['kit']}»: la tipología "
                              f"{fila['tipologia_codigo'] or '(genérico)'} no "
                              f"declara {clave}, se deja fijo en {fila['codigo']}")
                continue
            lineas.append(f"  eng.  kit «{fila['kit']}» renglón {fila['codigo']} "
                          f"-> lo elige {clave}")
            if aplicar:
                db.cx.execute("UPDATE kit_items SET variable_clave = ? WHERE id = ?",
                              (clave, fila["id"]))
    return lineas


def cargar_aluminio(db, aplicar: bool) -> list[str]:
    """Barras en stock de los perfiles más usados, con los tres casos.

    Se toman los perfiles que tienen fórmula de despiece: son los que un
    presupuesto va a consumir de verdad. Cargar barras de un perfil que nadie
    usa no prueba nada.
    """
    lineas = []
    perfiles = db.query(
        "SELECT DISTINCT p.id, p.codigo, p.descripcion FROM perfiles p "
        "JOIN tipologia_formulas f ON UPPER(f.perfil_codigo) = UPPER(p.codigo) "
        "ORDER BY p.codigo LIMIT 40")
    if not perfiles:
        perfiles = db.query("SELECT id, codigo, descripcion FROM perfiles "
                            "ORDER BY codigo LIMIT 20")

    for i, perfil in enumerate(perfiles):
        # Un ciclo de tres para que siempre haya de los tres casos, sin importar
        # cuántos perfiles tenga la base cargada.
        cantidad, estado = ((60.0, "sobra"), (4.0, "justo"), (0.0, "FALTA"))[i % 3]
        lineas.append(f"  {perfil['codigo']:<10} {cantidad:>5g} barras  ({estado})"
                      f"  {(perfil['descripcion'] or '')[:34]}")
        if aplicar:
            _poner_stock(db, "perfil", perfil["id"], cantidad, "barras", minimo=6.0)
    return lineas


def cargar_vidrio(db, aplicar: bool) -> list[str]:
    """m² en stock por tipo de vidrio, con los tres casos.

    La unidad es el m² porque es como se compra y como lo factura la vidriería.
    El optimizador dice cuántas planchas hacen falta; el stock dice si están.
    """
    lineas = []
    for i, vidrio in enumerate(db.query(
            "SELECT id, nombre, plancha_ancho_mm, plancha_alto_mm FROM vidrios "
            "WHERE activo = 1 ORDER BY id")):
        m2_plancha = ((vidrio["plancha_ancho_mm"] or 0) *
                      (vidrio["plancha_alto_mm"] or 0) / 1_000_000.0)
        # En planchas enteras, que es como llega el vidrio al taller.
        planchas, estado = ((8, "sobra"), (1, "justo"), (0, "FALTA"))[i % 3]
        cantidad = round(planchas * m2_plancha, 2)
        lineas.append(f"  {vidrio['nombre']:<18} {cantidad:>7g} m2 "
                      f"= {planchas} plancha(s) de {m2_plancha:g} m2  ({estado})")
        if aplicar:
            _poner_stock(db, "vidrio", vidrio["id"], cantidad, "m2",
                         minimo=round(m2_plancha, 2))
    return lineas


# ---------------------------------------------------------------------------
# Limpieza
# ---------------------------------------------------------------------------

def limpiar(db) -> int:
    """Saca todo lo que este script cargó. No toca el stock real."""
    cur = db.cx.execute("DELETE FROM stock WHERE deposito = ?", (DEPOSITO,))
    borrados = cur.rowcount
    db.cx.execute("UPDATE kit_items SET variable_clave = '' "
                  "WHERE variable_clave IN ('RODAMIENTO', 'CIERRE')")
    db.cx.execute("DELETE FROM tipologia_variables "
                  "WHERE clave IN ('RODAMIENTO', 'CIERRE') AND linea_id IS NULL")
    db.cx.commit()
    return borrados


# ---------------------------------------------------------------------------
# Programa
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deja la base en un estado conocido para probar el stock.")
    parser.add_argument("--aplicar", action="store_true",
                        help="escribir en la base (si no, sólo muestra)")
    parser.add_argument("--limpiar", action="store_true",
                        help="borrar lo que este script cargó y salir")
    args = parser.parse_args()

    ruta = Path(rutas.RUTA_DB)
    if not ruta.exists():
        print(f"No encuentro la base en {ruta}")
        return 1

    db = DB(ruta)

    if args.limpiar:
        copia = _copia_de_seguridad(ruta)
        volvio_a = sacar_deposito(db)
        borrados = limpiar(db)
        print(f"Copia previa: {copia}")
        print(f"Borrados {borrados} renglones del depósito {DEPOSITO}.")
        print("Las variables RODAMIENTO y CIERRE y sus enganches también se sacaron.")
        print(f"El depósito por defecto vuelve a ser «{volvio_a}».")
        return 0

    if args.aplicar:
        copia = _copia_de_seguridad(ruta)
        anterior = poner_deposito(db)
        print(f"Copia previa: {copia}")
        print(f"Depósito por defecto: «{anterior}» -> «{DEPOSITO}» "
              f"(se devuelve con --limpiar)\n")

    bloques = [
        ("ACCESORIOS  (catálogo Aluar + stock)", cargar_accesorios),
        ("VARIABLES DE ELECCIÓN  (rodamiento y cierre)", cargar_variables),
        ("ENGANCHE EN LOS KITS", enganchar_kits),
        ("ALUMINIO  (barras por perfil)", cargar_aluminio),
        ("VIDRIO  (m² por tipo)", cargar_vidrio),
    ]
    for titulo, funcion in bloques:
        print("=" * 74)
        print(titulo)
        print("=" * 74)
        for linea in funcion(db, args.aplicar):
            print(linea)
        print()

    if args.aplicar:
        db.cx.commit()
        print("Escrito. Abrí el programa y mirá la pantalla de Stock.")
        print(f"Todo quedó en el depósito «{DEPOSITO}». Para volver atrás:")
        print("    python -m tools.escenario_stock --limpiar")
    else:
        print("Esto es lo que HARÍA. Para escribirlo:")
        print("    python -m tools.escenario_stock --aplicar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
