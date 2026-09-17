"""
Módulo 3 — Configuración de la empresa emisora y control de correlatividad.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core.utils import a_int
from .widgets import ScrollFrame, etiqueta_seccion


class TabEmpresa(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.db = app.db

        scroll = ScrollFrame(self)
        scroll.pack(fill="both", expand=True)
        cont = ttk.Frame(scroll.interior, padding=16)
        cont.pack(fill="both", expand=True)
        cont.columnconfigure(1, weight=1)
        cont.columnconfigure(3, weight=1)

        self.var = {k: tk.StringVar() for k in
                    ("razon_social", "cuit", "direccion", "telefono", "email", "web", "logo_path",
                     "prefijo", "proximo_numero", "relleno_ceros", "validez_dias")}

        fila = etiqueta_seccion(cont, "Datos del emisor", 0)

        # Disposición en dos columnas: (izquierda, derecha) por fila
        campos = [
            (("Nombre / Razón social", "razon_social", 40), ("CUIT", "cuit", 20)),
            (("Dirección", "direccion", 40), ("Teléfono", "telefono", 20)),
            (("Email", "email", 40), ("Sitio web", "web", 20)),
        ]
        for izquierda, derecha in campos:
            for col, (etiqueta, clave, ancho) in ((0, izquierda), (2, derecha)):
                ttk.Label(cont, text=etiqueta + ":").grid(row=fila, column=col, sticky="w",
                                                          padx=(0, 8), pady=4)
                ttk.Entry(cont, textvariable=self.var[clave], width=ancho).grid(
                    row=fila, column=col + 1, sticky="ew", padx=(0, 20), pady=4)
            fila += 1

        # --- Logo
        ttk.Label(cont, text="Logo:").grid(row=fila, column=0, sticky="w", pady=4)
        marco_logo = ttk.Frame(cont)
        marco_logo.grid(row=fila, column=1, columnspan=3, sticky="ew", pady=4)
        marco_logo.columnconfigure(0, weight=1)
        ttk.Entry(marco_logo, textvariable=self.var["logo_path"]).grid(row=0, column=0, sticky="ew")
        ttk.Button(marco_logo, text="Buscar…", command=self._elegir_logo).grid(row=0, column=1,
                                                                               padx=4)
        ttk.Button(marco_logo, text="Quitar",
                   command=lambda: self.var["logo_path"].set("")).grid(row=0, column=2)
        fila += 1
        ttk.Label(cont, text="Formatos PNG o JPG. Se imprime arriba a la izquierda del PDF.",
                  foreground="#6B7A88", font=("Segoe UI", 8)).grid(
            row=fila, column=1, columnspan=3, sticky="w")
        fila += 1

        # --- Términos
        fila = etiqueta_seccion(cont, "Términos y condiciones de pago", fila)
        self.txt_terminos = tk.Text(cont, height=6, wrap="word", font=("Segoe UI", 9))
        self.txt_terminos.grid(row=fila, column=0, columnspan=4, sticky="ew", pady=(0, 6))
        fila += 1
        ttk.Label(cont, text="Se imprime al pie del presupuesto, antes de las firmas.",
                  foreground="#6B7A88", font=("Segoe UI", 8)).grid(
            row=fila, column=0, columnspan=4, sticky="w")
        fila += 1

        # --- Observaciones por defecto
        fila = etiqueta_seccion(cont, "Observaciones generales precargadas", fila)
        self.txt_obs = tk.Text(cont, height=6, wrap="word", font=("Segoe UI", 9))
        self.txt_obs.grid(row=fila, column=0, columnspan=4, sticky="ew", pady=(0, 6))
        fila += 1
        ttk.Label(cont, text="Este texto se carga automáticamente en cada presupuesto nuevo "
                             "(se puede editar por presupuesto).",
                  foreground="#6B7A88", font=("Segoe UI", 8)).grid(
            row=fila, column=0, columnspan=4, sticky="w")
        fila += 1

        # --- Numeración
        fila = etiqueta_seccion(cont, "Numeración de presupuestos", fila)
        numeracion = [
            ("Prefijo", "prefijo", 8, "Ej.: PRES, PPTO, COT"),
            ("Próximo número", "proximo_numero", 8, "Se adelanta solo al guardar"),
            ("Dígitos", "relleno_ceros", 5, "4 → PRES-0001"),
            ("Validez por defecto (días)", "validez_dias", 5, ""),
        ]
        for etiqueta, clave, ancho, ayuda in numeracion:
            ttk.Label(cont, text=etiqueta + ":").grid(row=fila, column=0, sticky="w", pady=4)
            ttk.Entry(cont, textvariable=self.var[clave], width=ancho).grid(
                row=fila, column=1, sticky="w", pady=4)
            if ayuda:
                ttk.Label(cont, text=ayuda, foreground="#6B7A88", font=("Segoe UI", 8)).grid(
                    row=fila, column=2, columnspan=2, sticky="w")
            fila += 1

        self.lbl_preview = ttk.Label(cont, text="", font=("Segoe UI", 10, "bold"),
                                     foreground="#1B3A57")
        self.lbl_preview.grid(row=fila, column=0, columnspan=4, sticky="w", pady=(6, 0))
        fila += 1
        for clave in ("prefijo", "proximo_numero", "relleno_ceros"):
            self.var[clave].trace_add("write", lambda *_a: self._actualizar_preview())

        # --- Botones
        botones = ttk.Frame(cont)
        botones.grid(row=fila, column=0, columnspan=4, sticky="e", pady=(18, 0))
        ttk.Button(botones, text="Descartar cambios", command=self.cargar).pack(side="right",
                                                                                padx=4)
        ttk.Button(botones, text="Guardar configuración", command=self.guardar).pack(side="right")

        self.cargar()

    # -- acciones ------------------------------------------------------------

    def _elegir_logo(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar logo",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.gif"), ("Todos los archivos", "*.*")])
        if ruta:
            self.var["logo_path"].set(ruta)

    def _actualizar_preview(self):
        try:
            numero = a_int(self.var["proximo_numero"].get(), 1)
            digitos = max(1, a_int(self.var["relleno_ceros"].get(), 4))
            prefijo = self.var["prefijo"].get() or "PRES"
            self.lbl_preview.config(
                text=f"Próximo presupuesto: {prefijo}-{str(numero).zfill(digitos)}")
        except Exception:
            self.lbl_preview.config(text="")

    def cargar(self):
        emp = self.db.empresa()
        for clave in self.var:
            self.var[clave].set(str(emp[clave] if emp[clave] is not None else ""))
        self.txt_terminos.delete("1.0", "end")
        self.txt_terminos.insert("1.0", emp["terminos"] or "")
        self.txt_obs.delete("1.0", "end")
        self.txt_obs.insert("1.0", self.db.parametro("observaciones_defecto", "") or "")
        self._actualizar_preview()

    def guardar(self):
        datos = {
            "razon_social": self.var["razon_social"].get().strip(),
            "cuit": self.var["cuit"].get().strip(),
            "direccion": self.var["direccion"].get().strip(),
            "telefono": self.var["telefono"].get().strip(),
            "email": self.var["email"].get().strip(),
            "web": self.var["web"].get().strip(),
            "logo_path": self.var["logo_path"].get().strip(),
            "terminos": self.txt_terminos.get("1.0", "end").rstrip(),
            "validez_dias": a_int(self.var["validez_dias"].get(), 15),
            "prefijo": self.var["prefijo"].get().strip() or "PRES",
            "proximo_numero": max(1, a_int(self.var["proximo_numero"].get(), 1)),
            "relleno_ceros": max(1, a_int(self.var["relleno_ceros"].get(), 4)),
        }
        if not datos["razon_social"]:
            messagebox.showwarning("Falta un dato", "Ingresá el nombre o razón social del emisor.")
            return

        self.db.guardar_empresa(datos)
        self.db.set_parametro("observaciones_defecto", self.txt_obs.get("1.0", "end").rstrip(),
                              "Observaciones generales precargadas", "Comercial")
        self.db.set_parametro("validez_dias", datos["validez_dias"],
                              "Validez de la oferta en días", "Comercial")
        self.app.estado("Configuración de la empresa guardada.")
        messagebox.showinfo("Guardado", "Los datos del emisor se guardaron correctamente.")
