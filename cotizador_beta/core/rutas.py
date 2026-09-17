"""
Separación estricta entre CÓDIGO y DATOS DE USUARIO.

    <proyecto>/  main.py, core/, ui/, reports/, tools/   -> se reemplaza al actualizar
    <datos>/     cotizador.db, licencia.lic, ajustes.json -> NUNCA se toca
    <salidas>/   PDF generados                             -> NUNCA se toca

Dónde viven los datos
---------------------
Por defecto, en ``<proyecto>/datos`` y ``<proyecto>/salidas`` (modo portable: la
app entera se puede llevar en un pendrive).

Se puede mover la carpeta de datos de dos formas, útiles cuando el instalador
deja el código en ``C:\\Program Files`` (donde el usuario no tiene permiso de
escritura):

1. Variable de entorno ``COTIZADOR_DATOS`` con la ruta deseada.
2. Archivo ``instalado.flag`` junto a ``main.py``: los datos pasan a
   ``%LOCALAPPDATA%\\CotizadorAberturas`` (o ``~/.local/share`` en Linux/macOS).

En cualquier caso el actualizador nunca escribe dentro de estas carpetas.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

NOMBRE_APP = "CotizadorAberturas"


def empaquetado() -> bool:
    """``True`` cuando corre desde un ejecutable de PyInstaller."""
    return getattr(sys, "frozen", False)


def raiz_proyecto() -> Path:
    """Carpeta donde vive el código (o el .exe si se empaquetó con PyInstaller)."""
    if empaquetado():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def carpeta_recursos() -> Path:
    """Recursos de sólo lectura que viajan con el programa.

    PyInstaller los descomprime en ``sys._MEIPASS`` (``_internal/`` en modo
    onedir), que **no** es la carpeta del .exe. Buscarlos junto al ejecutable
    hace que no se encuentren y, por ejemplo, la versión aparezca como 0.0.0.
    """
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) if base else raiz_proyecto()


def _base_datos_usuario() -> Path:
    proyecto = raiz_proyecto()

    ruta_env = os.environ.get("COTIZADOR_DATOS", "").strip()
    if ruta_env:
        return Path(ruta_env).expanduser().resolve()

    # Un ejecutable distribuido nunca escribe junto a sí mismo: puede estar en
    # "C:\\Program Files", donde el usuario no tiene permiso de escritura.
    if empaquetado() or (proyecto / "instalado.flag").exists():
        if sys.platform.startswith("win"):
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        return base / NOMBRE_APP

    return proyecto


RAIZ = raiz_proyecto()
RECURSOS = carpeta_recursos()
BASE_USUARIO = _base_datos_usuario()

DATOS = BASE_USUARIO / "datos"
SALIDAS = BASE_USUARIO / "salidas"
COPIAS = DATOS / "copias"          # respaldos automáticos previos a una actualización
IMAGENES = DATOS / "imagenes_perfiles"  # dibujos de sección de cada perfil

RUTA_DB = DATOS / "cotizador.db"
RUTA_LICENCIA = DATOS / "licencia.lic"
RUTA_AJUSTES = DATOS / "ajustes.json"
RUTA_VERSION = RECURSOS / "VERSION"

# Recursos que viajan con el código
TEMAS = RECURSOS / "ui" / "temas"


def asegurar_carpetas() -> None:
    """Crea las carpetas de datos de usuario si no existen."""
    for carpeta in (DATOS, SALIDAS, COPIAS, IMAGENES):
        carpeta.mkdir(parents=True, exist_ok=True)


def version() -> str:
    try:
        return RUTA_VERSION.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"


def migrar_datos_locales() -> bool:
    """Mueve ``<proyecto>/datos`` a la carpeta de usuario si se activó ``instalado.flag``.

    Devuelve ``True`` si migró algo. Nunca pisa datos ya existentes en el destino.
    """
    origen = RAIZ / "datos"
    if origen == DATOS or not origen.exists():
        return False

    import shutil

    asegurar_carpetas()
    movidos = False
    for archivo in origen.iterdir():
        destino = DATOS / archivo.name
        if destino.exists():
            continue
        shutil.move(str(archivo), str(destino))
        movidos = True
    return movidos


def espacio_libre_mb() -> float:
    try:
        import shutil
        return shutil.disk_usage(BASE_USUARIO).free / (1024 * 1024)
    except OSError:
        return 0.0
