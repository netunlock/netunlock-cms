"""
Módulo de inventario: saldos y movimientos de perfiles, vidrios y accesorios.

Es opcional. Mientras ``usar_stock`` esté apagado la vista muestra una pantalla
explicando qué hace y cómo encenderlo, en lugar de una tabla vacía que parece un
error.

Las cantidades no se editan a mano en la tabla: todo cambio entra como
movimiento (ingreso, egreso o ajuste por recuento) para que el historial siempre
explique de dónde salió el saldo actual.
"""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from core import formato as F
from core import stock
from . import tema
from .componentes import (CampoCombo, CampoTexto, DialogoFormulario, Tabla,
                          Tarjeta, boton_fantasma, boton_secundario)

FILTROS = {"Todo": "", "Perfiles": "perfil", "Vidrios": "vidrio",
           "Accesorios": "accesorio"}

MOTIVOS_VISIBLES = {
    "inicial": "Carga inicial", "compra": "Compra", "consumo": "Consumo",
    "ajuste": "Ajuste", "anulacion": "Anulación",
}


class VistaStock(ctk.CTkFrame):

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.db = app.db

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        self._barra()
        if stock.activo(self.db):
            self._panel_saldos()
            self._panel_movimientos()
            self.refrescar()
        else:
            self._panel_apagado()

    # =====================================================================
    # Cabecera
    # =====================================================================

    def _barra(self):
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ctk.CTkLabel(barra, text="Inventario", font=tema.fuente(22, "bold"),
                     text_color=tema.c("texto")).pack(side="left", padx=(0, 16))

        if not stock.activo(self.db):
            return

        self.combo_filtro = CampoCombo(barra, "", list(FILTROS), valor="Todo",
                                       ancho=150, al_cambiar=self.refrescar)
        self.combo_filtro.pack(side="left", padx=(0, 10))

        self.buscar = CampoTexto(barra, "", ancho=200)
        self.buscar.entrada.bind("<KeyRelease>", lambda _e: self.refrescar())
        self.buscar.pack(side="left", padx=(0, 10))

        self.var_bajo = ctk.CTkCheckBox(
            barra, text="Sólo bajo mínimo", font=tema.fuente(12),
            command=self.refrescar)
        self.var_bajo.pack(side="left")

        boton_fantasma(barra, "Recalcular saldos", self._recalcular,
                       ancho=150).pack(side="right")

    def _panel_apagado(self):
        """Pantalla de bienvenida cuando el control de stock está desactivado."""
        tarjeta = Tarjeta(self, "El control de stock está desactivado")
        tarjeta.grid(row=1, column=0, columnspan=2, sticky="new", pady=6)

        texto = (
            "Con el inventario activado, el programa lleva la cuenta de las barras "
            "de perfil, los m² de vidrio y los accesorios que hay en el depósito.\n\n"
            "El material se descuenta al emitir una orden de trabajo, y vuelve al "
            "depósito si la orden se anula. Nada de esto afecta el precio de los "
            "presupuestos: el stock informa, no cotiza.\n\n"
            "Para activarlo, andá a Materiales y Costos → Costos operativos y poné "
            "el parámetro «usar_stock» en 1. Después reabrí esta pantalla."
        )
        ctk.CTkLabel(tarjeta.cuerpo, text=texto, font=tema.fuente(12),
                     text_color=tema.c("texto_suave"), justify="left", anchor="w",
                     wraplength=680).pack(anchor="w", pady=(0, 12))

        boton_secundario(tarjeta.cuerpo, "Activar ahora", self._activar,
                         ancho=160).pack(anchor="w")

    def _activar(self):
        self.db.set_parametro("usar_stock", 1,
                              "Activar el control de inventario (1 = sí)", "Stock")
        messagebox.showinfo(
            "Inventario activado",
            "Ya podés cargar los saldos iniciales.\n\n"
            "Volvé a entrar a esta pantalla para verla.")
        self.app.navegar("cotizacion")

    # =====================================================================
    # Saldos
    # =====================================================================

    def _panel_saldos(self):
        tarjeta = Tarjeta(self, "Saldos por artículo")
        tarjeta.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        tarjeta.cuerpo.columnconfigure(0, weight=1)
        tarjeta.cuerpo.rowconfigure(1, weight=1)

        acciones = ctk.CTkFrame(tarjeta.cuerpo, fg_color="transparent")
        acciones.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        for texto, comando, ancho in (("Ingreso", lambda: self._movimiento(1), 90),
                                      ("Egreso", lambda: self._movimiento(-1), 90),
                                      ("Recuento", self._recuento, 100),
                                      ("Mínimo", self._minimo, 90),
                                      ("Alta de artículo", self._alta, 140)):
            boton_secundario(acciones, texto, comando, ancho=ancho).pack(
                side="left", padx=(0, 6))

        self.tabla = Tabla(
            tarjeta.cuerpo,
            [("tipo", "Tipo", 90, "w"), ("codigo", "Código", 130, "w"),
             ("descripcion", "Descripción", 260, "w"),
             ("cantidad", "Cantidad", 110, "e"), ("unidad", "Unidad", 80, "center"),
             ("minimo", "Mínimo", 90, "e"), ("estado", "Estado", 110, "center")],
            alto=16, al_elegir=self._al_elegir)
        self.tabla.grid(row=1, column=0, sticky="nsew")

    def _panel_movimientos(self):
        tarjeta = Tarjeta(self, "Movimientos del artículo seleccionado")
        tarjeta.grid(row=1, column=1, sticky="nsew")
        tarjeta.cuerpo.columnconfigure(0, weight=1)
        tarjeta.cuerpo.rowconfigure(0, weight=1)

        self.tabla_mov = Tabla(
            tarjeta.cuerpo,
            [("fecha", "Fecha", 130, "w"), ("motivo", "Motivo", 110, "w"),
             ("cantidad", "Cantidad", 100, "e"), ("documento", "Documento", 110, "w"),
             ("nota", "Nota", 200, "w")],
            alto=16)
        self.tabla_mov.grid(row=0, column=0, sticky="nsew")

    # =====================================================================
    # Datos
    # =====================================================================

    def refrescar(self, _evento=None):
        if not hasattr(self, "tabla"):
            return

        tipo = FILTROS.get(self.combo_filtro.get(), "")
        texto = (self.buscar.get() or "").strip().lower()
        solo_bajo = bool(self.var_bajo.get())

        filas = []
        for reg in stock.listar(self.db, tipo=tipo, solo_bajo_minimo=solo_bajo):
            if texto and texto not in f"{reg['codigo']} {reg['descripcion']}".lower():
                continue
            estado = "⚠ Bajo mínimo" if reg["bajo_minimo"] else (
                "Sin stock" if reg["cantidad"] <= 0 else "OK")
            filas.append((
                (reg["tipo"].title(), reg["codigo"] or "—", reg["descripcion"] or "",
                 F.numero(reg["cantidad"], 2, quitar_ceros=True),
                 reg["unidad"], F.numero(reg["minimo"], 2, quitar_ceros=True),
                 estado),
                {"id": reg["id"], "tipo": reg["tipo"],
                 "referencia_id": reg["referencia_id"], "codigo": reg["codigo"]},
                ("alerta",) if reg["bajo_minimo"] or reg["cantidad"] <= 0 else ()))

        self.tabla.cargar(filas)
        self._al_elegir()
        self.app.estado(f"{len(filas)} artículo(s) en inventario")

    def _al_elegir(self, _evento=None):
        if not hasattr(self, "tabla_mov"):
            return
        fila = self.tabla.seleccionado()
        if not fila:
            self.tabla_mov.cargar([])
            return

        filas = []
        for mov in stock.movimientos(self.db, tipo=fila["tipo"],
                                     referencia_id=fila["referencia_id"]):
            signo = "+" if mov["cantidad"] > 0 else ""
            filas.append((
                (mov["fecha"][:16].replace("T", " "),
                 MOTIVOS_VISIBLES.get(mov["motivo"], mov["motivo"]),
                 f"{signo}{F.numero(mov['cantidad'], 2, quitar_ceros=True)}",
                 mov["documento"] or "—", mov["nota"] or ""),
                {"id": mov["id"]},
                ("alerta",) if mov["cantidad"] < 0 else ()))
        self.tabla_mov.cargar(filas)

    # =====================================================================
    # Acciones
    # =====================================================================

    def _seleccion(self):
        fila = self.tabla.seleccionado()
        if fila is None:
            messagebox.showinfo("Elegí un artículo",
                                "Seleccioná primero una fila de la tabla.")
        return fila

    def _movimiento(self, signo: int):
        fila = self._seleccion()
        if fila is None:
            return
        titulo = "Ingreso de material" if signo > 0 else "Egreso de material"
        dialogo = DialogoFormulario(
            self.winfo_toplevel(), f"{titulo} — {fila['codigo']}",
            [{"key": "cantidad", "label": "Cantidad", "tipo": "decimal",
              "decimales": 2, "requerido": True},
             {"key": "motivo", "label": "Motivo", "tipo": "combo",
              "opciones": ["compra", "ajuste", "inicial"] if signo > 0 else
                          ["consumo", "ajuste"],
              "default": "compra" if signo > 0 else "consumo"},
             {"key": "documento", "label": "Documento", "placeholder": "Remito, OT…"},
             {"key": "nota", "label": "Nota"}])
        if dialogo.resultado is None:
            return

        cantidad = abs(float(dialogo.resultado["cantidad"] or 0)) * signo
        if not cantidad:
            return
        saldo = stock.registrar(
            self.db, fila["tipo"], fila["referencia_id"], cantidad,
            motivo=dialogo.resultado["motivo"],
            documento=dialogo.resultado["documento"], nota=dialogo.resultado["nota"])
        self.refrescar()
        self.app.estado(f"{fila['codigo']}: saldo {F.numero(saldo, 2, quitar_ceros=True)}")

    def _recuento(self):
        """Ajuste por conteo físico: se escribe lo que hay, no la diferencia."""
        fila = self._seleccion()
        if fila is None:
            return
        actual = stock.saldo(self.db, fila["tipo"], fila["referencia_id"])
        dialogo = DialogoFormulario(
            self.winfo_toplevel(), f"Recuento físico — {fila['codigo']}",
            [{"key": "cantidad", "label": "Cantidad contada", "tipo": "decimal",
              "decimales": 2, "default": actual,
              "ayuda": f"El sistema dice {F.numero(actual, 2, quitar_ceros=True)}. "
                       "La diferencia queda asentada como ajuste."},
             {"key": "nota", "label": "Nota", "default": "Recuento físico"}])
        if dialogo.resultado is None:
            return
        stock.fijar_saldo(self.db, fila["tipo"], fila["referencia_id"],
                          float(dialogo.resultado["cantidad"] or 0),
                          nota=dialogo.resultado["nota"])
        self.refrescar()

    def _minimo(self):
        fila = self._seleccion()
        if fila is None:
            return
        dialogo = DialogoFormulario(
            self.winfo_toplevel(), f"Punto de reposición — {fila['codigo']}",
            [{"key": "minimo", "label": "Mínimo", "tipo": "decimal", "decimales": 2,
              "ayuda": "Por debajo de este valor el artículo aparece marcado."}])
        if dialogo.resultado is None:
            return
        stock.fijar_minimo(self.db, fila["tipo"], fila["referencia_id"],
                           float(dialogo.resultado["minimo"] or 0))
        self.refrescar()

    def _alta(self):
        """Incorpora al inventario un artículo del catálogo que todavía no está."""
        catalogos = {
            "perfil": [(p["id"], f"{p['codigo']} — {p['descripcion']}")
                       for p in self.db.query(
                           "SELECT p.id, p.codigo, p.descripcion FROM perfiles p "
                           "ORDER BY p.codigo")],
            "vidrio": [(v["id"], v["nombre"]) for v in self.db.vidrios()],
            "accesorio": [(a["id"], f"{a['codigo']} — {a['descripcion']}")
                          for a in self.db.accesorios()],
        }

        dialogo = DialogoFormulario(
            self.winfo_toplevel(), "Incorporar artículo al inventario",
            [{"key": "tipo", "label": "Tipo", "tipo": "combo",
              "opciones": list(catalogos), "default": "perfil"},
             {"key": "articulo", "label": "Artículo (escribí el código)",
              "requerido": True,
              "ayuda": "Tiene que existir en el catálogo. Para perfiles se busca "
                       "por código; si hay dos líneas con el mismo código, se toma "
                       "el primero."},
             {"key": "cantidad", "label": "Cantidad inicial", "tipo": "decimal",
              "decimales": 2, "default": 0}])
        if dialogo.resultado is None:
            return

        tipo = dialogo.resultado["tipo"]
        buscado = (dialogo.resultado["articulo"] or "").strip().lower()
        encontrado = next((i for i, etiqueta in catalogos[tipo]
                           if buscado in etiqueta.lower()), None)
        if encontrado is None:
            messagebox.showwarning("No se encontró",
                                   f"No hay ningún {tipo} que coincida con «{buscado}».")
            return

        stock.registrar(self.db, tipo, encontrado,
                        float(dialogo.resultado["cantidad"] or 0),
                        motivo="inicial", nota="Alta en inventario")
        self.refrescar()

    def _recalcular(self):
        """Reconstruye los saldos desde los movimientos."""
        corregidos = stock.recalcular(self.db)
        self.refrescar()
        messagebox.showinfo(
            "Saldos recalculados",
            f"Se revisaron todos los artículos contra el historial de movimientos.\n\n"
            + (f"Se corrigieron {corregidos} saldo(s)." if corregidos
               else "Estaba todo correcto."))

    def al_entrar(self):
        if hasattr(self, "tabla"):
            self.refrescar()
