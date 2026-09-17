"""
Generador del par de claves Ed25519 para licenciamiento. **SE EJECUTA UNA SOLA VEZ.**

Produce:
    core/clave_publica.py                    -> viaja DENTRO del .exe del cliente
    ~/.cotizador_emisor/clave_privada.json   -> QUEDA SÓLO EN TU PC

La privada se guarda **fuera de la carpeta del proyecto** a propósito: así no se
cuela en el paquete de PyInstaller, ni en un zip, ni en un repositorio.

Uso:
    python -m tools.generar_claves

ATENCIÓN: si regenerás las claves, todas las licencias emitidas antes dejan de
ser válidas y hay que reemitirlas.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import ed25519  # noqa: E402

RUTA_PUBLICA = Path(__file__).resolve().parent.parent / "core" / "clave_publica.py"
CARPETA_EMISOR = Path.home() / ".cotizador_emisor"
RUTA_PRIVADA = CARPETA_EMISOR / "clave_privada.json"

PLANTILLA = '''"""
Clave PÚBLICA de licenciamiento — generada por tools/generar_claves.py

Se distribuye junto con la aplicación. Sólo sirve para VERIFICAR licencias; con
ella no se pueden emitir. La privada correspondiente está en la PC del emisor,
en ~/.cotizador_emisor/clave_privada.json

NO editar a mano.
"""

ALGORITMO = "Ed25519"

CLAVE_PUBLICA = "{publica}"
'''


def cargar_privada() -> bytes:
    """Lee la clave privada del emisor. La usan keygen y las pruebas."""
    if not RUTA_PRIVADA.exists():
        raise SystemExit(
            f"No se encontró la clave privada.\n\nEsperada en: {RUTA_PRIVADA}\n\n"
            "Generala una única vez con:\n    python -m tools.generar_claves")
    datos = json.loads(RUTA_PRIVADA.read_text(encoding="utf-8"))
    return bytes.fromhex(datos["privada"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera el par de claves de licenciamiento")
    parser.add_argument("--forzar", action="store_true",
                        help="Reemplaza el par existente (invalida las licencias emitidas)")
    args = parser.parse_args()

    if RUTA_PRIVADA.exists() and not args.forzar:
        print(f"Ya existe una clave privada en:\n  {RUTA_PRIVADA}\n")
        print("No se generó nada. Usá --forzar sólo si querés reemplazarla,")
        print("teniendo en cuenta que TODAS las licencias emitidas dejarán de funcionar.")
        return 1

    print("Generando par de claves Ed25519…")
    secreto = ed25519.generar_secreto()
    publica = ed25519.clave_publica(secreto)

    # Verificación de extremo a extremo antes de dar el par por bueno
    mensaje = b"prueba de integridad del par de claves"
    firma = ed25519.firmar(secreto, mensaje)
    if not ed25519.verificar(publica, mensaje, firma):
        print("ERROR: el par generado no verifica. No se guardó nada.")
        return 1
    if ed25519.verificar(publica, b"otro mensaje", firma):
        print("ERROR: la verificación acepta mensajes falsos. No se guardó nada.")
        return 1

    CARPETA_EMISOR.mkdir(parents=True, exist_ok=True)
    RUTA_PRIVADA.write_text(json.dumps({
        "algoritmo": "Ed25519",
        "privada": secreto.hex(),
        "publica": publica.hex(),
    }, indent=2), encoding="utf-8")
    try:
        RUTA_PRIVADA.chmod(0o600)
    except OSError:
        pass

    RUTA_PUBLICA.write_text(PLANTILLA.format(publica=publica.hex()), encoding="utf-8")

    print("\nListo. Verificación de firma correcta.\n")
    print(f"  Clave PÚBLICA (se distribuye):  {RUTA_PUBLICA}")
    print(f"  Clave PRIVADA (SÓLO TU PC):     {RUTA_PRIVADA}")
    print("\n  GUARDÁ UNA COPIA DE SEGURIDAD DE LA CLAVE PRIVADA.")
    print("  Si la perdés, no vas a poder emitir ni renovar licencias.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
