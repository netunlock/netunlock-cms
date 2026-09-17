"""
Vigilante de cuelgues: cuando la interfaz deja de responder, deja el rastro.

Por qué existe
--------------
Un cuelgue de Tkinter no deja traceback. La ventana se congela, el usuario cierra
el programa, y del otro lado no queda nada para mirar: ni un log, ni una
excepción, ni una pista de en qué línea se trabó. Reproducirlo después es
adivinar.

Cómo funciona
-------------
El hilo principal marca un latido con ``after()`` cada segundo. Un hilo aparte
—que no depende del bucle de Tk, y por eso sigue vivo aunque la interfaz no—
mira ese latido. Si pasa demasiado tiempo sin novedades, escribe en
``datos/cuelgue.log`` la **pila de todos los hilos**: ahí queda la función exacta
donde se trabó.

No frena ni cierra nada: sólo anota. Si la interfaz se recupera sola, queda el
registro del episodio igual, que es justo lo que hace falta para entenderlo.
"""

from __future__ import annotations

import sys
import threading
import time
import traceback
from datetime import datetime

from . import rutas

#: Cada cuánto late el hilo principal
INTERVALO_LATIDO_MS = 1000

#: Sin latido por más de esto, se considera colgada y se vuelca la pila.
#: Cinco segundos son muchos para una interfaz: un recálculo pesado no llega
#: a uno, así que no hay falsos positivos por lentitud normal.
UMBRAL_CUELGUE_S = 5.0

#: Para no llenar el disco si algo queda trabado de verdad
MAX_VOLCADOS = 20


class Vigilante:
    """Detecta que el bucle de la interfaz dejó de correr y anota la pila."""

    def __init__(self, ventana):
        self.ventana = ventana
        self.ultimo_latido = time.monotonic()
        self.volcados = 0
        self.colgada = False
        self._hilo: threading.Thread | None = None
        self._seguir = True

    # -- lado del hilo principal ---------------------------------------------

    def _latir(self):
        self.ultimo_latido = time.monotonic()
        if self.colgada:
            # Volvió de un episodio: queda anotado cuánto duró
            self.colgada = False
            self._anotar("La interfaz volvió a responder.\n")
        try:
            self.ventana.after(INTERVALO_LATIDO_MS, self._latir)
        except Exception:
            self._seguir = False

    # -- lado del vigilante ---------------------------------------------------

    def _vigilar(self):
        while self._seguir:
            time.sleep(1.0)
            demora = time.monotonic() - self.ultimo_latido
            if demora > UMBRAL_CUELGUE_S and not self.colgada:
                self.colgada = True
                self._volcar(demora)

    def _volcar(self, demora: float):
        if self.volcados >= MAX_VOLCADOS:
            return
        self.volcados += 1

        lineas = [
            "=" * 74,
            f"CUELGUE DETECTADO  ·  {datetime.now().isoformat(timespec='seconds')}",
            f"La interfaz lleva {demora:.1f} s sin responder.",
            "=" * 74,
            "",
        ]
        for ident, marco in sys._current_frames().items():
            nombre = next((h.name for h in threading.enumerate() if h.ident == ident),
                          str(ident))
            lineas.append(f"--- hilo {nombre} ({ident}) ---")
            lineas.extend(l.rstrip() for l in traceback.format_stack(marco))
            lineas.append("")
        self._anotar("\n".join(lineas) + "\n")

    @staticmethod
    def _anotar(texto: str):
        try:
            rutas.asegurar_carpetas()
            with open(rutas.DATOS / "cuelgue.log", "a", encoding="utf-8") as f:
                f.write(texto)
        except OSError:
            pass

    # -- arranque y parada ----------------------------------------------------

    def arrancar(self):
        self._latir()
        self._hilo = threading.Thread(target=self._vigilar, daemon=True,
                                      name="vigilante")
        self._hilo.start()
        return self

    def detener(self):
        self._seguir = False


def vigilar(ventana) -> Vigilante:
    """Arranca el vigilante sobre la ventana principal."""
    return Vigilante(ventana).arrancar()
