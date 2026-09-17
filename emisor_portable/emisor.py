# -*- coding: utf-8 -*-
"""
Emisor de licencias portable — Cotizador de Aberturas.

**HERRAMIENTA INTERNA. No se le da a nadie.** Quien tenga este programa, el
archivo ``emisor.llave`` y la contraseña puede emitir licencias del Cotizador
para siempre.

Para qué es
-----------
Para emitir una clave de activación desde cualquier computadora con Windows,
llevando todo en un pendrive, sin instalar Python ni nada.

Cómo se usa
-----------
1. El cliente te pasa su **código de equipo** (lo ve en Ajustes → Licencia).
2. Abrís este programa, ponés la contraseña.
3. Pegás el código, el nombre del cliente y los días.
4. Copiás la clave que sale y se la mandás por WhatsApp.

Todo lo que emitís queda anotado en ``registro.json``, al lado del programa: el
historial viaja con el pendrive.
"""

from __future__ import annotations

import json
import sys
import traceback
from datetime import date, timedelta
from pathlib import Path

import customtkinter as ctk
from tkinter import messagebox


# ---------------------------------------------------------------------------
# Dónde está todo
# ---------------------------------------------------------------------------

def _carpeta_base() -> Path:
    """La carpeta del ejecutable, que en el pendrive es donde vive todo.

    Con PyInstaller, ``sys.executable`` apunta al .exe; corriendo desde el
    código fuente, a python.exe, y ahí lo que vale es la carpeta del script.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE = _carpeta_base()
RUTA_LLAVE = BASE / "emisor.llave"
RUTA_REGISTRO = BASE / "registro.json"
CARPETA_LIC = BASE / "licencias"

DIAS_POR_DEFECTO = 30

# El código y las claves criptográficas salen del proyecto, no de una copia:
# una copia que se desincronice emitiría claves que la aplicación rechaza.
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(BASE.parent / "cotizador_beta"))

import caja  # noqa: E402
from core.licencia import (  # noqa: E402
    Licencia, emitir, emitir_clave, hwid_valido, validar_texto)


# ---------------------------------------------------------------------------
# Registro de emisiones
# ---------------------------------------------------------------------------

def historial() -> list[dict]:
    try:
        return json.loads(RUTA_REGISTRO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def anotar(lic: Licencia, clave: str) -> None:
    filas = historial()
    filas.append({**lic.como_dict(), "clave": clave})
    RUTA_REGISTRO.write_text(json.dumps(filas, indent=2, ensure_ascii=False),
                             encoding="utf-8")


def _nombre_archivo(cliente: str) -> str:
    limpio = "".join(c if c.isalnum() or c in " -_" else "" for c in cliente).strip()
    return (limpio.replace(" ", "_") or "cliente") + ".lic"


# ---------------------------------------------------------------------------
# Estética: la misma paleta del Cotizador, para que se vea de la misma familia
# ---------------------------------------------------------------------------
AZUL = "#1B3A57"
AZUL_CLARO = "#2C5A82"
GRIS = "#5B6B7C"
VERDE = "#0B6B60"
FONDO = "#F1F4F6"
PANEL = "#FFFFFF"
ROJO = "#B3261E"


def fuente(tam=13, peso="normal"):
    return ctk.CTkFont(family="Segoe UI", size=tam, weight=peso)


class Emisor(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=FONDO)
        self.title("Emisor de licencias — Cotizador de Aberturas")
        self.geometry("620x430")
        self.resizable(False, False)
        self.caja: caja.Caja | None = None
        self._pantalla_contrasena()

    # -- pantalla 1: la contraseña -------------------------------------------

    def _pantalla_contrasena(self):
        for hijo in self.winfo_children():
            hijo.destroy()

        marco = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=8)
        marco.pack(expand=True, fill="both", padx=26, pady=26)

        ctk.CTkLabel(marco, text="Emisor de licencias", font=fuente(24, "bold"),
                     text_color=AZUL).pack(pady=(38, 4))
        ctk.CTkLabel(marco, text="Cotizador de Aberturas de Aluminio",
                     font=fuente(13), text_color=GRIS).pack()

        if not RUTA_LLAVE.exists():
            ctk.CTkLabel(
                marco, text=f"No encuentro «{caja.NOMBRE_ARCHIVO}» en esta carpeta.",
                font=fuente(13, "bold"), text_color=ROJO).pack(pady=(34, 6))
            ctk.CTkLabel(marco, text=str(BASE), font=fuente(11), text_color=GRIS,
                         wraplength=520).pack()
            return

        ctk.CTkLabel(marco, text="Contraseña", font=fuente(12),
                     text_color=GRIS).pack(pady=(40, 6))
        self.campo = ctk.CTkEntry(marco, show="•", width=260, height=38,
                                  justify="center", font=fuente(16))
        self.campo.pack()
        self.campo.focus_set()
        self.campo.bind("<Return>", lambda _e: self._abrir())

        self.aviso = ctk.CTkLabel(marco, text="", font=fuente(12),
                                  text_color=ROJO, wraplength=480)
        self.aviso.pack(pady=(10, 0))

        self.boton = ctk.CTkButton(marco, text="Entrar", width=170, height=38,
                                   font=fuente(14, "bold"), fg_color=AZUL,
                                   hover_color=AZUL_CLARO, command=self._abrir)
        self.boton.pack(pady=(14, 0))

    def _abrir(self):
        contrasena = self.campo.get()
        if not contrasena:
            self.aviso.configure(text="Escribí la contraseña.")
            return
        # Descifrar tarda ~1 s a propósito; sin este aviso parece colgado.
        self.boton.configure(text="Abriendo…", state="disabled")
        self.aviso.configure(text="")
        self.update_idletasks()
        try:
            self.caja = caja.abrir(RUTA_LLAVE, contrasena)
        except caja.CajaError as exc:
            self.boton.configure(text="Entrar", state="normal")
            self.aviso.configure(text=str(exc))
            self.campo.delete(0, "end")
            self.campo.focus_set()
            return
        self._pantalla_emision()

    # -- pantalla 2: emitir ---------------------------------------------------

    def _pantalla_emision(self):
        for hijo in self.winfo_children():
            hijo.destroy()
        self.geometry("620x560")

        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.pack(fill="x", padx=26, pady=(20, 0))
        ctk.CTkLabel(cab, text="Emitir clave de activación",
                     font=fuente(19, "bold"), text_color=AZUL).pack(side="left")
        ctk.CTkLabel(cab, text=f"{len(historial())} emitidas",
                     font=fuente(12), text_color=GRIS).pack(side="right")

        marco = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=8)
        marco.pack(expand=True, fill="both", padx=26, pady=(12, 20))
        marco.columnconfigure(1, weight=1)

        def campo(fila, etiqueta, ancho=300, **kw):
            ctk.CTkLabel(marco, text=etiqueta, font=fuente(12), text_color=GRIS,
                         anchor="w").grid(row=fila, column=0, sticky="w",
                                          padx=(20, 12), pady=(14, 0))
            e = ctk.CTkEntry(marco, width=ancho, height=34, font=fuente(13), **kw)
            e.grid(row=fila, column=1, sticky="w", pady=(14, 0))
            return e

        self.e_hwid = campo(0, "Código de equipo")
        self.e_hwid.configure(placeholder_text="XXXX-XXXX-XXXX-XXXX")
        self.e_hwid.bind("<KeyRelease>", self._mirar_hwid)
        self.e_cliente = campo(1, "Cliente")
        self.e_dias = campo(2, "Días de validez", ancho=120)
        self.e_dias.insert(0, str(DIAS_POR_DEFECTO))
        ctk.CTkLabel(marco, text="0 = perpetua", font=fuente(11), text_color=GRIS
                     ).grid(row=2, column=1, sticky="w", padx=(132, 0), pady=(14, 0))

        self.previo = ctk.CTkLabel(marco, text="", font=fuente(11),
                                   text_color=VERDE, anchor="w", wraplength=540)
        self.previo.grid(row=3, column=0, columnspan=2, sticky="w",
                         padx=20, pady=(10, 0))

        ctk.CTkButton(marco, text="Emitir clave", width=180, height=40,
                      font=fuente(14, "bold"), fg_color=AZUL,
                      hover_color=AZUL_CLARO, command=self._emitir
                      ).grid(row=4, column=0, columnspan=2, pady=(16, 6))

        ctk.CTkLabel(marco, text="Clave para mandar por WhatsApp",
                     font=fuente(12), text_color=GRIS, anchor="w"
                     ).grid(row=5, column=0, columnspan=2, sticky="w", padx=20)
        self.salida = ctk.CTkTextbox(marco, height=88, font=("Consolas", 12),
                                     wrap="char", fg_color=FONDO)
        self.salida.grid(row=6, column=0, columnspan=2, sticky="ew",
                         padx=20, pady=(4, 8))

        pie = ctk.CTkFrame(marco, fg_color="transparent")
        pie.grid(row=7, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 16))
        self.b_copiar = ctk.CTkButton(pie, text="Copiar", width=120, height=34,
                                      font=fuente(13), fg_color=VERDE,
                                      hover_color="#0F8577", state="disabled",
                                      command=self._copiar)
        self.b_copiar.pack(side="left")
        ctk.CTkButton(pie, text="Ver historial", width=130, height=34,
                      font=fuente(13), fg_color="transparent", text_color=AZUL,
                      border_width=1, border_color="#C6D1D8",
                      hover_color=FONDO, command=self._historial).pack(side="left",
                                                                       padx=8)
        self.estado = ctk.CTkLabel(pie, text="", font=fuente(11), text_color=GRIS)
        self.estado.pack(side="right")

        self.e_hwid.focus_set()

    def _mirar_hwid(self, _e=None):
        """Avisa si el equipo ya tuvo licencias, mientras se escribe el código."""
        hwid = self.e_hwid.get().strip().upper()
        if not hwid_valido(hwid):
            self.previo.configure(text="")
            return
        previas = [r for r in historial() if r.get("hwid") == hwid]
        if not previas:
            self.previo.configure(text="Equipo nuevo.", text_color=GRIS)
            return
        ultima = previas[-1]
        if not self.e_cliente.get().strip():
            self.e_cliente.insert(0, ultima.get("cliente", ""))
        self.previo.configure(
            text=f"Este equipo ya tiene {len(previas)} emisión(es). "
                 f"Última: {ultima.get('cliente','')} — "
                 f"vence {ultima.get('vence') or 'nunca'}.", text_color=VERDE)

    def _emitir(self):
        hwid = self.e_hwid.get().strip().upper()
        if not hwid_valido(hwid):
            messagebox.showerror(
                "Código de equipo inválido",
                "Tienen que ser 4 grupos de 4 caracteres (0-9, A-F).\n\n"
                "Ejemplo:  00C0-5CF4-A01D-964C")
            return
        cliente = self.e_cliente.get().strip() or "Sin nombre"

        texto = self.e_dias.get().strip().lower()
        if texto in ("0", "p", "perpetua", ""):
            vence = ""
        else:
            try:
                dias = int(texto)
                if dias < 1:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Días inválidos",
                                     "Poné un número de días, o 0 para perpetua.")
                return
            vence = (date.today() + timedelta(days=dias)).isoformat()

        try:
            clave = emitir_clave(hwid, vence, "completa", self.caja.privada)
            lic = Licencia(cliente=cliente, hwid=hwid,
                           emitida=date.today().isoformat(), vence=vence,
                           plan="completa", notas="emitida con el emisor portable")

            # Control: se valida la clave recién emitida contra el equipo de
            # destino. Si algo salió mal, es mejor enterarse acá que cuando el
            # cliente no puede activar.
            control = validar_texto(clave, hwid_actual=hwid)
            if not control.valida:
                messagebox.showerror("La clave no valida",
                                     f"La clave emitida no pasa el control:\n\n"
                                     f"{control.motivo}")
                return

            CARPETA_LIC.mkdir(parents=True, exist_ok=True)
            (CARPETA_LIC / _nombre_archivo(cliente)).write_text(
                emitir(lic, self.caja.privada), encoding="utf-8")
            anotar(lic, clave)
        except Exception:
            messagebox.showerror("Error al emitir", traceback.format_exc())
            return

        self.salida.delete("1.0", "end")
        self.salida.insert("1.0", clave)
        self.b_copiar.configure(state="normal")
        cuando = "no vence" if not vence else \
            f"vence el {date.fromisoformat(vence):%d/%m/%Y}"
        self.estado.configure(text=f"{cliente} · {cuando}")
        self._copiar()

    def _copiar(self):
        clave = self.salida.get("1.0", "end").strip()
        if not clave:
            return
        self.clipboard_clear()
        self.clipboard_append(clave)
        self.update()
        self.b_copiar.configure(text="Copiada ✓")
        self.after(1800, lambda: self.b_copiar.configure(text="Copiar"))

    def _historial(self):
        filas = historial()
        if not filas:
            messagebox.showinfo("Historial", "Todavía no emitiste ninguna licencia.")
            return
        lineas = []
        for r in reversed(filas[-25:]):
            lineas.append(f"{r.get('emitida','')}   {r.get('hwid','')}   "
                          f"{(r.get('cliente') or '')[:24]:<24} "
                          f"vence {r.get('vence') or 'nunca'}")
        messagebox.showinfo(
            f"Últimas {len(lineas)} de {len(filas)} emisiones", "\n".join(lineas))


def main() -> int:
    ctk.set_appearance_mode("light")
    Emisor().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
