"""
Órdenes de trabajo: seguimiento de lo que está en el taller.

Las órdenes se emiten desde la pantalla de cotización (botón "Emitir OT"), que
es donde está el presupuesto con su despiece. Acá se las sigue: cambiar estado,
reimprimir la hoja de taller y ver qué material consumió cada una.
"""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from core import ordenes, rutas, stock
from core.database import ESTADOS_OT
from . import tema
from .componentes import (CampoCombo, CampoTexto, Tabla, Tarjeta, boton_fantasma,
                          boton_secundario)

class VistaOrdenes(ctk.CTkFrame):

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.db = app.db

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._barra()
        self._tabla()
        self.refrescar()

    def _barra(self):
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ctk.CTkLabel(barra, text="Órdenes de trabajo", font=tema.fuente(22, "bold"),
                     text_color=tema.c("texto")).pack(side="left", padx=(0, 16))

        self.combo_estado = CampoCombo(barra, "", ["Todas"] + list(ESTADOS_OT),
                                       valor="Todas", ancho=160,
                                       al_cambiar=self.refrescar)
        self.combo_estado.pack(side="left", padx=(0, 10))

        self.buscar = CampoTexto(barra, "", ancho=220)
        self.buscar.entrada.bind("<KeyRelease>", lambda _e: self.refrescar())
        self.buscar.pack(side="left")

        boton_fantasma(barra, "Abrir carpeta", self._abrir_carpeta,
                       ancho=130).pack(side="right")

    def _tabla(self):
        tarjeta = Tarjeta(self, "Producción")
        tarjeta.grid(row=1, column=0, sticky="nsew")
        tarjeta.cuerpo.columnconfigure(0, weight=1)
        tarjeta.cuerpo.rowconfigure(1, weight=1)

        acciones = ctk.CTkFrame(tarjeta.cuerpo, fg_color="transparent")
        acciones.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        for texto, comando, ancho in (
                ("Reimprimir", self.reimprimir, 110),
                ("En fabricación", lambda: self._estado("En fabricación"), 140),
                ("Terminada", lambda: self._estado("Terminada"), 110),
                ("Entregada", lambda: self._estado("Entregada"), 110),
                ("Anular", self.anular, 90)):
            boton_secundario(acciones, texto, comando, ancho=ancho).pack(
                side="left", padx=(0, 6))

        self.tabla = Tabla(
            tarjeta.cuerpo,
            [("numero", "N°", 100, "w"), ("fecha", "Fecha", 95, "center"),
             ("cliente", "Cliente", 180, "w"), ("obra", "Obra", 160, "w"),
             ("descripcion", "Abertura", 300, "w"),
             ("cantidad", "Cant.", 60, "center"),
             ("presupuesto", "Presupuesto", 110, "w"),
             ("entrega", "Entrega", 95, "center"),
             ("estado", "Estado", 120, "center")],
            alto=18, scroll_horizontal=True, al_activar=self.reimprimir)
        self.tabla.grid(row=1, column=0, sticky="nsew")

    # =====================================================================

    def refrescar(self, _evento=None):
        estado = self.combo_estado.get()
        filas = []
        for orden in ordenes.listar(
                self.db,
                estado="" if estado == "Todas" else estado,
                filtro=(self.buscar.get() or "").strip()):
            filas.append((
                (orden["numero"], orden["fecha"], orden["cliente"] or "—",
                 orden["obra"] or "—", orden["descripcion"] or "—",
                 orden["cantidad"], orden["presupuesto_numero"] or "—",
                 orden["entrega"] or "—", orden["estado"]),
                {"id": orden["id"], "numero": orden["numero"]},
                ("alerta",) if orden["estado"] == "Anulada" else ()))
        self.tabla.cargar(filas)
        self.app.estado(f"{len(filas)} orden(es) de trabajo")

    def _seleccion(self):
        fila = self.tabla.seleccionado()
        if fila is None:
            messagebox.showinfo("Elegí una orden",
                                "Seleccioná una orden de la lista.")
        return fila

    def reimprimir(self):
        fila = self._seleccion()
        if fila is None:
            return
        from reports.orden_trabajo import generar_ot

        orden = ordenes.obtener(self.db, fila["numero"])
        carpeta = rutas.SALIDAS / "ordenes"
        try:
            destino = generar_ot(self.db, orden, carpeta / f"{orden['numero']}.pdf")
        except Exception as exc:
            messagebox.showerror("No se pudo generar la orden", str(exc))
            return
        self.app.abrir_ruta(destino)

    def _estado(self, nuevo: str):
        fila = self._seleccion()
        if fila is None:
            return
        try:
            ordenes.cambiar_estado(self.db, fila["numero"], nuevo)
        except ValueError as exc:
            messagebox.showerror("No se pudo cambiar el estado", str(exc))
            return
        self.refrescar()
        self.app.estado(f"{fila['numero']} → {nuevo}")

    def anular(self):
        fila = self._seleccion()
        if fila is None:
            return
        orden = ordenes.obtener(self.db, fila["numero"])

        aviso = ""
        if orden["stock_descontado"] and stock.activo(self.db):
            aviso = ("\n\nEl material que consumió esta orden vuelve al "
                     "inventario.")
        if not messagebox.askyesno(
                "Anular orden",
                f"¿Anular la orden {fila['numero']}?\n\n"
                f"{orden['descripcion']}{aviso}\n\n"
                "La orden queda en el historial marcada como anulada; no se borra."):
            return

        ordenes.cambiar_estado(self.db, fila["numero"], "Anulada")
        self.refrescar()

    def _abrir_carpeta(self):
        carpeta = rutas.SALIDAS / "ordenes"
        carpeta.mkdir(parents=True, exist_ok=True)
        self.app.abrir_ruta(carpeta)

    def al_entrar(self):
        self.refrescar()
