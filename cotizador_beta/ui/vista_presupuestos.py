"""
Historial de presupuestos: buscar, reabrir, duplicar, cambiar estado y reimprimir.
"""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox

import customtkinter as ctk

from core import formato as F
from core.database import ESTADOS_PRESUPUESTO
from . import tema
from .componentes import Tabla, Tarjeta, boton_fantasma, boton_secundario

COLOR_ESTADO = {"Borrador": "texto_tenue", "Enviado": "primario", "Aprobado": "ok",
                "Rechazado": "error", "Facturado": "acento"}


class VistaPresupuestos(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.db = app.db

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._resumen()
        self._tabla()
        self.refrescar()

    def _resumen(self):
        self.tarjetas = ctk.CTkFrame(self, fg_color="transparent")
        self.tarjetas.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        for i in range(4):
            self.tarjetas.columnconfigure(i, weight=1)

    def _tabla(self):
        tarjeta = Tarjeta(self, "Historial")
        tarjeta.grid(row=1, column=0, sticky="nsew")
        tarjeta.cuerpo.columnconfigure(0, weight=1)
        tarjeta.cuerpo.rowconfigure(1, weight=1)

        acciones = tarjeta.zona_acciones
        ctk.CTkButton(acciones, text="Abrir", width=100, height=28, font=tema.fuente(12),
                      command=self.abrir).pack(side="right")

        barra = ctk.CTkFrame(tarjeta.cuerpo, fg_color="transparent")
        barra.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.var_filtro = tk.StringVar()
        entrada = ctk.CTkEntry(barra, textvariable=self.var_filtro, width=280,
                               placeholder_text="Buscar por número, cliente u obra…",
                               font=tema.fuente(12))
        entrada.pack(side="left")
        entrada.bind("<KeyRelease>", lambda _e: self.refrescar())

        self.combo_estado = ctk.CTkOptionMenu(
            barra, values=["Todos"] + list(ESTADOS_PRESUPUESTO), width=140,
            font=tema.fuente(12), command=lambda _v: self.refrescar())
        self.combo_estado.set("Todos")
        self.combo_estado.pack(side="left", padx=8)

        for texto, comando, ancho in (("Duplicar", self.duplicar, 100),
                                      ("Cambiar estado", self.cambiar_estado, 140),
                                      ("Reimprimir PDF", self.reimprimir, 140)):
            boton_secundario(barra, texto, comando, ancho=ancho).pack(side="left", padx=(0, 6))
        boton_fantasma(barra, "Eliminar", self.eliminar, ancho=100).pack(side="left")

        self.tabla = Tabla(
            tarjeta.cuerpo,
            [("numero", "Número", 130, "w"), ("fecha", "Fecha", 110, "center"),
             ("estado", "Estado", 120, "center"), ("cliente", "Cliente", 280, "w"),
             ("obra", "Obra", 250, "w"), ("items", "Ítems", 80, "e"),
             ("total", "Total", 160, "e"), ("actualizado", "Modificado", 150, "center")],
            alto=16, al_activar=self.abrir)
        self.tabla.grid(row=1, column=0, sticky="nsew")

    # -- datos ---------------------------------------------------------------

    def refrescar(self):
        filtro = self.var_filtro.get().strip()
        estado_filtro = self.combo_estado.get() if hasattr(self, "combo_estado") else "Todos"

        filas = []
        total_general = 0.0
        por_estado: dict[str, int] = {}

        for registro in self.db.listar_presupuestos(filtro):
            estado = registro["estado"] or "Borrador"
            por_estado[estado] = por_estado.get(estado, 0) + 1
            if estado_filtro != "Todos" and estado != estado_filtro:
                continue

            cantidad = self.db.query_one(
                "SELECT COUNT(*) AS n FROM presupuesto_items WHERE presupuesto_id = ?",
                (registro["id"],))["n"]
            try:
                fecha = date.fromisoformat(registro["fecha"]).strftime("%d/%m/%Y")
            except ValueError:
                fecha = registro["fecha"]
            actualizado = (registro["actualizado"] or "").replace("T", " ")[:16]

            total_general += registro["total"] or 0
            filas.append((
                (registro["numero"], fecha, estado, registro["cliente_razon_social"],
                 registro["cliente_obra"], F.unidades(cantidad),
                 F.moneda(registro["total"]), actualizado),
                {"id": registro["id"], "numero": registro["numero"], "estado": estado},
                ()))

        self.tabla.cargar(filas)
        self._pintar_resumen(len(filas), total_general, por_estado)

    def _pintar_resumen(self, cantidad, total, por_estado):
        for widget in self.tarjetas.winfo_children():
            widget.destroy()

        aprobados = por_estado.get("Aprobado", 0) + por_estado.get("Facturado", 0)
        datos = [
            ("Presupuestos listados", str(cantidad), "texto"),
            ("Monto total listado", F.moneda(total), "texto"),
            ("Enviados", str(por_estado.get("Enviado", 0)), "primario"),
            ("Aprobados / facturados", str(aprobados), "ok"),
        ]
        for col, (etiqueta, valor, color) in enumerate(datos):
            tarjeta = Tarjeta(self.tarjetas)
            tarjeta.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 10, 0))
            ctk.CTkLabel(tarjeta.cuerpo, text=etiqueta.upper(), font=tema.fuente(10, "bold"),
                         text_color=tema.c("texto_tenue"), anchor="w").pack(anchor="w")
            ctk.CTkLabel(tarjeta.cuerpo, text=valor, font=tema.fuente(20, "bold"),
                         text_color=tema.c(color), anchor="w").pack(anchor="w", pady=(4, 0))

    # -- acciones ------------------------------------------------------------

    def _seleccionado(self):
        fila = self.tabla.seleccionado()
        if not fila:
            messagebox.showinfo("Sin selección", "Elegí un presupuesto de la lista.")
        return fila

    def abrir(self):
        fila = self._seleccionado()
        if not fila:
            return
        self.app.vista_cotizacion.cargar_presupuesto(fila["id"])
        self.app.navegar("cotizacion")

    def duplicar(self):
        fila = self._seleccionado()
        if not fila:
            return
        vista = self.app.vista_cotizacion
        vista.cargar_presupuesto(fila["id"])
        vista._id_presupuesto = None
        vista._sugerir_numero()
        vista.campo_fecha.set(date.today().strftime("%d/%m/%Y"))
        vista.combo_estado.set("Borrador")
        vista.recalcular()
        self.app.navegar("cotizacion")
        self.app.estado("Copia creada con número nuevo. Revisá los precios antes de enviarla.")

    def cambiar_estado(self):
        fila = self._seleccionado()
        if not fila:
            return
        from .componentes import DialogoFormulario
        dialogo = DialogoFormulario(
            self.winfo_toplevel(), f"Estado de {fila['numero']}",
            [{"key": "estado", "label": "Estado del presupuesto", "tipo": "combo",
              "opciones": list(ESTADOS_PRESUPUESTO), "default": fila["estado"]}],
            texto_aceptar="Aplicar")
        if dialogo.resultado is None:
            return
        self.db.execute("UPDATE presupuestos SET estado = ?, actualizado = ? WHERE id = ?",
                        (dialogo.resultado["estado"],
                         __import__("datetime").datetime.now().isoformat(timespec="seconds"),
                         fila["id"]))
        self.refrescar()
        self.app.estado(f"{fila['numero']} → {dialogo.resultado['estado']}")

    def reimprimir(self):
        fila = self._seleccionado()
        if not fila:
            return
        self.app.vista_cotizacion.cargar_presupuesto(fila["id"])
        self.app.navegar("cotizacion")
        self.app.vista_cotizacion.generar_pdf()

    def eliminar(self):
        fila = self._seleccionado()
        if not fila:
            return
        if messagebox.askyesno(
                "Eliminar presupuesto",
                f"¿Eliminar definitivamente {fila['numero']}?\n\n"
                "Se borran también sus ítems. Esta acción no se puede deshacer."):
            self.db.borrar("presupuestos", fila["id"])
            self.refrescar()
            self.app.estado(f"Presupuesto {fila['numero']} eliminado.")

    def al_entrar(self):
        self.refrescar()

    def al_cambiar_tema(self):
        self.refrescar()
