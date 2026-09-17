"""
Panel de licencia dentro de la vista de Ajustes.

La ventana de activación que se muestra al arrancar vive en
:mod:`ui.activation_dialog`.
"""

from __future__ import annotations

from tkinter import filedialog, messagebox

import customtkinter as ctk

from core import licencia as lic
from core import reloj
from . import tema
from .componentes import DialogoBase, Tarjeta, boton_secundario


class PanelLicencia(Tarjeta):
    """Bloque de licencia dentro de la vista de Ajustes."""

    def __init__(self, master, app):
        super().__init__(master, "Licencia")
        self.app = app
        self._cuerpo = ctk.CTkFrame(self.cuerpo, fg_color="transparent")
        self._cuerpo.pack(fill="both", expand=True)
        self.refrescar()

    def refrescar(self):
        for w in self._cuerpo.winfo_children():
            w.destroy()

        estado = lic.estado_actual()
        color = "ok" if estado.valida else "error"
        texto_estado = "Suscripción activa" if estado.valida else "Sin licencia válida"

        encabezado = ctk.CTkFrame(self._cuerpo, fg_color="transparent")
        encabezado.pack(fill="x")
        punto = ctk.CTkLabel(encabezado, text="●", font=tema.fuente(16),
                             text_color=tema.c(color))
        punto.pack(side="left", padx=(0, 6))
        ctk.CTkLabel(encabezado, text=texto_estado, font=tema.fuente(13, "bold"),
                     text_color=tema.c("texto")).pack(side="left")

        filas = [("Código de este equipo", estado.hwid_actual)]
        if estado.licencia:
            l = estado.licencia
            filas.append(("Licenciado a", l.cliente or "—"))
            filas.append(("Emitida", l.emitida or "—"))
            if l.perpetua:
                filas.append(("Vencimiento", "Sin vencimiento"))
            else:
                dias = estado.dias_restantes
                detalle = l.fecha_vencimiento.strftime("%d/%m/%Y")  # noqa: E501
                if dias is not None:
                    detalle += f"  ({dias} días restantes)" if dias >= 0 else "  (vencida)"
                filas.append(("Vencimiento", detalle))
            if l.plan:
                filas.append(("Plan", l.plan))
        if not estado.valida:
            filas.append(("Motivo", estado.motivo.replace("\n", " ")))

        grilla = ctk.CTkFrame(self._cuerpo, fg_color="transparent")
        grilla.pack(fill="x", pady=(10, 0))
        grilla.columnconfigure(1, weight=1)
        for i, (etiqueta, valor) in enumerate(filas):
            ctk.CTkLabel(grilla, text=etiqueta, font=tema.fuente(11),
                         text_color=tema.c("texto_suave"), anchor="w").grid(
                row=i, column=0, sticky="w", padx=(0, 14), pady=3)
            fuente = ("Consolas", 12) if etiqueta.startswith("Código") else tema.fuente(12)
            ctk.CTkLabel(grilla, text=valor, font=fuente, text_color=tema.c("texto"),
                         anchor="w", wraplength=430, justify="left").grid(
                row=i, column=1, sticky="w", pady=3)

        if estado.por_vencer:
            ctk.CTkLabel(self._cuerpo, text="⚠  " + estado.aviso + " Contactá a tu proveedor para renovarla.",
                         font=tema.fuente(11), text_color=tema.c("alerta"),
                         anchor="w").pack(fill="x", pady=(10, 0))

        acciones = ctk.CTkFrame(self._cuerpo, fg_color="transparent")
        acciones.pack(fill="x", pady=(14, 0))
        acciones.columnconfigure((0, 1), weight=1)
        ctk.CTkButton(acciones, text="Activar / renovar suscripción…",
                      command=self._instalar).grid(row=0, column=0, columnspan=2,
                                                   sticky="ew", pady=(0, 6))
        boton_secundario(acciones, "Copiar código de equipo",
                         lambda: self._copiar(estado.hwid_actual)).grid(
            row=1, column=0, sticky="ew", padx=(0, 6))
        boton_secundario(acciones, "Datos para soporte", self._soporte).grid(
            row=1, column=1, sticky="ew")

    def _copiar(self, texto):
        self.clipboard_clear()
        self.clipboard_append(texto)
        self.app.estado("Código de equipo copiado al portapapeles.")

    def _soporte(self):
        texto = lic.resumen_para_soporte()
        self.clipboard_clear()
        self.clipboard_append(texto)
        messagebox.showinfo("Datos para soporte",
                            "Se copiaron al portapapeles:\n\n" + texto, parent=self)

    def _instalar(self):
        DialogoRenovacion(self.winfo_toplevel(), self.app, al_terminar=self.refrescar)


class DialogoRenovacion(DialogoBase):
    """Renovación desde Ajustes: pegar la clave o elegir un archivo .lic."""

    def __init__(self, master, app, al_terminar=None):
        super().__init__(master, "Activar o renovar suscripción", ancho=580)
        self.app = app
        self._al_terminar = al_terminar

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.pack(fill="both", expand=True, padx=22, pady=20)

        estado = lic.estado_actual(consultar_red=False)

        ctk.CTkLabel(cont, text="Código de este equipo", font=tema.fuente(11),
                     text_color=tema.c("texto_suave"), anchor="w").pack(anchor="w")
        fila = ctk.CTkFrame(cont, fg_color="transparent")
        fila.pack(fill="x", pady=(4, 16))
        caja_hwid = ctk.CTkEntry(fila, font=("Consolas", 15), justify="center", height=38)
        caja_hwid.insert(0, estado.hwid_actual)
        caja_hwid.configure(state="readonly")
        caja_hwid.pack(side="left", fill="x", expand=True)
        boton_secundario(fila, "Copiar", lambda: self._copiar(estado.hwid_actual),
                         ancho=90).pack(side="left", padx=(8, 0))

        ctk.CTkLabel(cont, text="Pegá la clave que te envió tu proveedor",
                     font=tema.fuente(11), text_color=tema.c("texto_suave"),
                     anchor="w").pack(anchor="w")
        self.caja = ctk.CTkTextbox(cont, height=74, font=("Consolas", 11), wrap="char")
        self.caja.pack(fill="x", pady=(4, 0))

        self.lbl_error = ctk.CTkLabel(cont, text="", font=tema.fuente(11),
                                      text_color=tema.c("error"), anchor="w",
                                      wraplength=520, justify="left")
        self.lbl_error.pack(anchor="w", pady=(6, 0))

        botones = ctk.CTkFrame(cont, fg_color="transparent")
        botones.pack(fill="x", pady=(14, 0))
        ctk.CTkButton(botones, text="Activar", width=130, height=36,
                      font=tema.fuente(13, "bold"), command=self._activar).pack(side="right")
        boton_secundario(botones, "Desde archivo .lic", self._desde_archivo,
                         ancho=160).pack(side="left")

        self.caja.focus_set()
        self.esperar()

    def _copiar(self, texto):
        self.clipboard_clear()
        self.clipboard_append(texto)
        self.app.estado("Código de equipo copiado al portapapeles.")

    def _aplicar(self, estado):
        if not estado.valida:
            self.lbl_error.configure(text=estado.motivo.replace("\n", " "))
            return
        if estado.licencia.perpetua:
            detalle = "Licencia sin vencimiento."
        else:
            detalle = (f"Suscripción activa hasta el "
                       f"{estado.licencia.fecha_vencimiento:%d/%m/%Y} "
                       f"({estado.dias_restantes} días).")
        messagebox.showinfo("Activación correcta", detalle, parent=self)
        self.app.estado(detalle)
        if self._al_terminar:
            self._al_terminar()
        self.destroy()

    def _activar(self):
        clave = self.caja.get("1.0", "end").strip()
        if not clave:
            self.lbl_error.configure(text="Pegá la clave de activación.")
            return
        self._aplicar(lic.instalar(clave))

    def _desde_archivo(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar archivo de licencia",
            filetypes=[("Licencia", "*.lic"), ("JSON", "*.json"), ("Todos", "*.*")],
            parent=self)
        if ruta:
            self._aplicar(lic.instalar_desde_archivo(ruta))
