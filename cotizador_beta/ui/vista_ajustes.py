"""
Ajustes: apariencia, licencia, datos de usuario, respaldos y actualizaciones.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core import formato as F
from core import rutas
from core.config import TEMAS_DISPONIBLES
from core.database import ESQUEMA_VERSION
from . import tema
from .componentes import DialogoFormulario, Tarjeta, boton_fantasma, boton_secundario
from .licencia_ui import PanelLicencia

ESCALAS = {"Compacto (90%)": 0.9, "Normal (100%)": 1.0,
           "Grande (110%)": 1.1, "Muy grande (125%)": 1.25}


class VistaAjustes(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.db = app.db

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        scroll.columnconfigure(0, weight=1)
        scroll.columnconfigure(1, weight=1)

        self._panel_apariencia(scroll)
        self.panel_licencia = PanelLicencia(scroll, app)
        self.panel_licencia.grid(row=0, column=1, sticky="nsew", pady=(0, 12))

        self._panel_datos(scroll)
        self._panel_actualizaciones(scroll)

    # =====================================================================

    def _panel_apariencia(self, master):
        tarjeta = Tarjeta(master, "Apariencia")
        tarjeta.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=(0, 12))
        cuerpo = tarjeta.cuerpo

        ctk.CTkLabel(cuerpo, text="Tema de la interfaz", font=tema.fuente(12, "bold"),
                     text_color=tema.c("texto"), anchor="w").pack(anchor="w")

        for clave in TEMAS_DISPONIBLES:
            fila = ctk.CTkFrame(cuerpo, fg_color="transparent")
            fila.pack(fill="x", pady=6)

            muestra = ctk.CTkFrame(fila, width=64, height=44, corner_radius=6,
                                   fg_color=tema.PALETAS[clave]["ventana"],
                                   border_width=1,
                                   border_color=tema.PALETAS[clave]["borde"])
            muestra.pack(side="left", padx=(0, 12))
            muestra.pack_propagate(False)
            interior = ctk.CTkFrame(muestra, height=14, corner_radius=3,
                                    fg_color=tema.PALETAS[clave]["superficie"])
            interior.pack(fill="x", padx=6, pady=(8, 2))
            acento = ctk.CTkFrame(muestra, height=8, width=30, corner_radius=3,
                                  fg_color=tema.PALETAS[clave]["primario"])
            acento.pack(anchor="w", padx=6)

            texto = ctk.CTkFrame(fila, fg_color="transparent")
            texto.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(texto, text=tema.NOMBRES[clave], font=tema.fuente(12, "bold"),
                         text_color=tema.c("texto"), anchor="w").pack(anchor="w")
            descripcion = ("Fondo claro tradicional, máximo contraste."
                           if clave == "claro" else
                           "Grises slate de baja luminancia para jornadas largas en taller.")
            ctk.CTkLabel(texto, text=descripcion, font=tema.fuente(10),
                         text_color=tema.c("texto_tenue"), anchor="w",
                         wraplength=280, justify="left").pack(anchor="w")

            ctk.CTkButton(fila, text="Usar", width=70, height=28, font=tema.fuente(11),
                          command=lambda c=clave: self._elegir_tema(c)).pack(side="right")

        ctk.CTkFrame(cuerpo, height=1, fg_color=tema.c("borde_suave")).pack(
            fill="x", pady=12)

        ctk.CTkLabel(cuerpo, text="Tamaño de la interfaz", font=tema.fuente(12, "bold"),
                     text_color=tema.c("texto"), anchor="w").pack(anchor="w")
        ctk.CTkLabel(cuerpo, text="Se aplica al reiniciar la aplicación.",
                     font=tema.fuente(10), text_color=tema.c("texto_tenue"),
                     anchor="w").pack(anchor="w", pady=(0, 6))

        actual = next((n for n, v in ESCALAS.items()
                       if abs(v - self.app.ajustes.escala_valida()) < 0.01), "Normal (100%)")
        self.combo_escala = ctk.CTkOptionMenu(cuerpo, values=list(ESCALAS), width=200,
                                              font=tema.fuente(12), command=self._elegir_escala)
        self.combo_escala.set(actual)
        self.combo_escala.pack(anchor="w")

        self.chk_maximizar = ctk.CTkCheckBox(
            cuerpo, text="Abrir maximizado", font=tema.fuente(12),
            command=self._alternar_maximizar)
        self.chk_maximizar.pack(anchor="w", pady=(10, 0))
        if self.app.ajustes.maximizar_al_iniciar:
            self.chk_maximizar.select()

    def _elegir_tema(self, clave):
        tema.aplicar(clave)
        self.app.ajustes.tema = clave
        self.app.ajustes.guardar()
        self.app.selector_tema.set(tema.NOMBRES_CORTOS[clave])
        self.app.estado(f"Tema cambiado a {tema.NOMBRES[clave]}.")

    def _elegir_escala(self, etiqueta):
        self.app.ajustes.escala = ESCALAS.get(etiqueta, 1.0)
        self.app.ajustes.guardar()
        self.app.estado("El nuevo tamaño se aplica al reiniciar la aplicación.")

    def _alternar_maximizar(self):
        self.app.ajustes.maximizar_al_iniciar = bool(self.chk_maximizar.get())
        self.app.ajustes.guardar()

    # =====================================================================

    def _panel_datos(self, master):
        tarjeta = Tarjeta(master, "Datos y respaldos")
        tarjeta.grid(row=1, column=0, sticky="nsew", padx=(0, 12), pady=(0, 12))
        cuerpo = tarjeta.cuerpo

        ctk.CTkLabel(cuerpo,
                     text="Estas carpetas guardan tu información y NUNCA se tocan "
                          "al instalar una actualización.",
                     font=tema.fuente(11), text_color=tema.c("texto_suave"),
                     wraplength=420, justify="left", anchor="w").pack(anchor="w", pady=(0, 10))

        self.info_datos = ctk.CTkFrame(cuerpo, fg_color="transparent")
        self.info_datos.pack(fill="x")
        self._pintar_info()

        acciones = ctk.CTkFrame(cuerpo, fg_color="transparent")
        acciones.pack(fill="x", pady=(14, 0))
        ctk.CTkButton(acciones, text="Crear copia de seguridad", width=200,
                      command=self._respaldar).pack(side="left")
        boton_secundario(acciones, "Abrir carpeta de datos",
                         lambda: self.app.abrir_ruta(rutas.DATOS), ancho=180).pack(
            side="left", padx=8)
        boton_secundario(acciones, "Abrir carpeta de PDF",
                         lambda: self.app.abrir_ruta(rutas.SALIDAS), ancho=170).pack(side="left")

        boton_fantasma(cuerpo, "Restaurar desde una copia…", self._restaurar,
                       ancho=220).pack(anchor="w", pady=(8, 0))

    def _pintar_info(self):
        for widget in self.info_datos.winfo_children():
            widget.destroy()

        copias = sorted(rutas.COPIAS.glob("cotizador_*.db"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
        tam = rutas.RUTA_DB.stat().st_size / 1024 if rutas.RUTA_DB.exists() else 0
        presupuestos = self.db.query_one("SELECT COUNT(*) AS n FROM presupuestos")["n"]

        filas = [
            ("Carpeta de datos", str(rutas.DATOS)),
            ("Carpeta de PDF", str(rutas.SALIDAS)),
            ("Base de datos", f"{F.numero(tam, 0)} KB · esquema v{self.db.version_esquema} "
                              f"(código v{ESQUEMA_VERSION})"),
            ("Presupuestos guardados", F.unidades(presupuestos)),
            ("Copias de seguridad", F.unidades(len(copias))
             + (f" · última {datetime.fromtimestamp(copias[0].stat().st_mtime):%d/%m/%Y %H:%M}"
                if copias else "")),
        ]
        self.info_datos.columnconfigure(1, weight=1)
        for i, (etiqueta, valor) in enumerate(filas):
            ctk.CTkLabel(self.info_datos, text=etiqueta, font=tema.fuente(11),
                         text_color=tema.c("texto_suave"), anchor="w").grid(
                row=i, column=0, sticky="w", padx=(0, 14), pady=2)
            ctk.CTkLabel(self.info_datos, text=valor, font=tema.fuente(11),
                         text_color=tema.c("texto"), anchor="w", wraplength=380,
                         justify="left").grid(row=i, column=1, sticky="w", pady=2)

    def _respaldar(self):
        destino = self.db.respaldar("manual")
        if destino:
            self._pintar_info()
            self.app.estado(f"Copia creada: {destino.name}")
            messagebox.showinfo("Copia creada", f"Se guardó en:\n{destino}")
        else:
            messagebox.showwarning("No se pudo", "No se pudo crear la copia de seguridad.")

    def _restaurar(self):
        ruta = filedialog.askopenfilename(
            title="Elegir copia de seguridad", initialdir=str(rutas.COPIAS),
            filetypes=[("Base de datos", "*.db"), ("Todos", "*.*")])
        if not ruta:
            return
        if not messagebox.askyesno(
                "Restaurar copia",
                "Se va a reemplazar la base actual por la copia elegida.\n\n"
                "Antes se guarda una copia del estado actual.\n"
                "La aplicación se cerrará y tenés que volver a abrirla.\n\n¿Continuar?"):
            return
        self.db.respaldar("antes_de_restaurar")
        try:
            self.db.cerrar()
            shutil.copy2(ruta, rutas.RUTA_DB)
        except OSError as exc:
            messagebox.showerror("Error al restaurar", str(exc))
            return
        messagebox.showinfo("Restaurado",
                            "La copia se restauró. La aplicación se va a cerrar.\n\n"
                            "Volvé a abrirla para trabajar con los datos restaurados.")
        self.app.destroy()

    # =====================================================================

    def _panel_actualizaciones(self, master):
        tarjeta = Tarjeta(master, "Versión y actualizaciones")
        tarjeta.grid(row=1, column=1, sticky="nsew", pady=(0, 12))
        cuerpo = tarjeta.cuerpo

        ctk.CTkLabel(cuerpo, text=f"Versión instalada:  {rutas.version()}",
                     font=tema.fuente(14, "bold"), text_color=tema.c("texto"),
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(cuerpo, text=f"Carpeta de programa:  {rutas.RAIZ}",
                     font=tema.fuente(10), text_color=tema.c("texto_tenue"),
                     wraplength=400, justify="left", anchor="w").pack(anchor="w", pady=(4, 12))

        # El paquete que sirve depende de cómo esté instalado: el .exe se
        # actualiza con el zip completo del programa, no con uno de código.
        cual = ("Usá el mismo .zip que se entrega a un cliente nuevo (trae el "
                "ejecutable y la carpeta _internal). Al terminar, el programa se "
                "cierra y se vuelve a abrir solo."
                if rutas.empaquetado() else
                "Usá el paquete de código (main.py y las carpetas core, ui, "
                "reports y tools).")

        ctk.CTkLabel(
            cuerpo,
            text="Al instalar una actualización se reemplaza únicamente el programa. "
                 "Tus presupuestos, listas de precios, fórmulas y configuración "
                 "quedan intactos, y la base se adapta sola al esquema nuevo.\n\n"
                 + cual,
            font=tema.fuente(11), text_color=tema.c("texto_suave"),
            wraplength=400, justify="left", anchor="w").pack(anchor="w")

        ctk.CTkButton(cuerpo, text="Instalar actualización desde archivo .zip…",
                      height=38, font=tema.fuente(12, "bold"),
                      command=self._actualizar).pack(fill="x", pady=(14, 0))
        boton_secundario(cuerpo, "Ver herramientas de mantenimiento",
                         self._mantenimiento, ancho=260).pack(anchor="w", pady=(8, 0))

    def _actualizar(self):
        ruta = filedialog.askopenfilename(
            title="Elegir el paquete de actualización",
            filetypes=[("Paquete de actualización", "*.zip"), ("Todos", "*.*")])
        if not ruta:
            return

        from tools.actualizar import TIPO_PROGRAMA, inspeccionar

        try:
            info = inspeccionar(ruta)
        except Exception as exc:
            messagebox.showerror("Paquete inválido", str(exc))
            return

        es_programa = info["tipo"] == TIPO_PROGRAMA
        que_pasa = (
            "Se reemplaza la carpeta entera del programa. Al aceptar, la "
            "aplicación se cierra, se instala la versión nueva y se vuelve a "
            "abrir sola."
            if es_programa else
            f"Se reemplazarán {info['archivos']} archivos de programa.\n"
            "La aplicación se cerrará al terminar.")

        if not messagebox.askyesno(
                "Instalar actualización",
                f"Versión del paquete: {info['version']}\n"
                f"Versión instalada:   {rutas.version()}\n\n"
                f"{que_pasa}\n\n"
                "Tus presupuestos, precios y configuración NO se tocan.\n\n"
                "¿Continuar?"):
            return

        from tools.actualizar import aplicar

        # La base no se cierra antes de tiempo: si la actualización falla, la
        # app sigue viva y tiene que poder seguir trabajando. respaldar() ya
        # dejó todo confirmado en disco.
        self.db.respaldar("antes_de_actualizar")
        try:
            resumen = aplicar(ruta)
        except Exception as exc:
            messagebox.showerror("Error al actualizar", str(exc))
            return

        self.db.cerrar()
        if es_programa:
            # El reemplazo lo termina el script externo, y no puede empezar
            # hasta que este proceso muera: cerrar acá no es opcional.
            messagebox.showinfo("Actualización lista para instalarse", resumen)
        else:
            messagebox.showinfo("Actualización instalada",
                                resumen + "\n\nLa aplicación se va a cerrar. "
                                          "Volvé a abrirla para usar la versión nueva.")
        self.app.destroy()

    def _mantenimiento(self):
        DialogoFormulario(
            self.winfo_toplevel(), "Herramientas de mantenimiento",
            [{"key": "info", "label": "Comandos disponibles", "tipo": "memo", "alto": 200,
              "default":
                  "Actualización masiva de precios y otras tareas se ejecutan desde\n"
                  "la carpeta del programa con estos comandos:\n\n"
                  "  python -m tools.prueba_rapida\n"
                  "      Verifica el motor de cálculo y genera un PDF de muestra.\n\n"
                  "  python -m tools.importar_excel\n"
                  "      Se usa desde Materiales; también funciona por línea de comandos.\n\n"
                  "  python -m tools.generar_claves\n"
                  "      SOLO EL PROVEEDOR. Crea el par de claves de licenciamiento.\n\n"
                  "  python -m tools.generar_licencia --hwid XXXX-XXXX-XXXX-XXXX \\\n"
                  "                                   --cliente \"Razón Social\"\n"
                  "      SOLO EL PROVEEDOR. Emite o renueva la suscripción de un equipo.\n\n"
                  "  python -m tools.empaquetar --version 2.1.0\n"
                  "      SOLO EL PROVEEDOR. Compila el ejecutable comercial."}],
            ancho=640, texto_aceptar="Cerrar")

    # =====================================================================

    def al_entrar(self):
        self.panel_licencia.refrescar()
        self._pintar_info()

    def al_cambiar_tema(self):
        self.panel_licencia.refrescar()
