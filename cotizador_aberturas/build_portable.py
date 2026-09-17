"""
Compila una versión PORTABLE de uso personal (pendrive), sin licencia.

    python build_portable.py

Diferencias con el ejecutable comercial
---------------------------------------
1. **Los datos viajan con el programa.** La base, los respaldos y los PDF quedan
   en ``datos/`` y ``salidas/`` **al lado del .exe**, no en ``%LOCALAPPDATA%``.
   Se puede llevar el pendrive a otra PC y sigue todo ahí.
2. **No pide activación.** ``estado_actual()`` devuelve una licencia perpetua de
   uso personal, sin consultar el reloj ni la red.

Por qué se compila desde una copia
----------------------------------
El proyecto **no se toca**: se copia a una carpeta temporal, se parchea la copia
y se compila desde ahí. Si este script se interrumpiera a la mitad, el código
del proyecto sigue intacto y el próximo build comercial sale con su licencia
donde corresponde. Un parche aplicado sobre el proyecto real y "restaurado
después" abre justo esa ventana de error.

La salida queda en ``portable/`` — **nunca en ``entregas/``**, que es la carpeta
de los paquetes que se le mandan a un cliente.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
NOMBRE = "CotizadorAberturas"
SALIDA = RAIZ / "portable"

#: No tiene sentido copiarlos a la carpeta de compilación
IGNORAR = shutil.ignore_patterns(
    "datos", "salidas", "dist", "build", "portable", "entregas", "docs",
    "__pycache__", "*.pyc", ".git", ".venv", "venv", "*.db", "*.zip")

EXCLUIR = [
    "tools.keygen", "tools.generar_claves", "tools.empaquetar",
    "matplotlib", "numpy", "pandas", "scipy", "IPython", "pytest",
    "PyQt5", "PyQt6", "PySide2", "PySide6", "notebook", "tornado",
    "test", "unittest", "pydoc", "doctest",
]

PROHIBIDOS = ("keygen", "generar_claves", "clave_privada")


def _log(mensaje: str = "") -> None:
    print(mensaje, flush=True)


def _titulo(texto: str) -> None:
    _log()
    _log("=" * 70)
    _log(f"  {texto}")
    _log("=" * 70)


# ---------------------------------------------------------------------------
# Parches sobre la copia
# ---------------------------------------------------------------------------

# Reemplaza la línea que fija dónde viven los datos. Se hace por sustitución de
# texto y no agregando una función al final del módulo porque DATOS, SALIDAS y
# RUTA_DB se calculan al importar: una redefinición posterior llegaría tarde.
RUTAS_ORIGINAL = "BASE_USUARIO = _base_datos_usuario()"

RUTAS_PORTABLE = '''def _base_datos_portable() -> Path:
    """Edición portable: los datos viven junto al ejecutable.

    Si la carpeta del programa no admite escritura (pendrive protegido, o el
    .exe copiado a "Archivos de programa"), cae a la carpeta del usuario en vez
    de reventar al arrancar.
    """
    ruta_env = os.environ.get("COTIZADOR_DATOS", "").strip()
    if ruta_env:
        return Path(ruta_env).expanduser().resolve()

    junto_al_exe = raiz_proyecto()
    try:
        prueba = junto_al_exe / ".escritura"
        prueba.touch()
        prueba.unlink()
        return junto_al_exe
    except OSError:
        return _base_datos_usuario()


BASE_USUARIO = _base_datos_portable()'''


LICENCIA_PORTABLE = '''

# ---------------------------------------------------------------------------
# Edición portable de uso personal
# ---------------------------------------------------------------------------
#
# Redefine estado_actual() para la compilación portable: no hay activación por
# equipo, ni verificación de reloj, ni consulta de red. El resto del módulo
# queda intacto — validar_texto() e instalar() siguen existiendo, simplemente
# nadie los llama.

def estado_actual(consultar_red: bool = True) -> Estado:   # noqa: F811
    """Licencia perpetua de uso personal, sin verificaciones."""
    return Estado(
        valida=True,
        motivo="Edición portable de uso personal.",
        licencia=Licencia(
            cliente="Uso personal",
            hwid=obtener_hwid(),
            emitida=date.today().isoformat(),
            vence="",                      # perpetua
            plan="completa",
            notas="Versión portable — no distribuir",
        ),
        dias_restantes=None,
        fuente_hora="sistema",
    )
'''


def preparar_copia(destino: Path) -> None:
    _titulo("2. Copiando y parcheando el código")
    shutil.copytree(RAIZ, destino, ignore=IGNORAR, dirs_exist_ok=True)
    _log(f"  copia en {destino}")

    # -- datos junto al ejecutable
    rutas = destino / "core" / "rutas.py"
    texto = rutas.read_text(encoding="utf-8")
    if RUTAS_ORIGINAL not in texto:
        raise SystemExit(
            "core/rutas.py cambió y el parche de portabilidad ya no aplica.\n"
            f"Se esperaba encontrar la línea:  {RUTAS_ORIGINAL}")
    rutas.write_text(texto.replace(RUTAS_ORIGINAL, RUTAS_PORTABLE), encoding="utf-8")
    _log("  + core/rutas.py    → datos junto al .exe")

    # -- sin activación
    licencia = destino / "core" / "licencia.py"
    licencia.write_text(
        licencia.read_text(encoding="utf-8") + LICENCIA_PORTABLE, encoding="utf-8")
    _log("  + core/licencia.py → licencia perpetua de uso personal")


# ---------------------------------------------------------------------------
# Compilación
# ---------------------------------------------------------------------------

def compilar(proyecto: Path, consola: bool) -> float:
    _titulo("3. Compilando")
    separador = ";" if sys.platform == "win32" else ":"
    trabajo = proyecto / "_build"

    comando = [
        sys.executable, "-m", "PyInstaller",
        "--name", NOMBRE,
        "--onedir",
        "--console" if consola else "--noconsole",
        "--noconfirm", "--clean",
        "--distpath", str(SALIDA),
        "--workpath", str(trabajo),
        "--specpath", str(trabajo),
    ]

    icono = proyecto / "recursos" / "icono.ico"
    if icono.exists():
        comando += ["--icon", str(icono)]

    version = proyecto / "VERSION"
    if version.exists():
        comando += ["--add-data", f"{version}{separador}."]

    for modulo in EXCLUIR:
        comando += ["--exclude-module", modulo]

    comando += ["--collect-data", "customtkinter"]
    comando += ["--hidden-import", "PIL._tkinter_finder"]
    comando += ["--hidden-import", "openpyxl", "--hidden-import", "PIL.Image"]
    comando.append(str(proyecto / "main.py"))

    inicio = time.perf_counter()
    resultado = subprocess.run(comando, cwd=proyecto)
    if resultado.returncode != 0:
        raise SystemExit(f"\nPyInstaller falló (código {resultado.returncode}).")
    return time.perf_counter() - inicio


def auditar() -> None:
    """Aunque sea de uso personal, la clave privada no puede viajar adentro."""
    _titulo("4. Auditoría")
    carpeta = SALIDA / NOMBRE
    archivos = [p for p in carpeta.rglob("*") if p.is_file()]

    filtrados = [p for p in archivos
                 if any(mal in p.name.lower() for mal in PROHIBIDOS)]

    fuga = []
    privada = Path.home() / ".cotizador_emisor" / "clave_privada.json"
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
                fuga.append(ruta.name)

    if filtrados or fuga:
        for p in filtrados:
            _log(f"  FALLA  archivo prohibido: {p}")
        for n in fuga:
            _log(f"  FALLA  clave privada dentro de: {n}")
        raise SystemExit("\nEl paquete no está limpio.")

    _log(f"  {len(archivos)} archivo(s) analizados")
    _log("  OK   sin keygen ni claves de emisor")


def probar(version: str) -> None:
    """Arranca el .exe y confirma que crea la base JUNTO A ÉL, no en AppData."""
    _titulo("5. Prueba de portabilidad")
    carpeta = SALIDA / NOMBRE
    exe = carpeta / f"{NOMBRE}.exe"

    proceso = subprocess.Popen([str(exe)], cwd=carpeta)
    base = carpeta / "datos" / "cotizador.db"
    for _ in range(30):
        time.sleep(1)
        if proceso.poll() is not None:
            raise SystemExit(
                f"\n  FALLA  el programa se cerró solo (código {proceso.returncode})."
                "\n         Recompilá con --consola para ver el error.")
        if base.exists():
            break

    vivo = proceso.poll() is None
    proceso.terminate()
    try:
        proceso.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proceso.kill()

    if not base.exists():
        raise SystemExit(
            "\n  FALLA  no se creó datos/cotizador.db junto al ejecutable.\n"
            "         El parche de portabilidad no tomó efecto.")
    if not vivo:
        raise SystemExit("\n  FALLA  el programa no se mantuvo abierto.")

    _log(f"  OK   arrancó sin pedir activación")
    _log(f"  OK   base creada en {base.relative_to(SALIDA)}")


def documentar(version: str) -> None:
    (SALIDA / NOMBRE / "LEEME - version portable.txt").write_text(
        f"""COTIZADOR DE ABERTURAS — versión portable {version}
{'=' * 62}

Uso personal. NO distribuir: esta compilación no lleva control de licencia.

Cómo se usa
-----------
Copiá la carpeta entera al pendrive y ejecutá CotizadorAberturas.exe.
No hay que instalar nada ni pide activación.

Dónde quedan los datos
----------------------
Junto al programa, dentro de esta misma carpeta:

    datos\\cotizador.db          la base (presupuestos, precios, catálogos)
    datos\\copias\\              respaldos automáticos
    datos\\imagenes_perfiles\\   dibujos de sección
    salidas\\                    los PDF que generes

O sea que todo viaja en el pendrive. Lo podés enchufar en otra PC y seguir
donde lo dejaste.

Si el pendrive está protegido contra escritura, o copiás el programa a una
carpeta sin permisos, cae solo a %LOCALAPPDATA%\\CotizadorAberturas y sigue
funcionando (pero ahí los datos ya no viajan).

Llevarte los datos que ya tenés
-------------------------------
Copiá el contenido de:

    %LOCALAPPDATA%\\CotizadorAberturas\\datos

adentro de la carpeta "datos" de acá. Cerrá el programa antes de copiar.

Forzar otra ubicación
---------------------
Si querés que los datos vayan a una carpeta fija, definí la variable de
entorno COTIZADOR_DATOS con la ruta antes de abrir el programa.

Ojo
---
Un pendrive es más lento y más frágil que un disco. Hacé copia de
datos\\cotizador.db cada tanto — el programa ya guarda respaldos automáticos
en datos\\copias antes de cada actualización de esquema.
""", encoding="utf-8")


def comprimir(version: str) -> Path:
    destino = SALIDA / f"{NOMBRE}_PORTABLE_v{version}_uso-personal.zip"
    origen = SALIDA / NOMBRE
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zf:
        for ruta in sorted(origen.rglob("*")):
            if ruta.is_file() and "datos" not in ruta.relative_to(origen).parts:
                zf.write(ruta, Path(NOMBRE) / ruta.relative_to(origen))
    return destino


# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compila la versión portable de uso personal")
    parser.add_argument("--consola", action="store_true",
                        help="Deja la consola visible, para depurar")
    parser.add_argument("--sin-zip", action="store_true")
    args = parser.parse_args()

    version = (RAIZ / "VERSION").read_text(encoding="utf-8").strip()

    _titulo(f"1. {NOMBRE} portable — versión {version}")
    _log("  Uso personal · sin licencia · datos junto al ejecutable")

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        raise SystemExit("Falta PyInstaller.\n\n    pip install pyinstaller")

    shutil.rmtree(SALIDA / NOMBRE, ignore_errors=True)
    SALIDA.mkdir(parents=True, exist_ok=True)

    temporal = Path(tempfile.mkdtemp(prefix="cotizador_portable_"))
    try:
        proyecto = temporal / "src"
        preparar_copia(proyecto)
        segundos = compilar(proyecto, args.consola)
        auditar()
        probar(version)
        documentar(version)
    finally:
        shutil.rmtree(temporal, ignore_errors=True)

    _titulo("Listo")
    _log(f"  Compilado en {segundos / 60:.1f} min")
    _log(f"  Carpeta:  {SALIDA / NOMBRE}")
    if not args.sin_zip:
        zip_ = comprimir(version)
        _log(f"  Zip:      {zip_}  ({zip_.stat().st_size / (1024 * 1024):.1f} MB)")
    _log()
    _log("  Copiá la carpeta al pendrive y listo. No pide activación y")
    _log("  guarda la base y los PDF adentro de la misma carpeta.")
    _log()
    _log("  Esta compilación NO se le da a un cliente: no tiene licencia.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
