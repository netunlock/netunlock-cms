"""
Licenciamiento por suscripción, atado al equipo (HWID) y firmado con Ed25519.

Modelo
------
Una licencia autoriza **un equipo** hasta **una fecha**. Para renovar la
suscripción se emite una clave nueva con la fecha corrida; no hace falta
desinstalar ni tocar nada.

Firma asimétrica
----------------
La aplicación lleva sólo la **clave pública** (``core/clave_publica.py``), que
sirve para verificar y no para firmar. La **clave privada** que emite licencias
vive únicamente en la PC del proveedor, fuera de la carpeta del proyecto.

Es la diferencia entre RSA/Ed25519 y HMAC: con HMAC la misma clave valida y
firma, así que tendría que viajar dentro del .exe. Como un ejecutable de
PyInstaller se desempaqueta en minutos, cualquiera podría extraerla y fabricar
un generador de claves. Con firma asimétrica eso es imposible sin la privada.

Límite honesto: ningún esquema impide que alguien modifique el programa para
saltear la verificación. Lo que esto detiene es la **fabricación y reventa de
licencias**, que es el riesgo real del negocio.

Dos formatos, el mismo contenido
--------------------------------
* **Clave corta** — ``COTIZ-XXXX…`` de una línea, para pegar por WhatsApp.
  Lleva vencimiento + plan + firma; el HWID va dentro de lo firmado.
* **Archivo .lic** — JSON con los datos completos (razón social, fecha de
  emisión, notas). Útil para respaldo y auditoría.

Ambos se instalan desde la misma ventana de activación.
"""

from __future__ import annotations

import base64
import json
import platform
import re
import shutil
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import ed25519, reloj
from .hardware import diagnostico, es_fuerte, fuentes, obtener_hwid

#: A partir de acá la aplicación empieza a avisar que hay que renovar.
MARGEN_AVISO_DIAS = 7

#: Días de gracia después del vencimiento: la app sigue abriendo pero insiste.
DIAS_GRACIA = 0

PREFIJO_CLAVE = "COTIZ-"
VERSION_FORMATO = 2
_EPOCA = date(2020, 1, 1)

PLANES = {0: "completa", 1: "prueba", 2: "básica"}
_PLANES_INV = {v: k for k, v in PLANES.items()}

_ALFABETO_B32 = re.compile(r"[^A-Z2-7]")


# ---------------------------------------------------------------------------
# Ubicación del archivo de licencia
# ---------------------------------------------------------------------------

def ruta_licencia() -> Path:
    return reloj.carpeta_datos() / "licencia.lic"


def _migrar_licencia_antigua() -> None:
    """Traslada la licencia de ``datos/`` a ``%APPDATA%`` la primera vez."""
    nueva = ruta_licencia()
    if nueva.exists():
        return
    try:
        from . import rutas
        vieja = rutas.DATOS / "licencia.lic"
        if not vieja.exists():
            return
        contenido = vieja.read_text(encoding="utf-8")
        # Sólo se traslada si el formato es el actual; una licencia RSA vieja se
        # deja donde está para no arrastrar un archivo que igual va a fallar.
        paquete = json.loads(contenido)
        if len(bytes.fromhex(paquete.get("firma", ""))) == ed25519.TAM_FIRMA:
            shutil.copy2(vieja, nueva)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------

@dataclass
class Licencia:
    cliente: str = ""
    hwid: str = ""
    emitida: str = ""
    vence: str = ""          # '' = perpetua
    plan: str = "completa"
    notas: str = ""

    def como_dict(self) -> dict:
        return {"cliente": self.cliente, "hwid": self.hwid, "emitida": self.emitida,
                "vence": self.vence, "plan": self.plan, "notas": self.notas}

    @property
    def perpetua(self) -> bool:
        return not self.vence

    @property
    def fecha_vencimiento(self) -> date | None:
        if self.perpetua:
            return None
        try:
            return date.fromisoformat(self.vence)
        except ValueError:
            return None

    def dias_restantes(self, hoy: date | None = None) -> int | None:
        vto = self.fecha_vencimiento
        if vto is None:
            return None
        return (vto - (hoy or date.today())).days


@dataclass
class Estado:
    valida: bool = False
    motivo: str = ""
    licencia: Licencia | None = None
    hwid_actual: str = field(default_factory=obtener_hwid)
    dias_restantes: int | None = None
    fuente_hora: str = "sistema"
    aviso_hora: str = ""
    reloj_manipulado: bool = False
    #: La habilita la prueba gratuita, no una clave comprada.
    es_prueba: bool = False
    #: Ya usó los días de prueba y no tiene clave.
    prueba_vencida: bool = False

    @property
    def por_vencer(self) -> bool:
        return (self.valida and self.dias_restantes is not None
                and 0 <= self.dias_restantes <= MARGEN_AVISO_DIAS)

    @property
    def aviso(self) -> str:
        if not self.por_vencer:
            return ""
        if self.dias_restantes == 0:
            return "La suscripción vence hoy."
        return (f"La suscripción vence en {self.dias_restantes} "
                f"día{'s' if self.dias_restantes != 1 else ''}.")


# ---------------------------------------------------------------------------
# Clave pública
# ---------------------------------------------------------------------------

def _clave_publica() -> bytes | None:
    try:
        from .clave_publica import CLAVE_PUBLICA
        datos = bytes.fromhex(CLAVE_PUBLICA)
        return datos if len(datos) == ed25519.TAM_CLAVE else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Codificación de la clave corta
# ---------------------------------------------------------------------------

def _hwid_bytes(hwid: str) -> bytes:
    return bytes.fromhex(hwid.replace("-", ""))


def _dias_desde_epoca(vence: str) -> int:
    if not vence:
        return 0
    return max(0, (date.fromisoformat(vence) - _EPOCA).days)


def _fecha_desde_dias(dias: int) -> str:
    return "" if dias == 0 else (_EPOCA + timedelta(days=dias)).isoformat()


def _cuerpo(hwid: str, vence: str, plan: str) -> bytes:
    """Los bytes que se firman. El HWID entra acá pero no viaja en la clave."""
    return (bytes([VERSION_FORMATO])
            + _hwid_bytes(hwid)
            + _dias_desde_epoca(vence).to_bytes(2, "big")
            + bytes([_PLANES_INV.get(plan, 0)]))


def _b32(datos: bytes) -> str:
    return base64.b32encode(datos).decode("ascii").rstrip("=")


def _des_b32(texto: str) -> bytes:
    relleno = "=" * (-len(texto) % 8)
    return base64.b32decode(texto + relleno)


def emitir_clave(hwid: str, vence: str, plan: str, secreto: bytes) -> str:
    """Genera la clave corta de una línea. Sólo la usa el emisor.

    Base32 en mayúsculas: sin símbolos ni ambigüedad de mayúsculas/minúsculas,
    que es lo que sobrevive a un copiar y pegar por WhatsApp.
    """
    hwid = hwid.strip().upper()
    firma = ed25519.firmar(secreto, _cuerpo(hwid, vence, plan))
    carga = (bytes([VERSION_FORMATO])
             + _dias_desde_epoca(vence).to_bytes(2, "big")
             + bytes([_PLANES_INV.get(plan, 0)])
             + firma)
    return PREFIJO_CLAVE + _b32(carga)


def _leer_clave(clave: str, hwid_actual: str) -> tuple[Licencia | None, str]:
    texto = _ALFABETO_B32.sub("", clave.strip().upper().replace(PREFIJO_CLAVE, ""))
    if len(texto) < 100:
        return None, "La clave está incompleta. Copiala entera, sin cortar."

    try:
        carga = _des_b32(texto)
    except Exception:
        return None, "La clave tiene caracteres inválidos. Volvé a copiarla."

    if len(carga) != 4 + ed25519.TAM_FIRMA:
        return None, "La clave no tiene el formato esperado."
    if carga[0] != VERSION_FORMATO:
        return None, (f"La clave es de otro formato (versión {carga[0]}). "
                      "Pedile a tu proveedor una clave actualizada.")

    dias = int.from_bytes(carga[1:3], "big")
    plan = PLANES.get(carga[3], "completa")
    firma = carga[4:]
    vence = _fecha_desde_dias(dias)

    publica = _clave_publica()
    if publica is None:
        return None, ("La aplicación no tiene clave pública configurada. "
                      "Ejecutá tools/generar_claves.py antes de distribuir.")

    if not ed25519.verificar(publica, _cuerpo(hwid_actual, vence, plan), firma):
        return None, ("La clave no es válida para este equipo.\n\n"
                      "Verificá que el código de equipo que enviaste sea "
                      f"exactamente:\n{hwid_actual}")

    return Licencia(cliente="", hwid=hwid_actual, emitida="", vence=vence, plan=plan), ""


# ---------------------------------------------------------------------------
# Archivo .lic
# ---------------------------------------------------------------------------

def _canonico(datos: dict) -> bytes:
    return json.dumps(datos, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def emitir(licencia: Licencia, secreto: bytes) -> str:
    """Contenido del archivo .lic firmado. Sólo lo usa el emisor."""
    datos = licencia.como_dict()
    paquete = {
        "datos": datos,
        "firma": ed25519.firmar(secreto, _canonico(datos)).hex(),
        "clave": emitir_clave(licencia.hwid, licencia.vence, licencia.plan, secreto),
    }
    return json.dumps(paquete, indent=2, ensure_ascii=False)


def _leer_archivo(contenido: str, hwid_actual: str) -> tuple[Licencia | None, str]:
    try:
        paquete = json.loads(contenido)
    except ValueError:
        return None, "El archivo de licencia está dañado o no tiene el formato esperado."

    # Un .lic sin firma pero con clave corta: se valida por la clave. Cubre los
    # archivos guardados por versiones anteriores y los que el cliente arme a mano.
    if isinstance(paquete, dict) and "firma" not in paquete and paquete.get("clave"):
        lic, error = _leer_clave(paquete["clave"], hwid_actual)
        if lic is not None and isinstance(paquete.get("datos"), dict):
            lic.cliente = paquete["datos"].get("cliente", "") or ""
            lic.emitida = paquete["datos"].get("emitida", "") or ""
        return lic, error

    try:
        datos = paquete["datos"]
        firma = bytes.fromhex(paquete["firma"])
    except (KeyError, TypeError, ValueError):
        return None, "El archivo de licencia está dañado o no tiene el formato esperado."

    if len(firma) != ed25519.TAM_FIRMA:
        # Licencia emitida por una versión anterior (firma RSA de 256 bytes).
        # Sin este aviso el usuario leería "archivo modificado" y pensaría que
        # su licencia fue adulterada.
        return None, ("Esta licencia es de una versión anterior del sistema y ya "
                      "no es compatible.\n\n"
                      "Pedile a tu proveedor una clave de activación nueva; "
                      "no perdés ningún dato ni presupuesto.")

    publica = _clave_publica()
    if publica is None:
        return None, "La aplicación no tiene clave pública configurada."

    if not ed25519.verificar(publica, _canonico(datos), firma):
        return None, ("La firma de la licencia no es válida: el archivo fue "
                      "modificado o no lo emitió tu proveedor.")

    lic = Licencia(**{k: datos.get(k, "") or "" for k in
                      ("cliente", "hwid", "emitida", "vence", "plan", "notas")})
    if lic.hwid.upper() != hwid_actual.upper():
        return None, ("Esta licencia fue emitida para otro equipo.\n\n"
                      f"Licencia:    {lic.hwid}\nEste equipo: {hwid_actual}")
    return lic, ""


# ---------------------------------------------------------------------------
# Validación
# ---------------------------------------------------------------------------

def validar_texto(contenido: str, hwid_actual: str | None = None,
                  hoy: date | None = None) -> Estado:
    """Valida una clave corta **o** el contenido de un archivo .lic."""
    hwid_actual = (hwid_actual or obtener_hwid()).upper()
    estado = Estado(hwid_actual=hwid_actual)

    contenido = (contenido or "").strip()
    if not contenido:
        estado.motivo = "No ingresaste ninguna clave."
        return estado

    if contenido.lstrip().startswith("{"):
        lic, error = _leer_archivo(contenido, hwid_actual)
    else:
        lic, error = _leer_clave(contenido, hwid_actual)

    if lic is None:
        estado.motivo = error
        return estado

    estado.licencia = lic
    hoy = hoy or date.today()
    estado.dias_restantes = lic.dias_restantes(hoy)

    if estado.dias_restantes is not None and estado.dias_restantes < -DIAS_GRACIA:
        vto = lic.fecha_vencimiento
        estado.motivo = (f"La suscripción venció el {vto.strftime('%d/%m/%Y')} "
                         f"(hace {abs(estado.dias_restantes)} días).\n\n"
                         "Pedile a tu proveedor una clave de renovación.")
        return estado

    estado.valida = True
    estado.motivo = "Licencia válida."
    return estado


def estado_actual(consultar_red: bool = True) -> Estado:
    """Verifica reloj + licencia instalada. Es lo que se llama al arrancar."""
    _migrar_licencia_antigua()

    hwid = obtener_hwid()
    archivo = ruta_licencia()

    # --- integridad temporal
    try:
        from . import rutas
        ruta_db = rutas.RUTA_DB
    except Exception:
        ruta_db = None

    try:
        tiempo = reloj.verificar_integridad_reloj(
            ruta_db=ruta_db, ruta_licencia=archivo, consultar_red=consultar_red)
    except reloj.RelojManipulado as exc:
        return Estado(hwid_actual=hwid, motivo=str(exc), reloj_manipulado=True)

    if not archivo.exists():
        # Sin licencia instalada todavía queda la prueba gratuita. Se consulta
        # DESPUÉS de verificar el reloj, a propósito: así los días de prueba se
        # cuentan contra la hora que el módulo de reloj considera confiable y no
        # contra la del sistema, que es lo que alguien tocaría para estirarla.
        from . import prueba as _prueba
        est = _prueba.estado(tiempo.ahora)
        if est.activa:
            return Estado(valida=True, hwid_actual=hwid,
                          licencia=_prueba.licencia_de_prueba(est),
                          dias_restantes=est.dias_restantes,
                          fuente_hora=tiempo.fuente, aviso_hora=tiempo.aviso,
                          motivo=est.texto, es_prueba=True)
        return Estado(
            hwid_actual=hwid, fuente_hora=tiempo.fuente, aviso_hora=tiempo.aviso,
            prueba_vencida=est.vencida,
            motivo=("Se terminaron los 3 días de prueba gratuita."
                    if est.vencida
                    else "Este equipo todavía no tiene una licencia activa."))

    try:
        contenido = archivo.read_text(encoding="utf-8")
    except OSError as exc:
        return Estado(hwid_actual=hwid,
                      motivo=f"No se pudo leer el archivo de licencia: {exc}")

    estado = validar_texto(contenido, hwid, hoy=tiempo.fecha)
    estado.fuente_hora = tiempo.fuente
    estado.aviso_hora = tiempo.aviso
    return estado


# ---------------------------------------------------------------------------
# Instalación
# ---------------------------------------------------------------------------

def instalar(contenido: str) -> Estado:
    """Valida y guarda. Acepta clave corta o contenido de un .lic."""
    estado = validar_texto(contenido)
    if not estado.valida:
        return estado

    contenido = contenido.strip()
    if not contenido.lstrip().startswith("{"):
        # La clave corta se guarda tal cual, normalizada. Envolverla en un JSON
        # sin firma la volvía irreconocible al releerla.
        contenido = PREFIJO_CLAVE + _ALFABETO_B32.sub(
            "", contenido.upper().replace(PREFIJO_CLAVE, ""))

    try:
        ruta_licencia().write_text(contenido, encoding="utf-8")
    except OSError as exc:
        estado.valida = False
        estado.motivo = f"No se pudo guardar la licencia: {exc}"
    else:
        # El sello de prueba recuerda por unos segundos si hacía falta, para no
        # revisar la licencia una vez por PDF. Recién activada hay que olvidarlo:
        # el próximo documento tiene que salir limpio, sin cerrar el programa.
        try:
            from reports.marca_prueba import limpiar_cache
            limpiar_cache()
        except Exception:
            pass
    return estado


def instalar_desde_archivo(ruta: str | Path) -> Estado:
    try:
        return instalar(Path(ruta).read_text(encoding="utf-8"))
    except OSError as exc:
        return Estado(motivo=f"No se pudo abrir el archivo: {exc}")


# ---------------------------------------------------------------------------
# Compatibilidad con la interfaz existente + soporte
# ---------------------------------------------------------------------------

def huella_hardware() -> str:
    return obtener_hwid()


def fuentes_hardware() -> dict[str, str]:
    return fuentes()


def resumen_para_soporte() -> str:
    """Texto que el cliente le manda al proveedor para pedir o renovar."""
    estado = estado_actual(consultar_red=False)
    lineas = ["SOLICITUD DE LICENCIA — Cotizador de Aberturas", ""]
    try:
        from . import rutas
        lineas.append(f"Versión: {rutas.version()}")
    except Exception:
        pass
    lineas += [
        f"Fecha del equipo: {datetime.now():%d/%m/%Y %H:%M}",
        "",
        f"CÓDIGO DE EQUIPO (HWID): {estado.hwid_actual}",
        "",
        diagnostico().split("\n", 1)[1],
    ]
    if estado.licencia and estado.licencia.vence:
        lineas += ["", f"Licencia actual vence: {estado.licencia.vence}"]
    if not estado.valida:
        lineas += ["", f"Estado: {estado.motivo.splitlines()[0]}"]
    return "\n".join(lineas)


def hwid_valido(texto: str) -> bool:
    return bool(re.fullmatch(r"[0-9A-F]{4}(-[0-9A-F]{4}){3}", (texto or "").strip().upper()))


__all__ = [
    "Licencia", "Estado", "MARGEN_AVISO_DIAS", "PREFIJO_CLAVE",
    "estado_actual", "validar_texto", "instalar", "instalar_desde_archivo",
    "emitir", "emitir_clave", "huella_hardware", "fuentes_hardware",
    "resumen_para_soporte", "hwid_valido", "ruta_licencia", "es_fuerte",
]
