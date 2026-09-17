"""
Identificación del equipo (HWID).

Combina varios identificadores físicos y de sistema en un hash estable:

    1. Serial de la placa base   (Win32_BaseBoard)
    2. Serial del disco principal (Win32_DiskDrive, el disco 0)
    3. UUID del sistema           (Win32_ComputerSystemProduct)
    4. MachineGuid de Windows     (registro, escrito al instalar el sistema)

Se usan los que estén disponibles, en ese orden, y se exige un mínimo de dos
fuentes para considerar la huella "fuerte". Si no hay ninguna, cae a la MAC y
al nombre del equipo, y lo informa: una huella débil sigue sirviendo para atar
la licencia, pero es más fácil de replicar.

Detalles que importan en producción
-----------------------------------
* ``wmic`` fue retirado de Windows 11 24H2. Se consulta primero por PowerShell
  (``Get-CimInstance``) y sólo se cae a ``wmic`` si PowerShell no responde.
* Todos los subprocesos se lanzan con ``CREATE_NO_WINDOW``. Sin eso, en un
  ejecutable compilado con ``--noconsole`` cada consulta abre y cierra una
  ventana negra en la cara del usuario.
* Todo tiene timeout: un WMI colgado no puede impedir que la aplicación abra.
"""

from __future__ import annotations

import hashlib
import platform
import re
import subprocess
import sys
import uuid

TIEMPO_LIMITE = 6  # segundos por consulta

# Seriales de relleno que devuelven muchas placas y discos genéricos: si se
# usaran, todos esos equipos compartirían HWID.
_BASURA = {
    "", "none", "null", "n/a", "na", "default string", "to be filled by o.e.m.",
    "to be filled by oem", "not applicable", "system serial number",
    "0", "00000000", "................", "unknown", "default",
    "0000000000000000", "无", "chassis serial number",
}


def _limpio(valor: str) -> str:
    """Normaliza y descarta los seriales de relleno del fabricante."""
    if not valor:
        return ""
    texto = re.sub(r"\s+", " ", str(valor)).strip()
    if texto.lower() in _BASURA:
        return ""
    if len(texto) < 3 or set(texto.strip()) <= {"0", ".", "-", " "}:
        return ""
    return texto


def _ejecutar(comando: list[str]) -> str:
    """Corre un comando sin abrir ventana de consola. Nunca lanza excepción."""
    banderas = 0
    arranque = None
    if sys.platform == "win32":
        banderas = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        arranque = subprocess.STARTUPINFO()
        arranque.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        arranque.wShowWindow = subprocess.SW_HIDE
    try:
        resultado = subprocess.run(
            comando, capture_output=True, text=True, timeout=TIEMPO_LIMITE,
            check=False, creationflags=banderas, startupinfo=arranque,
            encoding="utf-8", errors="ignore")
        return resultado.stdout or ""
    except (OSError, subprocess.SubprocessError, ValueError):
        return ""


def _powershell(consulta: str) -> str:
    salida = _ejecutar([
        "powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-Command", consulta])
    return _limpio(salida.strip().splitlines()[0] if salida.strip() else "")


def _wmic(clase: str, campo: str) -> str:
    """Respaldo para Windows viejos. wmic ya no existe en Windows 11 24H2."""
    salida = _ejecutar(["wmic", clase, "get", campo])
    for linea in salida.splitlines()[1:]:
        valor = _limpio(linea)
        if valor and valor.lower() != campo.lower():
            return valor
    return ""


def _consultar(clase_cim: str, propiedad: str, clase_wmic: str) -> str:
    """Pide una propiedad por PowerShell y, si falla, por wmic."""
    valor = _powershell(
        f"(Get-CimInstance -ClassName {clase_cim} -ErrorAction SilentlyContinue"
        f" | Select-Object -First 1 -ExpandProperty {propiedad})")
    return valor or _wmic(clase_wmic, propiedad)


# --- Fuentes individuales ---------------------------------------------------

def serial_placa_base() -> str:
    if sys.platform != "win32":
        return _leer_dmi("board_serial")
    return _consultar("Win32_BaseBoard", "SerialNumber", "baseboard")


def serial_disco() -> str:
    """Serial del disco 0 (el de arranque), no de cualquier disco conectado.

    Si se tomara "el primer disco que aparezca", conectar un pendrive podría
    cambiar el HWID y romper la licencia del cliente.
    """
    if sys.platform != "win32":
        return _leer_dmi("product_serial")
    valor = _powershell(
        "(Get-CimInstance -ClassName Win32_DiskDrive -ErrorAction SilentlyContinue"
        " | Where-Object { $_.Index -eq 0 }"
        " | Select-Object -First 1 -ExpandProperty SerialNumber)")
    return valor or _wmic("diskdrive", "serialnumber")


def uuid_sistema() -> str:
    if sys.platform != "win32":
        return _leer_dmi("product_uuid")
    return _consultar("Win32_ComputerSystemProduct", "UUID", "csproduct")


def machine_guid() -> str:
    """GUID que Windows escribe al instalarse. Sobrevive cambios de hardware."""
    if sys.platform != "win32":
        return _id_unix()
    try:
        import winreg
        clave = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        valor, _ = winreg.QueryValueEx(clave, "MachineGuid")
        return _limpio(valor)
    except Exception:
        return ""


def _leer_dmi(nombre: str) -> str:
    """Equivalente en Linux (requiere permisos para algunos campos)."""
    from pathlib import Path
    try:
        return _limpio(Path(f"/sys/class/dmi/id/{nombre}").read_text(encoding="utf-8"))
    except OSError:
        return ""


def _id_unix() -> str:
    from pathlib import Path
    for ruta in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            return _limpio(Path(ruta).read_text(encoding="utf-8"))
        except OSError:
            continue
    if sys.platform == "darwin":
        salida = _ejecutar(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"])
        for linea in salida.splitlines():
            if "IOPlatformUUID" in linea:
                return _limpio(linea.split('"')[-2])
    return ""


def _mac() -> str:
    nodo = uuid.getnode()
    # getnode() inventa un número aleatorio con el bit multicast si no encuentra
    # una placa de red real; en ese caso no sirve como identificador estable.
    if (nodo >> 40) % 2:
        return ""
    return f"{nodo:012x}"


# --- Huella -----------------------------------------------------------------

_cache: dict[str, object] = {}


# Una sola invocación de PowerShell para las tres consultas WMI. Arrancar
# PowerShell cuesta ~0,7 s; hacerlo tres veces sumaba más de 2 s al arranque.
_CONSULTA_UNICA = r"""
$ErrorActionPreference = 'SilentlyContinue'
$b = (Get-CimInstance Win32_BaseBoard | Select-Object -First 1).SerialNumber
$d = (Get-CimInstance Win32_DiskDrive | Where-Object { $_.Index -eq 0 } |
      Select-Object -First 1).SerialNumber
$u = (Get-CimInstance Win32_ComputerSystemProduct | Select-Object -First 1).UUID
Write-Output "PLACA=$b"
Write-Output "DISCO=$d"
Write-Output "UUID=$u"
"""


def _consultar_lote() -> dict[str, str]:
    """Las tres propiedades WMI en una sola llamada."""
    salida = _ejecutar([
        "powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-Command", _CONSULTA_UNICA])

    resultado = {"PLACA": "", "DISCO": "", "UUID": ""}
    for linea in salida.splitlines():
        if "=" in linea:
            clave, _, valor = linea.partition("=")
            clave = clave.strip()
            if clave in resultado:
                resultado[clave] = _limpio(valor)
    return resultado


def fuentes(refrescar: bool = False) -> dict[str, str]:
    """Identificadores disponibles en este equipo. Se cachea: consultar WMI es lento."""
    if not refrescar and "fuentes" in _cache:
        return _cache["fuentes"]  # type: ignore[return-value]

    if sys.platform == "win32":
        lote = _consultar_lote()
        # Sólo se cae a wmic para lo que el lote no haya podido resolver
        datos = {
            "Placa base": lote["PLACA"] or _wmic("baseboard", "serialnumber"),
            "Disco principal": lote["DISCO"] or _wmic("diskdrive", "serialnumber"),
            "UUID del sistema": lote["UUID"] or _wmic("csproduct", "uuid"),
            "MachineGuid": machine_guid(),
        }
    else:
        datos = {
            "Placa base": serial_placa_base(),
            "Disco principal": serial_disco(),
            "UUID del sistema": uuid_sistema(),
            "MachineGuid": machine_guid(),
        }

    _cache["fuentes"] = datos
    return datos


def obtener_hwid(refrescar: bool = False) -> str:
    """Identificador del equipo, con formato ``XXXX-XXXX-XXXX-XXXX``."""
    if not refrescar and "hwid" in _cache:
        return _cache["hwid"]  # type: ignore[return-value]

    disponibles = [v for v in fuentes(refrescar).values() if v]
    if not disponibles:
        # Sin ninguna fuente de hardware: se ata a lo que haya, y `es_fuerte()`
        # lo reporta para que el proveedor sepa que esa licencia es más débil.
        disponibles = [x for x in (_mac(), platform.node()) if x] or ["equipo-desconocido"]

    semilla = "|".join(v.lower() for v in disponibles) + "|cotizador-aberturas-v2"
    digest = hashlib.sha256(semilla.encode("utf-8")).hexdigest().upper()
    hwid = "-".join(digest[i:i + 4] for i in range(0, 16, 4))

    _cache["hwid"] = hwid
    return hwid


def es_fuerte() -> bool:
    """``True`` si la huella se apoya en al menos dos identificadores reales."""
    return sum(1 for v in fuentes().values() if v) >= 2


def diagnostico() -> str:
    """Texto para soporte: qué fuentes se detectaron, sin exponer los seriales."""
    lineas = [f"HWID: {obtener_hwid()}",
              f"Equipo: {platform.node()}   ({platform.system()} {platform.release()})",
              "", "Fuentes detectadas:"]
    for nombre, valor in fuentes().items():
        if valor:
            visible = valor[:4] + "…" + valor[-2:] if len(valor) > 8 else "presente"
            lineas.append(f"  · {nombre}: {visible}")
        else:
            lineas.append(f"  · {nombre}: no disponible")
    if not es_fuerte():
        lineas += ["", "AVISO: huella débil (menos de dos identificadores de hardware)."]
    return "\n".join(lineas)
