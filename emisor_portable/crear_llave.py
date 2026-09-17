# -*- coding: utf-8 -*-
"""
Crea el archivo ``emisor.llave`` cifrando la clave privada con tu contraseña.

Se corre **una sola vez**, en tu PC, donde está la clave privada original.
Después el archivo que sale es el que viaja en el pendrive.

    python crear_llave.py

La clave privada de origen (``~/.cotizador_emisor/clave_privada.json``) **no se
toca ni se mueve**: sigue estando donde estaba. Este script sólo hace una copia
cifrada. Eso importa: si el pendrive se pierde, con el original en casa podés
seguir emitiendo; si en cambio movieras la clave al pendrive y lo perdés, te
quedás sin poder emitir para siempre y sin poder reemplazarla (cambiar el par de
claves invalida todas las licencias ya entregadas).
"""

from __future__ import annotations

import getpass
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent / "cotizador_beta"))

import caja  # noqa: E402
from core import ed25519  # noqa: E402

ORIGEN = Path.home() / ".cotizador_emisor" / "clave_privada.json"
DESTINO = AQUI / caja.NOMBRE_ARCHIVO


def main() -> int:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    print("=" * 70)
    print("  CREAR LA LLAVE DEL EMISOR PORTABLE")
    print("=" * 70)

    if not ORIGEN.exists():
        print(f"\n  No encuentro la clave privada en:\n    {ORIGEN}")
        print("\n  Sin ella no se puede armar el emisor portable.")
        return 1

    datos = json.loads(ORIGEN.read_text(encoding="utf-8"))
    privada = bytes.fromhex(datos["privada"])
    publica = ed25519.clave_publica(privada)

    if publica.hex() != datos.get("publica", publica.hex()):
        print("\n  La clave pública guardada no coincide con la privada.")
        print("  El archivo de origen está dañado; no sigo.")
        return 1

    print(f"\n  Clave privada encontrada en {ORIGEN}")
    print(f"  Clave pública: {publica.hex()[:32]}…")

    segundos = caja.costo_estimado()
    print(f"\n  Cada intento de contraseña va a costar {segundos:.1f} s en esta PC.")
    print("  Eso es a propósito: encarece probar contraseñas de a millones.")

    if DESTINO.exists():
        print(f"\n  Ya existe {DESTINO.name}.")
        if input("  ¿Lo reemplazo? (s/N): ").strip().lower() != "s":
            print("  No se hizo nada.")
            return 1

    print()
    contrasena = getpass.getpass("  Contraseña del emisor: ")
    if not contrasena:
        print("  Contraseña vacía. No se hizo nada.")
        return 1
    if getpass.getpass("  Repetila: ") != contrasena:
        print("\n  No coinciden. No se hizo nada.")
        return 1

    caja.crear(DESTINO, privada, publica, contrasena,
               nota="Emisor portable del Cotizador de Aberturas")

    # Control: se vuelve a abrir con la misma contraseña, para no descubrir
    # recién en el pendrive que el archivo no sirve.
    prueba = caja.abrir(DESTINO, contrasena)
    if prueba.privada != privada:
        print("\n  FALLA: la llave no se pudo volver a abrir. Revisá el archivo.")
        return 1

    print(f"\n  Listo:  {DESTINO}")
    print(f"          {DESTINO.stat().st_size} bytes")
    print("\n  Comprobado: se abre con esa contraseña y devuelve la clave correcta.")
    print("\n  La clave privada original NO se movió: sigue en")
    print(f"    {ORIGEN}")
    print("  Guardá también un respaldo de ese archivo en otro lado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
