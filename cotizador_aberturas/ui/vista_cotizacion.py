"""
Módulo 2 — Armado del presupuesto, descuentos y observaciones.
"""

from __future__ import annotations

import copy
from dataclasses import asdict
from datetime import date
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core import formato as F
from core import rutas
from core.calculo import calcular_item, calcular_presupuesto
from core.database import ESTADOS_PRESUPUESTO
from core.models import Cliente, Item, Logistica, ManoObra, Presupuesto
from reports.pdf_generator import generar_pdf, nombre_sugerido
from . import tema
from .componentes import (Badge, CampoCheck, CampoCombo, CampoMemo, CampoPorcentaje,
                          CampoTexto, CampoUnidad, DialogoBase, Tabla, Tarjeta,
                          boton_fantasma, boton_secundario)
from .vista_despiece import VentanaDespiece

FORMAS_PAGO = ["Contado", "50% anticipo / 50% contra entrega", "30 / 30 / 40",
               "Transferencia bancaria", "Cheque a 30 días", "A convenir"]


class VistaCotizacion(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.db = app.db
        self.items: list[Item] = []
        self.presupuesto: Presupuesto | None = None
        self._id_presupuesto: int | None = None
        self._huella_guardada = ""
        # Los consumos (kilos de aluminio, m² de vidrio) se siguen calculando
        # siempre —el costeo por kg depende de ellos— pero pueden ocultarse de la
        # pantalla para no mostrárselos a un cliente que mira por encima del hombro.
        self._muestra_consumo = bool(self.db.parametro_int("mostrar_consumo_pantalla", 1))

        # Dos columnas: el trabajo (cliente + aberturas + observaciones) a la
        # izquierda y el dinero (mano de obra + resumen) en una columna fija a la
        # derecha. Aprovecha el ancho disponible y deja alto suficiente para el
        # desglose de totales incluso en pantallas de 768 px.
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, minsize=340)
        self.grid_rowconfigure(1, weight=1)

        self._cabecera()

        self.izquierda = ctk.CTkFrame(self, fg_color="transparent")
        self.izquierda.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        self.izquierda.grid_columnconfigure(0, weight=1)
        self.izquierda.grid_rowconfigure(1, weight=1, minsize=180)

        # Scrollable: en pantallas de 768 px el desglose completo no entra, y el
        # importe total nunca puede quedar fuera de alcance.
        self.derecha = ctk.CTkScrollableFrame(self, fg_color="transparent", width=326)
        self.derecha.grid(row=1, column=1, sticky="nsew")
        self.derecha.grid_columnconfigure(0, weight=1)

        self._panel_cliente()
        self._panel_items()
        self._panel_observaciones()
        self._panel_operativos()
        self._panel_resumen()

        self.nuevo_presupuesto(preguntar=False)

    # =====================================================================
    # Cabecera
    # =====================================================================

    def _cabecera(self):
        # columnspan=2: la cabecera cruza las dos columnas, si no los botones de
        # la derecha quedan encerrados en el ancho de la columna izquierda.
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        izq = ctk.CTkFrame(barra, fg_color="transparent")
        izq.pack(side="left")

        ctk.CTkLabel(izq, text="Presupuesto", font=tema.fuente(22, "bold"),
                     text_color=tema.c("texto")).pack(side="left", padx=(0, 12))

        self.campo_numero = CampoTexto(izq, "", ancho=130)
        self.campo_numero.entrada.configure(font=("Consolas", 15), justify="center", height=34)
        self.campo_numero.pack(side="left")
        boton_fantasma(izq, "↻", self._sugerir_numero, ancho=34).pack(side="left", padx=(4, 16))

        self.campo_fecha = CampoTexto(izq, "", ancho=110)
        self.campo_fecha.entrada.configure(justify="center", height=34)
        self.campo_fecha.pack(side="left", padx=(0, 8))

        self.campo_validez = CampoUnidad(izq, "", "dias", 15, ancho=52, entero=True)
        self.campo_validez.pack(side="left", padx=(0, 10))

        self.combo_estado = ctk.CTkOptionMenu(
            izq, values=list(ESTADOS_PRESUPUESTO), width=118, height=34,
            font=tema.fuente(12), command=lambda _v: self._marcar_sucio())
        self.combo_estado.set("Borrador")
        self.combo_estado.pack(side="left")

        der = ctk.CTkFrame(barra, fg_color="transparent")
        der.pack(side="right")
        ctk.CTkButton(der, text="Generar PDF", width=140, height=36,
                      font=tema.fuente(13, "bold"),
                      command=self.generar_pdf).pack(side="right")
        boton_secundario(der, "Guardar", self.guardar, ancho=110).pack(side="right", padx=8)
        boton_fantasma(der, "Nuevo", self.nuevo_presupuesto, ancho=90).pack(side="right")

    # =====================================================================
    # Cliente
    # =====================================================================

    def _panel_cliente(self):
        tarjeta = Tarjeta(self.izquierda, "Datos del cliente")
        tarjeta.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        cuerpo = tarjeta.cuerpo
        for col in range(3):
            cuerpo.columnconfigure(col, weight=1, uniform="cli")

        self.campos_cliente = {
            "razon_social": CampoTexto(cuerpo, "Cliente / Razón social"),
            "documento": CampoTexto(cuerpo, "CUIT / DNI"),
            "contacto": CampoTexto(cuerpo, "Contacto"),
            "obra": CampoTexto(cuerpo, "Obra / Dirección"),
            "localidad": CampoTexto(cuerpo, "Localidad"),
        }
        for i, campo in enumerate(self.campos_cliente.values()):
            campo.grid(row=i // 3, column=i % 3, sticky="ew", padx=(0, 12), pady=3)

        self.campo_pago = CampoCombo(cuerpo, "Forma de pago", FORMAS_PAGO, FORMAS_PAGO[1])
        self.campo_pago.grid(row=1, column=2, sticky="ew", pady=3)

    # =====================================================================
    # Ítems
    # =====================================================================

    def _panel_items(self):
        tarjeta = Tarjeta(self.izquierda, "Aberturas")
        tarjeta.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        tarjeta.cuerpo.columnconfigure(0, weight=1)
        tarjeta.cuerpo.rowconfigure(1, weight=1)

        acciones = tarjeta.zona_acciones
        ctk.CTkButton(acciones, text="+  Agregar abertura", width=160, height=30,
                      font=tema.fuente(12, "bold"),
                      command=self.agregar_item).pack(side="right")

        barra = ctk.CTkFrame(tarjeta.cuerpo, fg_color="transparent")
        barra.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        for texto, comando, ancho in (("Editar", self.editar_item, 80),
                                      ("Duplicar", self.duplicar_item, 90),
                                      ("Eliminar", self.eliminar_item, 90),
                                      ("Ver despiece", self.ver_despiece, 120),
                                      ("Materiales a Excel", self.exportar_materiales, 150),
                                      ("Emitir OT", self.emitir_ordenes, 100)):
            boton_secundario(barra, texto, comando, ancho=ancho).pack(side="left", padx=(0, 6))
        boton_fantasma(barra, "▲", lambda: self.mover_item(-1), ancho=34).pack(side="left")
        boton_fantasma(barra, "▼", lambda: self.mover_item(1), ancho=34).pack(side="left", padx=2)

        self.lbl_obs_item = ctk.CTkLabel(barra, text="", font=tema.fuente(11),
                                         text_color=tema.c("alerta"), anchor="e")
        self.lbl_obs_item.pack(side="right", fill="x", expand=True, padx=(12, 0))

        columnas = [("orden", "#", 36, "center"),
                    ("descripcion", "Descripción", 250, "w"),
                    ("medida", "Medidas", 118, "center"),
                    ("cantidad", "Cant.", 62, "e"),
                    ("unitario", "P. Unitario", 112, "e"),
                    ("importe", "Importe", 122, "e"),
                    ("bonif", "Bonif.", 62, "e")]
        if self._muestra_consumo:
            columnas += [("peso", "Peso", 88, "e"), ("vidrio", "Vidrio", 84, "e")]
        columnas += [("hojas", "Hojas", 56, "center"),
                     ("opcionales", "Opcionales", 148, "w")]

        self.tabla = Tabla(
            tarjeta.cuerpo, columnas,
            alto=7, al_elegir=self._mostrar_obs_item, al_activar=self.editar_item,
            scroll_horizontal=True)
        self.tabla.grid(row=1, column=0, sticky="nsew")

    def _panel_observaciones(self):
        tarjeta = Tarjeta(self.izquierda, "Observaciones generales del presupuesto")
        tarjeta.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        self.campo_obs = CampoMemo(tarjeta.cuerpo, "", alto=76)
        self.campo_obs.pack(fill="both", expand=True)

    # =====================================================================
    # Columna derecha
    # =====================================================================

    def _panel_operativos(self):
        tarjeta = Tarjeta(self.derecha, "Mano de obra y logística")
        tarjeta.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        cuerpo = tarjeta.cuerpo
        cuerpo.columnconfigure((0, 1), weight=1)

        self.campo_hora = CampoUnidad(cuerpo, "Valor hora-hombre", "moneda_hora", 0,
                                      ancho=100, al_cambiar=self.recalcular)
        self.campo_operarios = CampoUnidad(cuerpo, "Operarios", "operarios", 1, ancho=60,
                                           entero=True, al_cambiar=self.recalcular)
        self.campo_horas = CampoUnidad(cuerpo, "Horas estimadas", "horas", 0, ancho=80,
                                       al_cambiar=self.recalcular)
        self.campo_flete = CampoUnidad(cuerpo, "Flete / recepción", "moneda", 0, ancho=100,
                                       al_cambiar=self.recalcular)
        self.campo_envio = CampoUnidad(cuerpo, "Envío / colocación", "moneda", 0, ancho=100,
                                       al_cambiar=self.recalcular)
        for i, campo in enumerate((self.campo_hora, self.campo_operarios, self.campo_horas,
                                   self.campo_flete, self.campo_envio)):
            campo.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0, 8), pady=3)

        boton_secundario(cuerpo, "Colocación por m²", self._colocacion_por_m2,
                         ancho=140).grid(row=2, column=1, sticky="ew", pady=3)

        self.chk_horas_auto = CampoCheck(cuerpo, "Estimar horas por m² automáticamente",
                                         True, self._alternar_horas_auto)
        self.chk_horas_auto.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 2))
        self.chk_mo_item = CampoCheck(cuerpo, "Mano de obra dentro de cada ítem",
                                      False, self.recalcular)
        self.chk_mo_item.grid(row=4, column=0, columnspan=2, sticky="w")

    def _panel_resumen(self):
        tarjeta = Tarjeta(self.derecha, "Resumen")
        tarjeta.grid(row=1, column=0, sticky="ew")
        cuerpo = tarjeta.cuerpo
        cuerpo.columnconfigure(0, weight=1)
        cuerpo.rowconfigure(3, weight=1)

        controles = ctk.CTkFrame(cuerpo, fg_color="transparent")
        controles.grid(row=0, column=0, sticky="ew")
        controles.columnconfigure((0, 1), weight=1)

        self.campo_margen = CampoPorcentaje(controles, "Margen", 0.30,
                                            al_cambiar=self.recalcular)
        self.campo_margen.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.combo_dto = CampoCombo(controles, "Descuento global",
                                    ["porcentaje", "monto"], "porcentaje",
                                    ancho=130, al_cambiar=self._cambiar_tipo_descuento)
        self.combo_dto.grid(row=0, column=1, sticky="ew")

        segunda = ctk.CTkFrame(cuerpo, fg_color="transparent")
        segunda.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        segunda.columnconfigure((0, 1), weight=1)
        self.campo_dto = CampoUnidad(segunda, "Descuento", "porcentaje", 0, ancho=80,
                                     al_cambiar=self.recalcular)
        self.campo_dto.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.campo_iva = CampoPorcentaje(segunda, "IVA", 0.21, al_cambiar=self.recalcular)
        self.campo_iva.grid(row=0, column=1, sticky="ew")

        self.chk_iva = CampoCheck(cuerpo, "Facturar con IVA", True, self.recalcular)
        self.chk_iva.grid(row=2, column=0, sticky="w", pady=(8, 2))

        self.panel_totales = ctk.CTkFrame(cuerpo, fg_color="transparent")
        self.panel_totales.grid(row=3, column=0, sticky="new", pady=(6, 0))
        self.panel_totales.columnconfigure(1, weight=1)

    # =====================================================================
    # Acciones sobre ítems
    # =====================================================================

    def agregar_item(self):
        dialogo = DialogoItem(self, self.db, self._margen(), orden=len(self.items) + 1)
        if dialogo.resultado:
            self.items.append(dialogo.resultado)
            self.recalcular()
            self.tabla.seleccionar_indice(len(self.items) - 1)

    def editar_item(self):
        indice = self._indice()
        if indice is None:
            return
        dialogo = DialogoItem(self, self.db, self._margen(), item=self.items[indice])
        if dialogo.resultado:
            self.items[indice] = dialogo.resultado
            self.recalcular()
            self.tabla.seleccionar_indice(indice)

    def duplicar_item(self):
        indice = self._indice()
        if indice is None:
            return
        nuevo = copy.deepcopy(self.items[indice])
        nuevo.id = None
        self.items.insert(indice + 1, nuevo)
        self.recalcular()
        self.tabla.seleccionar_indice(indice + 1)

    def eliminar_item(self):
        indice = self._indice()
        if indice is None:
            return
        item = self.items[indice]
        if not messagebox.askyesno("Eliminar ítem",
                                   f"¿Eliminar el ítem {item.orden} — {item.descripcion}?"):
            return
        del self.items[indice]
        self.recalcular()

    def mover_item(self, delta: int):
        indice = self._indice()
        if indice is None:
            return
        destino = indice + delta
        if not 0 <= destino < len(self.items):
            return
        self.items[indice], self.items[destino] = self.items[destino], self.items[indice]
        self.recalcular()
        self.tabla.seleccionar_indice(destino)

    def ver_despiece(self):
        indice = self._indice()
        if indice is None:
            return
        item = self.items[indice]
        resultado = calcular_item(self.db, item, self._margen())
        VentanaDespiece(self, resultado.despiece,
                        f"Ítem {item.orden} · {item.descripcion} · {item.medida_texto}")

    def exportar_materiales(self):
        """Genera el Excel con el listado completo de materiales del presupuesto."""
        from tkinter import filedialog

        if not self.items:
            messagebox.showwarning("Sin aberturas",
                                   "Agregá al menos una abertura antes de exportar.")
            return

        from tools import exportar_materiales as exp

        presupuesto = self._armar()
        ruta = filedialog.asksaveasfilename(
            title="Guardar listado de materiales",
            defaultextension=".xlsx",
            initialdir=str(rutas.SALIDAS),
            initialfile=exp.nombre_sugerido(presupuesto),
            filetypes=[("Planilla de Excel", "*.xlsx")])
        if not ruta:
            return

        try:
            destino = exp.exportar(self.db, presupuesto, ruta)
        except ImportError as exc:
            messagebox.showerror("Falta openpyxl", str(exc))
            return
        except PermissionError:
            messagebox.showerror(
                "Archivo en uso",
                "No se pudo escribir la planilla.\n\n"
                "Si la tenés abierta en Excel, cerrala y volvé a intentar.")
            return
        except Exception as exc:
            messagebox.showerror("Error al exportar", str(exc))
            return

        self.app.estado(f"Listado de materiales generado: {destino.name}")
        if messagebox.askyesno("Listado generado",
                               f"{destino}\n\n¿Abrirlo ahora?"):
            self.app.abrir_ruta(destino)

    def emitir_ordenes(self):
        """Emite una orden de trabajo por cada abertura del presupuesto."""
        if not self.items:
            messagebox.showwarning("Sin aberturas",
                                   "Agregá al menos una abertura antes de emitir órdenes.")
            return

        from core import ordenes, stock
        from reports.orden_trabajo import generar_lote

        presupuesto = self._armar()
        if not presupuesto.numero:
            messagebox.showinfo("Falta el número",
                                "Ponele número al presupuesto antes de emitir las órdenes.")
            return

        aviso_stock = ("\n\nSe va a descontar el material del inventario."
                       if stock.activo(self.db) else "")
        if not messagebox.askyesno(
                "Emitir órdenes de trabajo",
                f"Se van a emitir {len(self.items)} orden(es) de trabajo, una por "
                f"abertura del presupuesto {presupuesto.numero}.\n\n"
                "Cada orden congela su despiece: aunque después cambies una fórmula "
                "o un precio, la hoja que está en el taller no se modifica."
                f"{aviso_stock}\n\n¿Continuar?"):
            return

        try:
            emision = ordenes.emitir(self.db, presupuesto)
        except ValueError as exc:
            messagebox.showerror("No se pudieron emitir", str(exc))
            return

        filas = [ordenes.obtener(self.db, numero) for numero in emision.numeros]
        carpeta = rutas.SALIDAS / "ordenes"
        try:
            generados = generar_lote(self.db, filas, carpeta)
        except Exception as exc:
            messagebox.showerror(
                "Órdenes emitidas, PDF con problemas",
                f"Las órdenes {', '.join(emision.numeros)} quedaron registradas, "
                f"pero no se pudo generar el PDF:\n\n{exc}")
            return

        texto = (f"Se emitieron {len(emision.numeros)} orden(es):\n"
                 f"   {', '.join(emision.numeros)}\n\n"
                 f"PDF en:\n{carpeta}")
        if emision.stock_movido:
            texto += f"\n\nSe descontaron {emision.stock_movido} artículos del inventario."
        if emision.aviso:
            texto += f"\n\n⚠ {emision.aviso}"

        self.app.estado(f"{len(generados)} orden(es) de trabajo emitidas.")
        if messagebox.askyesno("Órdenes de trabajo", texto + "\n\n¿Abrir la carpeta?"):
            self.app.abrir_ruta(carpeta)

    def _indice(self) -> int | None:
        indice = self.tabla.indice_seleccionado()
        if indice is None:
            messagebox.showinfo("Sin selección", "Elegí una abertura de la lista.")
        return indice

    def _mostrar_obs_item(self):
        indice = self.tabla.indice_seleccionado()
        if indice is None or indice >= len(self.items):
            self.lbl_obs_item.configure(text="")
            return
        item = self.items[indice]
        texto = item.observaciones.strip().replace("\n", " · ")
        self.lbl_obs_item.configure(
            text=f"Ítem {item.orden}: {texto[:110]}" if texto else "")

    # =====================================================================
    # Cálculo
    # =====================================================================

    def _margen(self) -> float:
        return self.campo_margen.get_fraccion()

    def _alternar_horas_auto(self):
        self.campo_horas.configure_estado(not self.chk_horas_auto.get())
        self.recalcular()

    def _cambiar_tipo_descuento(self):
        es_pct = self.combo_dto.get() == "porcentaje"
        self.campo_dto.unidad_texto = "%" if es_pct else "$"
        self.campo_dto.miles = not es_pct
        self.campo_dto.set(0)
        self.recalcular()

    def _armar(self) -> Presupuesto:
        for i, item in enumerate(self.items, start=1):
            item.orden = i

        try:
            dia, mes, anio = (int(x) for x in self.campo_fecha.get().split("/"))
            fecha = date(anio, mes, dia)
        except (ValueError, TypeError):
            fecha = date.today()

        es_pct = self.combo_dto.get() == "porcentaje"
        presupuesto = Presupuesto(
            numero=self.campo_numero.get() or self.db.numero_sugerido(),
            fecha=fecha,
            validez_dias=self.campo_validez.get_int() or 15,
            cliente=Cliente(**{k: c.get() for k, c in self.campos_cliente.items()},
                            forma_pago=self.campo_pago.get()),
            items=list(self.items),
            mano_obra=ManoObra(valor_hora=self.campo_hora.get(),
                               operarios=max(1, self.campo_operarios.get_int()),
                               horas=self.campo_horas.get(),
                               automatica=self.chk_horas_auto.get()),
            logistica=Logistica(flete_recepcion=self.campo_flete.get(),
                                envio_colocacion=self.campo_envio.get()),
            descuento_global_tipo="porcentaje" if es_pct else "monto",
            descuento_global_valor=(self.campo_dto.get() / 100.0 if es_pct
                                    else self.campo_dto.get()),
            aplica_iva=self.chk_iva.get(),
            iva_pct=self.campo_iva.get_fraccion(),
            margen_pct=self._margen(),
            observaciones_generales=self.campo_obs.get(),
            id=self._id_presupuesto,
        )
        return calcular_presupuesto(self.db, presupuesto, self.chk_mo_item.get())

    def recalcular(self, _evento=None):
        self.presupuesto = self._armar()

        if self.chk_horas_auto.get():
            self.campo_horas.set(self.presupuesto.mano_obra.horas)

        filas = []
        advertencias = []
        for resultado in self.presupuesto.resultados:
            item = resultado.item
            opcionales = []
            if item.incluye_premarco:
                opcionales.append("Premarco")
            if item.incluye_mosquitero:
                opcionales.append("Mosquitero")
            marcas = ("alerta",) if resultado.despiece.advertencias else ()
            valores = [item.orden,
                       item.descripcion,
                       item.medida_texto,
                       F.unidades(item.cantidad),
                       F.moneda(resultado.precio_unitario),
                       F.moneda(resultado.neto),
                       F.porcentaje(item.descuento_pct) if item.descuento_pct else "—"]
            if self._muestra_consumo:
                valores += [
                    F.kilos(resultado.despiece.aluminio.peso_total_kg * item.cantidad),
                    F.superficie(resultado.despiece.vidrio.m2_total * item.cantidad)]
            valores += [item.hojas, " + ".join(opcionales) or "—"]
            filas.append((tuple(valores), {"id": item.orden}, marcas))
            advertencias.extend(resultado.despiece.advertencias)

        self.tabla.cargar(filas)
        self._pintar_totales()
        self._mostrar_obs_item()

        resumen = f"{len(self.items)} ítem(s)"
        if self._muestra_consumo:
            m2 = sum(i.m2_total for i in self.items)
            peso = sum(r.despiece.aluminio.peso_total_kg * r.item.cantidad
                       for r in self.presupuesto.resultados)
            resumen += (f"   ·   {F.superficie(m2)}   ·   "
                        f"{F.kilos(peso)} de aluminio")
        if advertencias:
            self.app.estado(f"⚠  {advertencias[0]}"
                            + (f"   (+{len(advertencias) - 1} avisos)" if len(advertencias) > 1 else ""),
                            resumen)
        else:
            self.app.estado(resumen, F.moneda(self.presupuesto.resumen.total))

    def _pintar_totales(self):
        for widget in self.panel_totales.winfo_children():
            widget.destroy()

        r = self.presupuesto.resumen
        filas = [("Subtotal ítems", F.moneda(r.subtotal_items_bruto), False)]
        if r.descuentos_items:
            filas.append(("Descuentos por ítem", F.moneda(-r.descuentos_items), False))
        if r.mano_obra:
            mo = self.presupuesto.mano_obra
            filas.append((f"Mano de obra · {F.horas(mo.horas)} × {mo.operarios}",
                          F.moneda(r.mano_obra), False))
        if r.logistica:
            filas.append(("Logística", F.moneda(r.logistica), False))
        filas.append(("Subtotal general", F.moneda(r.subtotal_general), True))
        if r.descuento_global:
            etiqueta = ("Descuento global " + F.porcentaje(self.presupuesto.descuento_global_valor, 1)
                        if self.presupuesto.descuento_global_tipo == "porcentaje"
                        else "Descuento global")
            filas.append((etiqueta, F.moneda(-r.descuento_global), False))
            filas.append(("Neto", F.moneda(r.neto), False))
        if self.presupuesto.aplica_iva:
            filas.append((f"IVA {F.porcentaje(r.iva_pct)}", F.moneda(r.iva), False))
        else:
            filas.append(("Operación sin IVA", "—", False))

        for i, (etiqueta, valor, fuerte) in enumerate(filas):
            ctk.CTkLabel(self.panel_totales, text=etiqueta,
                         font=tema.fuente(11, "bold" if fuerte else "normal"),
                         text_color=tema.c("texto" if fuerte else "texto_suave"),
                         anchor="w").grid(row=i, column=0, sticky="w", pady=1)
            ctk.CTkLabel(self.panel_totales, text=valor,
                         font=tema.fuente(12, "bold" if fuerte else "normal"),
                         text_color=tema.c("texto" if fuerte else "texto_suave"),
                         anchor="e").grid(row=i, column=1, sticky="e", pady=1)

        caja = ctk.CTkFrame(self.panel_totales, fg_color=tema.c("primario"),
                            corner_radius=tema.RADIO_CHICO)
        caja.grid(row=len(filas), column=0, columnspan=2, sticky="ew", pady=(10, 0))
        caja.columnconfigure(1, weight=1)
        ctk.CTkLabel(caja, text="TOTAL", font=tema.fuente(13, "bold"),
                     text_color=tema.c("sobre_primario")).grid(
            row=0, column=0, sticky="w", padx=12, pady=9)
        ctk.CTkLabel(caja, text=F.moneda(r.total), font=tema.fuente(17, "bold"),
                     text_color=tema.c("sobre_primario"), anchor="e").grid(
            row=0, column=1, sticky="e", padx=12, pady=9)

    def _colocacion_por_m2(self):
        m2 = sum(i.m2_total for i in self.items)
        precio = self.db.parametro_float("log_colocacion_m2", 20000)
        self.campo_envio.set(m2 * precio)
        self.recalcular()
        self.app.estado(f"Colocación calculada: {F.superficie(m2)} × {F.moneda(precio)}/m²")

    # =====================================================================
    # Presupuesto
    # =====================================================================

    def _sugerir_numero(self):
        self.campo_numero.set(self.db.numero_sugerido())

    def _huella(self) -> str:
        try:
            presupuesto = self._armar()
            return repr([asdict(i) for i in presupuesto.items]) + repr(presupuesto.numero) \
                + repr(presupuesto.cliente) + presupuesto.observaciones_generales
        except Exception:
            return ""

    def _marcar_sucio(self):
        self._huella_guardada = ""

    def hay_cambios(self) -> bool:
        return self._huella() != self._huella_guardada

    def nuevo_presupuesto(self, preguntar: bool = True):
        if preguntar and self.items and hasattr(self, "_huella_guardada") and self.hay_cambios():
            if not messagebox.askyesno("Nuevo presupuesto",
                                       "Se descartarán los cambios en pantalla. ¿Continuar?"):
                return

        self.items.clear()
        self._id_presupuesto = None
        self._sugerir_numero()
        self.campo_fecha.set(date.today().strftime("%d/%m/%Y"))
        self.campo_validez.set(self.db.parametro_int("validez_dias", 15))
        self.combo_estado.set("Borrador")
        for campo in self.campos_cliente.values():
            campo.set("")
        self.campo_pago.set(FORMAS_PAGO[1])
        self.campo_hora.set(self.db.parametro_float("mo_valor_hora"))
        self.campo_operarios.set(self.db.parametro_int("mo_operarios", 1))
        self.campo_flete.set(self.db.parametro_float("log_recepcion"))
        self.campo_envio.set(self.db.parametro_float("log_envio_fijo"))
        self.campo_margen.set_fraccion(self.db.parametro_float("margen_pct", 0.30))
        self.combo_dto.set("porcentaje")
        self.campo_dto.unidad_texto = "%"
        self.campo_dto.set(0)
        self.chk_iva.set(bool(self.db.parametro_int("aplica_iva", 1)))
        self.campo_iva.set_fraccion(self.db.parametro_float("iva_pct", 0.21))
        self.chk_horas_auto.set(True)
        self.campo_horas.configure_estado(False)
        self.campo_obs.set(self.db.parametro("observaciones_defecto", "") or "")

        self.recalcular()
        self._huella_guardada = self._huella()

    def guardar(self, silencioso: bool = False) -> bool:
        presupuesto = self._armar()
        if not presupuesto.numero:
            messagebox.showwarning("Falta el número", "Ingresá el número de presupuesto.")
            return False
        if not presupuesto.items:
            messagebox.showwarning("Sin ítems", "Agregá al menos una abertura.")
            return False

        cabecera = {
            "numero": presupuesto.numero,
            "fecha": presupuesto.fecha.isoformat(),
            "validez_dias": presupuesto.validez_dias,
            "cliente_razon_social": presupuesto.cliente.razon_social,
            "cliente_documento": presupuesto.cliente.documento,
            "cliente_contacto": presupuesto.cliente.contacto,
            "cliente_localidad": presupuesto.cliente.localidad,
            "cliente_obra": presupuesto.cliente.obra,
            "cliente_forma_pago": presupuesto.cliente.forma_pago,
            "mo_valor_hora": presupuesto.mano_obra.valor_hora,
            "mo_operarios": presupuesto.mano_obra.operarios,
            "mo_horas": presupuesto.mano_obra.horas,
            "mo_automatica": int(presupuesto.mano_obra.automatica),
            "log_flete_recepcion": presupuesto.logistica.flete_recepcion,
            "log_envio_colocacion": presupuesto.logistica.envio_colocacion,
            "descuento_global_tipo": presupuesto.descuento_global_tipo,
            "descuento_global_valor": presupuesto.descuento_global_valor,
            "aplica_iva": int(presupuesto.aplica_iva),
            "iva_pct": presupuesto.iva_pct,
            "margen_pct": presupuesto.margen_pct,
            "observaciones_generales": presupuesto.observaciones_generales,
            "total": presupuesto.resumen.total,
            "estado": self.combo_estado.get(),
        }
        items = [{
            "orden": r.item.orden, "tipologia_codigo": r.item.tipologia_codigo,
            "tipologia_nombre": r.item.tipologia_nombre, "linea_id": r.item.linea_id,
            "linea_nombre": r.item.linea_nombre, "color": r.item.color,
            "ancho_mm": r.item.ancho_mm, "alto_mm": r.item.alto_mm, "hojas": r.item.hojas,
            "cantidad": r.item.cantidad, "vidrio_id": r.item.vidrio_id,
            "vidrio_nombre": r.item.vidrio_nombre,
            "incluye_premarco": int(r.item.incluye_premarco),
            "incluye_mosquitero": int(r.item.incluye_mosquitero),
            "descuento_pct": r.item.descuento_pct, "observaciones": r.item.observaciones,
            "precio_unitario": r.precio_unitario, "neto": r.neto,
        } for r in presupuesto.resultados]

        self._id_presupuesto = self.db.guardar_presupuesto(cabecera, items, presupuesto.snapshot)
        self._huella_guardada = self._huella()
        self.app.refrescar_presupuestos()
        self.app.estado(f"Presupuesto {presupuesto.numero} guardado.",
                        F.moneda(presupuesto.resumen.total))
        if not silencioso:
            messagebox.showinfo("Guardado",
                                f"Presupuesto {presupuesto.numero} guardado correctamente.")
        return True

    def generar_pdf(self):
        presupuesto = self._armar()
        if not presupuesto.items:
            messagebox.showwarning("Sin ítems", "Agregá al menos una abertura antes de exportar.")
            return

        carpeta = self.app.ajustes.carpeta_pdf or str(rutas.SALIDAS)
        ruta = filedialog.asksaveasfilename(
            title="Guardar presupuesto en PDF", defaultextension=".pdf",
            initialdir=carpeta, initialfile=nombre_sugerido(presupuesto),
            filetypes=[("PDF", "*.pdf")])
        if not ruta:
            return

        incluir = bool(self.db.parametro_int("incluir_despiece_pdf", 0))
        try:
            generar_pdf(self.db, presupuesto, ruta, incluir_despiece=incluir)
        except Exception as exc:
            messagebox.showerror("Error al generar el PDF", str(exc))
            return

        from pathlib import Path
        self.app.ajustes.carpeta_pdf = str(Path(ruta).parent)
        self.app.ajustes.guardar()
        self.app.estado(f"PDF generado: {ruta}")
        if messagebox.askyesno("PDF generado", f"Se guardó en:\n{ruta}\n\n¿Abrirlo ahora?"):
            self.app.abrir_ruta(ruta)

    def cargar_presupuesto(self, pid: int):
        cabecera, filas = self.db.cargar_presupuesto(pid)
        if cabecera is None:
            return
        self._id_presupuesto = pid
        self.campo_numero.set(cabecera["numero"])
        try:
            self.campo_fecha.set(date.fromisoformat(cabecera["fecha"]).strftime("%d/%m/%Y"))
        except ValueError:
            self.campo_fecha.set(cabecera["fecha"])
        self.campo_validez.set(cabecera["validez_dias"])
        self.combo_estado.set(cabecera["estado"] or "Borrador")

        self.campos_cliente["razon_social"].set(cabecera["cliente_razon_social"])
        self.campos_cliente["documento"].set(cabecera["cliente_documento"])
        self.campos_cliente["contacto"].set(cabecera["cliente_contacto"])
        self.campos_cliente["localidad"].set(cabecera["cliente_localidad"])
        self.campos_cliente["obra"].set(cabecera["cliente_obra"])
        self.campo_pago.set(cabecera["cliente_forma_pago"])

        self.campo_hora.set(cabecera["mo_valor_hora"])
        self.campo_operarios.set(cabecera["mo_operarios"])
        self.campo_horas.set(cabecera["mo_horas"])
        self.chk_horas_auto.set(bool(cabecera["mo_automatica"]))
        self.campo_horas.configure_estado(not self.chk_horas_auto.get())
        self.campo_flete.set(cabecera["log_flete_recepcion"])
        self.campo_envio.set(cabecera["log_envio_colocacion"])

        es_pct = cabecera["descuento_global_tipo"] == "porcentaje"
        self.combo_dto.set(cabecera["descuento_global_tipo"])
        self.campo_dto.unidad_texto = "%" if es_pct else "$"
        self.campo_dto.set(cabecera["descuento_global_valor"] * (100 if es_pct else 1))
        self.chk_iva.set(bool(cabecera["aplica_iva"]))
        self.campo_iva.set_fraccion(cabecera["iva_pct"])
        self.campo_margen.set_fraccion(cabecera["margen_pct"])
        self.campo_obs.set(cabecera["observaciones_generales"] or "")

        self.items = [Item(
            orden=f["orden"], tipologia_codigo=f["tipologia_codigo"],
            tipologia_nombre=f["tipologia_nombre"], linea_id=f["linea_id"],
            linea_nombre=f["linea_nombre"], color=f["color"], ancho_mm=f["ancho_mm"],
            alto_mm=f["alto_mm"], hojas=f["hojas"], cantidad=f["cantidad"],
            vidrio_id=f["vidrio_id"], vidrio_nombre=f["vidrio_nombre"],
            incluye_premarco=bool(f["incluye_premarco"]),
            incluye_mosquitero=bool(f["incluye_mosquitero"]),
            descuento_pct=f["descuento_pct"], observaciones=f["observaciones"] or "",
        ) for f in filas]

        self.recalcular()
        self._huella_guardada = self._huella()
        self.app.estado(f"Presupuesto {cabecera['numero']} abierto. "
                        "Los precios se recalcularon con las listas vigentes.")

    def recargar_catalogos(self):
        if self.items:
            self.recalcular()

    def al_cambiar_tema(self):
        self.lbl_obs_item.configure(text_color=tema.c("alerta"))
        if self.presupuesto:
            self._pintar_totales()


# =========================================================================
# Diálogo de carga de ítem
# =========================================================================


class DialogoItem(DialogoBase):
    """Alta y edición de una abertura, con vista previa de costos en vivo."""

    def __init__(self, master, db, margen_pct: float, item: Item | None = None,
                 orden: int = 1):
        super().__init__(master, "Editar abertura" if item else "Agregar abertura", ancho=980)
        self.db = db
        self.margen_pct = margen_pct
        self.resultado: Item | None = None
        self._orden = item.orden if item else orden
        self._id = item.id if item else None
        self._listo = False

        self.tipologias = {f"{t['codigo']} — {t['nombre']}": t for t in db.tipologias()}
        self.lineas = {l["nombre"]: l for l in db.lineas()}
        self.vidrios = {v["nombre"]: v for v in db.vidrios()}

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.pack(fill="both", expand=True, padx=20, pady=18)
        cont.columnconfigure(0, weight=3)
        cont.columnconfigure(1, weight=2)

        self._panel_datos(cont)
        self._panel_preview(cont)

        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.pack(fill="x", padx=20, pady=(0, 16))
        boton_secundario(pie, "Ver despiece", self._ver_despiece, ancho=130).pack(side="left")
        ctk.CTkButton(pie, text="Aceptar", width=140, height=36,
                      font=tema.fuente(13, "bold"), command=self._aceptar).pack(side="right")
        boton_fantasma(pie, "Cancelar", self.destroy, ancho=100).pack(side="right", padx=8)

        self._precargar(item)
        self._listo = True
        self._previsualizar()
        self.esperar()

    # -- construcción --------------------------------------------------------

    def _panel_datos(self, master):
        tarjeta = Tarjeta(master, "Datos de la abertura")
        tarjeta.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        cuerpo = tarjeta.cuerpo
        cuerpo.columnconfigure((0, 1, 2), weight=1)

        self.combo_tipologia = CampoCombo(cuerpo, "Tipología", list(self.tipologias),
                                          ancho=300, al_cambiar=self._cambiar_tipologia)
        self.combo_tipologia.grid(row=0, column=0, columnspan=3, sticky="ew", pady=4)

        self.combo_linea = CampoCombo(cuerpo, "Línea", list(self.lineas), ancho=180,
                                      al_cambiar=self._cambiar_linea)
        self.combo_linea.grid(row=1, column=0, sticky="ew", padx=(0, 10), pady=4)
        self.combo_color = CampoCombo(cuerpo, "Color / Terminación", (), ancho=180,
                                      al_cambiar=self._previsualizar)
        self.combo_color.grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=4)
        self.combo_vidrio = CampoCombo(cuerpo, "Vidrio", list(self.vidrios), ancho=180,
                                       al_cambiar=self._previsualizar)
        self.combo_vidrio.grid(row=1, column=2, sticky="ew", pady=4)

        self.campo_ancho = CampoUnidad(cuerpo, "Ancho (A)", "milimetros", 1500, ancho=110,
                                       entero=True, al_cambiar=self._previsualizar)
        self.campo_ancho.grid(row=2, column=0, sticky="ew", padx=(0, 10), pady=4)
        self.campo_alto = CampoUnidad(cuerpo, "Alto (H)", "milimetros", 1100, ancho=110,
                                      entero=True, al_cambiar=self._previsualizar)
        self.campo_alto.grid(row=2, column=1, sticky="ew", padx=(0, 10), pady=4)

        cantidades = ctk.CTkFrame(cuerpo, fg_color="transparent")
        cantidades.grid(row=2, column=2, sticky="ew", pady=4)
        cantidades.columnconfigure((0, 1), weight=1)
        self.campo_hojas = CampoUnidad(cantidades, "Hojas (N)", "", 2, ancho=60, entero=True,
                                       al_cambiar=self._previsualizar)
        self.campo_hojas.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.campo_cantidad = CampoUnidad(cantidades, "Cantidad", "unidades", 1, ancho=70,
                                          entero=True, al_cambiar=self._previsualizar)
        self.campo_cantidad.grid(row=0, column=1, sticky="ew")

        opciones = ctk.CTkFrame(cuerpo, fg_color="transparent")
        opciones.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(12, 4))
        self.chk_premarco = CampoCheck(opciones, "Incluye premarco", False, self._previsualizar)
        self.chk_premarco.pack(side="left", padx=(0, 22))
        self.chk_mosquitero = CampoCheck(opciones, "Incluye mosquitero", False,
                                         self._previsualizar)
        self.chk_mosquitero.pack(side="left", padx=(0, 22))
        self.campo_bonif = CampoPorcentaje(opciones, "", 0.0, al_cambiar=self._previsualizar)
        self.campo_bonif.pack(side="right")
        ctk.CTkLabel(opciones, text="Bonificación del ítem", font=tema.fuente(11),
                     text_color=tema.c("texto_suave")).pack(side="right", padx=(0, 8))

        self.campo_obs = CampoMemo(
            cuerpo, "Observaciones de este ítem", alto=80,
            ayuda="Ej.: vidrio esmerilado · manijón especial · colocación en altura · "
                  "color negro semimate")
        self.campo_obs.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(6, 0))

    def _panel_preview(self, master):
        self.tarjeta_preview = Tarjeta(master, "Costos de esta abertura")
        self.tarjeta_preview.grid(row=0, column=1, sticky="nsew")
        self.panel = ctk.CTkFrame(self.tarjeta_preview.cuerpo, fg_color="transparent")
        self.panel.pack(fill="both", expand=True)
        self.panel.columnconfigure(1, weight=1)

    # -- lógica --------------------------------------------------------------

    def _precargar(self, item):
        claves = list(self.tipologias)
        if item:
            for clave, tip in self.tipologias.items():
                if tip["codigo"] == item.tipologia_codigo:
                    self.combo_tipologia.set(clave)
                    break
            else:
                self.combo_tipologia.set(claves[0] if claves else "")
            self.combo_linea.set(item.linea_nombre)
            self.campo_ancho.set(item.ancho_mm)
            self.campo_alto.set(item.alto_mm)
            self.campo_hojas.set(item.hojas)
            self.campo_cantidad.set(item.cantidad)
            self.chk_premarco.set(item.incluye_premarco)
            self.chk_mosquitero.set(item.incluye_mosquitero)
            self.campo_bonif.set_fraccion(item.descuento_pct)
            self.campo_obs.set(item.observaciones)
            self._cambiar_linea(previsualizar=False)
            self.combo_color.set(item.color)
            self.combo_vidrio.set(item.vidrio_nombre)
            self._aplicar_reglas_tipologia()
        else:
            if claves:
                self.combo_tipologia.set(claves[0])
            if self.lineas:
                self.combo_linea.set(next(iter(self.lineas)))
            if self.vidrios:
                self.combo_vidrio.set(next(iter(self.vidrios)))
            self._cambiar_tipologia(previsualizar=False)
            self._cambiar_linea(previsualizar=False)

    def _aplicar_reglas_tipologia(self):
        tip = self.tipologias.get(self.combo_tipologia.get())
        if not tip:
            return
        if tip["admite_mosquitero"]:
            self.chk_mosquitero.configure(state="normal")
        else:
            self.chk_mosquitero.set(False)
            self.chk_mosquitero.configure(state="disabled")
        if tip["admite_premarco"]:
            self.chk_premarco.configure(state="normal")
        else:
            self.chk_premarco.set(False)
            self.chk_premarco.configure(state="disabled")

    def _cambiar_tipologia(self, previsualizar: bool = True):
        tip = self.tipologias.get(self.combo_tipologia.get())
        if tip:
            self.campo_hojas.set(tip["hojas_default"])
        self._aplicar_reglas_tipologia()
        if previsualizar:
            self._previsualizar()

    def _cambiar_linea(self, previsualizar: bool = True):
        linea = self.lineas.get(self.combo_linea.get())
        colores = [c["color"] for c in self.db.colores_de_linea(linea["id"])] if linea else []
        self.combo_color.opciones(colores)
        if previsualizar:
            self._previsualizar()

    def _construir_item(self) -> Item | None:
        tip = self.tipologias.get(self.combo_tipologia.get())
        linea = self.lineas.get(self.combo_linea.get())
        vidrio = self.vidrios.get(self.combo_vidrio.get())
        if not tip or not linea:
            return None
        return Item(
            orden=self._orden, tipologia_codigo=tip["codigo"], tipologia_nombre=tip["nombre"],
            linea_id=linea["id"], linea_nombre=linea["nombre"], color=self.combo_color.get(),
            ancho_mm=self.campo_ancho.get(), alto_mm=self.campo_alto.get(),
            hojas=max(1, self.campo_hojas.get_int()),
            cantidad=max(1, self.campo_cantidad.get_int()),
            vidrio_id=vidrio["id"] if vidrio else 0,
            vidrio_nombre=vidrio["nombre"] if vidrio else "",
            incluye_premarco=self.chk_premarco.get(),
            incluye_mosquitero=self.chk_mosquitero.get(),
            descuento_pct=self.campo_bonif.get_fraccion(),
            observaciones=self.campo_obs.get(), id=self._id)

    def _previsualizar(self, _evento=None):
        if not self._listo:
            return
        item = self._construir_item()
        for widget in self.panel.winfo_children():
            widget.destroy()
        if not item or item.ancho_mm <= 0 or item.alto_mm <= 0:
            ctk.CTkLabel(self.panel, text="Completá las medidas para ver el costo.",
                         font=tema.fuente(11), text_color=tema.c("texto_tenue")).grid(
                row=0, column=0, columnspan=2, sticky="w")
            return

        try:
            resultado = calcular_item(self.db, item, self.margen_pct)
        except Exception as exc:
            ctk.CTkLabel(self.panel, text=f"No se pudo calcular: {exc}", wraplength=280,
                         font=tema.fuente(11), text_color=tema.c("error"), justify="left").grid(
                row=0, column=0, columnspan=2, sticky="w")
            return

        c, d = resultado.costos, resultado.despiece
        modo = "por peso" if d.aluminio.modo_costeo == "kg" else "por m²"
        filas = [
            (f"Aluminio ({modo})", F.moneda(c.aluminio), F.kilos(d.aluminio.peso_total_kg)),
            ("Vidrio", F.moneda(c.vidrio), F.superficie(d.vidrio.m2_total)),
            ("Accesorios", F.moneda(c.accesorios), ""),
        ]
        if c.premarco:
            filas.append(("Premarco", F.moneda(c.premarco), ""))
        if c.mosquitero:
            filas.append(("Mosquitero", F.moneda(c.mosquitero), ""))

        fila = 0
        for etiqueta, valor, extra in filas:
            ctk.CTkLabel(self.panel, text=etiqueta, font=tema.fuente(11),
                         text_color=tema.c("texto_suave"), anchor="w").grid(
                row=fila, column=0, sticky="w", pady=2)
            ctk.CTkLabel(self.panel, text=valor, font=tema.fuente(12),
                         text_color=tema.c("texto"), anchor="e").grid(
                row=fila, column=1, sticky="e", pady=2)
            if extra:
                fila += 1
                ctk.CTkLabel(self.panel, text=extra, font=tema.fuente(10),
                             text_color=tema.c("texto_tenue"), anchor="w").grid(
                    row=fila, column=0, columnspan=2, sticky="w", pady=(0, 2))
            fila += 1

        separador = ctk.CTkFrame(self.panel, height=1, fg_color=tema.c("borde_suave"))
        separador.grid(row=fila, column=0, columnspan=2, sticky="ew", pady=8)
        fila += 1

        for etiqueta, valor, fuerte in (
                ("Costo unitario", F.moneda(resultado.costo_unitario), False),
                (f"Precio unitario · margen {F.porcentaje(self.margen_pct)}",
                 F.moneda(resultado.precio_unitario), False),
                (f"Importe · {F.unidades(item.cantidad)}"
                 + (f" − {F.porcentaje(item.descuento_pct)}" if item.descuento_pct else ""),
                 F.moneda(resultado.neto), True)):
            ctk.CTkLabel(self.panel, text=etiqueta,
                         font=tema.fuente(11, "bold" if fuerte else "normal"),
                         text_color=tema.c("texto" if fuerte else "texto_suave"),
                         anchor="w", wraplength=170, justify="left").grid(
                row=fila, column=0, sticky="w", pady=2)
            ctk.CTkLabel(self.panel, text=valor,
                         font=tema.fuente(15 if fuerte else 12, "bold" if fuerte else "normal"),
                         text_color=tema.c("acento" if fuerte else "texto"), anchor="e").grid(
                row=fila, column=1, sticky="e", pady=2)
            fila += 1

        if d.advertencias:
            ctk.CTkLabel(self.panel, text="⚠  " + d.advertencias[0], font=tema.fuente(10),
                         text_color=tema.c("alerta"), wraplength=280, justify="left",
                         anchor="w").grid(row=fila, column=0, columnspan=2,
                                          sticky="w", pady=(8, 0))

    def _ver_despiece(self):
        item = self._construir_item()
        if not item:
            return
        resultado = calcular_item(self.db, item, self.margen_pct)
        VentanaDespiece(self, resultado.despiece,
                        f"{item.tipologia_nombre} · {item.medida_texto}")

    def _aceptar(self):
        item = self._construir_item()
        if item is None:
            messagebox.showwarning("Faltan datos", "Elegí tipología y línea.", parent=self)
            return
        if item.ancho_mm <= 0 or item.alto_mm <= 0:
            messagebox.showwarning("Medidas inválidas",
                                   "El ancho y el alto deben ser mayores a 0 mm.", parent=self)
            return
        if not item.color:
            messagebox.showwarning(
                "Falta el color",
                "La línea elegida no tiene colores con precio cargado.\n\n"
                "Cargalos en Materiales y Costos → Líneas y precios.", parent=self)
            return
        self.resultado = item
        self.destroy()
