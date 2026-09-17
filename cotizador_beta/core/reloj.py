"""
Integridad temporal — evita extender una suscripción atrasando el reloj de Windows.

Cómo decide qué hora usar
-------------------------
1. **Anclas locales.** Se guarda la última hora de uso en
   ``%APPDATA%/CotizadorAberturas/last_run.dat`` y se toman además las marcas de
   modificación de la base de datos y del archivo de licencia. La hora de
   referencia es la mayor de las tres. Si el reloj del sistema quedó por debajo
   de esa referencia, hubo retroceso.

2. **Hora de red.** Se pide el header ``Date`` a un servidor público (HEAD, 2 s
   de timeout). Si difiere del sistema en más de una hora, **manda la de red**
   para todos los cálculos de vencimiento.

3. Si no hay internet, se sigue con la hora del sistema validada contra las
   anclas locales. Bloquear la red no habilita nada: sólo se pierde el chequeo
   externo, las anclas locales siguen activos.

Alcance honesto
---------------
Las anclas locales están firmadas con una clave derivada del HWID, lo que impide
editarlas con el Bloc de notas, pero esa clave está dentro del programa: alguien
con conocimiento puede recalcular la firma. Lo que esto detiene es el fraude
realista —"atraso la fecha de Windows y sigo usando el sistema"— no a un
atacante decidido a modificar el binario.

Borrar ``last_run.dat`` tampoco sirve: quedan como anclas la fecha de la base de
datos (que se toca en cada presupuesto) y la del propio archivo de licencia.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

NOMBRE_APP = "CotizadorAberturas"
ARCHIVO_MARCA = "last_run.dat"

#: Margen ante cambios legítimos de huso horario, horario de verano o un ajuste
#: manual razonable. Por debajo de esto no se considera manipulación.
TOLERANCIA_RETROCESO = timedelta(hours=12)

#: Diferencia a partir de la cual se le cree a la red y no al sistema.
UMBRAL_HORA_RED = timedelta(hours=1)

TIMEOUT_RED = 2  # segundos

SERVIDORES = ("https://www.google.com", "https://www.cloudflare.com")

# Sal para firmar la marca local. No es un secreto criptográfico: sube el costo
# de editar el archivo a mano, nada más.
_SAL = b"cotizador-aberturas::marca-temporal::v2"


class RelojManipulado(Exception):
    """El reloj del sistema está por detrás de la última actividad registrada."""


@dataclass
class Tiempo:
    ahora: datetime          # UTC, la hora que hay que usar para vencimientos
    fuente: str              # 'red' o 'sistema'
    aviso: str = ""          # texto para la barra de estado, si corresponde

    @property
    def fecha(self):
        return self.ahora.date()


# ---------------------------------------------------------------------------
# Ubicación
# ---------------------------------------------------------------------------

def carpeta_datos() -> Path:
    """``%APPDATA%/CotizadorAberturas`` (o equivalente en Linux/macOS)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    carpeta = base / NOMBRE_APP
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def ruta_marca() -> Path:
    return carpeta_datos() / ARCHIVO_MARCA


# ---------------------------------------------------------------------------
# Marca local firmada
# ---------------------------------------------------------------------------

def _clave_marca() -> bytes:
    from .hardware import obtener_hwid
    return hashlib.sha256(_SAL + obtener_hwid().encode("utf-8")).digest()


def _firmar(carga: str) -> str:
    return hmac.new(_clave_marca(), carga.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def _leer_marca() -> datetime | None:
    try:
        datos = json.loads(ruta_marca().read_text(encoding="utf-8"))
        carga = datos["ts"]
        if not hmac.compare_digest(datos.get("tag", ""), _firmar(carga)):
            # Editada a mano: se descarta el valor, pero no se bloquea la app.
            # Las otras anclas (base de datos, licencia) siguen sirviendo.
            return None
        return datetime.fromisoformat(carga)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _escribir_marca(momento: datetime) -> None:
    carga = momento.astimezone(timezone.utc).isoformat()
    try:
        ruta_marca().write_text(
            json.dumps({"ts": carga, "tag": _firmar(carga)}), encoding="utf-8")
    except OSError:
        pass  # sin permiso de escritura: se sigue con las otras anclas


def _mtime(ruta: Path | None) -> datetime | None:
    if not ruta:
        return None
    try:
        return datetime.fromtimestamp(Path(ruta).stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Hora de red
# ---------------------------------------------------------------------------

def hora_de_red() -> datetime | None:
    """Lee el header ``Date`` de un servidor público. ``None`` si no hay internet.

    Usa ``requests`` si está instalado; si no, ``urllib`` de la biblioteca
    estándar. Se evita exigir ``requests`` para no sumarle ~3 MB y los líos de
    empaquetado de certificados al ejecutable.
    """
    for url in SERVIDORES:
        cabecera = _head_requests(url) or _head_urllib(url)
        if not cabecera:
            continue
        try:
            momento = parsedate_to_datetime(cabecera)
            if momento.tzinfo is None:
                momento = momento.replace(tzinfo=timezone.utc)
            return momento.astimezone(timezone.utc)
        except (TypeError, ValueError):
            continue
    return None


def _head_requests(url: str) -> str | None:
    try:
        import requests
    except ImportError:
        return None
    try:
        respuesta = requests.head(url, timeout=TIMEOUT_RED,
                                  allow_redirects=True)
        return respuesta.headers.get("Date")
    except Exception:
        return None


def _head_urllib(url: str) -> str | None:
    import urllib.request
    try:
        peticion = urllib.request.Request(url, method="HEAD",
                                          headers={"User-Agent": "CotizadorAberturas"})
        with urllib.request.urlopen(peticion, timeout=TIMEOUT_RED) as respuesta:
            return respuesta.headers.get("Date")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Verificación
# ---------------------------------------------------------------------------

def verificar_integridad_reloj(ruta_db: Path | str | None = None,
                               ruta_licencia: Path | str | None = None,
                               consultar_red: bool = True) -> Tiempo:
    """Devuelve la hora confiable en UTC. Lanza :class:`RelojManipulado` si retrocedió.

    Actualiza la marca local antes de volver, de modo que cada ejecución sube el
    piso temporal.
    """
    sistema = datetime.now(timezone.utc)

    anclas = [a for a in (_leer_marca(), _mtime(ruta_db), _mtime(ruta_licencia)) if a]
    referencia = max(anclas) if anclas else None

    aviso = ""
    ahora, fuente = sistema, "sistema"

    if consultar_red:
        red = hora_de_red()
        if red is not None:
            desvio = abs(red - sistema)
            if desvio > UMBRAL_HORA_RED:
                ahora, fuente = red, "red"
                horas = desvio.total_seconds() / 3600
                aviso = (f"La fecha del equipo difiere {horas:.0f} h de la hora real; "
                         "se usa la hora de internet para la licencia.")

    if referencia is not None and ahora < referencia - TOLERANCIA_RETROCESO:
        atraso = referencia - ahora
        dias = atraso.days
        detalle = f"{dias} día(s)" if dias else f"{atraso.seconds // 3600} hora(s)"
        raise RelojManipulado(
            "La fecha y hora del equipo están atrasadas respecto del último uso "
            f"registrado ({detalle}).\n\n"
            f"Última actividad: {referencia.astimezone():%d/%m/%Y %H:%M}\n"
            f"Fecha del equipo: {ahora.astimezone():%d/%m/%Y %H:%M}\n\n"
            "Corregí la fecha del sistema para continuar.")

    # El piso temporal sólo sube
    _escribir_marca(max([ahora] + anclas) if anclas else ahora)
    return Tiempo(ahora=ahora, fuente=fuente, aviso=aviso)


def ahora_confiable(ruta_db=None, ruta_licencia=None) -> datetime:
    """Variante que no lanza: ante manipulación devuelve la referencia local.

    Útil donde interesa no romper el flujo, por ejemplo al fechar un presupuesto.
    """
    try:
        return verificar_integridad_reloj(ruta_db, ruta_licencia).ahora
    except RelojManipulado:
        anclas = [a for a in (_leer_marca(), _mtime(ruta_db), _mtime(ruta_licencia)) if a]
        return max(anclas) if anclas else datetime.now(timezone.utc)
