"""
Control de deriva: qué difiere entre el beta y producción.

El beta es una copia de trabajo, así que la única forma de que no se convierta en
un fork silencioso es poder ver, en un comando, exactamente qué se tocó.

    python tools/comparar_produccion.py           # resumen
    python tools/comparar_produccion.py --diff    # con el diff de cada archivo

Todo lo que salga acá tiene que estar declarado en COSTURAS.md. Si aparece un
archivo que no figura ahí, o se documenta o se revierte.
"""

from __future__ import annotations

import difflib
import sys
from pathlib import Path

BETA = Path(__file__).resolve().parent.parent
PRODUCCION = BETA.parent / "cotizador_aberturas"

#: No se comparan: son datos de usuario o artefactos de compilación.
IGNORAR = {"datos", "salidas", "dist", "build", "portable", "entregas",
           "__pycache__", ".git", ".venv", "venv"}

#: Extensiones que tiene sentido comparar como texto
TEXTO = {".py", ".md", ".txt", ".json", ".bat", ".cfg", ".ini", ""}


def _relevantes(raiz: Path) -> dict[str, Path]:
    encontrados = {}
    for ruta in raiz.rglob("*"):
        if not ruta.is_file():
            continue
        relativa = ruta.relative_to(raiz)
        if IGNORAR & set(relativa.parts):
            continue
        if ruta.suffix.lower() not in TEXTO:
            continue
        encontrados[str(relativa).replace("\\", "/")] = ruta
    return encontrados


def _leer(ruta: Path) -> list[str]:
    try:
        return ruta.read_text(encoding="utf-8").splitlines(keepends=True)
    except (OSError, UnicodeDecodeError):
        return []


def main(argv: list[str]) -> int:
    if not PRODUCCION.is_dir():
        print(f"No se encuentra producción en {PRODUCCION}")
        return 1

    mostrar_diff = "--diff" in argv

    beta = _relevantes(BETA)
    prod = _relevantes(PRODUCCION)

    nuevos = sorted(set(beta) - set(prod))
    borrados = sorted(set(prod) - set(beta))
    comunes = sorted(set(beta) & set(prod))

    modificados = []
    for nombre in comunes:
        if beta[nombre].read_bytes() != prod[nombre].read_bytes():
            modificados.append(nombre)

    print(f"beta        {BETA}")
    print(f"producción  {PRODUCCION}")
    print()
    print(f"{len(comunes) - len(modificados):>4} archivos idénticos")
    print(f"{len(modificados):>4} modificados")
    print(f"{len(nuevos):>4} nuevos en el beta")
    print(f"{len(borrados):>4} borrados en el beta")

    if nuevos:
        print("\nNUEVOS")
        for nombre in nuevos:
            lineas = len(_leer(beta[nombre]))
            print(f"  + {nombre}  ({lineas} líneas)")

    if borrados:
        print("\nBORRADOS  (ojo: el beta debería sumar, no restar)")
        for nombre in borrados:
            print(f"  - {nombre}")

    if modificados:
        print("\nMODIFICADOS")
        for nombre in modificados:
            a, b = _leer(prod[nombre]), _leer(beta[nombre])
            mas = sum(1 for l in difflib.ndiff(a, b) if l.startswith("+ "))
            menos = sum(1 for l in difflib.ndiff(a, b) if l.startswith("- "))
            print(f"  ~ {nombre}   +{mas} / -{menos}")

    if mostrar_diff and modificados:
        for nombre in modificados:
            print("\n" + "=" * 74)
            print(nombre)
            print("=" * 74)
            for linea in difflib.unified_diff(
                    _leer(prod[nombre]), _leer(beta[nombre]),
                    fromfile=f"produccion/{nombre}", tofile=f"beta/{nombre}", n=2):
                print(linea, end="")
    elif modificados:
        print("\n(agregá --diff para ver los cambios línea por línea)")

    print("\nTodo lo listado tiene que figurar en COSTURAS.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
