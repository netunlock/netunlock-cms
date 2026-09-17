"""
Panel de avisos del despiece: verlos todos y resolverlos desde ahí.

Antes se mostraba el primer problema en la barra de estado y se contaba el resto.
Un presupuesto con doce errores se veía igual que uno con uno solo, y para
arreglar cualquiera había que salir a buscar el perfil o el color a mano.

Acá están todos, agrupados por gravedad, y **cada uno se resuelve desde la
lista**: cuando falta un solo número —el $/kg de un color, el peso de un perfil—
se pide en el momento y se recalcula. Cuando el problema es estructural —no hay
fórmulas, una fórmula está rota— lleva a la pantalla donde se arregla.
"""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from core import avisos as av
from core import formato as F
from . import tema
from .componentes import (DialogoBase, DialogoFormulario, Tabla, boton_fantasma,
                          boton_secundario)


class VentanaAvisos(DialogoBase):
    """Lista accionable de los problemas de un presupuesto."""

    def __init__(self, master, app, avisos: list, al_resolver=None):
        errores, atenciones = av.contar(avisos)
        super().__init__(master, f"Avisos del despiece — {av.resumen(avisos)}", ancho=920)

        self.app = app
        self.db = app.db
        self.avisos = list(avisos)
        self._al_resolver = al_resolver

        ancho = min(940, self.winfo_screenwidth() - 80)
        alto = min(620, self.winfo_screenheight() - 120)
        self.geometry(f"{ancho}x{alto}")
        self.resizable(True, True)

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.pack(fill="both", expand=True, padx=18, pady=16)
        cont.columnconfigure(0, weight=1)
        cont.rowconfigure(1, weight=1)

        self._encabezado(cont, errores, atenciones)
        self._tabla(cont)
        self._pie(cont)

        self.refrescar()
        self.esperar()

    # -- construcción --------------------------------------------------------

    def _encabezado(self, master, errores: int, atenciones: int):
        barra = ctk.CTkFrame(master, fg_color="transparent")
        barra.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        if errores:
            ctk.CTkLabel(barra, text=f"●  {errores} error(es)",
                         font=tema.fuente(13, "bold"),
                         text_color=tema.c("error")).pack(side="left", padx=(0, 18))
        if atenciones:
            ctk.CTkLabel(barra, text=f"●  {atenciones} para revisar",
                         font=tema.fuente(13, "bold"),
                         text_color=tema.c("alerta")).pack(side="left")

        ctk.CTkLabel(
            barra,
            text="Doble clic en un aviso para resolverlo",
            font=tema.fuente(11), text_color=tema.c("texto_tenue")).pack(side="right")

    def _tabla(self, master):
        self.tabla = Tabla(
            master,
            [("sev", "", 34, "center"),
             ("item", "Abertura", 190, "w"),
             ("mensaje", "Qué pasa", 470, "w"),
             ("accion", "Cómo se arregla", 150, "w")],
            alto=12, al_elegir=self._mostrar_detalle, al_activar=self.resolver)
        self.tabla.grid(row=1, column=0, sticky="nsew")

        self.lbl_detalle = ctk.CTkLabel(
            master, text="", font=tema.fuente(12), text_color=tema.c("texto_suave"),
            anchor="w", justify="left", wraplength=860)
        self.lbl_detalle.grid(row=2, column=0, sticky="ew", pady=(10, 0))

    def _pie(self, master):
        pie = ctk.CTkFrame(master, fg_color="transparent")
        pie.grid(row=3, column=0, sticky="ew", pady=(14, 0))

        self.btn_resolver = ctk.CTkButton(
            pie, text="Resolver", width=130, height=34,
            font=tema.fuente(13, "bold"), command=self.resolver)
        self.btn_resolver.pack(side="left")

        boton_secundario(pie, "Copiar todo", self._copiar, ancho=120).pack(
            side="left", padx=8)
        boton_fantasma(pie, "Cerrar", self.destroy, ancho=100).pack(side="right")

    # -- datos ---------------------------------------------------------------

    def refrescar(self):
        """Los errores primero: es el orden en el que conviene atacarlos."""
        self.avisos.sort(key=lambda a: (0 if a.es_error else 1, a.codigo))

        etiquetas_accion = {
            av.ARREGLO_CAMPO: "Cargar el dato",
            av.ARREGLO_NAVEGAR: "Ir a la pantalla",
            av.ARREGLO_NINGUNO: "—",
        }

        filas = []
        for i, aviso in enumerate(self.avisos):
            filas.append((
                ("●", aviso.item or "—", aviso.mensaje,
                 etiquetas_accion.get(aviso.arreglo, "—")),
                {"id": i},
                ("alerta",) if aviso.es_error else ()))
        self.tabla.cargar(filas)
        self._mostrar_detalle()

    def _seleccionado(self):
        fila = self.tabla.seleccionado()
        return self.avisos[fila["id"]] if fila else None

    def _mostrar_detalle(self, _evento=None):
        aviso = self._seleccionado()
        if aviso is None:
            self.lbl_detalle.configure(text="")
            self.btn_resolver.configure(state="disabled")
            return
        self.lbl_detalle.configure(text=aviso.sugerencia)
        self.btn_resolver.configure(
            state="normal" if aviso.arreglo else "disabled")

    # -- resolución ----------------------------------------------------------

    def resolver(self, _evento=None):
        aviso = self._seleccionado()
        if aviso is None:
            return
        if aviso.arreglo == av.ARREGLO_CAMPO:
            self._resolver_campo(aviso)
        elif aviso.arreglo == av.ARREGLO_NAVEGAR:
            self._ir_a(aviso)

    def _resolver_campo(self, aviso):
        """Pide el único dato que falta y lo escribe. Es el 'doble clic para
        ingresar el precio': el problema se arregla sin salir de la lista."""
        campo = dict(aviso.campo)
        clave = campo.pop("clave", "")
        obj = aviso.objeto
        if not clave:
            return

        # core/avisos.py describe el campo en lenguaje del dominio ("etiqueta");
        # traducirlo a las claves del formulario es trabajo de esta capa.
        especificacion = {
            "key": clave,
            "label": campo.get("etiqueta", clave),
            "tipo": campo.get("tipo", "decimal"),
            "requerido": True,
            "ayuda": aviso.sugerencia,
        }
        for opcional in ("unidad", "decimales"):
            if opcional in campo:
                especificacion[opcional] = campo[opcional]

        dialogo = DialogoFormulario(self, aviso.mensaje.rstrip("."), [especificacion])
        if dialogo.resultado is None:
            return

        valor = dialogo.resultado.get(clave)
        try:
            if obj["tipo"] == "linea_precio":
                self._guardar_precio_linea(obj, clave, valor)
            elif obj["tipo"] == "perfil":
                self.db.actualizar("perfiles", obj["id"], {clave: valor})
            elif obj["tipo"] == "accesorio":
                self.db.actualizar("accesorios", obj["id"], {clave: valor})
            else:
                return
        except Exception as exc:
            messagebox.showerror("No se pudo guardar", str(exc), parent=self)
            return

        self.app.recargar_catalogos()
        if self._al_resolver:
            # El presupuesto se recalcula y vuelve con la lista nueva: si el
            # arreglo destapó otro problema, aparece acá mismo.
            self.avisos = list(self._al_resolver())
            self.refrescar()
        self.app.estado(f"Corregido: {aviso.mensaje}")

    def _guardar_precio_linea(self, obj, clave, valor):
        existente = self.db.query_one(
            "SELECT id FROM linea_precios WHERE linea_id = ? AND color = ?",
            (obj["linea_id"], obj["color"]))
        if existente:
            self.db.actualizar("linea_precios", existente["id"], {clave: valor})
        else:
            # El color puede no estar dado de alta todavía: el aviso salta
            # justamente porque no hay fila. Se crea con el precio recién cargado.
            self.db.insertar("linea_precios", {
                "linea_id": obj["linea_id"], "color": obj["color"],
                clave: valor, "activo": 1})

    def _ir_a(self, aviso):
        """Cierra la ventana y abre Materiales en el lugar del problema."""
        self.destroy()
        self.app.navegar("materiales")
        vista = self.app._vistas.get("materiales")
        if vista is not None and hasattr(vista, "ir_a"):
            vista.ir_a(aviso.objeto)

    def _copiar(self):
        """Todo el listado al portapapeles, para mandarlo por mensaje."""
        lineas = []
        for aviso in self.avisos:
            marca = "ERROR " if aviso.es_error else "AVISO "
            lineas.append(f"{marca}[{aviso.item or '-'}] {aviso.mensaje}")
            if aviso.sugerencia:
                lineas.append(f"       {aviso.sugerencia}")
        texto = "\n".join(lineas)
        try:
            self.clipboard_clear()
            self.clipboard_append(texto)
            self.app.estado(f"{len(self.avisos)} aviso(s) copiados al portapapeles.")
        except Exception:
            messagebox.showinfo("Avisos", texto, parent=self)


def badge(master, avisos, al_abrir, boton: ctk.CTkButton | None = None) -> ctk.CTkButton:
    """Botón contador para la barra de herramientas.

    Si se le pasa un botón existente lo **reconfigura** en vez de crear uno
    nuevo. Importa: esto se llama en cada recálculo, y el recálculo corre con
    cada tecla que se tipea en el margen o en el IVA. Crear un CTkButton cuesta
    unos 20 ms —son varios widgets sobre un canvas—, y destruir el botón cuya
    orden se está ejecutando es además una forma conocida de trabar Tk.
    """
    errores, atenciones = av.contar(avisos)
    total = errores + atenciones

    if not total:
        texto, color = "Sin avisos", tema.c("texto_tenue")
    elif errores:
        texto, color = f"⚠  {av.resumen(avisos)}", tema.c("error")
    else:
        texto, color = f"⚠  {av.resumen(avisos)}", tema.c("alerta")

    ajustes = {
        "text": texto,
        "text_color": color,
        "border_color": color,
        "command": al_abrir if total else None,
        "state": "normal" if total else "disabled",
    }

    if boton is not None and boton.winfo_exists():
        boton.configure(**ajustes)
        return boton

    return ctk.CTkButton(
        master, width=150, height=28, font=tema.fuente(12, "bold"),
        fg_color="transparent", hover_color=tema.c("superficie_3"),
        border_width=1, **ajustes)
