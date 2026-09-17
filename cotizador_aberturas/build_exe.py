"""
Compila el ejecutable comercial con PyInstaller.

    python build_exe.py                 # --onedir  (recomendado)
    python build_exe.py --onefile       # un solo .exe, arranca más lento
    python build_exe.py --version 2.1.0 --consola   # para depurar

Qué garantiza este script
-------------------------
1. **Datos en la carpeta del usuario.** ``core/rutas.py`` detecta que corre
   empaquetado y manda base de datos, respaldos y PDF a
   ``%LOCALAPPDATA%/CotizadorAberturas``. Un ejecutable instalado en
   ``C:\\Program Files`` no puede escribir junto a sí mismo.

2. **``tools/keygen.py`` afuera.** Se excluye del análisis y **se verifica sobre
   el binario ya construido**: se busca el nombre del módulo y la huella de la
   clave privada dentro de los archivos generados. Si aparece algo, el script
   falla y no te deja distribuir.

3. **Clave privada afuera.** Vive en ``~/.cotizador_emisor``, fuera del
   proyecto, así que PyInstaller no puede verla ni por accidente.

onedir vs onefile
-----------------
``--onefile`` produce un archivo único, cómodo de mandar, pero en cada arranque
descomprime todo a una carpeta temporal: con CustomTkinter + ReportLab son unos
3–6 segundos **cada vez que se abre el programa**. ``--onedir`` arranca en menos
de un segundo; se entrega comprimido en un .zip y se descomprime una sola vez.
Para uso diario en un taller, onedir es la mejor opción.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
NOMBRE = "CotizadorAberturas"

DIST = RAIZ / "dist"
BUILD = RAIZ / "build"
ENTREGAS = RAIZ.parent / "entregas"

# Nunca deben terminar dentro del paquete del cliente
PROHIBIDOS = ("keygen", "generar_claves", "clave_privada")

# Módulos que PyInstaller arrastra por las dudas y acá no se usan
EXCLUIR = [
    "tools.keygen", "tools.generar_claves", "tools.empaquetar",
    "matplotlib", "numpy", "pandas", "scipy", "IPython", "pytest",
    "PyQt5", "PyQt6", "PySide2", "PySide6", "notebook", "tornado",
    "test", "unittest", "pydoc", "doctest",
]


def _log(mensaje: str = "") -> None:
    print(mensaje, flush=True)


def _titulo(texto: str) -> None:
    _log()
    _log("=" * 70)
    _log(f"  {texto}")
    _log("=" * 70)


# ---------------------------------------------------------------------------
# Comprobaciones previas
# ---------------------------------------------------------------------------

def comprobar_entorno() -> None:
    _titulo("1. Comprobaciones previas")

    try:
        import PyInstaller  # noqa: F401
        _log(f"  PyInstaller  {PyInstaller.__version__}")
    except ImportError:
        raise SystemExit("Falta PyInstaller.\n\n    pip install pyinstaller")

    for modulo in ("customtkinter", "reportlab"):
        try:
            __import__(modulo)
            _log(f"  {modulo:<12} OK")
        except ImportError:
            raise SystemExit(f"Falta {modulo}.\n\n    pip install -r requirements.txt")

    publica = RAIZ / "core" / "clave_publica.py"
    if not publica.exists():
        raise SystemExit(
            "No existe core/clave_publica.py.\n\n"
            "Generá el par de claves una única vez:\n"
            "    python -m tools.generar_claves")
    _log("  clave_publica.py OK")

    privada = Path.home() / ".cotizador_emisor" / "clave_privada.json"
    if privada.exists():
        try:
            privada.relative_to(RAIZ)
            raise SystemExit(
                f"PELIGRO: la clave privada está dentro del proyecto ({privada}).\n"
                "Movela a ~/.cotizador_emisor/ antes de compilar.")
        except ValueError:
            _log(f"  clave privada fuera del proyecto OK")
    else:
        _log("  aviso: no hay clave privada en esta PC (no hace falta para compilar)")


# No hace falta ningún marcador en disco: core/rutas.py detecta sys.frozen y
# manda base de datos, respaldos y PDF a la carpeta del usuario.


# ---------------------------------------------------------------------------
# Compilación
# ---------------------------------------------------------------------------

def armar_comando(onefile: bool, consola: bool) -> list[str]:
    separador = ";" if sys.platform == "win32" else ":"

    comando = [
        sys.executable, "-m", "PyInstaller",
        "--name", NOMBRE,
        "--onefile" if onefile else "--onedir",
        "--console" if consola else "--noconsole",
        "--noconfirm",
        "--clean",
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        "--specpath", str(BUILD),
    ]

    icono = RAIZ / "recursos" / "icono.ico"
    if icono.exists():
        comando += ["--icon", str(icono)]
    else:
        _log("  aviso: no hay recursos/icono.ico, se usa el ícono por defecto")

    # Datos que tienen que viajar con el programa. Quedan en sys._MEIPASS,
    # que core/rutas.py resuelve con carpeta_recursos().
    origen = RAIZ / "VERSION"
    if origen.exists():
        comando += ["--add-data", f"{origen}{separador}."]

    for modulo in EXCLUIR:
        comando += ["--exclude-module", modulo]

    # CustomTkinter carga sus temas desde archivos en disco
    comando += ["--collect-data", "customtkinter"]
    comando += ["--hidden-import", "PIL._tkinter_finder"]
    # openpyxl se importa recién adentro del importador de catálogos, y Pillow
    # sólo aparece al mostrar el dibujo de un perfil: sin esto, PyInstaller
    # puede dejarlos afuera y esas dos funciones fallan únicamente en el .exe.
    comando += ["--hidden-import", "openpyxl", "--hidden-import", "PIL.Image"]

    comando.append(str(RAIZ / "main.py"))
    return comando


def compilar(onefile: bool, consola: bool) -> float:
    _titulo("2. Compilando")
    comando = armar_comando(onefile, consola)
    _log(f"  Modo: {'onefile' if onefile else 'onedir'} · "
         f"{'con consola' if consola else 'sin consola'}")
    _log()

    inicio = time.perf_counter()
    resultado = subprocess.run(comando, cwd=RAIZ)
    if resultado.returncode != 0:
        raise SystemExit(f"\nPyInstaller falló (código {resultado.returncode}).")
    return time.perf_counter() - inicio


# ---------------------------------------------------------------------------
# Auditoría del binario
# ---------------------------------------------------------------------------

def auditar(onefile: bool) -> None:
    """Verifica sobre el paquete YA CONSTRUIDO que no se filtró nada sensible."""
    _titulo("3. Auditoría del paquete")

    objetivo = DIST / (f"{NOMBRE}.exe" if onefile else NOMBRE)
    if not objetivo.exists():
        raise SystemExit(f"No se encontró la salida esperada: {objetivo}")

    archivos = [objetivo] if objetivo.is_file() else [
        p for p in objetivo.rglob("*") if p.is_file()]

    # 1) Ningún archivo con nombre prohibido
    filtrados = [p for p in archivos
                 if any(mal in p.name.lower() for mal in PROHIBIDOS)]

    # 2) Ninguna referencia a los módulos internos dentro de los binarios
    referencias = []
    for ruta in archivos:
        if ruta.suffix.lower() not in (".exe", ".pyz", ".pkg", ".dll", ""):
            continue
        try:
            contenido = ruta.read_bytes()
        except OSError:
            continue
        for mal in ("tools.keygen", "tools\\keygen", "cotizador_emisor"):
            if mal.encode("utf-8") in contenido:
                referencias.append(f"{ruta.name}: {mal}")

    # 3) La clave PRIVADA no puede estar en ningún lado
    privada = Path.home() / ".cotizador_emisor" / "clave_privada.json"
    fuga_clave = []
    if privada.exists():
        import json
        secreto = json.loads(privada.read_text(encoding="utf-8"))["privada"]
        aguja = bytes.fromhex(secreto)
        for ruta in archivos:
            try:
                datos = ruta.read_bytes()
            except OSError:
                continue
            if aguja in datos or secreto.encode() in datos:
                fuga_clave.append(ruta.name)

    problemas = []
    if filtrados:
        problemas.append("Archivos prohibidos:\n    " +
                         "\n    ".join(str(p) for p in filtrados))
    if referencias:
        problemas.append("Referencias internas:\n    " + "\n    ".join(referencias))
    if fuga_clave:
        problemas.append("LA CLAVE PRIVADA ESTÁ EN EL PAQUETE:\n    " +
                         "\n    ".join(fuga_clave))

    if problemas:
        _log()
        for problema in problemas:
            _log("  FALLA  " + problema)
        raise SystemExit(
            "\nEl paquete NO es apto para distribuir. Corregí lo anterior y recompilá.")

    _log(f"  {len(archivos)} archivo(s) analizados")
    _log("  OK   tools/keygen.py no está en el paquete")
    _log("  OK   sin referencias a los módulos del emisor")
    _log("  OK   la clave privada no aparece en ningún archivo")


def probar_arranque(onefile: bool) -> None:
    """Arranca el ejecutable y confirma que sigue vivo.

    Es la única verificación que prueba de verdad que el paquete está completo:
    si faltara un módulo o la clave pública, el programa moriría al arrancar.
    """
    _titulo("4. Prueba de arranque")
    objetivo = DIST / f"{NOMBRE}.exe" if onefile else DIST / NOMBRE / f"{NOMBRE}.exe"

    _log("  Abriendo el ejecutable…")
    proceso = subprocess.Popen([str(objetivo)], cwd=objetivo.parent)
    espera = 25 if onefile else 15
    for _ in range(espera):
        time.sleep(1)
        if proceso.poll() is not None:
            raise SystemExit(
                f"\n  FALLA  El programa se cerró solo (código {proceso.returncode}).\n"
                "         Recompilá con --consola para ver el error.")

    proceso.terminate()
    try:
        proceso.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proceso.kill()
    _log(f"  OK   arrancó y se mantuvo abierto {espera} s")


# ---------------------------------------------------------------------------
# Entrega
# ---------------------------------------------------------------------------

def copiar_documentos(onefile: bool) -> int:
    """Suma a la carpeta del programa los textos que lee el cliente.

    Van en ``recursos/entrega`` y no en ``dist``: PyInstaller borra ``dist`` en
    cada compilación, así que todo lo que se deje ahí a mano se pierde en la
    siguiente. Ojo: **todo lo que esté en esta carpeta viaja al cliente**; las
    notas internas van en ``docs/``.
    """
    origen = RAIZ / "recursos" / "entrega"
    if onefile or not origen.is_dir():
        return 0
    destino = DIST / NOMBRE
    copiados = 0
    for archivo in sorted(origen.iterdir()):
        if archivo.is_file():
            shutil.copy2(archivo, destino / archivo.name)
            _log(f"  + {archivo.name}")
            copiados += 1
    return copiados


def empaquetar_entrega(onefile: bool, version: str) -> Path:
    _titulo("5. Paquete de entrega")
    ENTREGAS.mkdir(parents=True, exist_ok=True)
    objetivo = DIST / (f"{NOMBRE}.exe" if onefile else NOMBRE)
    copiar_documentos(onefile)

    if onefile:
        destino = ENTREGAS / f"{NOMBRE}_v{version}.exe"
        shutil.copy2(objetivo, destino)
    else:
        destino = ENTREGAS / f"{NOMBRE}_v{version}.zip"
        with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zf:
            for ruta in sorted(objetivo.rglob("*")):
                if ruta.is_file():
                    zf.write(ruta, Path(NOMBRE) / ruta.relative_to(objetivo))

    _log(f"  {destino}")
    _log(f"  {destino.stat().st_size / (1024 * 1024):.1f} MB")
    return destino


def limpiar() -> None:
    shutil.rmtree(BUILD, ignore_errors=True)


# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Compila el ejecutable comercial")
    parser.add_argument("--onefile", action="store_true",
                        help="Un solo .exe (arranque más lento)")
    parser.add_argument("--consola", action="store_true",
                        help="Deja la consola visible, para depurar")
    parser.add_argument("--version", help="Número de versión para el nombre del paquete")
    parser.add_argument("--sin-limpiar", action="store_true")
    args = parser.parse_args()

    if args.version:
        (RAIZ / "VERSION").write_text(args.version + "\n", encoding="utf-8")
    version = (RAIZ / "VERSION").read_text(encoding="utf-8").strip()

    _log(f"\n  {NOMBRE} — compilación de la versión {version}")

    comprobar_entorno()

    try:
        segundos = compilar(args.onefile, args.consola)
        auditar(args.onefile)
        probar_arranque(args.onefile)
        destino = empaquetar_entrega(args.onefile, version)
    finally:
        if not args.sin_limpiar:
            limpiar()

    _titulo("Listo")
    _log(f"  Compilado en {segundos / 60:.1f} min")
    _log(f"  Entregable: {destino}")
    _log()
    _log("  Antes de enviarlo:")
    _log("    1. Probá el .exe en una PC limpia (sin Python instalado).")
    _log("    2. Anotá el código de equipo que muestre y emití la licencia:")
    _log("         python -m tools.keygen")
    _log()
    if not args.onefile:
        _log("  Se entrega el .zip: el cliente lo descomprime y ejecuta el .exe de adentro.")
        _log("  Ese mismo .zip es el paquete de actualización: un cliente que ya tenga")
        _log("  la versión 2.2.0 o posterior lo instala desde Ajustes, sin descomprimir.")
    else:
        _log("  Recordá que --onefile tarda unos segundos en abrir cada vez.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
