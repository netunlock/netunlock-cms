"""
Historial de presupuestos: buscar, reabrir, duplicar, reimprimir y eliminar.
"""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import filedialog, messagebox, ttk

from core.database import RUTA_SALIDAS
from core.utils import fmt_money


class TabPresupuestos(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=8)
        self.app = app
        self.db = app.db

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        barra = ttk.Frame(self)
        barra.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Label(barra, text="Buscar:").pack(side="left")
        self.var_filtro = tk.StringVar()
        entrada = ttk.Entry(barra, textvariable=self.var_filtro, width=32)
        entrada.pack(side="left", padx=6)
        entrada.bind("<KeyRelease>", lambda _e: self.refrescar())
        ttk.Label(barra, text="por número o cliente", foreground="#6B7A88",
                  font=("Segoe UI", 8)).pack(side="left")

        ttk.Button(barra, text="Eliminar", command=self.eliminar).pack(side="right", padx=3)
        ttk.Button(barra, text="Duplicar como nuevo", command=self.duplicar).pack(side="right",
                                                                                  padx=3)
        ttk.Button(barra, text="Reimprimir PDF", command=self.reimprimir).pack(side="right", padx=3)
        ttk.Button(barra, text="Abrir en Cotización", command=self.abrir).pack(side="right", padx=3)

        cols = ("numero", "fecha", "cliente", "obra", "items", "total")
        self.tv = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse")
        for c, t, w, a in (("numero", "Número", 110, "w"), ("fecha", "Fecha", 90, "center"),
                           ("cliente", "Cliente", 260, "w"), ("obra", "Obra", 240, "w"),
                           ("items", "Ítems", 60, "center"), ("total", "Total", 140, "e")):
            self.tv.heading(c, text=t)
            self.tv.column(c, width=w, anchor=a, stretch=(c in ("cliente", "obra")))
        self.tv.grid(row=1, column=0, sticky="nsew")
        self.tv.bind("<Double-1>", lambda _e: self.abrir())

        barra_v = ttk.Scrollbar(self, orient="vertical", command=self.tv.yview)
        barra_v.grid(row=1, column=1, sticky="ns")
        self.tv.configure(yscrollcommand=barra_v.set)

        self._ids: dict[str, int] = {}
        self.refrescar()

    def refrescar(self):
        self.tv.delete(*self.tv.get_children())
        self._ids.clear()
        for fila in self.db.listar_presupuestos(self.var_filtro.get().strip()):
            cantidad = self.db.query_one(
                "SELECT COUNT(*) AS n FROM presupuesto_items WHERE presupuesto_id = ?",
                (fila["id"],))["n"]
            try:
                fecha = date.fromisoformat(fila["fecha"]).strftime("%d/%m/%Y")
            except ValueError:
                fecha = fila["fecha"]
            iid = self.tv.insert("", "end", values=(
                fila["numero"], fecha, fila["cliente_razon_social"], fila["cliente_obra"],
                cantidad, fmt_money(fila["total"])))
            self._ids[iid] = fila["id"]

    def _seleccionado(self) -> int | None:
        sel = self.tv.selection()
        if not sel:
            messagebox.showinfo("Sin selección", "Elegí un presupuesto de la lista.", parent=self)
            return None
        return self._ids[sel[0]]

    def abrir(self):
        pid = self._seleccionado()
        if pid is None:
            return
        self.app.tab_cotizacion.cargar_presupuesto(pid)
        self.app.ir_a_cotizacion()

    def duplicar(self):
        pid = self._seleccionado()
        if pid is None:
            return
        self.app.tab_cotizacion.cargar_presupuesto(pid)
        self.app.tab_cotizacion._id_presupuesto = None
        self.app.tab_cotizacion._sugerir_numero()
        self.app.tab_cotizacion.var_fecha.set(date.today().strftime("%d/%m/%Y"))
        self.app.tab_cotizacion.recalcular()
        self.app.ir_a_cotizacion()
        self.app.estado("Copia creada con un número nuevo. Revisá los precios antes de enviar.")

    def reimprimir(self):
        pid = self._seleccionado()
        if pid is None:
            return
        self.app.tab_cotizacion.cargar_presupuesto(pid)
        self.app.ir_a_cotizacion()
        self.app.tab_cotizacion.generar_pdf()

    def eliminar(self):
        pid = self._seleccionado()
        if pid is None:
            return
        cab, _ = self.db.cargar_presupuesto(pid)
        if messagebox.askyesno(
                "Confirmar",
                f"¿Eliminar definitivamente el presupuesto {cab['numero']}?\n"
                "Se borran también sus ítems. Esta acción no se puede deshacer.",
                parent=self):
            self.db.borrar("presupuestos", pid)
            self.refrescar()
            self.app.estado(f"Presupuesto {cab['numero']} eliminado.")
