# -*- coding: utf-8 -*-
"""
Compila el emisor portable de licencias.

    python build_emisor.py

Qué garantiza
-------------
1. **La clave privada NO entra al ejecutable.** Se verifica sobre el binario ya
   construido, buscando la privada byte por byte. Si aparece, el script falla.
   El .exe por sí solo no sirve para nada: la llave va aparte, cifrada, en
   ``emisor.llave``.

2. **La llave tampoco se empaqueta.** Queda como archivo suelto en la carpeta,
   para poder cambiarle la contraseña sin recompilar nada.

3. **Firma con el mismo código que valida la aplicación.** Se empaquetan
   ``core.licencia`` y ``core.ed25519`` del proyecto, no una copia: una copia que
   se desincronice emitiría claves que el Cotizador rechaza.

Lo que sale queda en ``salida/EmisorLicencias`` y es lo que se copia al pendrive.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

AQUI = Path(__file__).resolve().parent
PROYECTO = AQUI.parent / "cotizador_beta"
SALIDA = AQUI / "salida"
NOMBRE = "EmisorLicencias"

PRIVADA = Path.home() / ".cotizador_emisor" / "clave_privada.json"

EXCLUIR = [
    "matplotlib", "numpy", "pandas", "scipy", "IPython", "pytest",
    "PyQt5", "PyQt6", "PySide2", "PySide6", "notebook", "tornado",
    "reportlab", "openpyxl", "PIL", "test", "unittest", "pydoc", "doctest",
]


def log(texto: str = "") -> None:
    print(texto, flush=True)


def titulo(texto: str) -> None:
    log()
    log("=" * 70)
    log(f"  {texto}")
    log("=" * 70)


def comprobar() -> None:
    titulo("1. Comprobaciones")
    try:
        import PyInstaller  # noqa: F401
        log(f"  PyInstaller      {PyInstaller.__version__}")
    except ImportError:
        raise SystemExit("Falta PyInstaller.\n\n    pip install pyinstaller")
    for modulo in ("customtkinter", "cryptography"):
        try:
            __import__(modulo)
            log(f"  {modulo:<16} OK")
        except ImportError:
            raise SystemExit(f"Falta {modulo}.\n\n    pip install {modulo}")

    if not (PROYECTO / "core" / "licencia.py").exists():
        raise SystemExit(f"No encuentro el proyecto en {PROYECTO}")
    if not (PROYECTO / "core" / "clave_publica.py").exists():
        raise SystemExit("Falta core/clave_publica.py en el proyecto.")
    log("  código del proyecto OK")

    if not PRIVADA.exists():
        log(f"  aviso: no hay clave privada en esta PC ({PRIVADA})")
        log("         se puede compilar igual, pero la auditoría será parcial")


def compilar(consola: bool) -> float:
    titulo("2. Compilando")
    trabajo = AQUI / "_build"
    comando = [
        sys.executable, "-m", "PyInstaller",
        "--name", NOMBRE,
        "--onefile",                       # un solo archivo: más cómodo en pendrive
        "--console" if consola else "--noconsole",
        "--noconfirm", "--clean",
        "--distpath", str(SALIDA / NOMBRE),
        "--workpath", str(trabajo),
        "--specpath", str(trabajo),
        "--paths", str(PROYECTO),
        "--paths", str(AQUI),
        "--hidden-import", "core.licencia",
        "--hidden-import", "core.ed25519",
        "--hidden-import", "core.clave_publica",
        "--hidden-import", "caja",
        "--collect-data", "customtkinter",
    ]
    icono = PROYECTO / "recursos" / "icono.ico"
    if icono.exists():
        comando += ["--icon", str(icono)]
    for modulo in EXCLUIR:
        comando += ["--exclude-module", modulo]
    comando.append(str(AQUI / "emisor.py"))

    inicio = time.perf_counter()
    if subprocess.run(comando, cwd=AQUI).returncode != 0:
        raise SystemExit("\nPyInstaller falló.")
    return time.perf_counter() - inicio


def auditar() -> None:
    """Lo único que de verdad importa: que la privada no esté adentro."""
    titulo("3. Auditoría del ejecutable")
    exe = SALIDA / NOMBRE / f"{NOMBRE}.exe"
    if not exe.exists():
        raise SystemExit(f"No se generó {exe}")
    datos = exe.read_bytes()
    log(f"  {exe.name}  {len(datos) / (1024 * 1024):.1f} MB")

    problemas = []
    if PRIVADA.exists():
        origen = json.loads(PRIVADA.read_text(encoding="utf-8"))
        secreto = origen["privada"]
        aguja = bytes.fromhex(secreto)
        if aguja in datos:
            problemas.append("la clave privada está EN CRUDO dentro del .exe")
        if secreto.encode() in datos:
            problemas.append("la clave privada está EN HEXA dentro del .exe")
        if not problemas:
            log("  OK   la clave privada NO está en el ejecutable")
    else:
        log("  (sin clave privada en esta PC: no se pudo auditar ese punto)")

    if b"cotizador_emisor" in datos:
        problemas.append("el .exe menciona la carpeta de la clave privada")
    else:
        log("  OK   no hay rastros de la carpeta del emisor")

    llave = SALIDA / NOMBRE / "emisor.llave"
    if llave.exists() and llave.read_bytes() in datos:
        problemas.append("la llave cifrada quedó empaquetada adentro")
    else:
        log("  OK   la llave cifrada queda afuera, como archivo suelto")

    if problemas:
        log()
        for p in problemas:
            log(f"  FALLA  {p}")
        raise SystemExit("\nEl ejecutable NO es seguro. Corregí y recompilá.")


def armar_carpeta() -> Path:
    titulo("4. Carpeta para el pendrive")
    destino = SALIDA / NOMBRE
    destino.mkdir(parents=True, exist_ok=True)

    llave = AQUI / "emisor.llave"
    if llave.exists():
        shutil.copy2(llave, destino / llave.name)
        log(f"  + {llave.name}   (la llave cifrada)")
    else:
        log("  aviso: todavía no existe emisor.llave")
        log("         creala con:  python crear_llave.py")

    leeme = AQUI / "LEEME.txt"
    if leeme.exists():
        shutil.copy2(leeme, destino / leeme.name)
        log(f"  + {leeme.name}")

    for archivo in sorted(destino.iterdir()):
        if archivo.is_file():
            log(f"    {archivo.name:<28} {archivo.stat().st_size / 1024:>9.0f} KB")
    return destino


def main() -> int:
    consola = "--consola" in sys.argv
    log(f"\n  Emisor portable de licencias — compilación")

    comprobar()
    try:
        segundos = compilar(consola)
        auditar()
        destino = armar_carpeta()
    finally:
        shutil.rmtree(AQUI / "_build", ignore_errors=True)

    titulo("Listo")
    log(f"  Compilado en {segundos / 60:.1f} min")
    log(f"  Carpeta: {destino}")
    log()
    log("  Copiá esa carpeta al pendrive. Adentro tiene que haber SIEMPRE dos")
    log("  archivos: el .exe y emisor.llave. Uno sin el otro no sirve.")
    log()
    log("  Esto NO se le da a nadie: quien tenga los dos archivos y la")
    log("  contraseña puede emitir licencias del Cotizador para siempre.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
