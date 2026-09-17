"""
Widgets reutilizables de la interfaz (Tkinter / ttk).

* :class:`FormDialog`  - diálogo de alta/edición armado a partir de una lista de campos.
* :class:`CrudFrame`   - tabla con botonera Nuevo / Editar / Eliminar sobre cualquier tabla SQL.
* Helpers de scroll y de formato.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core.utils import a_float, a_int, fmt_money, fmt_num, fmt_pct

# Tipos de campo admitidos por FormDialog
TIPOS = ("text", "int", "float", "money", "pct", "bool", "combo", "multiline", "archivo", "readonly")


class FormDialog(tk.Toplevel):
    """Diálogo modal genérico.

    ``campos`` es una lista de diccionarios::

        {"key": "precio_kg", "label": "Precio $/kg", "tipo": "money", "ancho": 18,
         "opciones": [...], "ayuda": "texto bajo el campo"}

    Al aceptar, ``self.resultado`` es un dict ``{key: valor_convertido}``;
    al cancelar queda en ``None``.
    """

    def __init__(self, parent, titulo, campos, valores=None, ancho=520, validador=None):
        super().__init__(parent)
        self.title(titulo)
        self.resultado = None
        self._campos = campos
        self._validador = validador
        self._vars: dict[str, tk.Variable] = {}
        self._textos: dict[str, tk.Text] = {}
        valores = valores or {}

        self.transient(parent)
        self.resizable(False, False)
        self.columnconfigure(0, weight=1)

        cont = ttk.Frame(self, padding=12)
        cont.grid(row=0, column=0, sticky="nsew")
        cont.columnconfigure(1, weight=1)

        for fila, campo in enumerate(campos):
            key = campo["key"]
            tipo = campo.get("tipo", "text")
            etiqueta = ttk.Label(cont, text=campo.get("label", key))
            etiqueta.grid(row=fila, column=0, sticky="nw", padx=(0, 10), pady=4)

            valor = valores.get(key, campo.get("default", ""))

            if tipo == "multiline":
                caja = tk.Text(cont, height=campo.get("altura", 5), width=52, wrap="word",
                               font=("Segoe UI", 9))
                caja.insert("1.0", str(valor or ""))
                caja.grid(row=fila, column=1, sticky="ew", pady=4)
                self._textos[key] = caja
                continue

            if tipo == "bool":
                var = tk.BooleanVar(value=bool(valor))
                ttk.Checkbutton(cont, variable=var, text=campo.get("texto", "")).grid(
                    row=fila, column=1, sticky="w", pady=4)
                self._vars[key] = var
                continue

            if tipo == "combo":
                var = tk.StringVar(value=str(valor or ""))
                combo = ttk.Combobox(cont, textvariable=var, state="readonly",
                                     values=campo.get("opciones", []), width=campo.get("ancho", 38))
                combo.grid(row=fila, column=1, sticky="ew", pady=4)
                self._vars[key] = var
                continue

            if tipo == "archivo":
                marco = ttk.Frame(cont)
                marco.grid(row=fila, column=1, sticky="ew", pady=4)
                marco.columnconfigure(0, weight=1)
                var = tk.StringVar(value=str(valor or ""))
                ttk.Entry(marco, textvariable=var).grid(row=0, column=0, sticky="ew")
                ttk.Button(marco, text="…", width=3,
                           command=lambda v=var: self._elegir_archivo(v)).grid(row=0, column=1, padx=(4, 0))
                self._vars[key] = var
                continue

            var = tk.StringVar(value=self._a_texto(valor, tipo))
            entrada = ttk.Entry(cont, textvariable=var, width=campo.get("ancho", 40))
            if tipo == "readonly":
                entrada.state(["readonly"])
            entrada.grid(row=fila, column=1, sticky="ew", pady=4)
            self._vars[key] = var

            if campo.get("ayuda"):
                ttk.Label(cont, text=campo["ayuda"], foreground="#6B7A88",
                          font=("Segoe UI", 8), wraplength=340).grid(
                    row=fila, column=2, sticky="w", padx=(8, 0))

        botones = ttk.Frame(self, padding=(12, 0, 12, 12))
        botones.grid(row=1, column=0, sticky="e")
        ttk.Button(botones, text="Cancelar", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(botones, text="Aceptar", command=self._aceptar).pack(side="right")

        self.bind("<Return>", lambda _e: self._aceptar())
        self.bind("<Escape>", lambda _e: self.destroy())

        self.update_idletasks()
        x = parent.winfo_rootx() + max(20, (parent.winfo_width() - self.winfo_width()) // 2)
        y = parent.winfo_rooty() + 60
        self.geometry(f"+{x}+{y}")
        self.grab_set()
        self.wait_window(self)

    @staticmethod
    def _a_texto(valor, tipo):
        if valor is None or valor == "":
            return ""
        if tipo == "pct":
            return fmt_num(float(valor) * 100.0, 2)
        if tipo in ("float", "money"):
            return fmt_num(float(valor), 2)
        if tipo == "int":
            return str(int(float(valor)))
        return str(valor)

    def _elegir_archivo(self, var):
        ruta = filedialog.askopenfilename(
            title="Seleccionar imagen",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.gif"), ("Todos", "*.*")])
        if ruta:
            var.set(ruta)

    def _aceptar(self):
        datos = {}
        for campo in self._campos:
            key, tipo = campo["key"], campo.get("tipo", "text")
            if tipo == "multiline":
                datos[key] = self._textos[key].get("1.0", "end").rstrip()
            elif tipo == "bool":
                datos[key] = int(self._vars[key].get())
            elif tipo in ("float", "money"):
                datos[key] = a_float(self._vars[key].get())
            elif tipo == "pct":
                datos[key] = a_float(self._vars[key].get()) / 100.0
            elif tipo == "int":
                datos[key] = a_int(self._vars[key].get())
            else:
                datos[key] = self._vars[key].get().strip()

            if campo.get("requerido") and datos[key] in ("", 0, None):
                messagebox.showwarning("Falta un dato",
                                       f"El campo «{campo.get('label', key)}» es obligatorio.",
                                       parent=self)
                return

        if self._validador:
            error = self._validador(datos)
            if error:
                messagebox.showwarning("Revisar datos", error, parent=self)
                return

        self.resultado = datos
        self.destroy()


class CrudFrame(ttk.Frame):
    """Tabla con ABM sobre una tabla de la base.

    ``columnas``: lista de ``(key, titulo, ancho, formato)`` donde ``formato`` puede ser
    ``None``, ``'money'``, ``'num'``, ``'pct'`` o ``'bool'``.
    """

    def __init__(self, parent, *, titulo, columnas, cargar, campos, al_guardar,
                 al_borrar=None, extra_botones=(), doble_click_edita=True, altura=14):
        super().__init__(parent, padding=8)
        self._columnas = columnas
        self._cargar = cargar
        self._campos = campos
        self._al_guardar = al_guardar
        self._al_borrar = al_borrar
        self._filas: dict[str, dict] = {}

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        cabecera = ttk.Frame(self)
        cabecera.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Label(cabecera, text=titulo, font=("Segoe UI", 11, "bold")).pack(side="left")

        ttk.Button(cabecera, text="Nuevo", command=self.nuevo).pack(side="right", padx=2)
        ttk.Button(cabecera, text="Editar", command=self.editar).pack(side="right", padx=2)
        if al_borrar:
            ttk.Button(cabecera, text="Eliminar", command=self.borrar).pack(side="right", padx=2)
        for texto, comando in extra_botones:
            ttk.Button(cabecera, text=texto, command=comando).pack(side="right", padx=2)

        marco = ttk.Frame(self)
        marco.grid(row=1, column=0, sticky="nsew")
        marco.columnconfigure(0, weight=1)
        marco.rowconfigure(0, weight=1)

        ids = [c[0] for c in columnas]
        self.tree = ttk.Treeview(marco, columns=ids, show="headings", height=altura,
                                 selectmode="browse")
        for key, titulo_col, ancho, formato in columnas:
            self.tree.heading(key, text=titulo_col)
            anclaje = "e" if formato in ("money", "num", "pct") else "w"
            self.tree.column(key, width=ancho, anchor=anclaje, stretch=(formato is None))
        self.tree.grid(row=0, column=0, sticky="nsew")

        barra = ttk.Scrollbar(marco, orient="vertical", command=self.tree.yview)
        barra.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=barra.set)
        self.tree.tag_configure("inactivo", foreground="#9AA5AF")

        if doble_click_edita:
            self.tree.bind("<Double-1>", lambda _e: self.editar())

        self.refrescar()

    # -- datos ---------------------------------------------------------------

    def refrescar(self):
        seleccion = self.tree.selection()
        recordado = self._filas.get(seleccion[0], {}).get("id") if seleccion else None
        self.tree.delete(*self.tree.get_children())
        self._filas.clear()

        for fila in self._cargar():
            datos = dict(fila)
            valores = [self._formatear(datos.get(k), f) for k, _t, _a, f in self._columnas]
            etiquetas = () if datos.get("activo", 1) else ("inactivo",)
            iid = self.tree.insert("", "end", values=valores, tags=etiquetas)
            self._filas[iid] = datos
            if recordado is not None and datos.get("id") == recordado:
                self.tree.selection_set(iid)

    @staticmethod
    def _formatear(valor, formato):
        if valor is None:
            return ""
        if formato == "money":
            return fmt_money(valor)
        if formato == "num":
            return fmt_num(valor, 3)
        if formato == "pct":
            return fmt_pct(valor, 1)
        if formato == "bool":
            return "Sí" if valor else "No"
        return str(valor)

    def seleccionado(self) -> dict | None:
        sel = self.tree.selection()
        return self._filas.get(sel[0]) if sel else None

    # -- acciones ------------------------------------------------------------

    def nuevo(self):
        campos = self._campos(None)
        dlg = FormDialog(self.winfo_toplevel(), "Nuevo registro", campos)
        if dlg.resultado is not None:
            self._al_guardar(None, dlg.resultado)
            self.refrescar()

    def editar(self):
        fila = self.seleccionado()
        if not fila:
            messagebox.showinfo("Sin selección", "Elegí una fila de la lista.", parent=self)
            return
        campos = self._campos(fila)
        dlg = FormDialog(self.winfo_toplevel(), "Editar registro", campos, fila)
        if dlg.resultado is not None:
            self._al_guardar(fila.get("id"), dlg.resultado)
            self.refrescar()

    def borrar(self):
        fila = self.seleccionado()
        if not fila:
            messagebox.showinfo("Sin selección", "Elegí una fila de la lista.", parent=self)
            return
        if messagebox.askyesno("Confirmar", "¿Eliminar el registro seleccionado?", parent=self):
            self._al_borrar(fila["id"])
            self.refrescar()


class ScrollFrame(ttk.Frame):
    """Contenedor con scroll vertical (para formularios largos)."""

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        lienzo = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        lienzo.grid(row=0, column=0, sticky="nsew")
        barra = ttk.Scrollbar(self, orient="vertical", command=lienzo.yview)
        barra.grid(row=0, column=1, sticky="ns")
        lienzo.configure(yscrollcommand=barra.set)

        self.interior = ttk.Frame(lienzo)
        ventana = lienzo.create_window((0, 0), window=self.interior, anchor="nw")

        self.interior.bind(
            "<Configure>", lambda _e: lienzo.configure(scrollregion=lienzo.bbox("all")))
        lienzo.bind("<Configure>", lambda e: lienzo.itemconfigure(ventana, width=e.width))
        lienzo.bind_all("<MouseWheel>",
                        lambda e: lienzo.yview_scroll(int(-e.delta / 120), "units"), add="+")


def etiqueta_seccion(parent, texto, fila, columnas=4):
    """Título de sección dentro de un formulario en grilla."""
    lbl = ttk.Label(parent, text=texto.upper(), font=("Segoe UI", 9, "bold"),
                    foreground="#1B3A57")
    lbl.grid(row=fila, column=0, columnspan=columnas, sticky="w", pady=(12, 4))
    sep = ttk.Separator(parent, orient="horizontal")
    sep.grid(row=fila + 1, column=0, columnspan=columnas, sticky="ew", pady=(0, 6))
    return fila + 2
