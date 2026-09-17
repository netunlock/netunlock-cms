"""
Cotizador de Aberturas de Aluminio — punto de entrada.

Secuencia de arranque:
    1. Verifica dependencias
    2. Prepara carpetas de datos (y migra las locales si se marcó ``instalado.flag``)
    3. Carga preferencias y aplica el tema
    4. Verifica la licencia de este equipo; si falta, abre la ventana de activación
    5. Abre la aplicación

Uso:
    python main.py
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _faltantes() -> list[str]:
    faltan = []
    for modulo, paquete in (("tkinter", "tkinter (viene con Python; en Linux: "
                                        "sudo apt install python3-tk)"),
                            ("customtkinter", "customtkinter"),
                            ("reportlab", "reportlab")):
        try:
            __import__(modulo)
        except ImportError:
            faltan.append(paquete)
    return faltan


def _aviso_consola(titulo: str, mensaje: str) -> None:
    print(f"\n{titulo}\n{'-' * len(titulo)}\n{mensaje}\n")


def main() -> int:
    faltan = _faltantes()
    if faltan:
        _aviso_consola("Faltan dependencias",
                       "  - " + "\n  - ".join(faltan)
                       + "\n\nInstalalas con:\n    pip install -r requirements.txt")
        return 1

    from core import rutas
    from core.config import Ajustes

    rutas.asegurar_carpetas()
    rutas.migrar_datos_locales()

    ajustes = Ajustes.cargar()

    from ui import tema
    tema.inicializar(ajustes.tema_valido(), ajustes.escala_valida())

    # -- Licencia: HWID + suscripción + integridad de reloj -----------------
    from core import licencia

    estado = licencia.estado_actual()          # verifica reloj y clave instalada
    if not estado.valida:
        from ui.activation_dialog import pedir_activacion

        if not pedir_activacion(estado):       # ventana bloqueante de activación
            return 0                           # el usuario cerró sin activar
        # La ventana de activación era una raíz Tk propia y al cerrarse la
        # destruyó: hay que reinicializar el tema antes de abrir la aplicación.
        tema.inicializar(ajustes.tema_valido(), ajustes.escala_valida())
        estado = licencia.estado_actual()

    if estado.aviso_hora:
        print(estado.aviso_hora)

    # -- Aplicación ---------------------------------------------------------
    from ui.app import App

    try:
        App(ajustes).mainloop()
    except Exception:
        traceback.print_exc()
        try:
            from tkinter import messagebox
            messagebox.showerror(
                "Error inesperado",
                "La aplicación encontró un error y debe cerrarse.\n\n"
                + traceback.format_exc(limit=3))
        except Exception:
            pass
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
