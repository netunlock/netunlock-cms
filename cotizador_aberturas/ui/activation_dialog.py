"""
Ventana de activación / renovación de suscripción.

Se abre **antes** que la aplicación cuando no hay licencia válida, y es
bloqueante: hasta que no se active, el programa no arranca.

Es una ventana raíz propia (``CTk``, no ``CTkToplevel``) porque corre cuando
todavía no existe la ventana principal. Al cerrarse, ``activada`` indica si se
puede continuar.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core import licencia as lic
from core import reloj
from . import tema

ANCHO = 660


class VentanaActivacion(ctk.CTk):
    def __init__(self, estado: lic.Estado):
        super().__init__()
        self.activada = False
        self.estado = estado

        self.title("Activación — Cotizador de Aberturas")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._salir)

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.pack(fill="both", expand=True, padx=26, pady=18)

        if estado.reloj_manipulado:
            self._modo_reloj(cont)
        else:
            self._modo_licencia(cont)

        self.update_idletasks()
        self._centrar()
        self.lift()
        self.focus_force()

    # =====================================================================

    def _centrar(self):
        # winfo_height() todavía no refleja el alto real recién construida la
        # ventana: hay que pedir el alto solicitado por el layout, o el botón
        # "Activar" y el pie quedan cortados abajo.
        self.update_idletasks()
        ancho = max(ANCHO, self.winfo_reqwidth())
        alto = self.winfo_reqheight()

        alto_max = self.winfo_screenheight() - 90
        if alto > alto_max:
            alto = alto_max
            self.resizable(False, True)

        x = max(0, (self.winfo_screenwidth() - ancho) // 2)
        y = max(0, (self.winfo_screenheight() - alto) // 3)
        self.geometry(f"{ancho}x{alto}+{x}+{y}")

    def _titulo(self, master, texto, subtexto):
        ctk.CTkLabel(master, text=texto, font=tema.fuente(21, "bold"),
                     text_color=tema.c("texto"), anchor="w").pack(anchor="w")
        ctk.CTkLabel(master, text=subtexto, font=tema.fuente(12),
                     text_color=tema.c("texto_suave"), anchor="w",
                     wraplength=ANCHO - 70, justify="left").pack(anchor="w", pady=(2, 12))

    def _aviso(self, master, texto, color="alerta"):
        caja = ctk.CTkFrame(master, fg_color=tema.c("alerta_fondo"),
                            corner_radius=tema.RADIO)
        caja.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(caja, text=texto, font=tema.fuente(12), text_color=tema.c(color),
                     wraplength=ANCHO - 90, justify="left", anchor="w").pack(
            fill="x", padx=14, pady=12)

    # =====================================================================
    # Reloj manipulado: no tiene sentido pedir una clave
    # =====================================================================

    def _modo_reloj(self, cont):
        self._titulo(cont, "Revisá la fecha del equipo",
                     "La aplicación no puede validar la suscripción con la fecha actual.")
        self._aviso(cont, self.estado.motivo)

        ctk.CTkLabel(cont,
                     text="Corregí la fecha y hora de Windows (clic derecho en el reloj → "
                          "Ajustar fecha y hora → Establecer la hora automáticamente) "
                          "y volvé a abrir el programa.",
                     font=tema.fuente(11), text_color=tema.c("texto_suave"),
                     wraplength=ANCHO - 70, justify="left", anchor="w").pack(
            anchor="w", pady=(0, 18))

        botones = ctk.CTkFrame(cont, fg_color="transparent")
        botones.pack(fill="x")
        ctk.CTkButton(botones, text="Reintentar", width=140, height=38,
                      font=tema.fuente(13, "bold"), command=self._reintentar).pack(side="left")
        ctk.CTkButton(botones, text="Salir", width=110, height=38, command=self._salir,
                      fg_color="transparent", hover_color=tema.c("superficie_3"),
                      text_color=tema.c("texto_suave")).pack(side="right")

    def _reintentar(self):
        estado = lic.estado_actual()
        if estado.valida:
            self.activada = True
            self.destroy()
            return
        if not estado.reloj_manipulado:
            messagebox.showinfo(
                "Fecha corregida",
                "La fecha del equipo ya es correcta.\n\n"
                "Ahora se va a pedir la clave de activación.", parent=self)
            for widget in self.winfo_children():
                widget.destroy()
            self.estado = estado
            cont = ctk.CTkFrame(self, fg_color="transparent")
            cont.pack(fill="both", expand=True, padx=26, pady=18)
            self._modo_licencia(cont)
            self.update_idletasks()
            self._centrar()
            return
        messagebox.showwarning("Fecha incorrecta", estado.motivo, parent=self)

    # =====================================================================
    # Activación normal
    # =====================================================================

    def _modo_licencia(self, cont):
        vencida = bool(self.estado.licencia)
        self._titulo(
            cont,
            "Renovar suscripción" if vencida else "Activación de licencia",
            "Su suscripción ha vencido o el equipo no está registrado. "
            "Envíe el código de equipo a su proveedor para recibir la clave.")

        self._aviso(cont, self.estado.motivo)

        # -- Código de equipo
        ctk.CTkLabel(cont, text="1.  Código de este equipo",
                     font=tema.fuente(13, "bold"), text_color=tema.c("texto"),
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(cont, text="Envialo por WhatsApp a tu proveedor.",
                     font=tema.fuente(11), text_color=tema.c("texto_suave"),
                     anchor="w").pack(anchor="w", pady=(0, 6))

        fila = ctk.CTkFrame(cont, fg_color="transparent")
        fila.pack(fill="x", pady=(0, 14))
        self.var_hwid = tk.StringVar(value=self.estado.hwid_actual)
        entrada = ctk.CTkEntry(fila, textvariable=self.var_hwid, font=("Consolas", 19),
                               justify="center", height=46)
        entrada.pack(side="left", fill="x", expand=True)
        entrada.configure(state="readonly")
        ctk.CTkButton(fila, text="Copiar", width=100, height=46,
                      font=tema.fuente(12, "bold"),
                      command=self._copiar_hwid).pack(side="left", padx=(8, 0))

        # -- Clave
        ctk.CTkLabel(cont, text="2.  Clave de activación",
                     font=tema.fuente(13, "bold"), text_color=tema.c("texto"),
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(cont, text="Pegá acá la clave que te enviaron "
                                "(empieza con COTIZ-).",
                     font=tema.fuente(11), text_color=tema.c("texto_suave"),
                     anchor="w").pack(anchor="w", pady=(0, 6))

        self.caja_clave = ctk.CTkTextbox(cont, height=64, font=("Consolas", 12),
                                         wrap="char")
        self.caja_clave.pack(fill="x")
        self.caja_clave.bind("<Control-v>", lambda _e: self.after(30, self._activar_si_completa))

        self.lbl_error = ctk.CTkLabel(cont, text="", font=tema.fuente(11),
                                      text_color=tema.c("error"), anchor="w",
                                      wraplength=ANCHO - 70, justify="left")
        self.lbl_error.pack(anchor="w", pady=(6, 0))

        ctk.CTkButton(cont, text="Activar", height=42, font=tema.fuente(14, "bold"),
                      command=self._activar).pack(fill="x", pady=(14, 0))

        # -- Pie
        pie = ctk.CTkFrame(cont, fg_color="transparent")
        pie.pack(fill="x", pady=(14, 0))
        ctk.CTkButton(pie, text="Tengo un archivo .lic", width=170,
                      command=self._desde_archivo,
                      fg_color=tema.c("superficie_3"), hover_color=tema.c("borde"),
                      text_color=tema.c("texto")).pack(side="left")
        ctk.CTkButton(pie, text="Datos para soporte", width=160,
                      command=self._soporte,
                      fg_color="transparent", hover_color=tema.c("superficie_3"),
                      text_color=tema.c("texto_suave")).pack(side="left", padx=8)
        ctk.CTkButton(pie, text="Salir", width=100, command=self._salir,
                      fg_color="transparent", hover_color=tema.c("superficie_3"),
                      text_color=tema.c("texto_suave")).pack(side="right")

        self.caja_clave.focus_set()

    # =====================================================================

    def _copiar_hwid(self):
        self.clipboard_clear()
        self.clipboard_append(self.estado.hwid_actual)
        messagebox.showinfo(
            "Copiado",
            f"Código de equipo copiado:\n\n{self.estado.hwid_actual}\n\n"
            "Pegalo en el mensaje a tu proveedor.", parent=self)

    def _activar_si_completa(self):
        """Tras pegar, si la clave ya está entera se activa sin tocar el botón."""
        texto = self.caja_clave.get("1.0", "end").strip()
        if len(texto) >= 100:
            self._activar()

    def _activar(self):
        clave = self.caja_clave.get("1.0", "end").strip()
        if not clave:
            self.lbl_error.configure(text="Pegá la clave que te envió tu proveedor.")
            return

        estado = lic.instalar(clave)
        if not estado.valida:
            self.lbl_error.configure(text=estado.motivo.replace("\n\n", "  ").replace("\n", " "))
            return

        self._exito(estado)

    def _desde_archivo(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar archivo de licencia",
            filetypes=[("Licencia", "*.lic"), ("JSON", "*.json"), ("Todos", "*.*")],
            parent=self)
        if not ruta:
            return
        estado = lic.instalar_desde_archivo(ruta)
        if estado.valida:
            self._exito(estado)
        else:
            messagebox.showerror("Licencia rechazada", estado.motivo, parent=self)

    def _exito(self, estado):
        licencia = estado.licencia
        if licencia.perpetua:
            detalle = "Licencia sin vencimiento."
        else:
            detalle = (f"Suscripción activa hasta el "
                       f"{licencia.fecha_vencimiento:%d/%m/%Y}\n"
                       f"({estado.dias_restantes} días).")
        messagebox.showinfo("Activación correcta",
                            f"{detalle}\n\nYa podés usar el sistema.", parent=self)
        self.activada = True
        self.destroy()

    def _soporte(self):
        texto = lic.resumen_para_soporte()
        self.clipboard_clear()
        self.clipboard_append(texto)
        try:
            destino = reloj.carpeta_datos() / "solicitud_licencia.txt"
            destino.write_text(texto, encoding="utf-8")
            extra = f"\n\nTambién se guardó en:\n{destino}"
        except OSError:
            extra = ""
        messagebox.showinfo(
            "Datos para soporte",
            "Se copiaron al portapapeles. Pegalos en el mensaje a tu proveedor."
            + extra + "\n\n" + texto, parent=self)

    def _salir(self):
        self.activada = False
        self.destroy()


def pedir_activacion(estado: lic.Estado) -> bool:
    """Abre la ventana y devuelve ``True`` si el equipo quedó activado."""
    ventana = VentanaActivacion(estado)
    ventana.mainloop()
    return ventana.activada
