"""
Instalador de actualizaciones.

Regla central: **se reemplaza sólo el programa; los datos del usuario no se tocan.**

Hay dos formas de instalación y cada una necesita su tipo de paquete:

``codigo``    La app corre desde los .py (desarrollo, o instalación portable con
              Python). El paquete trae ``main.py`` + ``core/`` + ``ui/``… y se
              reemplazan esos archivos en el lugar.

``programa``  La app corre desde el .exe compilado con PyInstaller. **Adentro del
              .exe no hay archivos .py**: el código va compilado en el binario y
              en ``_internal/``. Copiar .py sueltos junto al ejecutable no cambia
              absolutamente nada — el importador congelado nunca los mira. Por eso
              la actualización de un .exe reemplaza la carpeta entera del programa,
              usando el mismo .zip que se le entrega a un cliente nuevo.

Ese reemplazo no se puede hacer desde adentro del propio programa: Windows tiene
el .exe abierto mientras corre. Se deja la versión nueva al lado, se lanza un
script que espera a que la app cierre, intercambia las carpetas y vuelve a abrir
el programa.

Nunca se toca: la carpeta de datos del usuario (``%LOCALAPPDATA%\\CotizadorAberturas``
cuando está empaquetado), las salidas ni las licencias emitidas. Están fuera de la
carpeta de programa justamente para que una actualización no pueda romperlas.

Uso desde la interfaz: Ajustes → Instalar actualización desde archivo .zip
Uso por línea de comandos::

    python -m tools.actualizar paquete.zip
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import rutas  # noqa: E402

#: Lo único que un paquete de código puede reemplazar.
CARPETAS_CODIGO = ("core", "ui", "reports", "tools")
ARCHIVOS_CODIGO = ("main.py", "VERSION", "requirements.txt", "README.md", "Cotizador.bat")

#: Nunca se sobrescriben, aunque vengan dentro del zip.
PROTEGIDOS = {"datos", "salidas", "licencias", "instalado.flag",
              "core/clave_publica.py"}

TIPO_CODIGO = "codigo"
TIPO_PROGRAMA = "programa"


class PaqueteInvalido(Exception):
    pass


def _raiz_del_zip(zf: zipfile.ZipFile) -> str:
    """Detecta si el zip tiene todo dentro de una carpeta contenedora."""
    nombres = [n for n in zf.namelist() if not n.startswith("__MACOSX")]
    if not nombres:
        raise PaqueteInvalido("El paquete está vacío.")
    if any(n == "main.py" or n.startswith("core/") for n in nombres):
        return ""
    primeras = {n.split("/")[0] for n in nombres if "/" in n}
    if len(primeras) == 1:
        return primeras.pop() + "/"
    raise PaqueteInvalido(
        "No se reconoce el contenido del paquete. ¿Es el zip correcto?")


def inspeccionar(ruta_zip: str | Path) -> dict:
    """Valida el paquete.

    Devuelve ``{'tipo', 'version', 'archivos', 'raiz', 'exe', 'compatible'}``.
    ``compatible`` dice si ese paquete sirve para *esta* instalación.
    """
    with zipfile.ZipFile(ruta_zip) as zf:
        raiz = _raiz_del_zip(zf)
        nombres = [n for n in zf.namelist() if n.startswith(raiz)]
        relativos = [n[len(raiz):] for n in nombres if n[len(raiz):]]
        archivos = [r for r in relativos if not r.endswith("/")]

        exe = next((r for r in archivos
                    if r.lower().endswith(".exe") and "/" not in r), "")
        tiene_internal = any(r.startswith("_internal/") for r in relativos)

        if exe and tiene_internal:
            version = "desconocida"
            for candidato in ("_internal/VERSION", "VERSION"):
                if candidato in archivos:
                    version = zf.read(raiz + candidato).decode("utf-8").strip()
                    break
            return {"tipo": TIPO_PROGRAMA, "version": version,
                    "archivos": len(archivos), "raiz": raiz, "exe": exe,
                    "compatible": rutas.empaquetado()}

        if "main.py" not in archivos:
            raise PaqueteInvalido(
                "El paquete no contiene ni main.py ni un ejecutable con su "
                "carpeta _internal. ¿Es el zip correcto?")

        version = "desconocida"
        if "VERSION" in archivos:
            version = zf.read(raiz + "VERSION").decode("utf-8").strip()

        utiles = [r for r in archivos if _es_codigo(r)]
        return {"tipo": TIPO_CODIGO, "version": version, "archivos": len(utiles),
                "raiz": raiz, "exe": "", "compatible": not rutas.empaquetado()}


def _es_codigo(relativo: str) -> bool:
    if relativo in PROTEGIDOS:
        return False
    raiz = relativo.split("/")[0]
    if raiz in PROTEGIDOS:
        return False
    if relativo in ARCHIVOS_CODIGO:
        return True
    return raiz in CARPETAS_CODIGO and relativo.endswith((".py", ".json", ".txt", ".md"))


def _respaldar_programa(version_actual: str) -> Path:
    rutas.asegurar_carpetas()
    sello = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = rutas.COPIAS / f"programa_v{version_actual}_{sello}"
    destino.mkdir(parents=True, exist_ok=True)
    for nombre in ARCHIVOS_CODIGO:
        origen = rutas.RAIZ / nombre
        if origen.exists():
            shutil.copy2(origen, destino / nombre)
    for carpeta in CARPETAS_CODIGO:
        origen = rutas.RAIZ / carpeta
        if origen.exists():
            shutil.copytree(origen, destino / carpeta,
                            ignore=shutil.ignore_patterns("__pycache__"),
                            dirs_exist_ok=True)
    return destino


def aplicar(ruta_zip: str | Path) -> str:
    """Instala la actualización que corresponda al tipo de instalación.

    Si el paquete es de programa (.exe), esto **no termina la actualización**:
    deja todo preparado y lanza el script que la completa cuando la app cierre.
    El llamador tiene que cerrar la aplicación enseguida.
    """
    info = inspeccionar(ruta_zip)

    if not info["compatible"]:
        if info["tipo"] == TIPO_CODIGO:
            raise PaqueteInvalido(
                "Este paquete trae los archivos .py del programa, pero estás "
                "usando la versión compilada (.exe).\n\n"
                "Adentro del .exe no hay archivos .py que reemplazar: el código "
                "va compilado en el ejecutable. Para actualizar el .exe hace "
                "falta el zip completo del programa, el mismo que se entrega a "
                "un cliente nuevo (contiene el .exe y la carpeta _internal).")
        raise PaqueteInvalido(
            "Este paquete trae el programa compilado (.exe + _internal), pero "
            "estás corriendo desde el código fuente.\n\n"
            "Para esta instalación hace falta el paquete de código, el que "
            "contiene main.py y las carpetas core/, ui/, reports/ y tools/.")

    if info["tipo"] == TIPO_PROGRAMA:
        return _aplicar_programa(ruta_zip, info)
    return _aplicar_codigo(ruta_zip, info)


def _aplicar_codigo(ruta_zip: str | Path, info: dict) -> str:
    """Reemplaza los .py de una instalación que corre desde el código fuente."""
    version_previa = rutas.version()
    respaldo = _respaldar_programa(version_previa)

    tenia_clave = (rutas.RAIZ / "core" / "clave_publica.py").exists()
    escritos = 0

    with tempfile.TemporaryDirectory() as tmp:
        temporal = Path(tmp)
        with zipfile.ZipFile(ruta_zip) as zf:
            zf.extractall(temporal)
        origen = temporal / info["raiz"] if info["raiz"] else temporal

        try:
            # El código viejo se retira antes de copiar el nuevo, para que no
            # queden módulos eliminados dando vueltas.
            for carpeta in CARPETAS_CODIGO:
                if (origen / carpeta).is_dir() and (rutas.RAIZ / carpeta).is_dir():
                    shutil.rmtree(rutas.RAIZ / carpeta, ignore_errors=True)

            for elemento in origen.rglob("*"):
                if elemento.is_dir():
                    continue
                relativo = elemento.relative_to(origen).as_posix()
                if not _es_codigo(relativo):
                    continue
                destino = rutas.RAIZ / relativo
                destino.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(elemento, destino)
                escritos += 1
        except Exception:
            _revertir(respaldo)
            raise

    # Una actualización que no trae clave pública no debe dejar la instalación
    # sin ella: eso invalidaría todas las licencias emitidas.
    destino_clave = rutas.RAIZ / "core" / "clave_publica.py"
    if tenia_clave and not destino_clave.exists():
        origen_clave = respaldo / "core" / "clave_publica.py"
        if origen_clave.exists():
            shutil.copy2(origen_clave, destino_clave)

    return (f"Actualizado de la versión {version_previa} a la {info['version']}.\n"
            f"{escritos} archivos de programa reemplazados.\n\n"
            f"Tus datos siguen en:\n{rutas.DATOS}\n\n"
            f"Copia del programa anterior:\n{respaldo}")


# ---------------------------------------------------------------------------
# Actualización del programa compilado (.exe)
# ---------------------------------------------------------------------------


def _escribible(carpeta: Path) -> bool:
    """¿Se puede crear y renombrar dentro de esta carpeta?

    Se prueba de verdad en lugar de mirar permisos: en Windows los permisos
    efectivos dependen de ACL, UAC y virtualización, y ``os.access`` miente.
    """
    prueba = carpeta / f".prueba_escritura_{os.getpid()}"
    try:
        prueba.mkdir()
        prueba.rmdir()
        return True
    except OSError:
        return False


def preparar_programa(ruta_zip: str | Path, info: dict | None = None) -> dict:
    """Deja la versión nueva descomprimida al lado de la instalación.

    No modifica todavía la instalación en uso. Devuelve las rutas que necesita
    el script de intercambio.
    """
    info = info or inspeccionar(ruta_zip)
    instalacion = rutas.RAIZ
    contenedor = instalacion.parent

    if not _escribible(contenedor):
        raise PaqueteInvalido(
            f"No hay permiso para escribir en:\n{contenedor}\n\n"
            "Para actualizarse, el programa tiene que poder reemplazar su propia "
            "carpeta. Movelo a una carpeta tuya (por ejemplo el Escritorio o "
            "Documentos), o ejecutalo como administrador.")

    nueva = contenedor / f"{instalacion.name}_nuevo"
    shutil.rmtree(nueva, ignore_errors=True)
    nueva.mkdir(parents=True)

    with tempfile.TemporaryDirectory(dir=str(contenedor)) as tmp:
        temporal = Path(tmp)
        with zipfile.ZipFile(ruta_zip) as zf:
            zf.extractall(temporal)
        origen = temporal / info["raiz"].rstrip("/") if info["raiz"] else temporal
        for elemento in origen.iterdir():
            shutil.move(str(elemento), str(nueva / elemento.name))

    exe_nuevo = nueva / info["exe"]
    if not exe_nuevo.is_file() or not (nueva / "_internal").is_dir():
        shutil.rmtree(nueva, ignore_errors=True)
        raise PaqueteInvalido(
            "El paquete se descomprimió pero no tiene la forma esperada "
            f"({info['exe']} + carpeta _internal). No se instaló nada.")

    return {"instalacion": instalacion, "nueva": nueva,
            "exe": instalacion / info["exe"], "info": info}


#: El intercambio lo hace un .bat porque tiene que correr **después** de que el
#: programa cierre: mientras el .exe está abierto, Windows no deja renombrar su
#: carpeta. ``ping`` se usa como espera porque ``timeout`` falla sin consola.
GUION_INTERCAMBIO = r"""@echo off
chcp 65001 >nul
title Actualizando {nombre}
cd /d "{contenedor}"

echo Esperando a que el programa termine de cerrarse...
set INTENTOS=0
:esperar
tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul
if errorlevel 1 goto cerrado
set /a INTENTOS+=1
if %INTENTOS% GEQ 60 goto no_cerro
ping -n 2 127.0.0.1 >nul
goto esperar

:cerrado
rem Un par de segundos de gracia: el antivirus suele mantener el .exe tomado
rem un momento más después de que el proceso termina.
ping -n 3 127.0.0.1 >nul

set INTENTOS=0
:mover
move "{instalacion}" "{vieja}" >nul 2>&1
if not errorlevel 1 goto poner_nueva
set /a INTENTOS+=1
if %INTENTOS% GEQ 15 goto no_pudo_mover
ping -n 3 127.0.0.1 >nul
goto mover

:poner_nueva
move "{nueva}" "{instalacion}" >nul 2>&1
if errorlevel 1 goto revertir
rmdir /s /q "{vieja}" >nul 2>&1
echo Listo. Abriendo la version nueva...
start "" "{exe}"
goto fin

:revertir
move "{vieja}" "{instalacion}" >nul 2>&1
echo.
echo No se pudo instalar la version nueva. Se dejo la anterior como estaba.
echo La version nueva quedo sin instalar en:
echo    {nueva}
pause
goto fin

:no_cerro
echo.
echo El programa no termino de cerrarse. Cerralo y volve a intentar.
echo La version nueva quedo en:  {nueva}
pause
goto fin

:no_pudo_mover
echo.
echo No se pudo reemplazar la carpeta del programa. Puede haber otra ventana
echo abierta o el antivirus la tiene tomada. No se cambio nada.
echo La version nueva quedo en:  {nueva}
pause

:fin
del "%~f0"
"""


def _aplicar_programa(ruta_zip: str | Path, info: dict) -> str:
    """Prepara el reemplazo de la carpeta del .exe y lanza el script que lo hace."""
    version_previa = rutas.version()
    plan = preparar_programa(ruta_zip, info)

    sello = datetime.now().strftime("%Y%m%d_%H%M%S")
    vieja = plan["instalacion"].parent / f"{plan['instalacion'].name}_viejo_{sello}"

    guion = Path(tempfile.gettempdir()) / f"actualizar_cotizador_{sello}.bat"
    guion.write_text(
        GUION_INTERCAMBIO.format(
            nombre=plan["instalacion"].name,
            contenedor=plan["instalacion"].parent,
            pid=os.getpid(),
            instalacion=plan["instalacion"],
            nueva=plan["nueva"],
            vieja=vieja,
            exe=plan["exe"]),
        encoding="utf-8")

    # Consola propia, no DETACHED_PROCESS: el script sobrevive igual al cierre de
    # la app (Windows no mata a los hijos), y con ventana el usuario ve que se
    # está instalando algo en vez de mirar la pantalla vacía. Sin consola, además,
    # los avisos de error del script no se verían nunca.
    banderas = 0
    if sys.platform.startswith("win"):
        banderas = getattr(subprocess, "CREATE_NEW_CONSOLE", 0) | \
                   getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(["cmd", "/c", str(guion)], close_fds=True,
                     creationflags=banderas, cwd=str(plan["instalacion"].parent))

    return (f"Actualización preparada: de la versión {version_previa} "
            f"a la {info['version']}.\n\n"
            "Al cerrar el programa se reemplaza la carpeta y se vuelve a abrir "
            "solo. Puede tardar unos segundos.\n\n"
            f"Tus datos siguen en:\n{rutas.DATOS}")


def _revertir(respaldo: Path) -> None:
    for carpeta in CARPETAS_CODIGO:
        origen = respaldo / carpeta
        if origen.is_dir():
            shutil.rmtree(rutas.RAIZ / carpeta, ignore_errors=True)
            shutil.copytree(origen, rutas.RAIZ / carpeta, dirs_exist_ok=True)
    for nombre in ARCHIVOS_CODIGO:
        origen = respaldo / nombre
        if origen.exists():
            shutil.copy2(origen, rutas.RAIZ / nombre)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    ruta = sys.argv[1]
    try:
        info = inspeccionar(ruta)
    except Exception as exc:
        print(f"Paquete inválido: {exc}")
        return 1

    print(f"Paquete   : {ruta}")
    print(f"Tipo      : {info['tipo']}"
          f"{'' if info['compatible'] else '   << NO sirve para esta instalación >>'}")
    print(f"Versión   : {info['version']}  (instalada: {rutas.version()})")
    print(f"Archivos  : {info['archivos']}")
    if input("\n¿Instalar? [s/N] ").strip().lower() not in ("s", "si", "sí"):
        print("Cancelado.")
        return 0

    print("\n" + aplicar(ruta))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
