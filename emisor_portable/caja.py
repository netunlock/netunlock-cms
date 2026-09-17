# -*- coding: utf-8 -*-
"""
Caja fuerte de la clave privada de licenciamiento.

Por qué esto y no una pantalla de contraseña
---------------------------------------------
Un pendrive se pierde. Si la clave privada viajara en claro y el programa sólo
preguntara una contraseña antes de mostrar el menú, cualquiera que encuentre el
pendrive abre el archivo con el Bloc de notas y se lleva la clave: la pantalla
de contraseña no protege nada, sólo tapa el botón.

Acá la contraseña **es** la llave: de ella se deriva la clave con la que está
cifrada la privada. Sin la contraseña correcta el archivo es ruido, no hay nada
que saltear.

Cómo está armado
----------------
    scrypt(contraseña, sal)  ->  32 bytes  ->  clave AES-256
    AES-256-GCM(clave, nonce, privada)     ->  cifrado + etiqueta

* **scrypt** en vez de un hash simple porque está diseñado para ser lento y
  comer memoria: encarece a propósito el probar contraseñas de a millones. Con
  los parámetros de acá cada intento cuesta ~1 segundo y 128 MB de RAM, así que
  una máquina que probaría mil millones de claves por segundo pasa a probar una.
* **AES-GCM** porque además de cifrar autentica: si la contraseña está mal, o si
  alguien tocó un byte del archivo, el descifrado **falla** en vez de devolver
  basura que después se usaría para firmar.

La clave pública se guarda en claro al lado —es pública, no hay nada que
esconder— y sirve de control: al abrir la caja se deriva la pública desde la
privada descifrada y se compara. Si no coincide, el archivo está corrupto.

Lo que esto NO resuelve
-----------------------
Si alguien consigue el pendrive **y** la contraseña, puede emitir licencias del
programa para siempre, y no hay forma de revocarlas sin invalidar también las
que ya emitiste. La caja compra tiempo contra un pendrive perdido; no reemplaza
tener el respaldo de la clave en casa.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

#: Parámetros de scrypt. n=2^17 con r=8 pide unos 128 MB y tarda cerca de un
#: segundo: molesto de más para quien prueba contraseñas, imperceptible para
#: quien sabe la suya. Quedan escritos en el archivo para poder subirlos más
#: adelante sin romper las cajas ya creadas.
SCRYPT_N = 1 << 17
SCRYPT_R = 8
SCRYPT_P = 1

#: scrypt necesita permiso explícito para usar tanta memoria.
MAXMEM = 256 * 1024 * 1024

FORMATO = 1
NOMBRE_ARCHIVO = "emisor.llave"


class CajaError(Exception):
    """Algo impide abrir la caja: contraseña incorrecta o archivo dañado."""


@dataclass
class Caja:
    """La clave privada ya descifrada, lista para firmar."""

    privada: bytes
    publica: bytes
    emitida: str = ""
    nota: str = ""


def _derivar(contrasena: str, sal: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(contrasena.encode("utf-8"), salt=sal,
                          n=n, r=r, p=p, dklen=32, maxmem=MAXMEM)


def crear(ruta: Path, privada: bytes, publica: bytes, contrasena: str,
          nota: str = "") -> Path:
    """Cifra la clave privada con la contraseña y la guarda."""
    if len(privada) != 32:
        raise CajaError(f"La clave privada tiene {len(privada)} bytes; se esperaban 32.")
    if not contrasena:
        raise CajaError("Hace falta una contraseña.")

    sal = os.urandom(16)
    nonce = os.urandom(12)
    clave = _derivar(contrasena, sal, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    # La pública va como datos asociados: queda autenticada por la etiqueta de
    # GCM, así que nadie puede cambiarla sin que el descifrado falle.
    cifrado = AESGCM(clave).encrypt(nonce, privada, publica)

    from datetime import date
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps({
        "formato": FORMATO,
        "kdf": "scrypt", "n": SCRYPT_N, "r": SCRYPT_R, "p": SCRYPT_P,
        "cifrado": "AES-256-GCM",
        "sal": sal.hex(),
        "nonce": nonce.hex(),
        "secreto": cifrado.hex(),
        "publica": publica.hex(),
        "emitida": date.today().isoformat(),
        "nota": nota,
    }, indent=2), encoding="utf-8")
    return ruta


def abrir(ruta: Path, contrasena: str) -> Caja:
    """Descifra la caja. Levanta ``CajaError`` si la contraseña no es la correcta."""
    if not ruta.exists():
        raise CajaError(f"No encuentro el archivo de la llave:\n{ruta}")
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CajaError(f"El archivo de la llave está dañado: {exc}") from exc

    if datos.get("formato") != FORMATO:
        raise CajaError(f"Formato de llave desconocido ({datos.get('formato')}).")

    try:
        sal = bytes.fromhex(datos["sal"])
        nonce = bytes.fromhex(datos["nonce"])
        cifrado = bytes.fromhex(datos["secreto"])
        publica = bytes.fromhex(datos["publica"])
    except (KeyError, ValueError) as exc:
        raise CajaError(f"El archivo de la llave está incompleto: {exc}") from exc

    clave = _derivar(contrasena, sal, datos["n"], datos["r"], datos["p"])
    try:
        privada = AESGCM(clave).decrypt(nonce, cifrado, publica)
    except Exception as exc:                      # InvalidTag y cualquier otra
        raise CajaError(
            "Contraseña incorrecta.\n\n"
            "Si estás seguro de la contraseña, el archivo de la llave puede "
            "estar dañado: copiá de nuevo el respaldo al pendrive."
        ) from exc

    # Control final: la pública tiene que salir de la privada descifrada.
    # Se usa el MISMO módulo que el programa, no una copia: una copia que se
    # desincronice emitiría claves que la aplicación rechaza.
    from core import ed25519
    if ed25519.clave_publica(privada) != publica:
        raise CajaError("La llave se descifró pero no es coherente: archivo dañado.")

    return Caja(privada=privada, publica=publica,
                emitida=datos.get("emitida", ""), nota=datos.get("nota", ""))


def costo_estimado() -> float:
    """Cuánto tarda un intento de contraseña, en segundos. Para informarlo."""
    import time
    sal = os.urandom(16)
    t0 = time.perf_counter()
    _derivar("medicion", sal, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    return time.perf_counter() - t0
