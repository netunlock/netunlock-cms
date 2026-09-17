"""
Módulo 1 — Carga de materiales y costos base.
"""

from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from core import formato as F
from core.despiece import FUNCIONES_CONOCIDAS, calcular_despiece
from core.formula_engine import AYUDA_VARIABLES, validar
from . import tema
from .componentes import (CampoCombo, DialogoFormulario, Tabla, Tarjeta,
                          boton_fantasma, boton_secundario)
from .vista_despiece import VentanaDespiece

#: 'kg/m' es distinta de las demás: la fórmula del kit da METROS y el precio es
#: $/kg, así que el consumo se factura en kilos (metros x peso lineal). Es la
#: forma de cotizar un accesorio extruido que el proveedor vende por peso.
UNIDADES_ACC = ["u", "jgo", "ml", "m2", "kg", "kg/m"]
MODOS_COSTEO = ["kg", "m2"]


class PanelABM(Tarjeta):
    """Tarjeta con tabla y botonera Nuevo / Editar / Eliminar sobre una tabla SQL."""

    def __init__(self, master, titulo, columnas, cargar, campos, al_guardar,
                 al_borrar=None, extras=(), alto=13, al_elegir=None):
        super().__init__(master, titulo)
        self._cargar = cargar
        self._campos = campos
        self._al_guardar = al_guardar
        self._al_borrar = al_borrar

        acciones = self.zona_acciones
        ctk.CTkButton(acciones, text="+  Nuevo", width=100, height=28,
                      font=tema.fuente(12), command=self.nuevo).pack(side="right")
        for texto, comando in reversed(extras):
            boton_fantasma(acciones, texto, comando, ancho=150).pack(side="right", padx=(0, 6))

        self.cuerpo.columnconfigure(0, weight=1)
        self.cuerpo.rowconfigure(0, weight=1)
        self.tabla = Tabla(self.cuerpo, columnas, alto=alto,
                           al_activar=self.editar, al_elegir=al_elegir)
        self.tabla.grid(row=0, column=0, sticky="nsew")

        barra = ctk.CTkFrame(self.cuerpo, fg_color="transparent")
        barra.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        boton_secundario(barra, "Editar", self.editar, ancho=90).pack(side="left")
        if al_borrar:
            boton_fantasma(barra, "Eliminar", self.borrar, ancho=90).pack(side="left", padx=6)
        self.lbl_info = ctk.CTkLabel(barra, text="", font=tema.fuente(10),
                                     text_color=tema.c("texto_tenue"), anchor="e")
        self.lbl_info.pack(side="right")

        self.refrescar()

    def refrescar(self):
        filas = []
        for fila in self._cargar():
            datos = dict(fila)
            valores = [self._formatear(datos.get(clave), fmt)
                       for clave, _t, _a, fmt in self._columnas_fmt()]
            etiquetas = () if datos.get("activo", 1) else ("inactivo",)
            filas.append((valores, datos, etiquetas))
        self.tabla.cargar(filas)
        self.lbl_info.configure(text=f"{len(filas)} registro(s)")

    def _columnas_fmt(self):
        return [(c[0], c[1], c[3], self._fmt.get(c[0])) for c in self.tabla.columnas]

    _fmt: dict[str, str] = {}

    def formatos(self, mapa: dict[str, str]):
        self._fmt = mapa
        self.refrescar()
        return self

    @staticmethod
    def _formatear(valor, fmt):
        if valor is None:
            return ""
        if fmt == "moneda":
            return F.moneda(valor)
        if fmt == "kg_m":
            return F.kilos_metro(valor)
        if fmt == "mm":
            return F.milimetros(valor)
        if fmt == "pct":
            return F.porcentaje(valor, 1)
        if fmt == "horas":
            return F.horas(valor)
        if fmt == "bool":
            return "Sí" if valor else "No"
        if fmt == "num":
            return F.numero(valor, 2, quitar_ceros=True)
        return str(valor)

    def seleccionado(self):
        return self.tabla.seleccionado()

    def nuevo(self):
        dialogo = DialogoFormulario(self.winfo_toplevel(), "Nuevo registro", self._campos(None))
        if dialogo.resultado is not None:
            self._al_guardar(None, dialogo.resultado)
            self.refrescar()

    def editar(self):
        fila = self.seleccionado()
        if not fila:
            messagebox.showinfo("Sin selección", "Elegí una fila de la lista.")
            return
        dialogo = DialogoFormulario(self.winfo_toplevel(), "Editar registro",
                                    self._campos(fila), fila)
        if dialogo.resultado is not None:
            self._al_guardar(fila.get("id"), dialogo.resultado)
            self.refrescar()

    def borrar(self):
        fila = self.seleccionado()
        if not fila:
            messagebox.showinfo("Sin selección", "Elegí una fila de la lista.")
            return
        if messagebox.askyesno("Confirmar", "¿Eliminar el registro seleccionado?"):
            self._al_borrar(fila["id"])
            self.refrescar()


class FichaPerfil(Tarjeta):
    """Ficha de catálogo del perfil elegido: dibujo de la sección y sus datos.

    Es lo que convierte la lista de perfiles en un catálogo consultable: se elige
    una fila y acá se ve el corte del perfil, como en la hoja del extrusor.
    """

    ANCHO_IMAGEN = 260
    ALTO_IMAGEN = 240

    def __init__(self, master):
        super().__init__(master, "Ficha del perfil", width=self.ANCHO_IMAGEN + 56)
        self.pack_propagate(False)
        self._imagen = None  # referencia viva: Tk descarta la imagen si se libera

        self.lbl_imagen = ctk.CTkLabel(
            self.cuerpo, text="", width=self.ANCHO_IMAGEN, height=self.ALTO_IMAGEN,
            fg_color=tema.c("superficie_2"), corner_radius=tema.RADIO)
        self.lbl_imagen.pack(fill="x")

        self.lbl_codigo = ctk.CTkLabel(self.cuerpo, text="", font=tema.fuente(18, "bold"),
                                       text_color=tema.c("texto"), anchor="w")
        self.lbl_codigo.pack(fill="x", pady=(10, 0))
        self.lbl_desc = ctk.CTkLabel(self.cuerpo, text="", font=tema.fuente(12),
                                     text_color=tema.c("texto_suave"), anchor="w",
                                     justify="left", wraplength=self.ANCHO_IMAGEN)
        self.lbl_desc.pack(fill="x")
        self.lbl_datos = ctk.CTkLabel(self.cuerpo, text="", font=tema.fuente(11),
                                      text_color=tema.c("texto_tenue"), anchor="w",
                                      justify="left", wraplength=self.ANCHO_IMAGEN)
        self.lbl_datos.pack(fill="x", pady=(8, 0))

        self.mostrar(None)

    def mostrar(self, fila):
        if not fila:
            self._poner_imagen(None)
            self.lbl_codigo.configure(text="—")
            self.lbl_desc.configure(text="Elegí un perfil de la lista.")
            self.lbl_datos.configure(text="")
            return

        self.lbl_codigo.configure(text=str(fila.get("codigo", "")))
        self.lbl_desc.configure(text=str(fila.get("descripcion", "") or ""))

        renglones = []
        if fila.get("familia"):
            renglones.append(f"Familia:  {fila['familia']}")
        renglones.append(f"Peso:  {F.kilos_metro(fila.get('peso_kg_m') or 0)}")
        renglones.append(f"Barra:  {F.milimetros(fila.get('largo_barra_mm') or 0)}")
        if fila.get("notas"):
            renglones.append("")
            renglones.append(str(fila["notas"]))
        self.lbl_datos.configure(text="\n".join(renglones))

        self._poner_imagen(fila.get("imagen"))

    def _poner_imagen(self, nombre):
        from core import imagenes

        ruta = imagenes.ruta_de(nombre)
        if ruta is None:
            self._imagen = None
            self.lbl_imagen.configure(
                image=None,
                text="Sin dibujo\n\nEditá el perfil y cargá\nla imagen de la sección.",
                font=tema.fuente(11), text_color=tema.c("texto_tenue"))
            return

        try:
            from PIL import Image
        except ImportError:
            self._imagen = None
            self.lbl_imagen.configure(image=None, text="Falta Pillow\n(pip install pillow)",
                                      font=tema.fuente(11))
            return

        try:
            with Image.open(ruta) as img:
                img.load()
                # thumbnail respeta la proporción: un perfil alto y angosto no se
                # deforma para llenar el recuadro.
                img.thumbnail((self.ANCHO_IMAGEN, self.ALTO_IMAGEN))
                self._imagen = ctk.CTkImage(light_image=img.copy(), dark_image=img.copy(),
                                            size=img.size)
        except OSError:
            self._imagen = None
            self.lbl_imagen.configure(image=None, text="No se pudo abrir el dibujo",
                                      font=tema.fuente(11))
            return

        self.lbl_imagen.configure(image=self._imagen, text="")


class VistaMateriales(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.db = app.db

        self.pestanias = ctk.CTkTabview(
            self, fg_color=tema.c("superficie"),
            segmented_button_selected_color=tema.c("primario"),
            segmented_button_selected_hover_color=tema.c("primario_hover"))
        self.pestanias.pack(fill="both", expand=True)

        self._panel_lineas(self.pestanias.add("  Líneas y precios  "))
        self._panel_perfiles(self.pestanias.add("  Perfiles  "))
        self._panel_vidrios(self.pestanias.add("  Vidrios  "))
        self._panel_accesorios(self.pestanias.add("  Accesorios  "))
        self._panel_kits(self.pestanias.add("  Kits  "))
        self._panel_tipologias(self.pestanias.add("  Tipologías  "))
        self._panel_formulas(self.pestanias.add("  Fórmulas de despiece  "))
        self._panel_parametros(self.pestanias.add("  Costos operativos  "))

    # =====================================================================
    # Líneas y precios por color
    # =====================================================================

    def _panel_lineas(self, hoja):
        hoja.columnconfigure(0, weight=3)
        hoja.columnconfigure(1, weight=4)
        hoja.rowconfigure(0, weight=1)

        def campos(_fila):
            return [
                {"key": "nombre", "label": "Nombre de la línea", "requerido": True},
                {"key": "descripcion", "label": "Descripción"},
                {"key": "extrusora", "label": "Extrusora",
                 "placeholder": "Aluar · Hydro · Alcemar…",
                 "ayuda": "Sólo informativo: identifica de quién es el catálogo."},
                {"key": "modo_costeo", "label": "Modo de costeo", "tipo": "combo",
                 "opciones": MODOS_COSTEO, "default": "kg",
                 "ayuda": "kg = por peso del despiece (recomendado) · "
                          "m2 = precio por m² de abertura, como la planilla Excel"},
                {"key": "activo", "label": "Línea activa", "tipo": "bool", "default": 1},
            ]

        def guardar(id_, datos):
            if id_:
                self.db.actualizar("lineas", id_, datos)
            else:
                self.db.insertar("lineas", datos)
            self.app.recargar_catalogos()

        self.abm_lineas = PanelABM(
            hoja, "Líneas de aluminio",
            [("nombre", "Línea", 160, "w"), ("modo_costeo", "Costeo", 80, "center"),
             ("descripcion", "Descripción", 230, "w"), ("activo", "Activa", 70, "center")],
            cargar=lambda: self.db.query("SELECT * FROM lineas ORDER BY nombre"),
            campos=campos, al_guardar=guardar,
            al_borrar=lambda i: (self.db.borrar("lineas", i), self.app.recargar_catalogos()),
            al_elegir=lambda: self.abm_precios.refrescar(),
            extras=(("Duplicar sistema…", self._duplicar_linea),
                    ("Importar JSON…", lambda: self._importar_json("lineas"))),
        ).formatos({"activo": "bool"})
        self.abm_lineas.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=6)

        def linea_actual():
            fila = self.abm_lineas.seleccionado()
            return fila["id"] if fila else 0

        def cargar_precios():
            lid = linea_actual()
            return self.db.query(
                "SELECT * FROM linea_precios WHERE linea_id = ? ORDER BY color", (lid,)
            ) if lid else []

        def campos_precio(_fila):
            return [
                {"key": "color", "label": "Color / Terminación", "requerido": True},
                {"key": "precio_kg", "label": "Precio del aluminio", "tipo": "moneda",
                 "unidad": "moneda_kg",
                 "ayuda": "Se usa cuando la línea cotiza en modo 'kg'"},
                {"key": "precio_m2_perfil", "label": "Precio de perfil por m²",
                 "tipo": "moneda", "unidad": "moneda_m2",
                 "ayuda": "Se usa cuando la línea cotiza en modo 'm2'"},
                {"key": "activo", "label": "Activo", "tipo": "bool", "default": 1},
            ]

        def guardar_precio(id_, datos):
            lid = linea_actual()
            if not lid:
                messagebox.showinfo("Elegí una línea", "Seleccioná primero una línea.")
                return
            datos["linea_id"] = lid
            if id_:
                self.db.actualizar("linea_precios", id_, datos)
            else:
                self.db.insertar("linea_precios", datos)
            self.app.recargar_catalogos()

        self.abm_precios = PanelABM(
            hoja, "Colores y precios de la línea seleccionada",
            [("color", "Color", 190, "w"), ("precio_kg", "Precio", 150, "e"),
             ("precio_m2_perfil", "Precio por m²", 160, "e"),
             ("activo", "Activo", 70, "center")],
            cargar=cargar_precios, campos=campos_precio, al_guardar=guardar_precio,
            al_borrar=lambda i: (self.db.borrar("linea_precios", i),
                                 self.app.recargar_catalogos()),
        ).formatos({"precio_kg": "moneda", "precio_m2_perfil": "moneda", "activo": "bool"})
        self.abm_precios.grid(row=0, column=1, sticky="nsew", pady=6)

    def _duplicar_linea(self):
        """Clona la línea seleccionada con todo lo que cuelga de ella."""
        fila = self.abm_lineas.seleccionado()
        if fila is None:
            messagebox.showinfo("Elegí una línea",
                                "Seleccioná la línea que querés duplicar.")
            return

        resumen = self.db.resumen_linea(fila["id"])
        detalle = (f"{resumen['perfiles']} perfiles · {resumen['colores']} colores · "
                   f"{resumen['formulas']} fórmulas · "
                   f"{resumen['formulas_vidrio']} fórmulas de vidrio · "
                   f"{resumen['kits']} kits")

        dialogo = DialogoFormulario(
            self.winfo_toplevel(), f"Duplicar «{fila['nombre']}»",
            [{"key": "nombre", "label": "Nombre de la línea nueva", "requerido": True,
              "default": f"{fila['nombre']} (copia)",
              "ayuda": f"Se copian: {detalle}.\n"
                       "Los vidrios, accesorios y tipologías son globales: se "
                       "comparten, no se duplican."}])
        if dialogo.resultado is None:
            return

        try:
            nueva = self.db.duplicar_linea(fila["id"], dialogo.resultado["nombre"])
        except ValueError as exc:
            messagebox.showerror("No se pudo duplicar", str(exc))
            return

        self.abm_lineas.refrescar()
        self.app.recargar_catalogos()
        nuevo_resumen = self.db.resumen_linea(nueva)
        messagebox.showinfo(
            "Sistema duplicado",
            f"Se creó «{dialogo.resultado['nombre']}» con:\n\n"
            f"   {nuevo_resumen['perfiles']} perfiles\n"
            f"   {nuevo_resumen['colores']} colores con precio\n"
            f"   {nuevo_resumen['formulas']} fórmulas de despiece\n"
            f"   {nuevo_resumen['kits']} kits de accesorios\n\n"
            "Revisá los precios por color antes de cotizar con ella.")

    def _importar_json(self, seccion: str = ""):
        """Importa un catálogo JSON (líneas, perfiles, vidrios, accesorios…)."""
        from tkinter import filedialog

        from tools import importar_json as imp

        ruta = filedialog.askopenfilename(
            title="Catálogo en JSON",
            filetypes=[("Archivos JSON", "*.json"), ("Todos", "*.*")])
        if not ruta:
            return

        analisis = imp.analizar(self.db, ruta)
        if analisis.errores:
            messagebox.showerror("No se pudo leer el catálogo",
                                 imp.resumen_texto(analisis))
            return
        if not analisis.valido:
            messagebox.showwarning("Nada para importar", imp.resumen_texto(analisis))
            return

        if not messagebox.askyesno(
                "Confirmar importación",
                f"{imp.resumen_texto(analisis)}\n\n"
                "Lo que ya existe se actualiza; nada se borra.\n\n¿Importar?"):
            return

        # Un catálogo puede tocar cientos de registros de una: si algo sale mal,
        # el respaldo es la única vuelta atrás.
        self.db.respaldar("antes_de_importar_json")
        try:
            resultado = imp.importar(self.db, analisis)
        except Exception as exc:
            messagebox.showerror("Error al importar", str(exc))
            return

        self.app.recargar_catalogos()
        self._refrescar_todo()
        messagebox.showinfo("Catálogo importado", imp.resumen_texto(analisis, resultado))

    def _refrescar_todo(self):
        """Recarga las tablas de esta vista tras una importación masiva."""
        for atributo in ("abm_lineas", "abm_precios", "abm_perfiles", "abm_formulas",
                         "abm_kits", "abm_kit_items"):
            panel = getattr(self, atributo, None)
            if panel is not None:
                try:
                    panel.refrescar()
                except Exception:
                    pass

    # =====================================================================
    # Perfiles
    # =====================================================================

    def _panel_perfiles(self, hoja):
        hoja.columnconfigure(0, weight=3)
        hoja.columnconfigure(1, weight=0)
        hoja.rowconfigure(1, weight=1)

        barra = ctk.CTkFrame(hoja, fg_color="transparent")
        barra.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        nombres = [l["nombre"] for l in self.db.lineas()]
        # Arranca en la primera línea: si el combo queda vacío la tabla se ve
        # vacía y parece que no hay perfiles cargados.
        self.combo_perfil_linea = CampoCombo(
            barra, "Línea", nombres, valor=nombres[0] if nombres else "", ancho=240,
            al_cambiar=lambda: self.abm_perfiles.refrescar())
        self.combo_perfil_linea.pack(side="left")

        def cargar():
            lid = self._id_linea(self.combo_perfil_linea.get())
            return self.db.query(
                "SELECT p.*, l.nombre AS linea FROM perfiles p "
                "LEFT JOIN lineas l ON l.id = p.linea_id WHERE p.linea_id = ? "
                "ORDER BY p.familia, p.codigo", (lid,)) if lid else []

        def campos(_fila):
            return [
                {"key": "codigo", "label": "Código del perfil", "requerido": True},
                {"key": "descripcion", "label": "Descripción"},
                {"key": "familia", "label": "Familia", "tipo": "combo",
                 "opciones": self._familias_de_linea(),
                 "ayuda": "Agrupa el catálogo: Marcos, Hojas, Contravidrios…"},
                {"key": "peso_kg_m", "label": "Peso nominal", "tipo": "decimal",
                 "unidad": "kilos_metro", "decimales": 3,
                 "ayuda": "Dato del catálogo del extrusor. Define el peso del despiece "
                          "y, con él, el costo del aluminio."},
                {"key": "largo_barra_mm", "label": "Largo de barra", "tipo": "entero",
                 "unidad": "milimetros", "default": 6000},
                {"key": "imagen", "label": "Dibujo de la sección", "tipo": "archivo",
                 "ayuda": "Se copia a la carpeta de datos, así el dibujo no se pierde "
                          "si después movés el archivo original."},
                {"key": "notas", "label": "Notas", "tipo": "memo", "alto": 70},
            ]

        def guardar(id_, datos):
            lid = self._id_linea(self.combo_perfil_linea.get())
            if not lid:
                messagebox.showinfo("Elegí una línea", "Seleccioná la línea primero.")
                return
            datos["linea_id"] = lid
            datos["imagen"] = self._guardar_imagen(
                datos.get("imagen", ""), self.combo_perfil_linea.get(),
                datos.get("codigo", ""))
            if id_:
                self.db.actualizar("perfiles", id_, datos)
            else:
                self.db.insertar("perfiles", datos)
            self.ficha_perfil.mostrar(None)

        self.abm_perfiles = PanelABM(
            hoja, "Perfiles de la línea",
            [("codigo", "Código", 110, "w"), ("descripcion", "Descripción", 280, "w"),
             ("familia", "Familia", 120, "w"),
             ("peso_kg_m", "Peso lineal", 130, "e"), ("largo_barra_mm", "Barra", 110, "e")],
            cargar=cargar, campos=campos, al_guardar=guardar,
            al_borrar=lambda i: self.db.borrar("perfiles", i), alto=16,
            extras=(("Importar catálogo…", self._importar_catalogo),),
            al_elegir=lambda: self.ficha_perfil.mostrar(self.abm_perfiles.seleccionado()),
        ).formatos({"peso_kg_m": "kg_m", "largo_barra_mm": "mm"})
        self.abm_perfiles.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=6)

        self.ficha_perfil = FichaPerfil(hoja)
        self.ficha_perfil.grid(row=1, column=1, sticky="nsew", pady=6)

    def _familias_de_linea(self) -> list[str]:
        lid = self._id_linea(self.combo_perfil_linea.get())
        filas = self.db.query(
            "SELECT DISTINCT familia FROM perfiles WHERE linea_id = ? AND familia <> '' "
            "ORDER BY familia", (lid,)) if lid else []
        return [""] + [f["familia"] for f in filas]

    @staticmethod
    def _guardar_imagen(elegido: str, linea_nombre: str, codigo: str) -> str:
        """Copia la imagen elegida a la carpeta de datos y devuelve el nombre a guardar."""
        from core import imagenes

        elegido = (elegido or "").strip()
        if not elegido:
            return ""
        # Si el valor no cambió, ya es un nombre relativo: no hay nada que copiar.
        if not Path(elegido).is_absolute() and imagenes.ruta_de(elegido):
            return elegido
        try:
            return imagenes.guardar(elegido, linea_nombre, codigo)
        except (ValueError, OSError) as exc:
            messagebox.showwarning("No se pudo guardar la imagen", str(exc))
            return ""

    def _importar_catalogo(self):
        from tkinter import filedialog

        from tools import importar_catalogo as imp

        lid = self._id_linea(self.combo_perfil_linea.get())
        if not lid:
            messagebox.showinfo("Elegí una línea", "Seleccioná primero la línea de destino.")
            return

        ruta = filedialog.askopenfilename(
            title="Catálogo de perfiles (Excel)",
            filetypes=[("Planillas de Excel", "*.xlsx *.xlsm"), ("Todos", "*.*")])
        if not ruta:
            return

        try:
            analisis = imp.analizar(ruta)
        except ImportError:
            messagebox.showerror(
                "Falta openpyxl",
                "Para leer planillas de Excel hace falta la librería openpyxl.\n\n"
                "Instalala con:   pip install openpyxl")
            return
        except Exception as exc:                     # archivo corrupto, protegido, etc.
            messagebox.showerror("No se pudo leer la planilla", str(exc))
            return

        if not analisis.validas:
            messagebox.showwarning("Sin perfiles para importar",
                                   imp.resumen_texto(analisis))
            return

        muestra = "\n".join(
            f"   {f.codigo:<12} {f.descripcion[:34]:<36} {f.peso_kg_m:.3f} kg/m   "
            f"{f.largo_barra_mm} mm"
            for f in analisis.validas[:12])
        if len(analisis.validas) > 12:
            muestra += f"\n   … y {len(analisis.validas) - 12} más"

        confirmar = messagebox.askyesno(
            "Confirmar importación",
            f"{imp.resumen_texto(analisis)}\n\n{muestra}\n\n"
            f"Se van a cargar en la línea «{self.combo_perfil_linea.get()}».\n"
            "Los códigos que ya existan se actualizan; ninguno se borra.\n\n"
            "¿Importar?")
        if not confirmar:
            return

        resultado = imp.importar(self.db, lid, analisis.validas)
        self.abm_perfiles.refrescar()
        messagebox.showinfo("Catálogo importado", imp.resumen_texto(analisis, resultado))

    # =====================================================================
    # Vidrios
    # =====================================================================

    def _panel_vidrios(self, hoja):
        hoja.columnconfigure(0, weight=1)
        hoja.rowconfigure(0, weight=1)

        def campos(_fila):
            return [
                {"key": "nombre", "label": "Denominación", "requerido": True,
                 "placeholder": "Float 4mm · DVH 4/9/4 · Laminado 3+3"},
                {"key": "tipo", "label": "Tipo", "tipo": "combo",
                 "opciones": ["Float", "Laminado", "DVH", "Templado", "Espejo"],
                 "default": "Float"},
                {"key": "espesor_mm", "label": "Espesor total", "tipo": "decimal",
                 "unidad": "milimetros", "decimales": 1},
                {"key": "precio_m2", "label": "Precio", "tipo": "moneda",
                 "unidad": "moneda_m2", "requerido": True},
                {"key": "plancha_ancho_mm", "label": "Plancha base · ancho", "tipo": "entero",
                 "unidad": "milimetros", "default": 3600},
                {"key": "plancha_alto_mm", "label": "Plancha base · alto", "tipo": "entero",
                 "unidad": "milimetros", "default": 2500},
                {"key": "precio_plancha", "label": "Precio por plancha", "tipo": "moneda",
                 "ayuda": "Informativo. Si lo dejás en 0 se recalcula desde el precio por m²."},
                {"key": "desperdicio_pct", "label": "Desperdicio de plancha",
                 "tipo": "porcentaje", "default": 0.10},
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

        PanelABM(
            hoja, "Tipos de vidrio",
            [("nombre", "Denominación", 190, "w"), ("tipo", "Tipo", 110, "w"),
             ("espesor_mm", "Espesor", 110, "e"), ("precio_m2", "Precio por m²", 150, "e"),
             ("plancha_ancho_mm", "Plancha ancho", 130, "e"),
             ("plancha_alto_mm", "Plancha alto", 130, "e"),
             ("precio_plancha", "Precio plancha", 150, "e"),
             ("desperdicio_pct", "Desperdicio", 110, "e"),
             ("activo", "Activo", 70, "center")],
            cargar=lambda: self.db.query("SELECT * FROM vidrios ORDER BY nombre"),
            campos=campos, al_guardar=guardar,
            al_borrar=lambda i: (self.db.borrar("vidrios", i), self.app.recargar_catalogos()),
            alto=16,
            extras=(("Importar JSON…", lambda: self._importar_json("vidrios")),),
        ).formatos({"espesor_mm": "mm", "precio_m2": "moneda", "plancha_ancho_mm": "mm",
                    "plancha_alto_mm": "mm", "precio_plancha": "moneda",
                    "desperdicio_pct": "pct", "activo": "bool"}
                   ).grid(row=0, column=0, sticky="nsew", pady=6)

    # =====================================================================
    # Accesorios
    # =====================================================================

    def _panel_accesorios(self, hoja):
        hoja.columnconfigure(0, weight=1)
        hoja.rowconfigure(0, weight=1)

        def campos(_fila):
            return [
                {"key": "codigo", "label": "Código", "requerido": True},
                {"key": "descripcion", "label": "Descripción"},
                {"key": "unidad", "label": "Unidad", "tipo": "combo",
                 "opciones": UNIDADES_ACC, "default": "u",
                 "ayuda": "u / jgo se redondean hacia arriba · ml, m2 y kg admiten "
                          "decimales · kg/m: la fórmula da metros y se factura por peso"},
                {"key": "precio", "label": "Precio unitario", "tipo": "moneda",
                 "unidad": "moneda_ud",
                 "ayuda": "Con unidad 'kg/m' este precio es el $/kg del proveedor"},
                {"key": "peso_kg_m", "label": "Peso lineal", "tipo": "decimal",
                 "unidad": "kilos_metro", "decimales": 3,
                 "ayuda": "Sólo para unidad 'kg/m': convierte los metros de la "
                          "fórmula en kilos facturables"},
                {"key": "activo", "label": "Activo", "tipo": "bool", "default": 1},
            ]

        def guardar(id_, datos):
            # Un accesorio en kg/m sin peso lineal se cotiza en cero y nadie se
            # entera hasta ver la factura: mejor frenarlo acá.
            if datos.get("unidad") == "kg/m" and not datos.get("peso_kg_m"):
                messagebox.showwarning(
                    "Falta el peso lineal",
                    "Un accesorio con unidad «kg/m» necesita el peso lineal para "
                    "poder costearse.\n\nCargá los Kg/m que figuran en el catálogo "
                    "del proveedor.")
                return
            if id_:
                self.db.actualizar("accesorios", id_, datos)
            else:
                self.db.insertar("accesorios", datos)

        PanelABM(
            hoja, "Accesorios — ruedas, cierres, felpas, burletes, escuadras",
            [("codigo", "Código", 140, "w"), ("descripcion", "Descripción", 360, "w"),
             ("unidad", "Unidad", 80, "center"), ("precio", "Precio", 150, "e"),
             ("peso_kg_m", "Peso lineal", 120, "e"),
             ("activo", "Activo", 70, "center")],
            cargar=lambda: self.db.query("SELECT * FROM accesorios ORDER BY codigo"),
            campos=campos, al_guardar=guardar,
            al_borrar=lambda i: self.db.borrar("accesorios", i), alto=16,
            extras=(("Importar JSON…", lambda: self._importar_json("accesorios")),),
        ).formatos({"precio": "moneda", "peso_kg_m": "kg_m", "activo": "bool"}
                   ).grid(row=0, column=0, sticky="nsew", pady=6)

    # =====================================================================
    # Kits
    # =====================================================================

    def _panel_kits(self, hoja):
        hoja.columnconfigure(0, weight=3)
        hoja.columnconfigure(1, weight=4)
        hoja.rowconfigure(0, weight=1)

        def cargar_kits():
            return [dict(f, linea_txt=f["linea"] or "") for f in self.db.query(
                "SELECT k.*, l.nombre AS linea FROM kits k "
                "LEFT JOIN lineas l ON l.id = k.linea_id ORDER BY l.nombre, k.nombre")]

        def campos_kit(_fila):
            return [
                {"key": "nombre", "label": "Nombre del kit", "requerido": True},
                {"key": "linea_txt", "label": "Línea", "tipo": "combo",
                 "opciones": [l["nombre"] for l in self.db.lineas()]},
                {"key": "tipologia_codigo", "label": "Tipología", "tipo": "combo",
                 "opciones": [""] + [t["codigo"] for t in self.db.tipologias()],
                 "ayuda": "Vacío = kit por defecto para toda la línea"},
                {"key": "descripcion", "label": "Descripción"},
                {"key": "activo", "label": "Activo", "tipo": "bool", "default": 1},
            ]

        def guardar_kit(id_, datos):
            datos = dict(datos)
            datos["linea_id"] = self._id_linea(datos.pop("linea_txt", ""))
            if id_:
                self.db.actualizar("kits", id_, datos)
            else:
                self.db.insertar("kits", datos)

        self.abm_kits = PanelABM(
            hoja, "Kits de accesorios",
            [("nombre", "Kit", 200, "w"), ("linea", "Línea", 150, "w"),
             ("tipologia_codigo", "Tipología", 100, "center"),
             ("activo", "Activo", 70, "center")],
            cargar=cargar_kits, campos=campos_kit, al_guardar=guardar_kit,
            al_borrar=lambda i: self.db.borrar("kits", i),
            al_elegir=lambda: self.abm_kit_items.refrescar(),
        ).formatos({"activo": "bool"})
        self.abm_kits.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=6)

        def kit_actual():
            fila = self.abm_kits.seleccionado()
            return fila["id"] if fila else 0

        def cargar_items():
            kid = kit_actual()
            if not kid:
                return []
            return [dict(f, accesorio=f"{f['codigo']} — {f['descripcion']}")
                    for f in self.db.items_de_kit(kid)]

        def campos_item(_fila):
            accesorios = self.db.accesorios()
            return [
                {"key": "accesorio", "label": "Accesorio", "tipo": "combo", "requerido": True,
                 "opciones": [f"{a['codigo']} — {a['descripcion']}" for a in accesorios]},
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
            accesorio = self.db.query_one("SELECT id FROM accesorios WHERE codigo = ?", (codigo,))
            if not accesorio:
                return
            registro = {"kit_id": kid, "accesorio_id": accesorio["id"],
                        "cantidad_formula": datos["cantidad_formula"]}
            if id_:
                self.db.actualizar("kit_items", id_, registro)
            else:
                self.db.insertar("kit_items", registro)

        self.abm_kit_items = PanelABM(
            hoja, "Composición del kit seleccionado",
            [("codigo", "Código", 120, "w"), ("descripcion", "Accesorio", 260, "w"),
             ("unidad", "Un.", 70, "center"),
             ("cantidad_formula", "Cantidad (fórmula)", 200, "w"),
             ("precio", "Precio", 140, "e")],
            cargar=cargar_items, campos=campos_item, al_guardar=guardar_item,
            al_borrar=lambda i: self.db.borrar("kit_items", i),
        ).formatos({"precio": "moneda"})
        self.abm_kit_items.grid(row=0, column=1, sticky="nsew", pady=6)

    # =====================================================================
    # Tipologías
    # =====================================================================

    def _panel_tipologias(self, hoja):
        hoja.columnconfigure(0, weight=1)
        hoja.rowconfigure(0, weight=1)

        def campos(_fila):
            return [
                {"key": "codigo", "label": "Código", "requerido": True,
                 "ayuda": "Vincula fórmulas y kits. Ej.: COR2, BAT1, FIJO"},
                {"key": "nombre", "label": "Nombre", "requerido": True},
                {"key": "hojas_default", "label": "Hojas por defecto", "tipo": "entero",
                 "default": 2},
                {"key": "esquema", "label": "Dibujo en el PDF", "tipo": "combo",
                 "opciones": ["corrediza", "fijo", "batiente", "banderola", "puerta_batiente"],
                 "default": "corrediza",
                 "ayuda": "Esquema que dibuja el programa. Sólo se usa si no hay "
                          "imagen propia cargada abajo."},
                {"key": "imagen", "label": "Imagen de la abertura", "tipo": "archivo",
                 "ayuda": "Reemplaza al esquema en el presupuesto y en la orden de "
                          "trabajo. Sirve para tipologías compuestas, que el dibujo "
                          "automático no sabe representar."},
                {"key": "horas_por_m2", "label": "Fabricación por m²", "tipo": "decimal",
                 "unidad": "horas", "default": 0.85},
                {"key": "admite_mosquitero", "label": "Admite mosquitero", "tipo": "bool",
                 "default": 1},
                {"key": "admite_premarco", "label": "Admite premarco", "tipo": "bool",
                 "default": 1},
                {"key": "activo", "label": "Activa", "tipo": "bool", "default": 1},
            ]

        def guardar(id_, datos):
            datos = dict(datos)
            datos["imagen"] = self._guardar_imagen(
                datos.get("imagen", ""), "tipologia", datos.get("codigo", ""))
            if id_:
                self.db.actualizar("tipologias", id_, datos)
            else:
                self.db.insertar("tipologias", datos)
            self.app.recargar_catalogos()

        PanelABM(
            hoja, "Tipologías de abertura",
            [("codigo", "Código", 100, "w"), ("nombre", "Nombre", 300, "w"),
             ("hojas_default", "Hojas", 80, "center"), ("esquema", "Esquema", 130, "w"),
             ("imagen", "Imagen", 130, "w"),
             ("horas_por_m2", "Fabricación / m²", 150, "e"),
             ("admite_mosquitero", "Mosquitero", 110, "center"),
             ("admite_premarco", "Premarco", 100, "center"),
             ("activo", "Activa", 70, "center")],
            cargar=lambda: self.db.query("SELECT * FROM tipologias ORDER BY nombre"),
            campos=campos, al_guardar=guardar,
            al_borrar=lambda i: (self.db.borrar("tipologias", i),
                                 self.app.recargar_catalogos()), alto=16,
        ).formatos({"horas_por_m2": "horas", "admite_mosquitero": "bool",
                    "admite_premarco": "bool", "activo": "bool"}
                   ).grid(row=0, column=0, sticky="nsew", pady=6)

    # =====================================================================
    # Fórmulas de despiece
    # =====================================================================

    def _panel_formulas(self, hoja):
        hoja.columnconfigure(0, weight=1)
        hoja.rowconfigure(2, weight=1)

        barra = ctk.CTkFrame(hoja, fg_color="transparent")
        barra.grid(row=0, column=0, sticky="ew", pady=(8, 0))

        self.combo_f_tip = CampoCombo(
            barra, "Tipología", [f"{t['codigo']} — {t['nombre']}" for t in self.db.tipologias()],
            ancho=270, al_cambiar=lambda: self.abm_formulas.refrescar())
        self.combo_f_tip.pack(side="left", padx=(0, 14))

        self.combo_f_linea = CampoCombo(
            barra, "Línea", ["(Genérica — todas las líneas)"] +
            [l["nombre"] for l in self.db.lineas()], ancho=230,
            al_cambiar=lambda: self.abm_formulas.refrescar())
        self.combo_f_linea.pack(side="left")

        ctk.CTkLabel(hoja, text=AYUDA_VARIABLES, font=tema.fuente(10),
                     text_color=tema.c("texto_tenue"), justify="left",
                     anchor="w").grid(row=1, column=0, sticky="w", pady=(8, 0))

        def es_generica():
            return self.combo_f_linea.get().startswith("(")

        def cargar():
            tip = self._codigo_tipologia()
            if not tip:
                return []
            if es_generica():
                return self.db.query(
                    "SELECT * FROM tipologia_formulas WHERE tipologia_codigo = ? "
                    "AND linea_id IS NULL ORDER BY orden, id", (tip,))
            return self.db.query(
                "SELECT * FROM tipologia_formulas WHERE tipologia_codigo = ? AND linea_id = ? "
                "ORDER BY orden, id", (tip, self._id_linea(self.combo_f_linea.get())))

        def campos(_fila):
            lid = self._id_linea(self.combo_f_linea.get())
            perfiles = self.db.query(
                "SELECT codigo FROM perfiles WHERE linea_id = ? ORDER BY codigo",
                (lid,)) if lid else []
            return [
                {"key": "perfil_codigo", "label": "Perfil", "requerido": True,
                 "tipo": "combo" if perfiles else "texto",
                 "opciones": [p["codigo"] for p in perfiles]},
                {"key": "funcion", "label": "Función", "tipo": "combo",
                 "opciones": FUNCIONES_CONOCIDAS, "default": "MARCO_HORIZONTAL",
                 "ayuda": "HOJA_HORIZONTAL define AH y HOJA_VERTICAL define HH, "
                          "que usan las fórmulas de vidrio"},
                {"key": "formula_largo", "label": "Fórmula del largo (mm)", "requerido": True,
                 "ayuda": "Ej.:  A  ·  H - 48  ·  (A + 26) / N"},
                {"key": "cantidad_piezas", "label": "Cantidad de piezas", "default": "1",
                 "ayuda": "Ej.:  2  ·  2*N"},
                {"key": "nota", "label": "Aclaración", "tipo": "texto",
                 "placeholder": "Refuerzo de parante · Tapajunta superior…",
                 "ayuda": "Obligatoria con la función OTRO: es lo único que le dice "
                          "al taller qué es esa pieza. En el resto es opcional."},
                {"key": "peso_kg_m", "label": "Peso lineal de respaldo", "tipo": "decimal",
                 "unidad": "kilos_metro", "decimales": 3,
                 "ayuda": "Sólo se usa si el perfil no está cargado en la línea"},
                {"key": "orden", "label": "Orden", "tipo": "entero", "default": 0},
            ]

        def guardar(id_, datos):
            tip = self._codigo_tipologia()
            if not tip:
                return
            for clave in ("formula_largo", "cantidad_piezas"):
                ok, detalle = validar(datos[clave])
                if not ok:
                    messagebox.showerror("Fórmula inválida", f"{clave}: {detalle}")
                    return
            # "OTRO" sin aclaración es una pieza anónima en la orden de trabajo:
            # el operario ve un largo y un código, y no sabe qué está cortando.
            if datos.get("funcion") == "OTRO" and not (datos.get("nota") or "").strip():
                messagebox.showwarning(
                    "Falta la aclaración",
                    "La función OTRO no dice qué es la pieza.\n\n"
                    "Escribí una aclaración (por ejemplo «refuerzo de parante "
                    "central») para que se entienda en el despiece y en la orden "
                    "de trabajo.")
                return
            datos = dict(datos)
            datos["tipologia_codigo"] = tip
            datos["linea_id"] = None if es_generica() else self._id_linea(self.combo_f_linea.get())
            if id_:
                self.db.actualizar("tipologia_formulas", id_, datos)
            else:
                self.db.insertar("tipologia_formulas", datos)

        self.abm_formulas = PanelABM(
            hoja, "Tipologias_Formulas — despiece paramétrico",
            [("orden", "#", 50, "center"), ("perfil_codigo", "Perfil", 120, "w"),
             ("funcion", "Función", 170, "w"),
             ("nota", "Aclaración", 190, "w"),
             ("formula_largo", "Fórmula del largo", 200, "w"),
             ("cantidad_piezas", "Cantidad", 120, "w"),
             ("peso_kg_m", "Peso lineal", 130, "e")],
            cargar=cargar, campos=campos, al_guardar=guardar,
            al_borrar=lambda i: self.db.borrar("tipologia_formulas", i),
            extras=[("Probar despiece…", self._probar_despiece),
                    ("Fórmulas de vidrio…", self._formula_vidrio),
                    ("Copiar a otra línea…", self._duplicar_formulas)],
            alto=12,
        ).formatos({"peso_kg_m": "kg_m"})
        self.abm_formulas.grid(row=2, column=0, sticky="nsew", pady=6)

    def _formula_vidrio(self):
        tip = self._codigo_tipologia()
        if not tip:
            return
        generica = self.combo_f_linea.get().startswith("(")
        lid = None if generica else self._id_linea(self.combo_f_linea.get())

        if lid is None:
            fila = self.db.query_one(
                "SELECT * FROM vidrio_formulas WHERE tipologia_codigo = ? AND linea_id IS NULL",
                (tip,))
        else:
            fila = self.db.query_one(
                "SELECT * FROM vidrio_formulas WHERE tipologia_codigo = ? AND linea_id = ?",
                (tip, lid))

        dialogo = DialogoFormulario(
            self.winfo_toplevel(), f"Fórmulas de vidrio — {tip}",
            [{"key": "formula_ancho", "label": "Ancho del vidrio (mm)", "default": "AH - 60",
              "ayuda": "Deducción de junquillo/perfil sobre el ancho de hoja (AH)"},
             {"key": "formula_alto", "label": "Alto del vidrio (mm)", "default": "HH - 60"},
             {"key": "formula_cantidad", "label": "Cantidad de paños", "default": "N"}],
            dict(fila) if fila else None)
        if dialogo.resultado is None:
            return
        for clave, valor in dialogo.resultado.items():
            ok, detalle = validar(valor)
            if not ok:
                messagebox.showerror("Fórmula inválida", f"{clave}: {detalle}")
                return
        datos = dict(dialogo.resultado, tipologia_codigo=tip, linea_id=lid)
        if fila:
            self.db.actualizar("vidrio_formulas", fila["id"], datos)
        else:
            self.db.insertar("vidrio_formulas", datos)
        self.app.estado("Fórmulas de vidrio actualizadas.")

    def _duplicar_formulas(self):
        tip = self._codigo_tipologia()
        if not tip:
            return
        generica = self.combo_f_linea.get().startswith("(")
        origen = None if generica else self._id_linea(self.combo_f_linea.get())

        dialogo = DialogoFormulario(
            self.winfo_toplevel(), "Copiar fórmulas a otra línea",
            [{"key": "destino", "label": "Línea destino", "tipo": "combo", "requerido": True,
              "opciones": [l["nombre"] for l in self.db.lineas()]}])
        if dialogo.resultado is None:
            return
        destino = self._id_linea(dialogo.resultado["destino"])
        if destino == origen:
            return

        if origen is None:
            filas = self.db.query(
                "SELECT * FROM tipologia_formulas WHERE tipologia_codigo = ? AND linea_id IS NULL",
                (tip,))
        else:
            filas = self.db.query(
                "SELECT * FROM tipologia_formulas WHERE tipologia_codigo = ? AND linea_id = ?",
                (tip, origen))
        for f in filas:
            self.db.insertar("tipologia_formulas", {
                "tipologia_codigo": tip, "linea_id": destino,
                "perfil_codigo": f["perfil_codigo"], "funcion": f["funcion"],
                "formula_largo": f["formula_largo"], "cantidad_piezas": f["cantidad_piezas"],
                "peso_kg_m": f["peso_kg_m"], "orden": f["orden"]})
        messagebox.showinfo("Listo", f"Se copiaron {len(filas)} fórmulas.")

    def _probar_despiece(self):
        tip = self._codigo_tipologia()
        lid = self._id_linea(self.combo_f_linea.get())
        if not tip or not lid:
            messagebox.showinfo("Faltan datos",
                                "Elegí una tipología y una línea concreta (no la genérica).")
            return

        colores = self.db.colores_de_linea(lid)
        vidrios = self.db.vidrios()
        tipologia = self.db.tipologia(tip)
        dialogo = DialogoFormulario(
            self.winfo_toplevel(), "Probar despiece",
            [{"key": "ancho", "label": "Ancho (A)", "tipo": "entero", "unidad": "milimetros",
              "default": 1500},
             {"key": "alto", "label": "Alto (H)", "tipo": "entero", "unidad": "milimetros",
              "default": 1100},
             {"key": "hojas", "label": "Hojas (N)", "tipo": "entero",
              "default": tipologia["hojas_default"] if tipologia else 2},
             {"key": "color", "label": "Color", "tipo": "combo",
              "opciones": [c["color"] for c in colores],
              "default": colores[0]["color"] if colores else ""},
             {"key": "vidrio", "label": "Vidrio", "tipo": "combo",
              "opciones": [v["nombre"] for v in vidrios],
              "default": vidrios[0]["nombre"] if vidrios else ""}])
        if dialogo.resultado is None:
            return

        vidrio = self.db.query_one("SELECT id FROM vidrios WHERE nombre = ?",
                                   (dialogo.resultado["vidrio"],))
        despiece = calcular_despiece(
            self.db, tip, lid, dialogo.resultado["color"], dialogo.resultado["ancho"],
            dialogo.resultado["alto"], dialogo.resultado["hojas"],
            vidrio["id"] if vidrio else 0)
        VentanaDespiece(self.winfo_toplevel(), despiece,
                        f"{tip} · {F.medida(dialogo.resultado['ancho'], dialogo.resultado['alto'])}")

    # =====================================================================
    # Parámetros
    # =====================================================================

    def _panel_parametros(self, hoja):
        hoja.columnconfigure(0, weight=1)
        hoja.rowconfigure(0, weight=1)

        def cargar():
            filas = []
            for f in self.db.query("SELECT rowid AS id, * FROM parametros ORDER BY grupo, clave"):
                d = dict(f)
                d["valor_visible"] = self._valor_visible(d["clave"], d["valor"])
                filas.append(d)
            return filas

        def campos(fila):
            clave = (fila or {}).get("clave", "")
            es_pct = clave.endswith("_pct")
            return [
                {"key": "clave", "label": "Clave",
                 "tipo": "solo_lectura" if fila else "texto", "requerido": True},
                {"key": "valor", "label": "Valor" + (" (%)" if es_pct else ""),
                 "ayuda": (fila or {}).get("descripcion", "")},
                {"key": "descripcion", "label": "Descripción"},
                {"key": "grupo", "label": "Grupo", "tipo": "combo",
                 "opciones": ["Mano de obra", "Logística", "Opcionales", "Comercial",
                              "Técnico", "General"], "default": "General"},
            ]

        def guardar(_id, datos):
            valor = datos["valor"]
            if datos["clave"].endswith("_pct"):
                leido = F.a_float(valor)
                valor = leido / 100.0 if leido > 1 else leido
            self.db.set_parametro(datos["clave"], valor, datos["descripcion"], datos["grupo"])
            self.app.recargar_catalogos()

        PanelABM(
            hoja, "Costos operativos y parámetros generales",
            [("grupo", "Grupo", 140, "w"), ("clave", "Clave", 240, "w"),
             ("valor_visible", "Valor", 160, "e"), ("descripcion", "Descripción", 480, "w")],
            cargar=cargar, campos=campos, al_guardar=guardar,
            al_borrar=lambda i: self.db.execute("DELETE FROM parametros WHERE rowid = ?", (i,)),
            alto=18,
        ).grid(row=0, column=0, sticky="nsew", pady=6)

    @staticmethod
    def _valor_visible(clave: str, valor) -> str:
        numero = F.a_float(valor, None) if str(valor).replace(".", "").replace("-", "").isdigit() \
            else F.a_float(valor, 0.0)
        if clave.endswith("_pct"):
            return F.porcentaje(F.a_float(valor), 1)
        if clave.startswith("mo_valor_hora"):
            return F.moneda(numero)
        if clave.endswith("_m2") or clave.endswith("_ml") or clave.startswith("log_") \
                or "precio" in clave or clave.endswith("_hoja") or clave.endswith("_directo"):
            return F.moneda(numero)
        if clave.endswith("_dias"):
            return f"{F.numero(numero, 0)} días"
        if "horas" in clave:
            return F.horas(numero)
        return str(valor)

    # =====================================================================
    # Helpers
    # =====================================================================

    def _id_linea(self, nombre: str) -> int:
        if not nombre or nombre.startswith("("):
            return 0
        fila = self.db.query_one("SELECT id FROM lineas WHERE nombre = ?", (nombre,))
        return fila["id"] if fila else 0

    def _codigo_tipologia(self) -> str:
        texto = self.combo_f_tip.get()
        return texto.split(" — ")[0] if texto else ""

    def recargar_catalogos(self):
        lineas = [l["nombre"] for l in self.db.lineas()]
        self.combo_perfil_linea.opciones(lineas)
        self.combo_f_linea.opciones(["(Genérica — todas las líneas)"] + lineas)
        self.combo_f_tip.opciones([f"{t['codigo']} — {t['nombre']}"
                                   for t in self.db.tipologias()])
        for abm in (self.abm_lineas, self.abm_precios, self.abm_perfiles,
                    self.abm_formulas, self.abm_kits):
            abm.refrescar()

    def al_entrar(self):
        pass
