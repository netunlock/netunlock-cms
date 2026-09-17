"""
Firma digital Ed25519 — implementación de referencia del RFC 8032, sin dependencias.

Por qué está acá
----------------
El licenciamiento necesita firma **asimétrica**: la aplicación que se entrega al
cliente lleva sólo la clave pública (sirve para verificar, no para firmar), y la
clave privada que emite licencias no sale nunca de la PC del proveedor. Con eso,
aunque alguien desempaquete el .exe y lea todo el código, no puede fabricar
licencias válidas.

Ed25519 en lugar de RSA porque la firma ocupa **64 bytes** en vez de 256: eso es
lo que permite que una licencia entre en una clave de texto que se pega por
WhatsApp, en lugar de tener que mandar un archivo.

Esta implementación es la del apéndice del RFC 8032 (coordenadas homogéneas
extendidas). Está verificada contra los vectores de prueba oficiales del propio
RFC — ver ``tools/prueba_licencia.py``.

Nota de alcance: ``point_mul`` no es de tiempo constante. Para **verificar**
firmas con una clave pública eso es irrelevante (no hay secreto involucrado).
La firma sólo corre en la máquina del emisor, sobre su propia clave.
"""

from __future__ import annotations

import hashlib
import secrets

# --- Parámetros de la curva (RFC 8032 §5.1) ---------------------------------
P = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493

_D = -121665 * pow(121666, P - 2, P) % P
_MODP_SQRT_M1 = pow(2, (P - 1) // 4, P)

TAM_CLAVE = 32
TAM_FIRMA = 64


def _sha512(datos: bytes) -> bytes:
    return hashlib.sha512(datos).digest()


def _sha512_modq(datos: bytes) -> int:
    return int.from_bytes(_sha512(datos), "little") % L


# --- Aritmética de puntos en coordenadas (X, Y, Z, T) -----------------------

def _point_add(p, q):
    a = (p[1] - p[0]) * (q[1] - q[0]) % P
    b = (p[1] + p[0]) * (q[1] + q[0]) % P
    c = 2 * p[3] * q[3] * _D % P
    d = 2 * p[2] * q[2] % P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % P, g * h % P, f * g % P, e * h % P)


def _point_mul(escalar: int, punto):
    resultado = (0, 1, 1, 0)  # elemento neutro
    while escalar > 0:
        if escalar & 1:
            resultado = _point_add(resultado, punto)
        punto = _point_add(punto, punto)
        escalar >>= 1
    return resultado


def _point_equal(p, q) -> bool:
    if (p[0] * q[2] - q[0] * p[2]) % P != 0:
        return False
    return (p[1] * q[2] - q[1] * p[2]) % P == 0


# Punto base B (RFC 8032 §5.1)
_G_Y = 4 * pow(5, P - 2, P) % P


def _recuperar_x(y: int, signo: int):
    if y >= P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, P - 2, P) % P
    if x2 == 0:
        return None if signo else 0

    x = pow(x2, (P + 3) // 8, P)
    if (x * x - x2) % P != 0:
        x = x * _MODP_SQRT_M1 % P
    if (x * x - x2) % P != 0:
        return None

    if x & 1 != signo:
        x = P - x
    return x


_G = (_recuperar_x(_G_Y, 0), _G_Y, 1, _recuperar_x(_G_Y, 0) * _G_Y % P)


def _comprimir(punto) -> bytes:
    zinv = pow(punto[2], P - 2, P)
    x = punto[0] * zinv % P
    y = punto[1] * zinv % P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _descomprimir(datos: bytes):
    if len(datos) != 32:
        return None
    y = int.from_bytes(datos, "little")
    signo = y >> 255
    y &= (1 << 255) - 1
    x = _recuperar_x(y, signo)
    if x is None:
        return None
    return (x, y, 1, x * y % P)


# --- API --------------------------------------------------------------------

def _expandir_secreto(secreto: bytes):
    h = _sha512(secreto[:32])
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8      # limpia los 3 bits bajos
    a |= 1 << 254            # fija el bit alto
    return a, h[32:]


def generar_secreto() -> bytes:
    """Clave privada de 32 bytes desde el generador criptográfico del sistema."""
    return secrets.token_bytes(TAM_CLAVE)


def clave_publica(secreto: bytes) -> bytes:
    """Deriva la clave pública (32 bytes) a partir de la privada."""
    a, _ = _expandir_secreto(secreto)
    return _comprimir(_point_mul(a, _G))


def firmar(secreto: bytes, mensaje: bytes) -> bytes:
    """Firma de 64 bytes. Sólo corre en la PC del emisor."""
    a, prefijo = _expandir_secreto(secreto)
    publica = _comprimir(_point_mul(a, _G))
    r = _sha512_modq(prefijo + mensaje)
    big_r = _comprimir(_point_mul(r, _G))
    h = _sha512_modq(big_r + publica + mensaje)
    s = (r + h * a) % L
    return big_r + int.to_bytes(s, 32, "little")


def verificar(publica: bytes, mensaje: bytes, firma: bytes) -> bool:
    """Verifica una firma. Es lo único que corre en la PC del cliente."""
    if len(publica) != TAM_CLAVE or len(firma) != TAM_FIRMA:
        return False

    punto_a = _descomprimir(publica)
    if punto_a is None:
        return False

    big_r_bytes = firma[:32]
    punto_r = _descomprimir(big_r_bytes)
    if punto_r is None:
        return False

    s = int.from_bytes(firma[32:], "little")
    if s >= L:  # rechaza firmas maleables
        return False

    h = _sha512_modq(big_r_bytes + publica + mensaje)
    return _point_equal(_point_mul(s, _G), _point_add(punto_r, _point_mul(h, punto_a)))
