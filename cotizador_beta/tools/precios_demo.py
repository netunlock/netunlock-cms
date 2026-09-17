# -*- coding: utf-8 -*-
"""
Carga una lista de precios de demostración sobre los catálogos MDT.

Para qué está
-------------
Los catálogos MDT entran en **$0** a propósito: el fabricante no publica precios
y cada carpintería compra a su lista. Eso está bien para trabajar, pero no para
**grabar una demostración**: un presupuesto de $0 no muestra nada.

Este script pone valores plausibles de plaza en todo lo que esté en cero, para
que la pantalla tenga números de verdad mientras se filma, y los saca después.

    python -m tools.precios_demo              # ver qué haría, sin tocar nada
    python -m tools.precios_demo --aplicar    # cargar los precios
    python -m tools.precios_demo --limpiar    # devolver todo a $0

**Sólo toca lo que está en $0.** Si ya cargaste tus precios reales, no te los
pisa: los saltea y te lo dice. Y `--limpiar` sólo devuelve a cero lo que este
script puso, que queda anotado en un parámetro de la base.

Los valores son orientativos, del orden de lo que se manejaba en plaza a
mediados de 2026. No son una lista de precios: no los uses para cotizarle a un
cliente.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

from core import rutas
from core.database import DB

#: Dónde se anota qué tocó este script, para poder deshacerlo sin llevarse
#: puesto un precio que el usuario haya cargado a mano después.
PARAM_MARCA = "precios_demo_aplicados"

#: Precio del aluminio por kilo, según el color. El natural es el más barato y
#: el símil madera el más caro, que es como se comporta la lista de verdad.
PRECIO_KG = {
    "Natural": 9800.0,
    "Blanco": 11200.0,
    "Negro": 12400.0,
    "Símil madera": 15900.0,
}
PRECIO_KG_OTRO = 11000.0

#: Precio del m² de vidrio por tipo.
PRECIO_M2 = {
    "Float 3 mm": 17500.0,
    "Float 4 mm": 21000.0,
    "Float 5 mm": 25500.0,
    "Float 6 mm": 29000.0,
    "Esmerilado 4 mm": 27000.0,
    "Laminado 3+3": 42000.0,
    "Laminado 4+4": 51000.0,
    "Templado 6 mm": 58000.0,
    "DVH 4/9/4": 55000.0,
    "DVH 4/12/4": 60000.0,
    "DVH 5/12/5": 68000.0,
}

#: Precio de accesorio según la familia, que es lo que dice el prefijo del
#: código MDT. Un burlete se vende por metro y una escuadra por unidad, así que
#: los órdenes de magnitud son muy distintos.
PRECIO_ACC = {
    "ME": 950.0,        # escuadras de armado
    "MB": 1600.0,       # burletes y felpas, por metro
    "MR": 3200.0,       # rodamientos
    "MS": 3900.0,       # selladores
    "HD": 5400.0,       # herrajes
}
PRECIO_ACC_NOMBRADO = {
    "MDT-CIERRE": 5200.0,
    "MDT-MANIJA": 8900.0,
    "MDT-BISAGRA": 2600.0,
    "MDT-FELPA": 900.0,
    "MDT-TORN": 4800.0,
}


def _precio_accesorio(codigo: str) -> float:
    if codigo in PRECIO_ACC_NOMBRADO:
        return PRECIO_ACC_NOMBRADO[codigo]
    return PRECIO_ACC.get(codigo[:2].upper(), 1500.0)


def aplicar(db, escribir: bool) -> dict:
    """Pone precio a todo lo que esté en cero. Devuelve qué tocó."""
    tocado = {"colores": [], "vidrios": [], "accesorios": []}
    salteado = {"colores": 0, "vidrios": 0, "accesorios": 0}

    for fila in db.query(
            "SELECT lp.id, lp.color, lp.precio_kg, l.nombre AS linea "
            "FROM linea_precios lp JOIN lineas l ON l.id = lp.linea_id "
            "ORDER BY l.nombre, lp.color"):
        if fila["precio_kg"]:
            salteado["colores"] += 1
            continue
        precio = PRECIO_KG.get(fila["color"], PRECIO_KG_OTRO)
        tocado["colores"].append((f"{fila['linea']} · {fila['color']}", precio))
        if escribir:
            db.cx.execute("UPDATE linea_precios SET precio_kg = ? WHERE id = ?",
                          (precio, fila["id"]))

    for fila in db.query("SELECT id, nombre, precio_m2, plancha_ancho_mm, "
                         "plancha_alto_mm FROM vidrios ORDER BY id"):
        if fila["precio_m2"]:
            salteado["vidrios"] += 1
            continue
        precio = PRECIO_M2.get(fila["nombre"], 25000.0)
        tocado["vidrios"].append((fila["nombre"], precio))
        if escribir:
            # El precio de la plancha entera se deja coherente con el del m²:
            # si no, el listado de compras diría dos cosas distintas.
            m2 = ((fila["plancha_ancho_mm"] or 0) *
                  (fila["plancha_alto_mm"] or 0) / 1_000_000.0)
            db.cx.execute(
                "UPDATE vidrios SET precio_m2 = ?, precio_plancha = ? WHERE id = ?",
                (precio, round(precio * m2, 2), fila["id"]))

    for fila in db.query("SELECT id, codigo, precio FROM accesorios ORDER BY codigo"):
        if fila["precio"]:
            salteado["accesorios"] += 1
            continue
        precio = _precio_accesorio(fila["codigo"])
        tocado["accesorios"].append((fila["codigo"], precio))
        if escribir:
            db.cx.execute("UPDATE accesorios SET precio = ? WHERE id = ?",
                          (precio, fila["id"]))

    if escribir:
        db.set_parametro(PARAM_MARCA, json.dumps({
            "colores": [c for c, _p in tocado["colores"]],
            "vidrios": [v for v, _p in tocado["vidrios"]],
            "accesorios": [a for a, _p in tocado["accesorios"]],
        }, ensure_ascii=False),
            "Precios de demostración cargados por tools.precios_demo", "Técnico")
        db.cx.commit()

    return {"tocado": tocado, "salteado": salteado}


def limpiar(db) -> int:
    """Devuelve a $0 sólo lo que este script había puesto."""
    crudo = db.parametro(PARAM_MARCA, "")
    if not crudo:
        print("  No hay precios de demostración cargados.")
        return 0
    marca = json.loads(crudo)
    n = 0

    for etiqueta in marca.get("colores", []):
        linea, _, color = etiqueta.partition(" · ")
        cur = db.cx.execute(
            "UPDATE linea_precios SET precio_kg = 0 WHERE color = ? AND linea_id = "
            "(SELECT id FROM lineas WHERE nombre = ?)", (color, linea))
        n += cur.rowcount
    for nombre in marca.get("vidrios", []):
        n += db.cx.execute("UPDATE vidrios SET precio_m2 = 0, precio_plancha = 0 "
                           "WHERE nombre = ?", (nombre,)).rowcount
    for codigo in marca.get("accesorios", []):
        n += db.cx.execute("UPDATE accesorios SET precio = 0 WHERE codigo = ?",
                           (codigo,)).rowcount

    db.cx.execute("DELETE FROM parametros WHERE clave = ?", (PARAM_MARCA,))
    db.cx.commit()
    return n


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Precios de demostración para grabar la pantalla")
    parser.add_argument("--aplicar", action="store_true")
    parser.add_argument("--limpiar", action="store_true")
    args = parser.parse_args()

    db = DB(rutas.RUTA_DB)

    if args.limpiar:
        n = limpiar(db)
        print(f"  {n} precio(s) devueltos a $0.")
        return 0

    r = aplicar(db, args.aplicar)
    for rubro, filas in r["tocado"].items():
        print("=" * 66)
        print(f"{rubro.upper()}  ({len(filas)})")
        print("=" * 66)
        for nombre, precio in filas[:14]:
            print(f"  {nombre:<34} $ {precio:>12,.2f}")
        if len(filas) > 14:
            print(f"  … y {len(filas) - 14} más")
        print()

    saltados = sum(r["salteado"].values())
    if saltados:
        print(f"  {saltados} renglón(es) ya tenían precio y no se tocaron: "
              f"{r['salteado']}")
    print()
    if args.aplicar:
        print("  Cargado. Para devolver todo a $0:")
        print("      python -m tools.precios_demo --limpiar")
    else:
        print("  Esto es lo que HARÍA. Para cargarlo:")
        print("      python -m tools.precios_demo --aplicar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
