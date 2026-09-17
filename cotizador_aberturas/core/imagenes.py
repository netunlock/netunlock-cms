"""
Dibujos de sección de los perfiles.

Las imágenes **no** se guardan dentro de la base: se copian a
``datos/imagenes_perfiles`` y en la tabla ``perfiles`` queda sólo el nombre del
archivo. Así la base no se infla, el respaldo sigue siendo un archivo chico y el
dibujo sobrevive aunque el usuario borre o mueva el original que eligió.

En la base se guarda el nombre relativo. Se acepta leer una ruta absoluta (bases
tocadas a mano), pero al importar siempre se copia adentro.
"""

from __future__ import annotations

import re
import shutil
import unicodedata
from pathlib import Path

from . import rutas

#: Formatos que Pillow lee y que tienen sentido para un dibujo de catálogo.
EXTENSIONES = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")

_INVALIDOS = re.compile(r"[^A-Za-z0-9._-]+")


def _nombre_seguro(linea: str, codigo: str, extension: str) -> str:
    """``Módena`` + ``6200`` -> ``Modena_6200.png``.

    Se quitan los acentos antes de filtrar para que 'Módena' no termine como
    'M_dena': el nombre del archivo lo ve el usuario en la carpeta de datos.
    """
    crudo = unicodedata.normalize("NFKD", f"{linea}_{codigo}")
    crudo = "".join(c for c in crudo if unicodedata.category(c) != "Mn")
    base = _INVALIDOS.sub("_", crudo).strip("_") or "perfil"
    return f"{base}{extension.lower()}"


def ruta_de(imagen: str | None) -> Path | None:
    """Ruta absoluta de la imagen guardada, o ``None`` si no existe."""
    if not imagen:
        return None
    ruta = Path(imagen)
    if not ruta.is_absolute():
        ruta = rutas.IMAGENES / ruta
    return ruta if ruta.is_file() else None


def guardar(origen: str | Path, linea_nombre: str, perfil_codigo: str) -> str:
    """Copia ``origen`` a la carpeta de imágenes y devuelve el nombre a guardar.

    Levanta ``ValueError`` si el archivo no existe o el formato no sirve.
    """
    origen = Path(origen)
    if not origen.is_file():
        raise ValueError(f"No se encuentra el archivo:\n{origen}")
    if origen.suffix.lower() not in EXTENSIONES:
        raise ValueError(
            f"Formato no admitido ({origen.suffix}). "
            f"Usá alguno de estos: {', '.join(EXTENSIONES)}"
        )

    rutas.asegurar_carpetas()
    destino = rutas.IMAGENES / _nombre_seguro(linea_nombre, perfil_codigo, origen.suffix)

    # Si el usuario elige la misma imagen que ya estaba, copiar sobre sí misma
    # truncaría el archivo.
    if destino.resolve() != origen.resolve():
        shutil.copyfile(origen, destino)
    return destino.name


def borrar(imagen: str | None) -> None:
    """Elimina el archivo copiado. Nunca toca rutas fuera de la carpeta de datos."""
    ruta = ruta_de(imagen)
    if ruta and ruta.parent.resolve() == rutas.IMAGENES.resolve():
        ruta.unlink(missing_ok=True)
