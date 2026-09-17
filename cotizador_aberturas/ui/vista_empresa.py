"""
Módulo 3 — Datos del emisor y numeración correlativa.
"""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from . import tema
from .componentes import (CampoMemo, CampoTexto, CampoUnidad, Tarjeta, _CampoArchivo,
                          boton_fantasma)


class VistaEmpresa(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.db = app.db

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        scroll.columnconfigure(0, weight=3)
        scroll.columnconfigure(1, weight=2)

        self._panel_emisor(scroll)
        self._panel_numeracion(scroll)
        self._panel_textos(scroll)
        self._panel_acciones(scroll)

        self.cargar()

    # =====================================================================

    def _panel_emisor(self, master):
        tarjeta = Tarjeta(master, "Datos del emisor")
        tarjeta.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=(0, 12))
        cuerpo = tarjeta.cuerpo
        cuerpo.columnconfigure((0, 1), weight=1)

        self.campos = {
            "razon_social": CampoTexto(cuerpo, "Nombre / Razón social"),
            "cuit": CampoTexto(cuerpo, "CUIT"),
            "direccion": CampoTexto(cuerpo, "Dirección"),
            "telefono": CampoTexto(cuerpo, "Teléfono"),
            "email": CampoTexto(cuerpo, "Email"),
            "web": CampoTexto(cuerpo, "Sitio web"),
        }
        for i, campo in enumerate(self.campos.values()):
            campo.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0, 12), pady=5)

        self.campo_logo = _CampoArchivo(
            cuerpo, "Logo", ayuda="PNG o JPG. Se imprime arriba a la izquierda del PDF.")
        self.campo_logo.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    def _panel_numeracion(self, master):
        tarjeta = Tarjeta(master, "Numeración de presupuestos")
        tarjeta.grid(row=0, column=1, sticky="nsew", pady=(0, 12))
        cuerpo = tarjeta.cuerpo
        cuerpo.columnconfigure((0, 1), weight=1)

        self.campo_prefijo = CampoTexto(cuerpo, "Prefijo", ancho=100,
                                        ayuda="Ej.: PRES, PPTO, COT")
        self.campo_numero = CampoUnidad(cuerpo, "Próximo número", "", 1, ancho=100, entero=True)
        self.campo_digitos = CampoUnidad(cuerpo, "Dígitos", "", 4, ancho=70, entero=True,
                                         ayuda="4 → PRES-0001")
        self.campo_validez = CampoUnidad(cuerpo, "Validez por defecto", "dias", 15, ancho=80,
                                         entero=True)
        for i, campo in enumerate((self.campo_prefijo, self.campo_numero,
                                   self.campo_digitos, self.campo_validez)):
            campo.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0, 12), pady=5)

        self.lbl_preview = ctk.CTkLabel(cuerpo, text="", font=("Consolas", 17, "bold"),
                                        text_color=tema.c("primario"), anchor="w")
        self.lbl_preview.grid(row=2, column=0, columnspan=2, sticky="w", pady=(14, 0))
        ctk.CTkLabel(cuerpo, text="El correlativo avanza solo al guardar cada presupuesto, "
                                  "y podés editar el número a mano cuando haga falta.",
                     font=tema.fuente(10), text_color=tema.c("texto_tenue"),
                     wraplength=300, justify="left", anchor="w").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))

        for campo in (self.campo_prefijo, self.campo_numero, self.campo_digitos):
            campo.var.trace_add("write", lambda *_a: self._actualizar_preview())

    def _panel_textos(self, master):
        tarjeta = Tarjeta(master, "Términos y condiciones de pago")
        tarjeta.grid(row=1, column=0, sticky="nsew", padx=(0, 12), pady=(0, 12))
        self.campo_terminos = CampoMemo(
            tarjeta.cuerpo, "", alto=140,
            ayuda="Se imprime al pie del presupuesto, antes de las firmas.")
        self.campo_terminos.pack(fill="both", expand=True)

        tarjeta2 = Tarjeta(master, "Observaciones generales precargadas")
        tarjeta2.grid(row=1, column=1, sticky="nsew", pady=(0, 12))
        self.campo_obs = CampoMemo(
            tarjeta2.cuerpo, "", alto=140,
            ayuda="Se carga automáticamente en cada presupuesto nuevo. "
                  "Se puede editar en cada presupuesto.")
        self.campo_obs.pack(fill="both", expand=True)

    def _panel_acciones(self, master):
        barra = ctk.CTkFrame(master, fg_color="transparent")
        barra.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        ctk.CTkButton(barra, text="Guardar configuración", width=190, height=38,
                      font=tema.fuente(13, "bold"), command=self.guardar).pack(side="right")
        boton_fantasma(barra, "Descartar cambios", self.cargar, ancho=150).pack(
            side="right", padx=8)

    # =====================================================================

    def _actualizar_preview(self):
        from core.formato import a_int
        prefijo = self.campo_prefijo.get() or "PRES"
        numero = max(1, self.campo_numero.get_int())
        digitos = max(1, min(10, self.campo_digitos.get_int() or 4))
        self.lbl_preview.configure(text=f"{prefijo}-{str(numero).zfill(digitos)}")

    def cargar(self):
        empresa = self.db.empresa()
        for clave, campo in self.campos.items():
            campo.set(empresa[clave] or "")
        self.campo_logo.var.set(empresa["logo_path"] or "")
        self.campo_prefijo.set(empresa["prefijo"] or "PRES")
        self.campo_numero.set(empresa["proximo_numero"] or 1)
        self.campo_digitos.set(empresa["relleno_ceros"] or 4)
        self.campo_validez.set(empresa["validez_dias"] or 15)
        self.campo_terminos.set(empresa["terminos"] or "")
        self.campo_obs.set(self.db.parametro("observaciones_defecto", "") or "")
        self._actualizar_preview()

    def guardar(self):
        if not self.campos["razon_social"].get():
            messagebox.showwarning("Falta un dato",
                                   "Ingresá el nombre o razón social del emisor.")
            return

        datos = {clave: campo.get() for clave, campo in self.campos.items()}
        datos.update({
            "logo_path": self.campo_logo.get(),
            "terminos": self.campo_terminos.get(),
            "validez_dias": max(1, self.campo_validez.get_int() or 15),
            "prefijo": self.campo_prefijo.get() or "PRES",
            "proximo_numero": max(1, self.campo_numero.get_int()),
            "relleno_ceros": max(1, min(10, self.campo_digitos.get_int() or 4)),
        })
        self.db.guardar_empresa(datos)
        self.db.set_parametro("observaciones_defecto", self.campo_obs.get(),
                              "Observaciones generales precargadas", "Comercial")
        self.db.set_parametro("validez_dias", datos["validez_dias"],
                              "Validez de la oferta en días", "Comercial")
        self.app.estado("Configuración de la empresa guardada.")
        messagebox.showinfo("Guardado", "Los datos del emisor se guardaron correctamente.")

    def al_entrar(self):
        self.cargar()

    def al_cambiar_tema(self):
        self.lbl_preview.configure(text_color=tema.c("primario"))
