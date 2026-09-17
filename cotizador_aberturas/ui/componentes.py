"""
Componentes reutilizables de la interfaz.

Lo importante acá es :class:`CampoUnidad`: **todo campo numérico muestra su
unidad** dentro del propio control (badge a la izquierda para ``$``, a la
derecha para ``mm`` / ``hrs`` / ``Kgs`` / ``uds.``), de modo que el operario
nunca tenga que adivinar en qué unidad está cargando un valor.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from core.formato import UNIDADES, a_float, a_int, numero
from . import tema

# Unidades que se muestran como prefijo (delante del número)
_PREFIJOS = {"$", "$ / Kg", "$ / m²", "$ / ml", "$ / ud.", "$ / hora"}


# ---------------------------------------------------------------------------
# Contenedores
# ---------------------------------------------------------------------------

class Tarjeta(ctk.CTkFrame):
    """Panel con esquinas redondeadas, borde suave y título opcional."""

    def __init__(self, master, titulo: str = "", **kw):
        kw.setdefault("fg_color", tema.c("superficie"))
        kw.setdefault("corner_radius", tema.RADIO)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", tema.c("borde_suave"))
        super().__init__(master, **kw)

        # Se usa pack (no grid) para la estructura propia de la tarjeta: garantiza
        # que el encabezado quede pegado arriba y el cuerpo absorba el resto,
        # sin depender de cómo se configuren los pesos de fila desde afuera.
        if titulo:
            cabecera = ctk.CTkFrame(self, fg_color="transparent", height=22)
            cabecera.pack(fill="x", padx=16, pady=(13, 0))
            cabecera.pack_propagate(False)
            self.lbl_titulo = ctk.CTkLabel(
                cabecera, text=titulo, font=tema.fuente(13, "bold"),
                text_color=tema.c("texto"), anchor="w")
            self.lbl_titulo.pack(side="left")
            self.zona_acciones = ctk.CTkFrame(cabecera, fg_color="transparent")
            self.zona_acciones.pack(side="right")

        self.cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        self.cuerpo.pack(fill="both", expand=True, padx=16,
                         pady=((10 if titulo else 14), 14))


class Separador(ctk.CTkFrame):
    def __init__(self, master, **kw):
        kw.setdefault("height", 1)
        kw.setdefault("fg_color", tema.c("borde_suave"))
        kw.setdefault("corner_radius", 0)
        super().__init__(master, **kw)


class Badge(ctk.CTkLabel):
    """Etiqueta chica con fondo, para estados y unidades."""

    def __init__(self, master, texto: str, color: str = "badge", **kw):
        kw.setdefault("fg_color", tema.c(color))
        kw.setdefault("text_color", tema.c("badge_texto" if color == "badge" else "sobre_primario"))
        kw.setdefault("corner_radius", 5)
        kw.setdefault("font", tema.fuente(11))
        kw.setdefault("padx", 8)
        super().__init__(master, text=texto, **kw)


# ---------------------------------------------------------------------------
# Campos de carga
# ---------------------------------------------------------------------------

class _CampoBase(ctk.CTkFrame):
    """Etiqueta arriba, control abajo y una línea de ayuda opcional."""

    def __init__(self, master, etiqueta: str = "", ayuda: str = "", **kw):
        kw.setdefault("fg_color", "transparent")
        super().__init__(master, **kw)
        self.columnconfigure(0, weight=1)
        self._fila = 0

        if etiqueta:
            ctk.CTkLabel(self, text=etiqueta, font=tema.fuente(11),
                         text_color=tema.c("texto_suave"), anchor="w").grid(
                row=0, column=0, sticky="ew", pady=(0, 3))
            self._fila = 1

        self._ayuda = ayuda

    def _poner_ayuda(self, fila: int):
        if self._ayuda:
            ctk.CTkLabel(self, text=self._ayuda, font=tema.fuente(10),
                         text_color=tema.c("texto_tenue"), anchor="w",
                         wraplength=320, justify="left").grid(
                row=fila, column=0, sticky="ew", pady=(3, 0))


class CampoUnidad(_CampoBase):
    """Campo numérico con la unidad visible dentro del control.

    ``unidad`` puede ser una clave de :data:`core.formato.UNIDADES`
    (``'moneda'``, ``'milimetros'``, ``'horas'``, ``'kilos'``, ``'unidades'``…)
    o directamente el texto a mostrar.
    """

    def __init__(self, master, etiqueta: str = "", unidad: str = "moneda",
                 valor=None, ancho: int = 150, decimales: int = 2,
                 entero: bool = False, quitar_ceros: bool = False,
                 ayuda: str = "", al_cambiar=None, **kw):
        super().__init__(master, etiqueta, ayuda, **kw)
        self.unidad_texto = UNIDADES.get(unidad, unidad)
        self.decimales = 0 if entero else decimales
        self.entero = entero
        # 'hrs' y 'Kgs' se leen mejor sin decimales sobrantes: 8 hrs, no 8,00 hrs
        self.quitar_ceros = quitar_ceros or entero or self.unidad_texto in ("hrs", "Kgs")
        # En un campo de medida, '1500' se lee mejor que '1.500'
        self.miles = self.unidad_texto not in ("mm", "m", "%")
        self._al_cambiar = al_cambiar

        caja = ctk.CTkFrame(self, fg_color=tema.c("campo"), corner_radius=tema.RADIO_CHICO,
                            border_width=1, border_color=tema.c("campo_borde"))
        caja.grid(row=self._fila, column=0, sticky="ew")
        caja.columnconfigure(1, weight=1)
        self._caja = caja

        es_prefijo = self.unidad_texto in _PREFIJOS
        etiqueta_unidad = ctk.CTkLabel(
            caja, text=self.unidad_texto, font=tema.fuente(11),
            text_color=tema.c("texto_tenue"), width=0)

        self.var = tk.StringVar()
        self.entrada = ctk.CTkEntry(
            caja, textvariable=self.var, width=ancho, border_width=0,
            fg_color="transparent", justify="right", font=tema.fuente(13))

        if es_prefijo:
            etiqueta_unidad.grid(row=0, column=0, padx=(10, 2), pady=6)
            self.entrada.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=2)
        else:
            self.entrada.grid(row=0, column=1, sticky="ew", padx=(10, 2), pady=2)
            etiqueta_unidad.grid(row=0, column=2, padx=(2, 10), pady=6)

        self._poner_ayuda(self._fila + 1)

        if valor is not None:
            self.set(valor)

        self.entrada.bind("<FocusOut>", self._normalizar)
        self.entrada.bind("<Return>", self._normalizar)
        self.entrada.bind("<FocusIn>", lambda _e: self.entrada.select_range(0, "end"))

    # -- valor ---------------------------------------------------------------

    def get(self) -> float:
        return a_float(self.var.get())

    def get_int(self) -> int:
        return a_int(self.var.get())

    def set(self, valor) -> None:
        self.var.set(numero(valor, self.decimales, quitar_ceros=self.quitar_ceros,
                            miles=self.miles))

    def _normalizar(self, _evento=None):
        self.set(self.get())
        if self._al_cambiar:
            self._al_cambiar()

    def configure_estado(self, activo: bool) -> None:
        self.entrada.configure(state="normal" if activo else "disabled")


class CampoPorcentaje(CampoUnidad):
    """Igual que :class:`CampoUnidad` pero convierte entre 0-100 y fracción."""

    def __init__(self, master, etiqueta: str = "", valor: float = 0.0, **kw):
        kw.setdefault("unidad", "porcentaje")
        kw.setdefault("ancho", 90)
        super().__init__(master, etiqueta, valor=None, **kw)
        self.set_fraccion(valor)

    def get_fraccion(self) -> float:
        return self.get() / 100.0

    def set_fraccion(self, valor: float) -> None:
        self.set((valor or 0.0) * 100.0)


class CampoTexto(_CampoBase):
    def __init__(self, master, etiqueta: str = "", valor: str = "", ancho: int = 200,
                 ayuda: str = "", placeholder: str = "", **kw):
        super().__init__(master, etiqueta, ayuda, **kw)
        self.var = tk.StringVar(value=str(valor or ""))
        self.entrada = ctk.CTkEntry(self, textvariable=self.var, width=ancho,
                                    font=tema.fuente(13), placeholder_text=placeholder)
        self.entrada.grid(row=self._fila, column=0, sticky="ew")
        self._poner_ayuda(self._fila + 1)

    def get(self) -> str:
        return self.var.get().strip()

    def set(self, valor) -> None:
        self.var.set(str(valor or ""))


class CampoCombo(_CampoBase):
    def __init__(self, master, etiqueta: str = "", opciones=(), valor: str = "",
                 ancho: int = 200, ayuda: str = "", al_cambiar=None, **kw):
        super().__init__(master, etiqueta, ayuda, **kw)
        self.var = tk.StringVar(value=str(valor or ""))
        self.menu = ctk.CTkOptionMenu(
            self, variable=self.var, values=list(opciones) or [""], width=ancho,
            font=tema.fuente(12), dynamic_resizing=False,
            command=(lambda _v: al_cambiar()) if al_cambiar else None)
        self.menu.grid(row=self._fila, column=0, sticky="ew")
        self._poner_ayuda(self._fila + 1)

    def get(self) -> str:
        return self.var.get()

    def set(self, valor) -> None:
        self.var.set(str(valor or ""))

    def opciones(self, valores, conservar: bool = True) -> None:
        valores = list(valores) or [""]
        actual = self.var.get()
        self.menu.configure(values=valores)
        if not conservar or actual not in valores:
            self.var.set(valores[0])


class CampoMemo(_CampoBase):
    def __init__(self, master, etiqueta: str = "", valor: str = "", alto: int = 90,
                 ayuda: str = "", **kw):
        super().__init__(master, etiqueta, ayuda, **kw)
        self.caja = ctk.CTkTextbox(self, height=alto, font=tema.fuente(12), wrap="word")
        self.caja.grid(row=self._fila, column=0, sticky="nsew")
        self.rowconfigure(self._fila, weight=1)
        if valor:
            self.caja.insert("1.0", str(valor))
        self._poner_ayuda(self._fila + 1)

    def get(self) -> str:
        return self.caja.get("1.0", "end").rstrip()

    def set(self, valor) -> None:
        self.caja.delete("1.0", "end")
        if valor:
            self.caja.insert("1.0", str(valor))


class CampoCheck(ctk.CTkCheckBox):
    def __init__(self, master, texto: str, valor: bool = False, al_cambiar=None, **kw):
        self.var = tk.BooleanVar(value=bool(valor))
        kw.setdefault("font", tema.fuente(12))
        super().__init__(master, text=texto, variable=self.var,
                         onvalue=True, offvalue=False, command=al_cambiar, **kw)

    def get(self) -> bool:
        return bool(self.var.get())

    def set(self, valor, from_variable_callback: bool = False) -> None:
        # CTkCheckBox llama a set(valor, from_variable_callback) desde select()
        # y desde su propio __init__: la firma tiene que aceptar el segundo
        # argumento, y hay que delegar para que se repinte el tilde.
        super().set(bool(valor), from_variable_callback)


# ---------------------------------------------------------------------------
# Tabla
# ---------------------------------------------------------------------------

class Tabla(ctk.CTkFrame):
    """``ttk.Treeview`` con la paleta activa, rayado alterno y scrollbar.

    ``columnas`` es una lista de ``(clave, titulo, ancho, alineacion)`` donde
    alineación es ``'w'``, ``'e'`` o ``'center'``.
    """

    def __init__(self, master, columnas, alto: int = 12, al_elegir=None,
                 al_activar=None, scroll_horizontal: bool = False, **kw):
        kw.setdefault("fg_color", tema.c("superficie"))
        kw.setdefault("corner_radius", tema.RADIO_CHICO)
        super().__init__(master, **kw)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.columnas = columnas

        claves = [c[0] for c in columnas]
        self.tree = ttk.Treeview(self, columns=claves, show="headings", height=alto,
                                 selectmode="browse", style="Cotizador.Treeview")
        for clave, titulo, ancho, alineacion in columnas:
            self.tree.heading(clave, text=titulo, anchor="w" if alineacion == "w" else alineacion)
            # Con scroll horizontal las columnas conservan su ancho: es preferible
            # desplazar a comprimir los importes hasta volverlos ilegibles.
            self.tree.column(clave, width=ancho, anchor=alineacion, minwidth=40,
                             stretch=(alineacion == "w" and not scroll_horizontal))
        self.tree.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)

        self.barra = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview,
                                   style="Cotizador.Vertical.TScrollbar")
        self.barra.grid(row=0, column=1, sticky="ns", padx=(0, 1), pady=1)
        self.tree.configure(yscrollcommand=self.barra.set)

        if scroll_horizontal:
            self.barra_h = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview,
                                         style="Cotizador.Horizontal.TScrollbar")
            self.barra_h.grid(row=1, column=0, sticky="ew", padx=1, pady=(0, 1))
            self.tree.configure(xscrollcommand=self.barra_h.set)

        tema.etiquetas_filas(self.tree)
        tema.al_cambiar(lambda _n: tema.etiquetas_filas(self.tree))

        self._filas: dict[str, dict] = {}
        if al_elegir:
            self.tree.bind("<<TreeviewSelect>>", lambda _e: al_elegir())
        if al_activar:
            self.tree.bind("<Double-1>", lambda _e: al_activar())
            self.tree.bind("<Return>", lambda _e: al_activar())

    # -- datos ---------------------------------------------------------------

    def limpiar(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._filas.clear()

    def agregar(self, valores, datos: dict | None = None, etiquetas=()) -> str:
        indice = len(self._filas)
        tags = tuple(etiquetas) + ("par" if indice % 2 == 0 else "impar",)
        iid = self.tree.insert("", "end", values=valores, tags=tags)
        self._filas[iid] = datos if datos is not None else {}
        return iid

    def cargar(self, filas) -> None:
        """``filas`` = iterable de ``(valores, datos, etiquetas)`` o de ``valores``."""
        recordado = self.clave_seleccionada()
        self.limpiar()
        for fila in filas:
            if isinstance(fila, tuple) and len(fila) == 3:
                iid = self.agregar(*fila)
            else:
                iid = self.agregar(fila)
            if recordado is not None and self._filas.get(iid, {}).get("id") == recordado:
                self.tree.selection_set(iid)

    def seleccionado(self) -> dict | None:
        sel = self.tree.selection()
        return self._filas.get(sel[0]) if sel else None

    def clave_seleccionada(self):
        fila = self.seleccionado()
        return fila.get("id") if fila else None

    def indice_seleccionado(self) -> int | None:
        sel = self.tree.selection()
        return self.tree.index(sel[0]) if sel else None

    def seleccionar_indice(self, indice: int) -> None:
        hijos = self.tree.get_children()
        if 0 <= indice < len(hijos):
            self.tree.selection_set(hijos[indice])
            self.tree.see(hijos[indice])

    def cantidad(self) -> int:
        return len(self._filas)


# ---------------------------------------------------------------------------
# Diálogos
# ---------------------------------------------------------------------------

class DialogoBase(ctk.CTkToplevel):
    """Ventana modal centrada sobre el padre, con Escape para cerrar."""

    def __init__(self, master, titulo: str, ancho: int = 560, alto: int | None = None):
        super().__init__(master)
        self.title(titulo)
        self.resizable(False, False)
        self.configure(fg_color=tema.c("ventana"))
        self._ancho = ancho
        self._alto = alto
        self.bind("<Escape>", lambda _e: self.destroy())
        # En Windows el Toplevel de CTk tarda un instante en existir; sin este
        # after el grab_set falla de forma intermitente.
        self.after(60, self._presentar)

    def _presentar(self):
        # El diálogo puede haberse cerrado antes de que corra este after().
        if not self.winfo_exists():
            return
        try:
            self.update_idletasks()
            maestro = self.master.winfo_toplevel()
            ancho = self._ancho or self.winfo_width()
            alto = self._alto or self.winfo_height()
            x = maestro.winfo_rootx() + max(0, (maestro.winfo_width() - ancho) // 2)
            y = maestro.winfo_rooty() + max(30, (maestro.winfo_height() - alto) // 3)
            self.geometry(f"+{x}+{y}")
            self.lift()
            self.focus_force()
            self.grab_set()
        except tk.TclError:
            pass

    def esperar(self):
        self.wait_window(self)


class DialogoFormulario(DialogoBase):
    """Formulario modal genérico armado desde una lista de descriptores.

    Cada campo es un dict::

        {"key": "precio_kg", "label": "Precio", "tipo": "moneda",
         "unidad": "moneda_kg", "requerido": True, "ayuda": "…"}

    Tipos: ``texto``, ``entero``, ``decimal``, ``moneda``, ``porcentaje``,
    ``bool``, ``combo``, ``memo``, ``archivo``, ``solo_lectura``.
    """

    def __init__(self, master, titulo: str, campos, valores=None, validador=None,
                 ancho: int = 560, texto_aceptar: str = "Guardar"):
        super().__init__(master, titulo, ancho=ancho)
        self.resultado = None
        self._campos = campos
        self._validador = validador
        self._widgets: dict[str, object] = {}
        valores = valores or {}

        contenedor = ctk.CTkScrollableFrame(self, fg_color="transparent", width=ancho - 40,
                                            height=min(560, 90 + 74 * len(campos)))
        contenedor.pack(fill="both", expand=True, padx=18, pady=(18, 6))
        contenedor.columnconfigure(0, weight=1)

        for fila, campo in enumerate(campos):
            self._widgets[campo["key"]] = self._crear(contenedor, campo, valores)
            self._widgets[campo["key"]].grid(row=fila, column=0, sticky="ew", pady=6)

        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.pack(fill="x", padx=18, pady=(4, 16))
        ctk.CTkButton(pie, text="Cancelar", width=110, command=self.destroy,
                      fg_color=tema.c("superficie_3"), hover_color=tema.c("borde"),
                      text_color=tema.c("texto")).pack(side="right", padx=(8, 0))
        ctk.CTkButton(pie, text=texto_aceptar, width=130,
                      command=self._aceptar).pack(side="right")

        self.bind("<Return>", lambda _e: self._aceptar())
        self.esperar()

    def _crear(self, master, campo, valores):
        key = campo["key"]
        tipo = campo.get("tipo", "texto")
        etiqueta = campo.get("label", key)
        ayuda = campo.get("ayuda", "")
        valor = valores.get(key, campo.get("default", ""))

        if tipo == "bool":
            marco = ctk.CTkFrame(master, fg_color="transparent")
            chk = CampoCheck(marco, campo.get("texto", etiqueta), bool(valor))
            chk.pack(anchor="w")
            marco.get = chk.get
            return marco
        if tipo == "combo":
            return CampoCombo(master, etiqueta, campo.get("opciones", ()), valor,
                              ancho=campo.get("ancho", 300), ayuda=ayuda)
        if tipo == "memo":
            return CampoMemo(master, etiqueta, valor, alto=campo.get("alto", 100), ayuda=ayuda)
        if tipo == "porcentaje":
            return CampoPorcentaje(master, etiqueta, float(valor or 0), ayuda=ayuda)
        if tipo in ("moneda", "decimal", "entero"):
            return CampoUnidad(
                master, etiqueta,
                unidad=campo.get("unidad", "moneda" if tipo == "moneda" else ""),
                valor=valor or 0, entero=(tipo == "entero"),
                decimales=campo.get("decimales", 2),
                ancho=campo.get("ancho", 160), ayuda=ayuda)
        if tipo == "archivo":
            return _CampoArchivo(master, etiqueta, valor, ayuda=ayuda)

        campo_texto = CampoTexto(master, etiqueta, valor, ancho=campo.get("ancho", 300),
                                 ayuda=ayuda, placeholder=campo.get("placeholder", ""))
        if tipo == "solo_lectura":
            campo_texto.entrada.configure(state="disabled")
        return campo_texto

    def _aceptar(self):
        from tkinter import messagebox

        datos = {}
        for campo in self._campos:
            key, tipo = campo["key"], campo.get("tipo", "texto")
            widget = self._widgets[key]
            if tipo == "bool":
                datos[key] = int(widget.get())
            elif tipo == "porcentaje":
                datos[key] = widget.get_fraccion()
            elif tipo == "entero":
                datos[key] = widget.get_int()
            elif tipo in ("moneda", "decimal"):
                datos[key] = widget.get()
            else:
                datos[key] = widget.get()

            if campo.get("requerido") and not str(datos[key]).strip():
                messagebox.showwarning(
                    "Falta un dato",
                    f"El campo «{campo.get('label', key)}» es obligatorio.", parent=self)
                return

        if self._validador:
            error = self._validador(datos)
            if error:
                messagebox.showwarning("Revisá los datos", error, parent=self)
                return

        self.resultado = datos
        self.destroy()


class _CampoArchivo(_CampoBase):
    def __init__(self, master, etiqueta: str = "", valor: str = "", ayuda: str = "", **kw):
        super().__init__(master, etiqueta, ayuda, **kw)
        marco = ctk.CTkFrame(self, fg_color="transparent")
        marco.grid(row=self._fila, column=0, sticky="ew")
        marco.columnconfigure(0, weight=1)
        self.var = tk.StringVar(value=str(valor or ""))
        ctk.CTkEntry(marco, textvariable=self.var, font=tema.fuente(12)).grid(
            row=0, column=0, sticky="ew")
        ctk.CTkButton(marco, text="Buscar…", width=90, command=self._elegir,
                      fg_color=tema.c("superficie_3"), hover_color=tema.c("borde"),
                      text_color=tema.c("texto")).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(marco, text="Quitar", width=70,
                      command=lambda: self.var.set(""),
                      fg_color="transparent", hover_color=tema.c("superficie_3"),
                      text_color=tema.c("texto_suave")).grid(row=0, column=2, padx=(6, 0))
        self._poner_ayuda(self._fila + 1)

    def _elegir(self):
        from tkinter import filedialog
        ruta = filedialog.askopenfilename(
            title="Seleccionar imagen",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.gif"), ("Todos", "*.*")])
        if ruta:
            self.var.set(ruta)

    def get(self) -> str:
        return self.var.get().strip()


def boton_secundario(master, texto, comando, ancho: int = 120, **kw):
    kw.setdefault("fg_color", tema.c("superficie_3"))
    kw.setdefault("hover_color", tema.c("borde"))
    kw.setdefault("text_color", tema.c("texto"))
    return ctk.CTkButton(master, text=texto, command=comando, width=ancho,
                         font=tema.fuente(12), **kw)


def boton_fantasma(master, texto, comando, ancho: int = 100, **kw):
    kw.setdefault("fg_color", "transparent")
    kw.setdefault("hover_color", tema.c("superficie_3"))
    kw.setdefault("text_color", tema.c("texto_suave"))
    return ctk.CTkButton(master, text=texto, command=comando, width=ancho,
                         font=tema.fuente(12), **kw)
