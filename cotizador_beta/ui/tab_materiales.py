"""
Módulo 1 — Carga de materiales y costos base.

Sub-pestañas:
    Líneas y precios · Perfiles · Vidrios · Accesorios · Kits ·
    Fórmulas de despiece · Tipologías · Costos operativos
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from core.despiece import FUNCIONES_CONOCIDAS, calcular_despiece
from core.formula_engine import AYUDA_VARIABLES, validar
from core.utils import a_float, fmt_money, fmt_num
from .widgets import CrudFrame, FormDialog

MODOS_COSTEO = ["kg", "m2"]
UNIDADES = ["u", "jgo", "ml", "m2"]


class TabMateriales(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.db = app.db

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=6)

        nb.add(self._panel_lineas(nb), text="  Líneas y precios  ")
        nb.add(self._panel_perfiles(nb), text="  Perfiles  ")
        nb.add(self._panel_vidrios(nb), text="  Vidrios  ")
        nb.add(self._panel_accesorios(nb), text="  Accesorios  ")
        nb.add(self._panel_kits(nb), text="  Kits de accesorios  ")
        nb.add(self._panel_tipologias(nb), text="  Tipologías  ")
        nb.add(self._panel_formulas(nb), text="  Fórmulas de despiece  ")
        nb.add(self._panel_parametros(nb), text="  Costos operativos  ")

    # =====================================================================
    # Líneas de aluminio + precios por color
    # =====================================================================

    def _panel_lineas(self, parent):
        marco = ttk.Frame(parent)
        marco.columnconfigure(0, weight=3)
        marco.columnconfigure(1, weight=4)
        marco.rowconfigure(0, weight=1)

        def campos_linea(_fila):
            return [
                {"key": "nombre", "label": "Línea", "requerido": True},
                {"key": "descripcion", "label": "Descripción"},
                {"key": "modo_costeo", "label": "Modo de costeo", "tipo": "combo",
                 "opciones": MODOS_COSTEO, "default": "kg",
                 "ayuda": "kg = por peso del despiece · m2 = precio por m² de abertura"},
                {"key": "activo", "label": "Activa", "tipo": "bool", "default": 1},
            ]

        def guardar_linea(id_, datos):
            if id_:
                self.db.actualizar("lineas", id_, datos)
            else:
                self.db.insertar("lineas", datos)
            self.app.recargar_catalogos()

        self.crud_lineas = CrudFrame(
            marco,
            titulo="Líneas de aluminio",
            columnas=[("nombre", "Línea", 150, None), ("modo_costeo", "Costeo", 60, None),
                      ("descripcion", "Descripción", 180, None), ("activo", "Activa", 55, "bool")],
            cargar=lambda: self.db.query("SELECT * FROM lineas ORDER BY nombre"),
            campos=campos_linea,
            al_guardar=guardar_linea,
            al_borrar=lambda id_: (self.db.borrar("lineas", id_), self.app.recargar_catalogos()),
            altura=16,
        )
        self.crud_lineas.grid(row=0, column=0, sticky="nsew")
        self.crud_lineas.tree.bind("<<TreeviewSelect>>", lambda _e: self.crud_precios.refrescar())

        def linea_actual():
            fila = self.crud_lineas.seleccionado()
            return fila["id"] if fila else 0

        def cargar_precios():
            lid = linea_actual()
            if not lid:
                return []
            return self.db.query(
                "SELECT * FROM linea_precios WHERE linea_id = ? ORDER BY color", (lid,))

        def campos_precio(_fila):
            return [
                {"key": "color", "label": "Color / Terminación", "requerido": True},
                {"key": "precio_kg", "label": "Precio $/kg", "tipo": "money",
                 "ayuda": "Se usa cuando la línea cotiza en modo 'kg'"},
                {"key": "precio_m2_perfil", "label": "Precio $/m² de perfil", "tipo": "money",
                 "ayuda": "Se usa cuando la línea cotiza en modo 'm2' (como tu planilla Excel)"},
                {"key": "activo", "label": "Activo", "tipo": "bool", "default": 1},
            ]

        def guardar_precio(id_, datos):
            lid = linea_actual()
            if not lid:
                messagebox.showinfo("Elegí una línea", "Primero seleccioná una línea de aluminio.")
                return
            datos["linea_id"] = lid
            if id_:
                self.db.actualizar("linea_precios", id_, datos)
            else:
                self.db.insertar("linea_precios", datos)
            self.app.recargar_catalogos()

        self.crud_precios = CrudFrame(
            marco,
            titulo="Colores y precios de la línea seleccionada",
            columnas=[("color", "Color", 150, None), ("precio_kg", "$/kg", 110, "money"),
                      ("precio_m2_perfil", "$/m² perfil", 110, "money"),
                      ("activo", "Activo", 55, "bool")],
            cargar=cargar_precios,
            campos=campos_precio,
            al_guardar=guardar_precio,
            al_borrar=lambda id_: (self.db.borrar("linea_precios", id_),
                                   self.app.recargar_catalogos()),
            altura=16,
        )
        self.crud_precios.grid(row=0, column=1, sticky="nsew")
        return marco

    # =====================================================================
    # Perfiles
    # =====================================================================

    def _panel_perfiles(self, parent):
        marco = ttk.Frame(parent)
        marco.columnconfigure(0, weight=1)
        marco.rowconfigure(1, weight=1)

        barra = ttk.Frame(marco, padding=(8, 8, 8, 0))
        barra.grid(row=0, column=0, sticky="ew")
        ttk.Label(barra, text="Línea:").pack(side="left")
        self.var_perfil_linea = tk.StringVar()
        self.cb_perfil_linea = ttk.Combobox(barra, textvariable=self.var_perfil_linea,
                                            state="readonly", width=28)
        self.cb_perfil_linea.pack(side="left", padx=6)
        self.cb_perfil_linea.bind("<<ComboboxSelected>>", lambda _e: self.crud_perfiles.refrescar())

        def cargar():
            lid = self._id_linea(self.var_perfil_linea.get())
            if not lid:
                return self.db.query(
                    "SELECT p.*, l.nombre AS linea FROM perfiles p "
                    "LEFT JOIN lineas l ON l.id = p.linea_id ORDER BY l.nombre, p.codigo")
            return self.db.query(
                "SELECT p.*, l.nombre AS linea FROM perfiles p "
                "LEFT JOIN lineas l ON l.id = p.linea_id WHERE p.linea_id = ? ORDER BY p.codigo",
                (lid,))

        def campos(_fila):
            return [
                {"key": "codigo", "label": "Código de perfil", "requerido": True},
                {"key": "descripcion", "label": "Descripción"},
                {"key": "peso_kg_m", "label": "Peso nominal (kg/m)", "tipo": "float",
                 "ayuda": "Dato de catálogo del extrusor. Define el peso del despiece."},
                {"key": "largo_barra_mm", "label": "Largo de barra (mm)", "tipo": "int",
                 "default": 6000},
            ]

        def guardar(id_, datos):
            lid = self._id_linea(self.var_perfil_linea.get())
            if not lid:
                messagebox.showinfo("Elegí una línea", "Seleccioná la línea antes de cargar perfiles.")
                return
            datos["linea_id"] = lid
            if id_:
                self.db.actualizar("perfiles", id_, datos)
            else:
                self.db.insertar("perfiles", datos)

        self.crud_perfiles = CrudFrame(
            marco,
            titulo="Perfiles por línea",
            columnas=[("linea", "Línea", 130, None), ("codigo", "Código", 100, None),
                      ("descripcion", "Descripción", 260, None),
                      ("peso_kg_m", "Kg/m", 80, "num"),
                      ("largo_barra_mm", "Barra (mm)", 90, None)],
            cargar=cargar, campos=campos, al_guardar=guardar,
            al_borrar=lambda id_: self.db.borrar("perfiles", id_), altura=18,
        )
        self.crud_perfiles.grid(row=1, column=0, sticky="nsew")
        return marco

    # =====================================================================
    # Vidrios
    # =====================================================================

    def _panel_vidrios(self, parent):
        def campos(_fila):
            return [
                {"key": "nombre", "label": "Denominación", "requerido": True,
                 "ayuda": "Ej.: Float 4mm, DVH 4/9/4, Laminado 3+3"},
                {"key": "tipo", "label": "Tipo", "tipo": "combo",
                 "opciones": ["Float", "Laminado", "DVH", "Templado", "Espejo"], "default": "Float"},
                {"key": "espesor_mm", "label": "Espesor total (mm)", "tipo": "float"},
                {"key": "precio_m2", "label": "Precio $/m²", "tipo": "money", "requerido": True},
                {"key": "plancha_ancho_mm", "label": "Plancha base - ancho (mm)", "tipo": "int",
                 "default": 3600},
                {"key": "plancha_alto_mm", "label": "Plancha base - alto (mm)", "tipo": "int",
                 "default": 2500},
                {"key": "precio_plancha", "label": "Precio por plancha", "tipo": "money",
                 "ayuda": "Informativo. Si lo dejás en 0 se recalcula desde el $/m²."},
                {"key": "desperdicio_pct", "label": "Desperdicio de plancha (%)", "tipo": "pct",
                 "default": 0.10},
                {"key": "activo", "label": "Activo", "tipo": "bool", "default": 1},
            ]

        def guardar(id_, datos):
            if not datos.get("precio_plancha"):
                area = datos["plancha_ancho_mm"] * datos["plancha_alto_mm"] / 1_000_000
                datos["precio_plancha"] = round(datos["precio_m2"] * area, 2)
            if id_:
                self.db.actualizar("vidrios", id_, datos)
            else:
                self.db.insertar("vidrios", datos)
            self.app.recargar_catalogos()

        return CrudFrame(
            parent,
            titulo="Tipos de vidrio",
            columnas=[("nombre", "Denominación", 150, None), ("tipo", "Tipo", 90, None),
                      ("espesor_mm", "Esp. (mm)", 70, "num"),
                      ("precio_m2", "$/m²", 110, "money"),
                      ("plancha_ancho_mm", "Plancha A", 80, None),
                      ("plancha_alto_mm", "Plancha H", 80, None),
                      ("precio_plancha", "$/plancha", 110, "money"),
                      ("desperdicio_pct", "Desperd.", 70, "pct"),
                      ("activo", "Activo", 55, "bool")],
            cargar=lambda: self.db.query("SELECT * FROM vidrios ORDER BY nombre"),
            campos=campos, al_guardar=guardar,
            al_borrar=lambda id_: (self.db.borrar("vidrios", id_), self.app.recargar_catalogos()),
            altura=18,
        )

    # =====================================================================
    # Accesorios
    # =====================================================================

    def _panel_accesorios(self, parent):
        def campos(_fila):
            return [
                {"key": "codigo", "label": "Código", "requerido": True},
                {"key": "descripcion", "label": "Descripción"},
                {"key": "unidad", "label": "Unidad", "tipo": "combo", "opciones": UNIDADES,
                 "default": "u", "ayuda": "u/jgo se redondean · ml y m2 admiten decimales"},
                {"key": "precio", "label": "Precio unitario", "tipo": "money"},
                {"key": "activo", "label": "Activo", "tipo": "bool", "default": 1},
            ]

        def guardar(id_, datos):
            if id_:
                self.db.actualizar("accesorios", id_, datos)
            else:
                self.db.insertar("accesorios", datos)

        return CrudFrame(
            parent,
            titulo="Accesorios (ruedas, cierres, felpas, burletes, escuadras…)",
            columnas=[("codigo", "Código", 110, None), ("descripcion", "Descripción", 330, None),
                      ("unidad", "Un.", 55, None), ("precio", "Precio", 120, "money"),
                      ("activo", "Activo", 55, "bool")],
            cargar=lambda: self.db.query("SELECT * FROM accesorios ORDER BY codigo"),
            campos=campos, al_guardar=guardar,
            al_borrar=lambda id_: self.db.borrar("accesorios", id_), altura=18,
        )

    # =====================================================================
    # Kits de accesorios
    # =====================================================================

    def _panel_kits(self, parent):
        marco = ttk.Frame(parent)
        marco.columnconfigure(0, weight=3)
        marco.columnconfigure(1, weight=4)
        marco.rowconfigure(0, weight=1)

        def campos_kit(_fila):
            return [
                {"key": "nombre", "label": "Nombre del kit", "requerido": True},
                {"key": "linea_id_txt", "label": "Línea", "tipo": "combo",
                 "opciones": [l["nombre"] for l in self.db.lineas()]},
                {"key": "tipologia_codigo", "label": "Tipología", "tipo": "combo",
                 "opciones": [""] + [t["codigo"] for t in self.db.tipologias()],
                 "ayuda": "Vacío = kit por defecto para toda la línea"},
                {"key": "descripcion", "label": "Descripción"},
                {"key": "activo", "label": "Activo", "tipo": "bool", "default": 1},
            ]

        def cargar_kits():
            filas = self.db.query(
                "SELECT k.*, l.nombre AS linea FROM kits k "
                "LEFT JOIN lineas l ON l.id = k.linea_id ORDER BY l.nombre, k.nombre")
            return [dict(f, linea_id_txt=f["linea"] or "") for f in filas]

        def guardar_kit(id_, datos):
            datos = dict(datos)
            datos["linea_id"] = self._id_linea(datos.pop("linea_id_txt", ""))
            if id_:
                self.db.actualizar("kits", id_, datos)
            else:
                self.db.insertar("kits", datos)

        self.crud_kits = CrudFrame(
            marco,
            titulo="Kits",
            columnas=[("nombre", "Kit", 170, None), ("linea", "Línea", 130, None),
                      ("tipologia_codigo", "Tipología", 80, None), ("activo", "Activo", 55, "bool")],
            cargar=cargar_kits, campos=campos_kit, al_guardar=guardar_kit,
            al_borrar=lambda id_: self.db.borrar("kits", id_), altura=16,
        )
        self.crud_kits.grid(row=0, column=0, sticky="nsew")
        self.crud_kits.tree.bind("<<TreeviewSelect>>", lambda _e: self.crud_kit_items.refrescar())

        def kit_actual():
            fila = self.crud_kits.seleccionado()
            return fila["id"] if fila else 0

        def cargar_items():
            kid = kit_actual()
            if not kid:
                return []
            filas = self.db.items_de_kit(kid)
            return [dict(f, accesorio=f"{f['codigo']} — {f['descripcion']}") for f in filas]

        def campos_item(_fila):
            accs = self.db.accesorios()
            return [
                {"key": "accesorio", "label": "Accesorio", "tipo": "combo",
                 "opciones": [f"{a['codigo']} — {a['descripcion']}" for a in accs],
                 "requerido": True},
                {"key": "cantidad_formula", "label": "Cantidad (fórmula)", "default": "1",
                 "ayuda": AYUDA_VARIABLES},
            ]

        def guardar_item(id_, datos):
            kid = kit_actual()
            if not kid:
                messagebox.showinfo("Elegí un kit", "Seleccioná primero un kit.")
                return
            ok, detalle = validar(datos["cantidad_formula"])
            if not ok:
                messagebox.showerror("Fórmula inválida", str(detalle))
                return
            codigo = datos["accesorio"].split(" — ")[0]
            acc = self.db.query_one("SELECT id FROM accesorios WHERE codigo = ?", (codigo,))
            if not acc:
                messagebox.showerror("Accesorio", "No se encontró el accesorio seleccionado.")
                return
            registro = {"kit_id": kid, "accesorio_id": acc["id"],
                        "cantidad_formula": datos["cantidad_formula"]}
            if id_:
                self.db.actualizar("kit_items", id_, registro)
            else:
                self.db.insertar("kit_items", registro)

        self.crud_kit_items = CrudFrame(
            marco,
            titulo="Composición del kit seleccionado",
            columnas=[("codigo", "Código", 100, None), ("descripcion", "Accesorio", 240, None),
                      ("unidad", "Un.", 50, None),
                      ("cantidad_formula", "Cantidad (fórmula)", 170, None),
                      ("precio", "Precio", 100, "money")],
            cargar=cargar_items, campos=campos_item, al_guardar=guardar_item,
            al_borrar=lambda id_: self.db.borrar("kit_items", id_), altura=16,
        )
        self.crud_kit_items.grid(row=0, column=1, sticky="nsew")
        return marco

    # =====================================================================
    # Tipologías
    # =====================================================================

    def _panel_tipologias(self, parent):
        def campos(_fila):
            return [
                {"key": "codigo", "label": "Código", "requerido": True,
                 "ayuda": "Se usa para vincular fórmulas y kits. Ej.: COR2, BAT1, FIJO"},
                {"key": "nombre", "label": "Nombre", "requerido": True},
                {"key": "hojas_default", "label": "Hojas por defecto", "tipo": "int", "default": 2},
                {"key": "esquema", "label": "Dibujo en el PDF", "tipo": "combo",
                 "opciones": ["corrediza", "fijo", "batiente", "banderola", "puerta_batiente"],
                 "default": "corrediza"},
                {"key": "horas_por_m2", "label": "Horas de fabricación por m²", "tipo": "float",
                 "default": 0.85},
                {"key": "admite_mosquitero", "label": "Admite mosquitero", "tipo": "bool",
                 "default": 1},
                {"key": "admite_premarco", "label": "Admite premarco", "tipo": "bool", "default": 1},
                {"key": "activo", "label": "Activa", "tipo": "bool", "default": 1},
            ]

        def guardar(id_, datos):
            if id_:
                self.db.actualizar("tipologias", id_, datos)
            else:
                self.db.insertar("tipologias", datos)
            self.app.recargar_catalogos()

        return CrudFrame(
            parent,
            titulo="Tipologías de abertura",
            columnas=[("codigo", "Código", 80, None), ("nombre", "Nombre", 280, None),
                      ("hojas_default", "Hojas", 55, None), ("esquema", "Esquema", 110, None),
                      ("horas_por_m2", "h/m²", 60, "num"),
                      ("admite_mosquitero", "Mosq.", 55, "bool"),
                      ("admite_premarco", "Prem.", 55, "bool"),
                      ("activo", "Activa", 55, "bool")],
            cargar=lambda: self.db.query("SELECT * FROM tipologias ORDER BY nombre"),
            campos=campos, al_guardar=guardar,
            al_borrar=lambda id_: (self.db.borrar("tipologias", id_), self.app.recargar_catalogos()),
            altura=18,
        )

    # =====================================================================
    # Fórmulas de despiece  (Tipologias_Formulas)
    # =====================================================================

    def _panel_formulas(self, parent):
        marco = ttk.Frame(parent)
        marco.columnconfigure(0, weight=1)
        marco.rowconfigure(2, weight=1)

        barra = ttk.Frame(marco, padding=(8, 8, 8, 0))
        barra.grid(row=0, column=0, sticky="ew")

        ttk.Label(barra, text="Tipología:").pack(side="left")
        self.var_f_tip = tk.StringVar()
        self.cb_f_tip = ttk.Combobox(barra, textvariable=self.var_f_tip, state="readonly", width=32)
        self.cb_f_tip.pack(side="left", padx=6)

        ttk.Label(barra, text="Línea:").pack(side="left", padx=(14, 0))
        self.var_f_linea = tk.StringVar()
        self.cb_f_linea = ttk.Combobox(barra, textvariable=self.var_f_linea, state="readonly",
                                       width=26)
        self.cb_f_linea.pack(side="left", padx=6)

        for cb in (self.cb_f_tip, self.cb_f_linea):
            cb.bind("<<ComboboxSelected>>", lambda _e: self.crud_formulas.refrescar())

        ttk.Button(barra, text="Probar despiece…", command=self._probar_despiece).pack(
            side="right", padx=4)
        ttk.Button(barra, text="Fórmulas de vidrio…", command=self._editar_formula_vidrio).pack(
            side="right", padx=4)

        ttk.Label(marco, text=AYUDA_VARIABLES, foreground="#6B7A88",
                  font=("Segoe UI", 8)).grid(row=1, column=0, sticky="w", padx=10, pady=(6, 0))

        def cargar():
            tip = self._codigo_tipologia(self.var_f_tip.get())
            if not tip:
                return []
            lid = self._id_linea(self.var_f_linea.get())
            if self.var_f_linea.get().startswith("("):  # "(Genérica…)"
                return self.db.query(
                    "SELECT * FROM tipologia_formulas WHERE tipologia_codigo = ? AND linea_id IS NULL "
                    "ORDER BY orden, id", (tip,))
            return self.db.query(
                "SELECT * FROM tipologia_formulas WHERE tipologia_codigo = ? AND linea_id = ? "
                "ORDER BY orden, id", (tip, lid))

        def campos(_fila):
            lid = self._id_linea(self.var_f_linea.get())
            perfiles = self.db.query(
                "SELECT codigo FROM perfiles WHERE linea_id = ? ORDER BY codigo", (lid,)) if lid else []
            return [
                {"key": "perfil_codigo", "label": "Perfil", "requerido": True,
                 "tipo": "combo" if perfiles else "text",
                 "opciones": [p["codigo"] for p in perfiles]},
                {"key": "funcion", "label": "Función", "tipo": "combo",
                 "opciones": FUNCIONES_CONOCIDAS, "default": "MARCO_HORIZONTAL",
                 "ayuda": "HOJA_HORIZONTAL define AH y HOJA_VERTICAL define HH para el vidrio"},
                {"key": "formula_largo", "label": "Fórmula del largo (mm)", "requerido": True,
                 "ayuda": "Ej.: A · H - 48 · (A + 26) / N"},
                {"key": "cantidad_piezas", "label": "Cantidad de piezas", "default": "1",
                 "ayuda": "Ej.: 2 · 2*N"},
                {"key": "peso_kg_m", "label": "Peso kg/m (respaldo)", "tipo": "float",
                 "ayuda": "Sólo se usa si el perfil no está cargado en la línea"},
                {"key": "orden", "label": "Orden", "tipo": "int", "default": 0},
            ]

        def guardar(id_, datos):
            tip = self._codigo_tipologia(self.var_f_tip.get())
            if not tip:
                messagebox.showinfo("Elegí una tipología", "Seleccioná la tipología primero.")
                return
            for clave in ("formula_largo", "cantidad_piezas"):
                ok, detalle = validar(datos[clave])
                if not ok:
                    messagebox.showerror("Fórmula inválida", f"{clave}: {detalle}")
                    return
            datos = dict(datos)
            datos["tipologia_codigo"] = tip
            datos["linea_id"] = (None if self.var_f_linea.get().startswith("(")
                                 else self._id_linea(self.var_f_linea.get()))
            if id_:
                self.db.actualizar("tipologia_formulas", id_, datos)
            else:
                self.db.insertar("tipologia_formulas", datos)

        self.crud_formulas = CrudFrame(
            marco,
            titulo="Tipologias_Formulas — despiece paramétrico",
            columnas=[("orden", "#", 40, None), ("perfil_codigo", "Perfil", 100, None),
                      ("funcion", "Función", 150, None),
                      ("formula_largo", "Fórmula del largo", 200, None),
                      ("cantidad_piezas", "Cantidad", 110, None),
                      ("peso_kg_m", "Kg/m", 70, "num")],
            cargar=cargar, campos=campos, al_guardar=guardar,
            al_borrar=lambda id_: self.db.borrar("tipologia_formulas", id_),
            extra_botones=[("Duplicar a otra línea…", self._duplicar_formulas)],
            altura=14,
        )
        self.crud_formulas.grid(row=2, column=0, sticky="nsew")
        return marco

    def _editar_formula_vidrio(self):
        tip = self._codigo_tipologia(self.var_f_tip.get())
        if not tip:
            messagebox.showinfo("Elegí una tipología", "Seleccioná la tipología primero.")
            return
        generica = self.var_f_linea.get().startswith("(")
        lid = None if generica else self._id_linea(self.var_f_linea.get())

        fila = self.db.query_one(
            "SELECT * FROM vidrio_formulas WHERE tipologia_codigo = ? AND linea_id IS ?",
            (tip, lid)) if lid is None else self.db.query_one(
            "SELECT * FROM vidrio_formulas WHERE tipologia_codigo = ? AND linea_id = ?", (tip, lid))

        campos = [
            {"key": "formula_ancho", "label": "Ancho del vidrio (mm)", "default": "AH - 60",
             "ayuda": "Descuento de junquillo/perfil sobre el ancho de hoja"},
            {"key": "formula_alto", "label": "Alto del vidrio (mm)", "default": "HH - 60"},
            {"key": "formula_cantidad", "label": "Cantidad de paños", "default": "N"},
        ]
        dlg = FormDialog(self.winfo_toplevel(),
                         f"Fórmulas de vidrio — {tip}", campos, dict(fila) if fila else None)
        if dlg.resultado is None:
            return
        for clave, valor in dlg.resultado.items():
            ok, detalle = validar(valor)
            if not ok:
                messagebox.showerror("Fórmula inválida", f"{clave}: {detalle}")
                return
        datos = dict(dlg.resultado, tipologia_codigo=tip, linea_id=lid)
        if fila:
            self.db.actualizar("vidrio_formulas", fila["id"], datos)
        else:
            self.db.insertar("vidrio_formulas", datos)
        messagebox.showinfo("Guardado", "Fórmulas de vidrio actualizadas.")

    def _duplicar_formulas(self):
        tip = self._codigo_tipologia(self.var_f_tip.get())
        if not tip:
            return
        origen_generico = self.var_f_linea.get().startswith("(")
        lid_origen = None if origen_generico else self._id_linea(self.var_f_linea.get())

        campos = [{"key": "destino", "label": "Copiar a la línea", "tipo": "combo",
                   "opciones": [l["nombre"] for l in self.db.lineas()], "requerido": True}]
        dlg = FormDialog(self.winfo_toplevel(), "Duplicar fórmulas", campos)
        if dlg.resultado is None:
            return
        lid_destino = self._id_linea(dlg.resultado["destino"])
        if lid_destino == lid_origen:
            return

        if lid_origen is None:
            filas = self.db.query(
                "SELECT * FROM tipologia_formulas WHERE tipologia_codigo = ? AND linea_id IS NULL",
                (tip,))
        else:
            filas = self.db.query(
                "SELECT * FROM tipologia_formulas WHERE tipologia_codigo = ? AND linea_id = ?",
                (tip, lid_origen))

        for f in filas:
            self.db.insertar("tipologia_formulas", {
                "tipologia_codigo": tip, "linea_id": lid_destino,
                "perfil_codigo": f["perfil_codigo"], "funcion": f["funcion"],
                "formula_largo": f["formula_largo"], "cantidad_piezas": f["cantidad_piezas"],
                "peso_kg_m": f["peso_kg_m"], "orden": f["orden"]})
        messagebox.showinfo("Listo", f"Se copiaron {len(filas)} fórmulas.")

    def _probar_despiece(self):
        tip = self._codigo_tipologia(self.var_f_tip.get())
        lid = self._id_linea(self.var_f_linea.get())
        if not tip or not lid:
            messagebox.showinfo("Faltan datos", "Elegí una tipología y una línea concreta.")
            return

        colores = self.db.colores_de_linea(lid)
        vidrios = self.db.vidrios()
        tipologia = self.db.tipologia(tip)
        campos = [
            {"key": "ancho", "label": "Ancho A (mm)", "tipo": "float", "default": 1500},
            {"key": "alto", "label": "Alto H (mm)", "tipo": "float", "default": 1100},
            {"key": "hojas", "label": "Hojas N", "tipo": "int",
             "default": tipologia["hojas_default"] if tipologia else 2},
            {"key": "color", "label": "Color", "tipo": "combo",
             "opciones": [c["color"] for c in colores],
             "default": colores[0]["color"] if colores else ""},
            {"key": "vidrio", "label": "Vidrio", "tipo": "combo",
             "opciones": [v["nombre"] for v in vidrios],
             "default": vidrios[0]["nombre"] if vidrios else ""},
        ]
        dlg = FormDialog(self.winfo_toplevel(), "Probar despiece", campos)
        if dlg.resultado is None:
            return

        vid = self.db.query_one("SELECT id FROM vidrios WHERE nombre = ?", (dlg.resultado["vidrio"],))
        d = calcular_despiece(self.db, tip, lid, dlg.resultado["color"], dlg.resultado["ancho"],
                              dlg.resultado["alto"], dlg.resultado["hojas"],
                              vid["id"] if vid else 0)
        VentanaDespiece(self.winfo_toplevel(), d, f"{tip} · {dlg.resultado['ancho']:.0f} x "
                                                  f"{dlg.resultado['alto']:.0f} mm")

    # =====================================================================
    # Parámetros / costos operativos
    # =====================================================================

    def _panel_parametros(self, parent):
        def campos(fila):
            clave = (fila or {}).get("clave", "")
            es_pct = clave.endswith("_pct") or clave in ("margen_pct", "iva_pct")
            return [
                {"key": "clave", "label": "Clave", "tipo": "readonly" if fila else "text",
                 "requerido": True},
                {"key": "valor", "label": "Valor" + (" (%)" if es_pct else ""),
                 "requerido": False,
                 "ayuda": (fila or {}).get("descripcion", "")},
                {"key": "descripcion", "label": "Descripción"},
                {"key": "grupo", "label": "Grupo", "tipo": "combo",
                 "opciones": ["Mano de obra", "Logística", "Opcionales", "Comercial", "Técnico",
                              "General"], "default": "General"},
            ]

        def cargar():
            filas = self.db.query("SELECT rowid AS id, * FROM parametros ORDER BY grupo, clave")
            salida = []
            for f in filas:
                d = dict(f)
                if d["clave"].endswith("_pct"):
                    d["valor_visible"] = f"{a_float(d['valor']) * 100:.2f} %"
                else:
                    d["valor_visible"] = d["valor"]
                salida.append(d)
            return salida

        def guardar(_id, datos):
            valor = datos["valor"]
            if datos["clave"].endswith("_pct"):
                valor = a_float(valor) / 100.0 if a_float(valor) > 1 else a_float(valor)
            self.db.set_parametro(datos["clave"], valor, datos["descripcion"], datos["grupo"])

        return CrudFrame(
            parent,
            titulo="Costos operativos y parámetros generales",
            columnas=[("grupo", "Grupo", 110, None), ("clave", "Clave", 200, None),
                      ("valor_visible", "Valor", 120, None),
                      ("descripcion", "Descripción", 400, None)],
            cargar=cargar, campos=campos, al_guardar=guardar,
            al_borrar=lambda id_: self.db.execute("DELETE FROM parametros WHERE rowid = ?", (id_,)),
            altura=20,
        )

    # =====================================================================
    # Helpers
    # =====================================================================

    def _id_linea(self, nombre: str) -> int:
        if not nombre or nombre.startswith("("):
            return 0
        fila = self.db.query_one("SELECT id FROM lineas WHERE nombre = ?", (nombre,))
        return fila["id"] if fila else 0

    def _codigo_tipologia(self, texto: str) -> str:
        return texto.split(" — ")[0] if texto else ""

    def recargar_combos(self):
        lineas = [l["nombre"] for l in self.db.lineas()]
        tipologias = [f"{t['codigo']} — {t['nombre']}" for t in self.db.tipologias()]

        self.cb_perfil_linea["values"] = lineas
        if lineas and self.var_perfil_linea.get() not in lineas:
            self.var_perfil_linea.set(lineas[0])

        self.cb_f_tip["values"] = tipologias
        if tipologias and self.var_f_tip.get() not in tipologias:
            self.var_f_tip.set(tipologias[0])

        opciones_linea = ["(Genérica — todas las líneas)"] + lineas
        self.cb_f_linea["values"] = opciones_linea
        if self.var_f_linea.get() not in opciones_linea:
            self.var_f_linea.set(lineas[0] if lineas else opciones_linea[0])

        for crud in (self.crud_perfiles, self.crud_formulas):
            crud.refrescar()


class VentanaDespiece(tk.Toplevel):
    """Ventana de sólo lectura con el detalle de corte de una abertura."""

    def __init__(self, parent, despiece, titulo=""):
        super().__init__(parent)
        self.title(f"Despiece — {titulo}")
        self.geometry("880x560")
        self.transient(parent)

        cont = ttk.Frame(self, padding=10)
        cont.pack(fill="both", expand=True)
        cont.rowconfigure(1, weight=1)
        cont.columnconfigure(0, weight=1)

        al = despiece.aluminio
        resumen = (
            f"Hoja: {despiece.ancho_hoja_mm:.0f} x {despiece.alto_hoja_mm:.0f} mm     "
            f"Metros de perfil: {fmt_num(al.metros_totales, 2)} m     "
            f"Peso: {fmt_num(al.peso_total_kg, 3)} kg "
            f"(+{al.desperdicio_pct * 100:.0f}% desperdicio = {fmt_num(al.peso_con_desperdicio_kg, 3)} kg)\n"
            f"Costo aluminio: {fmt_money(al.costo)}  ·  "
            f"Vidrio: {fmt_num(despiece.vidrio.m2_total, 3)} m² = {fmt_money(despiece.vidrio.costo)}  ·  "
            f"Accesorios: {fmt_money(despiece.accesorios.costo)}"
        )
        ttk.Label(cont, text=resumen, font=("Consolas", 9), justify="left").grid(
            row=0, column=0, sticky="w", pady=(0, 8))

        nb = ttk.Notebook(cont)
        nb.grid(row=1, column=0, sticky="nsew")

        # --- Perfiles
        f1 = ttk.Frame(nb)
        cols = ("perfil", "funcion", "largo", "cant", "kgm", "peso")
        tv = ttk.Treeview(f1, columns=cols, show="headings")
        for c, t, w, a in (("perfil", "Perfil", 110, "w"), ("funcion", "Función", 170, "w"),
                           ("largo", "Largo (mm)", 100, "e"), ("cant", "Piezas", 70, "e"),
                           ("kgm", "Kg/m", 80, "e"), ("peso", "Peso (kg)", 100, "e")):
            tv.heading(c, text=t)
            tv.column(c, width=w, anchor=a)
        for p in al.piezas:
            tv.insert("", "end", values=(p.perfil_codigo, p.funcion, fmt_num(p.largo_mm, 1),
                                         p.cantidad, fmt_num(p.peso_kg_m, 3), fmt_num(p.peso_kg, 3)))
        tv.pack(fill="both", expand=True)
        nb.add(f1, text="  Perfiles  ")

        # --- Vidrios
        f2 = ttk.Frame(nb)
        tv2 = ttk.Treeview(f2, columns=("tipo", "med", "cant", "m2"), show="headings")
        for c, t, w, a in (("tipo", "Vidrio", 220, "w"), ("med", "Medida (mm)", 160, "e"),
                           ("cant", "Paños", 70, "e"), ("m2", "m²", 100, "e")):
            tv2.heading(c, text=t)
            tv2.column(c, width=w, anchor=a)
        for pano in despiece.vidrio.panos:
            tv2.insert("", "end", values=(pano.descripcion,
                                          f"{fmt_num(pano.ancho_mm, 0)} x {fmt_num(pano.alto_mm, 0)}",
                                          pano.cantidad, fmt_num(pano.m2_total, 3)))
        tv2.pack(fill="both", expand=True)
        nb.add(f2, text="  Vidrios  ")

        # --- Accesorios
        f3 = ttk.Frame(nb)
        tv3 = ttk.Treeview(f3, columns=("cod", "desc", "un", "cant", "pu", "tot"), show="headings")
        for c, t, w, a in (("cod", "Código", 100, "w"), ("desc", "Descripción", 260, "w"),
                           ("un", "Un.", 50, "w"), ("cant", "Cantidad", 90, "e"),
                           ("pu", "P. Unit.", 100, "e"), ("tot", "Total", 110, "e")):
            tv3.heading(c, text=t)
            tv3.column(c, width=w, anchor=a)
        for acc in despiece.accesorios.lineas:
            tv3.insert("", "end", values=(acc.codigo, acc.descripcion, acc.unidad,
                                          fmt_num(acc.cantidad, 2), fmt_money(acc.precio_unitario),
                                          fmt_money(acc.total)))
        tv3.pack(fill="both", expand=True)
        nb.add(f3, text=f"  Accesorios — {despiece.accesorios.kit_nombre}  ")

        if despiece.advertencias:
            ttk.Label(cont, text="⚠ " + " | ".join(despiece.advertencias),
                      foreground="#B45309", wraplength=840, justify="left").grid(
                row=2, column=0, sticky="w", pady=(8, 0))

        ttk.Button(cont, text="Cerrar", command=self.destroy).grid(row=3, column=0, sticky="e",
                                                                   pady=(8, 0))
