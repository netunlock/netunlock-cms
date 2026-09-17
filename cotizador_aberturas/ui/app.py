"""
Ventana principal: barra lateral de navegación + área de contenido + barra de estado.

Las vistas se construyen de forma perezosa (la primera vez que se entra a cada
una), para que el arranque sea inmediato.
"""

from __future__ import annotations

import os
import subprocess
import sys
from tkinter import messagebox

import customtkinter as ctk

from core import rutas
from core.config import Ajustes
from core.database import DB
from . import tema
from .componentes import boton_fantasma

TITULO = "Cotizador de Aberturas de Aluminio"

NAVEGACION = [
    ("cotizacion", "Cotización", "Armar y exportar presupuestos"),
    ("presupuestos", "Presupuestos", "Historial y seguimiento"),
    ("ordenes", "Órdenes de trabajo", "Producción del taller"),
    ("stock", "Inventario", "Perfiles, vidrios y accesorios en depósito"),
    ("materiales", "Materiales y Costos", "Líneas, vidrios, accesorios y fórmulas"),
    ("empresa", "Empresa", "Datos del emisor y numeración"),
    ("ajustes", "Ajustes", "Tema, licencia y actualizaciones"),
]


class App(ctk.CTk):
    def __init__(self, ajustes: Ajustes):
        super().__init__()
        self.ajustes = ajustes
        self.db = DB()
        self._vistas: dict[str, ctk.CTkFrame] = {}
        self._botones: dict[str, ctk.CTkButton] = {}
        self._activa = ""

        self.title(f"{TITULO}  ·  v{rutas.version()}")
        self._ajustar_a_pantalla()
        self.configure(fg_color=tema.c("ventana"))
        tema.estilizar_tablas(self)
        tema.al_cambiar(self._al_cambiar_tema)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._construir_lateral()
        self._construir_contenido()
        self._construir_estado()

        self.protocol("WM_DELETE_WINDOW", self.cerrar)
        self.bind("<Control-s>", lambda _e: self._atajo_guardar())
        self.bind("<Control-p>", lambda _e: self._atajo_pdf())
        self.bind("<Control-n>", lambda _e: self._atajo_nuevo())

        self.navegar("cotizacion")
        self._mensaje_inicial()
        if ajustes.maximizar_al_iniciar:
            try:
                self.state("zoomed")
            except Exception:
                pass

    # =====================================================================
    # Estructura
    # =====================================================================

    def _ajustar_a_pantalla(self):
        """Dimensiona la ventana al monitor disponible.

        En este rubro son habituales las notebooks de 1366x768: una ventana fija
        de 1440x880 quedaría con los totales y los botones fuera de pantalla.
        """
        ancho_pantalla = self.winfo_screenwidth()
        alto_pantalla = self.winfo_screenheight()

        ancho = min(1440, max(1024, ancho_pantalla - 60))
        alto = min(880, max(600, alto_pantalla - 90))
        x = max(0, (ancho_pantalla - ancho) // 2)
        y = max(0, (alto_pantalla - alto) // 3)

        self.geometry(f"{ancho}x{alto}+{x}+{y}")
        self.minsize(min(1024, ancho), min(600, alto))

    def _construir_lateral(self):
        lateral = ctk.CTkFrame(self, width=232, corner_radius=0,
                               fg_color=tema.c("superficie"))
        lateral.grid(row=0, column=0, rowspan=2, sticky="nsw")
        lateral.grid_propagate(False)
        lateral.grid_rowconfigure(1, weight=1)

        marca = ctk.CTkFrame(lateral, fg_color="transparent")
        marca.grid(row=0, column=0, sticky="ew", padx=20, pady=(24, 22))
        ctk.CTkLabel(marca, text="COTIZADOR", font=tema.fuente(17, "bold"),
                     text_color=tema.c("primario"), anchor="w").pack(anchor="w")
        ctk.CTkLabel(marca, text="Aberturas de aluminio", font=tema.fuente(11),
                     text_color=tema.c("texto_tenue"), anchor="w").pack(anchor="w")

        menu = ctk.CTkFrame(lateral, fg_color="transparent")
        menu.grid(row=1, column=0, sticky="new", padx=12)
        for clave, etiqueta, descripcion in NAVEGACION:
            boton = ctk.CTkButton(
                menu, text=etiqueta, anchor="w", height=40, corner_radius=tema.RADIO_CHICO,
                font=tema.fuente(13), fg_color="transparent",
                hover_color=tema.c("superficie_3"), text_color=tema.c("texto_suave"),
                command=lambda c=clave: self.navegar(c))
            boton.pack(fill="x", pady=2)
            self._botones[clave] = boton

        pie = ctk.CTkFrame(lateral, fg_color="transparent")
        pie.grid(row=2, column=0, sticky="ews", padx=16, pady=16)
        ctk.CTkLabel(pie, text="Tema", font=tema.fuente(11),
                     text_color=tema.c("texto_tenue"), anchor="w").pack(anchor="w", pady=(0, 4))
        self.selector_tema = ctk.CTkSegmentedButton(
            pie, values=[tema.NOMBRES_CORTOS["claro"], tema.NOMBRES_CORTOS["silver"]],
            font=tema.fuente(11), command=self._cambiar_tema)
        self.selector_tema.set(tema.NOMBRES_CORTOS[tema.actual()])
        self.selector_tema.pack(fill="x")

    def _construir_contenido(self):
        self.contenido = ctk.CTkFrame(self, fg_color="transparent")
        self.contenido.grid(row=0, column=1, sticky="nsew", padx=(14, 16), pady=(14, 0))
        self.contenido.grid_columnconfigure(0, weight=1)
        self.contenido.grid_rowconfigure(0, weight=1)

    def _construir_estado(self):
        barra = ctk.CTkFrame(self, height=30, corner_radius=0, fg_color="transparent")
        barra.grid(row=1, column=1, sticky="ew", padx=(14, 16), pady=(2, 4))
        barra.grid_propagate(False)
        self.lbl_estado = ctk.CTkLabel(barra, text="", font=tema.fuente(11),
                                       text_color=tema.c("texto_tenue"), anchor="w")
        self.lbl_estado.pack(side="left")
        self.lbl_estado_der = ctk.CTkLabel(barra, text="", font=tema.fuente(11),
                                           text_color=tema.c("texto_tenue"), anchor="e")
        self.lbl_estado_der.pack(side="right")

    # =====================================================================
    # Navegación
    # =====================================================================

    def _crear_vista(self, clave):
        if clave == "cotizacion":
            from .vista_cotizacion import VistaCotizacion
            return VistaCotizacion(self.contenido, self)
        if clave == "materiales":
            from .vista_materiales import VistaMateriales
            return VistaMateriales(self.contenido, self)
        if clave == "presupuestos":
            from .vista_presupuestos import VistaPresupuestos
            return VistaPresupuestos(self.contenido, self)
        if clave == "ordenes":
            from .vista_ordenes import VistaOrdenes
            return VistaOrdenes(self.contenido, self)
        if clave == "stock":
            from .vista_stock import VistaStock
            return VistaStock(self.contenido, self)
        if clave == "empresa":
            from .vista_empresa import VistaEmpresa
            return VistaEmpresa(self.contenido, self)
        from .vista_ajustes import VistaAjustes
        return VistaAjustes(self.contenido, self)

    def navegar(self, clave: str):
        if clave == self._activa:
            return
        if self._activa and self._activa in self._vistas:
            self._vistas[self._activa].grid_forget()

        if clave not in self._vistas:
            self.configure(cursor="watch")
            self.update_idletasks()
            try:
                self._vistas[clave] = self._crear_vista(clave)
            finally:
                self.configure(cursor="")

        self._vistas[clave].grid(row=0, column=0, sticky="nsew")
        self._activa = clave

        for c, boton in self._botones.items():
            activo = c == clave
            boton.configure(
                fg_color=tema.c("primario") if activo else "transparent",
                text_color=tema.c("sobre_primario") if activo else tema.c("texto_suave"),
                font=tema.fuente(13, "bold" if activo else "normal"))

        vista = self._vistas[clave]
        if hasattr(vista, "al_entrar"):
            vista.al_entrar()

    @property
    def vista_cotizacion(self):
        if "cotizacion" not in self._vistas:
            self._vistas["cotizacion"] = self._crear_vista("cotizacion")
        return self._vistas["cotizacion"]

    # =====================================================================
    # Servicios para las vistas
    # =====================================================================

    def estado(self, texto: str, derecha: str = ""):
        self.lbl_estado.configure(text=texto)
        if derecha:
            self.lbl_estado_der.configure(text=derecha)

    def recargar_catalogos(self):
        for clave in ("materiales", "cotizacion"):
            vista = self._vistas.get(clave)
            if vista is not None and hasattr(vista, "recargar_catalogos"):
                vista.recargar_catalogos()

    def refrescar_presupuestos(self):
        vista = self._vistas.get("presupuestos")
        if vista is not None:
            vista.refrescar()

    def abrir_ruta(self, ruta):
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(ruta))  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.run(["open", str(ruta)], check=False)
            else:
                subprocess.run(["xdg-open", str(ruta)], check=False)
        except OSError as exc:
            messagebox.showwarning("No se pudo abrir", str(exc))

    # =====================================================================
    # Tema
    # =====================================================================

    def _cambiar_tema(self, etiqueta: str):
        clave = "silver" if etiqueta == tema.NOMBRES_CORTOS["silver"] else "claro"
        tema.aplicar(clave)
        self.ajustes.tema = clave
        self.ajustes.guardar()
        self.estado(f"Tema cambiado a {tema.NOMBRES[clave]}.")

    def _al_cambiar_tema(self, _clave):
        tema.estilizar_tablas(self)
        self.configure(fg_color=tema.c("ventana"))
        for c, boton in self._botones.items():
            activo = c == self._activa
            boton.configure(
                fg_color=tema.c("primario") if activo else "transparent",
                text_color=tema.c("sobre_primario") if activo else tema.c("texto_suave"))
        for vista in self._vistas.values():
            if hasattr(vista, "al_cambiar_tema"):
                vista.al_cambiar_tema()

    # =====================================================================
    # Atajos y cierre
    # =====================================================================

    def _atajo_guardar(self):
        if self._activa == "cotizacion":
            self.vista_cotizacion.guardar()
        elif self._activa == "empresa":
            self._vistas["empresa"].guardar()

    def _atajo_pdf(self):
        self.navegar("cotizacion")
        self.vista_cotizacion.generar_pdf()

    def _atajo_nuevo(self):
        self.navegar("cotizacion")
        self.vista_cotizacion.nuevo_presupuesto()

    def _mensaje_inicial(self):
        from core import licencia as lic

        partes = [f"Base: {rutas.RUTA_DB}"]
        if self.db.migraciones_aplicadas:
            partes.append(f"base actualizada al esquema v{self.db.version_esquema}")
        self.estado("   ·   ".join(partes), f"v{rutas.version()}")

        estado = lic.estado_actual()
        if estado.por_vencer and self.ajustes.aviso_licencia_visto != estado.licencia.vence:
            self.ajustes.aviso_licencia_visto = estado.licencia.vence
            self.ajustes.guardar()
            self.after(700, lambda: messagebox.showwarning(
                "Licencia por vencer",
                f"{estado.aviso}\n\nContactá a tu proveedor para renovarla y evitar "
                "interrupciones."))

    def cerrar(self):
        vista = self._vistas.get("cotizacion")
        if vista is not None and getattr(vista, "items", None) and vista.hay_cambios():
            respuesta = messagebox.askyesnocancel(
                "Salir",
                "El presupuesto en pantalla tiene cambios sin guardar.\n\n"
                "¿Querés guardarlo antes de salir?")
            if respuesta is None:
                return
            if respuesta and not vista.guardar(silencioso=True):
                return
        try:
            self.db.cerrar()
        except Exception:
            pass
        self.destroy()
