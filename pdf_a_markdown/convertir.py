# -*- coding: utf-8 -*-
r"""
convertir.py — Conversor de PDF a Markdown usando MarkItDown (Microsoft).

Modos de uso
------------
1) Sin argumentos: convierte todos los PDF que haya en la carpeta 'entrada'
   y deja los .md en la carpeta 'salida'.

       python convertir.py

2) Con argumentos: convierte los archivos o carpetas que le pases.
   Sirve para arrastrar y soltar PDFs sobre el .bat.

       python convertir.py "C:\ruta\documento.pdf" "C:\otra\carpeta"

Opciones
--------
    --forzar          Reconvierte aunque el .md ya exista (por defecto se saltea).
    --salida RUTA     Carpeta destino distinta a 'salida'.
    --junto           Deja cada .md al lado de su PDF original (ignora --salida).
    --recursivo       Al pasar una carpeta, tambien busca en las subcarpetas.
"""

import sys
import time
from pathlib import Path

# MarkItDown es la clase principal de la libreria: se instancia una vez
# y se reutiliza para todos los archivos (asi no recarga los detectores).
from markitdown import MarkItDown

# La consola de Windows a veces usa cp1252 y rompe con ciertos caracteres.
# Forzamos UTF-8 en la salida y reemplazamos lo que no se pueda mostrar.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Carpeta donde vive este script. Todas las rutas por defecto cuelgan de aca,
# asi el script funciona sin importar desde donde se lo invoque.
BASE = Path(__file__).resolve().parent
ENTRADA_POR_DEFECTO = BASE / "entrada"
SALIDA_POR_DEFECTO = BASE / "salida"


def juntar_pdfs(objetivo: Path, recursivo: bool) -> list:
    """Devuelve la lista de PDFs a convertir a partir de un archivo o carpeta."""
    if objetivo.is_file():
        # Si es un archivo suelto, lo aceptamos aunque no sea .pdf:
        # MarkItDown tambien lee docx, pptx, xlsx, html, etc.
        return [objetivo]
    if objetivo.is_dir():
        patron = "**/*.pdf" if recursivo else "*.pdf"
        # sorted() para que el orden de procesado sea siempre el mismo.
        return sorted(objetivo.glob(patron))
    return []


def convertir_uno(md: MarkItDown, pdf: Path, destino: Path, forzar: bool) -> str:
    """
    Convierte un PDF a .md.
    Devuelve un codigo de estado: 'ok', 'salteado' o 'error'.
    """
    salida = destino / (pdf.stem + ".md")

    # Si ya existe el .md y no se pidio --forzar, no lo tocamos.
    if salida.exists() and not forzar:
        print(f"  ~ salteado (ya existe): {salida.name}")
        return "salteado"

    try:
        inicio = time.time()

        # Aca ocurre la conversion. convert() detecta el tipo de archivo
        # y devuelve un objeto con .text_content (el Markdown resultante).
        resultado = md.convert(str(pdf))
        texto = resultado.text_content or ""

        # La carpeta destino puede no existir todavia (caso --junto en rutas nuevas).
        destino.mkdir(parents=True, exist_ok=True)

        # Escribimos siempre en UTF-8: el PDF puede traer acentos, simbolos, etc.
        salida.write_text(texto, encoding="utf-8")

        tardo = time.time() - inicio
        kb = len(texto.encode("utf-8")) / 1024
        print(f"  + {pdf.name}  ->  {salida.name}  ({kb:.1f} KB, {tardo:.1f}s)")
        return "ok"

    except Exception as e:
        # No cortamos el lote por un archivo roto: avisamos y seguimos.
        print(f"  ! ERROR en {pdf.name}: {type(e).__name__}: {e}")
        return "error"


def main(argv: list) -> int:
    # --- Parseo simple de argumentos (sin argparse, para mantenerlo liviano) ---
    forzar = "--forzar" in argv
    recursivo = "--recursivo" in argv
    junto = "--junto" in argv

    salida_custom = None
    if "--salida" in argv:
        i = argv.index("--salida")
        if i + 1 < len(argv):
            salida_custom = Path(argv[i + 1]).expanduser().resolve()
            # Sacamos la bandera y su valor para que no se confundan con rutas.
            del argv[i:i + 2]

    # Lo que quede sin guion son las rutas a convertir.
    rutas = [Path(a).expanduser() for a in argv if not a.startswith("--")]

    # Sin rutas explicitas -> modo carpeta 'entrada'.
    if not rutas:
        if not ENTRADA_POR_DEFECTO.exists():
            ENTRADA_POR_DEFECTO.mkdir(parents=True, exist_ok=True)
        rutas = [ENTRADA_POR_DEFECTO]

    destino_base = salida_custom or SALIDA_POR_DEFECTO

    # --- Armado de la lista de trabajo ---
    trabajos = []  # tuplas (pdf, carpeta_destino)
    for ruta in rutas:
        if not ruta.exists():
            print(f"! No existe: {ruta}")
            continue
        for pdf in juntar_pdfs(ruta.resolve(), recursivo):
            # --junto deja el .md al lado del PDF; si no, va a la carpeta destino.
            trabajos.append((pdf, pdf.parent if junto else destino_base))

    if not trabajos:
        print("\nNo se encontro ningun PDF para convertir.")
        print(f"Copia tus PDFs en:  {ENTRADA_POR_DEFECTO}")
        return 1

    print(f"\nConvirtiendo {len(trabajos)} archivo(s)...\n")

    # Una sola instancia reutilizada para todo el lote.
    md = MarkItDown()

    conteo = {"ok": 0, "salteado": 0, "error": 0}
    for pdf, destino in trabajos:
        conteo[convertir_uno(md, pdf, destino, forzar)] += 1

    # --- Resumen final ---
    print(
        f"\nListo: {conteo['ok']} convertido(s), "
        f"{conteo['salteado']} salteado(s), {conteo['error']} con error."
    )
    if conteo["ok"] and not junto:
        print(f"Los .md quedaron en: {destino_base}")

    # Codigo de salida distinto de 0 si hubo algun error (util para scripts).
    return 0 if conteo["error"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
