"""
Módulo 2 — Armado del presupuesto, descuentos y observaciones.

Contiene el diálogo de carga de ítems (con vista previa de costos en vivo) y el
panel de totales con el desglose Subtotal -> Descuentos -> IVA -> Total.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core.calculo import calcular_item, calcular_presupuesto, horas_sugeridas
from core.database import RUTA_SALIDAS
from core.models import Cliente, Item, Logistica, ManoObra, Presupuesto
from core.utils import a_float, a_int, fmt_money, fmt_num, fmt_pct, pct_desde_texto
from reports.pdf_generator import generar_pdf, nombre_sugerido
from .tab_materiales import VentanaDespiece
from .widgets import FormDialog

FORMAS_PAGO = ["Contado", "50% anticipo / 50% contra entrega", "30/30/40",
               "Transferencia bancaria", "Cheque a 30 días", "A convenir"]


class TabCotizacion(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=8)
        self.app = app
        self.db = app.db
        self.items: list[Item] = []
        self.presupuesto: Presupuesto | None = None
        self._id_presupuesto: int | None = None

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self._barra_superior()
        self._panel_cliente()
        self._panel_items()
        self._panel_inferior()

        self.nuevo_presupuesto(preguntar=False)

    # =====================================================================
    # Construcción de la interfaz
    # =====================================================================

    def _barra_superior(self):
        barra = ttk.Frame(self)
        barra.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(barra, text="Presupuesto N°", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.var_numero = tk.StringVar()
        ttk.Entry(barra, textvariable=self.var_numero, width=14,
                  font=("Segoe UI", 10, "bold")).pack(side="left", padx=(6, 2))
        ttk.Button(barra, text="↻", width=3, command=self._sugerir_numero).pack(side="left")
        ttk.Label(barra, text="(editable)", foreground="#6B7A88",
                  font=("Segoe UI", 8)).pack(side="left", padx=(4, 16))

        ttk.Label(barra, text="Fecha:").pack(side="left")
        self.var_fecha = tk.StringVar(value=date.today().strftime("%d/%m/%Y"))
        ttk.Entry(barra, textvariable=self.var_fecha, width=12).pack(side="left", padx=(4, 16))

        ttk.Label(barra, text="Validez (días):").pack(side="left")
        self.var_validez = tk.StringVar(value=str(self.db.parametro_int("validez_dias", 15)))
        ttk.Entry(barra, textvariable=self.var_validez, width=5).pack(side="left", padx=4)

        ttk.Button(barra, text="Generar PDF", command=self.generar_pdf).pack(side="right", padx=3)
        ttk.Button(barra, text="Guardar", command=self.guardar).pack(side="right", padx=3)
        ttk.Button(barra, text="Nuevo", command=self.nuevo_presupuesto).pack(side="right", padx=3)

    def _panel_cliente(self):
        caja = ttk.LabelFrame(self, text=" Datos del cliente ", padding=8)
        caja.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        for c in (1, 3, 5):
            caja.columnconfigure(c, weight=1)

        self.var_cli = {k: tk.StringVar() for k in
                        ("razon_social", "documento", "contacto", "localidad", "obra", "forma_pago")}

        campos = [
            ("Cliente / Razón Social", "razon_social", 0, 0, 28),
            ("DNI / CUIT", "documento", 0, 2, 18),
            ("Contacto", "contacto", 0, 4, 20),
            ("Obra / Dirección", "obra", 1, 0, 28),
            ("Localidad", "localidad", 1, 2, 18),
        ]
        for etiqueta, clave, fila, col, ancho in campos:
            ttk.Label(caja, text=etiqueta + ":").grid(row=fila, column=col, sticky="w",
                                                     padx=(0, 6), pady=3)
            ttk.Entry(caja, textvariable=self.var_cli[clave], width=ancho).grid(
                row=fila, column=col + 1, sticky="ew", padx=(0, 14), pady=3)

        ttk.Label(caja, text="Forma de pago:").grid(row=1, column=4, sticky="w", padx=(0, 6))
        ttk.Combobox(caja, textvariable=self.var_cli["forma_pago"], values=FORMAS_PAGO,
                     width=20).grid(row=1, column=5, sticky="ew", pady=3)

    def _panel_items(self):
        caja = ttk.LabelFrame(self, text=" Ítems / Aberturas ", padding=8)
        caja.grid(row=2, column=0, sticky="nsew")
        caja.columnconfigure(0, weight=1)
        caja.rowconfigure(1, weight=1)

        barra = ttk.Frame(caja)
        barra.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        for texto, comando in (("Agregar ítem", self.agregar_item),
                               ("Editar", self.editar_item),
                               ("Duplicar", self.duplicar_item),
                               ("Eliminar", self.eliminar_item),
                               ("▲", lambda: self.mover_item(-1)),
                               ("▼", lambda: self.mover_item(1)),
                               ("Ver despiece", self.ver_despiece)):
            ancho = 3 if texto in ("▲", "▼") else None
            ttk.Button(barra, text=texto, command=comando,
                       **({"width": ancho} if ancho else {})).pack(side="left", padx=2)

        cols = ("orden", "descripcion", "medida", "hojas", "cant", "opc", "unit", "bonif", "neto")
        self.tv = ttk.Treeview(caja, columns=cols, show="headings", selectmode="browse")
        for c, t, w, a in (("orden", "#", 34, "center"), ("descripcion", "Descripción", 330, "w"),
                           ("medida", "Medidas (mm)", 110, "center"), ("hojas", "Hojas", 45, "center"),
                           ("cant", "Cant.", 45, "center"), ("opc", "Opcionales", 130, "w"),
                           ("unit", "P. Unitario", 110, "e"), ("bonif", "Bonif.", 60, "e"),
                           ("neto", "Importe", 120, "e")):
            self.tv.heading(c, text=t)
            self.tv.column(c, width=w, anchor=a, stretch=(c == "descripcion"))
        self.tv.grid(row=1, column=0, sticky="nsew")
        self.tv.bind("<Double-1>", lambda _e: self.editar_item())

        barra_v = ttk.Scrollbar(caja, orient="vertical", command=self.tv.yview)
        barra_v.grid(row=1, column=1, sticky="ns")
        self.tv.configure(yscrollcommand=barra_v.set)

        self.lbl_obs_item = ttk.Label(caja, text="", foreground="#7A5C1E", wraplength=900,
                                      justify="left", font=("Segoe UI", 8))
        self.lbl_obs_item.grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.tv.bind("<<TreeviewSelect>>", self._mostrar_obs_item)

    def _panel_inferior(self):
        marco = ttk.Frame(self)
        marco.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        marco.columnconfigure(0, weight=3)
        marco.columnconfigure(1, weight=2)
        marco.columnconfigure(2, weight=2)

        # --- Observaciones generales
        caja_obs = ttk.LabelFrame(marco, text=" Observaciones generales del presupuesto ", padding=6)
        caja_obs.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        caja_obs.columnconfigure(0, weight=1)
        self.txt_obs = tk.Text(caja_obs, height=9, wrap="word", font=("Segoe UI", 9))
        self.txt_obs.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(caja_obs, orient="vertical", command=self.txt_obs.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.txt_obs.configure(yscrollcommand=sb.set)

        # --- Costos operativos del presupuesto
        caja_costos = ttk.LabelFrame(marco, text=" Mano de obra y logística ", padding=6)
        caja_costos.grid(row=0, column=1, sticky="nsew", padx=(0, 8))
        caja_costos.columnconfigure(1, weight=1)

        self.var_mo_hora = tk.StringVar(value=fmt_num(self.db.parametro_float("mo_valor_hora"), 2))
        self.var_mo_oper = tk.StringVar(value=str(self.db.parametro_int("mo_operarios", 1)))
        self.var_mo_horas = tk.StringVar(value="0")
        self.var_mo_auto = tk.BooleanVar(value=True)
        self.var_mo_en_item = tk.BooleanVar(value=False)
        self.var_flete = tk.StringVar(value=fmt_num(self.db.parametro_float("log_recepcion"), 2))
        self.var_envio = tk.StringVar(value=fmt_num(self.db.parametro_float("log_envio_fijo"), 2))

        filas = [
            ("Valor hora-hombre", self.var_mo_hora),
            ("Cantidad de operarios", self.var_mo_oper),
            ("Horas estimadas", self.var_mo_horas),
            ("Flete / recepción de materiales", self.var_flete),
            ("Envío / colocación en obra", self.var_envio),
        ]
        for i, (etiqueta, var) in enumerate(filas):
            ttk.Label(caja_costos, text=etiqueta + ":").grid(row=i, column=0, sticky="w", pady=2)
            e = ttk.Entry(caja_costos, textvariable=var, width=12, justify="right")
            e.grid(row=i, column=1, sticky="ew", pady=2)
            e.bind("<FocusOut>", lambda _e: self.recalcular())
            e.bind("<Return>", lambda _e: self.recalcular())

        ttk.Checkbutton(caja_costos, text="Estimar horas automáticamente (por m²)",
                        variable=self.var_mo_auto,
                        command=self.recalcular).grid(row=5, column=0, columnspan=2, sticky="w",
                                                      pady=(4, 0))
        ttk.Checkbutton(caja_costos, text="Cargar mano de obra por m² dentro de cada ítem",
                        variable=self.var_mo_en_item,
                        command=self.recalcular).grid(row=6, column=0, columnspan=2, sticky="w")
        ttk.Button(caja_costos, text="Calcular colocación por m²",
                   command=self._colocacion_por_m2).grid(row=7, column=0, columnspan=2,
                                                         sticky="ew", pady=(6, 0))

        # --- Totales
        caja_tot = ttk.LabelFrame(marco, text=" Resumen y descuentos ", padding=6)
        caja_tot.grid(row=0, column=2, sticky="nsew")
        caja_tot.columnconfigure(1, weight=1)

        self.var_margen = tk.StringVar(value=fmt_num(self.db.parametro_float("margen_pct") * 100, 2))
        self.var_dto_tipo = tk.StringVar(value="porcentaje")
        self.var_dto_valor = tk.StringVar(value="0")
        self.var_iva = tk.BooleanVar(value=bool(self.db.parametro_int("aplica_iva", 1)))
        self.var_iva_pct = tk.StringVar(value=fmt_num(self.db.parametro_float("iva_pct") * 100, 2))

        ttk.Label(caja_tot, text="Margen (%):").grid(row=0, column=0, sticky="w", pady=2)
        e = ttk.Entry(caja_tot, textvariable=self.var_margen, width=10, justify="right")
        e.grid(row=0, column=1, sticky="ew")
        e.bind("<FocusOut>", lambda _e: self.recalcular())
        e.bind("<Return>", lambda _e: self.recalcular())

        ttk.Label(caja_tot, text="Descuento global:").grid(row=1, column=0, sticky="w", pady=2)
        marco_dto = ttk.Frame(caja_tot)
        marco_dto.grid(row=1, column=1, sticky="ew")
        marco_dto.columnconfigure(0, weight=1)
        e = ttk.Entry(marco_dto, textvariable=self.var_dto_valor, width=8, justify="right")
        e.grid(row=0, column=0, sticky="ew")
        e.bind("<FocusOut>", lambda _e: self.recalcular())
        e.bind("<Return>", lambda _e: self.recalcular())
        cb = ttk.Combobox(marco_dto, textvariable=self.var_dto_tipo, state="readonly", width=6,
                          values=["porcentaje", "monto"])
        cb.grid(row=0, column=1, padx=(4, 0))
        cb.bind("<<ComboboxSelected>>", lambda _e: self.recalcular())

        ttk.Checkbutton(caja_tot, text="Facturar con IVA", variable=self.var_iva,
                        command=self.recalcular).grid(row=2, column=0, sticky="w", pady=2)
        e = ttk.Entry(caja_tot, textvariable=self.var_iva_pct, width=10, justify="right")
        e.grid(row=2, column=1, sticky="ew")
        e.bind("<FocusOut>", lambda _e: self.recalcular())
        e.bind("<Return>", lambda _e: self.recalcular())

        ttk.Separator(caja_tot).grid(row=3, column=0, columnspan=2, sticky="ew", pady=6)

        # ttk.Frame no expone 'background' vía cget: se pide al tema activo.
        fondo = ttk.Style().lookup("TFrame", "background") or "#F0F0F0"
        self.lbl_totales = tk.Text(caja_tot, height=9, width=34, font=("Consolas", 9),
                                   relief="flat", background=fondo,
                                   state="disabled", wrap="none")
        self.lbl_totales.grid(row=4, column=0, columnspan=2, sticky="nsew")

    # =====================================================================
    # Acciones sobre ítems
    # =====================================================================

    def agregar_item(self):
        dlg = DialogoItem(self.winfo_toplevel(), self.db, self._margen(), orden=len(self.items) + 1)
        if dlg.resultado:
            self.items.append(dlg.resultado)
            self.recalcular()

    def editar_item(self):
        idx = self._indice_seleccionado()
        if idx is None:
            return
        dlg = DialogoItem(self.winfo_toplevel(), self.db, self._margen(), item=self.items[idx])
        if dlg.resultado:
            self.items[idx] = dlg.resultado
            self.recalcular()

    def duplicar_item(self):
        idx = self._indice_seleccionado()
        if idx is None:
            return
        import copy
        nuevo = copy.deepcopy(self.items[idx])
        nuevo.id = None
        nuevo.orden = len(self.items) + 1
        self.items.append(nuevo)
        self.recalcular()

    def eliminar_item(self):
        idx = self._indice_seleccionado()
        if idx is None:
            return
        del self.items[idx]
        self.recalcular()

    def mover_item(self, delta):
        idx = self._indice_seleccionado()
        if idx is None:
            return
        nuevo = idx + delta
        if not 0 <= nuevo < len(self.items):
            return
        self.items[idx], self.items[nuevo] = self.items[nuevo], self.items[idx]
        self.recalcular()
        hijos = self.tv.get_children()
        if nuevo < len(hijos):
            self.tv.selection_set(hijos[nuevo])

    def ver_despiece(self):
        idx = self._indice_seleccionado()
        if idx is None:
            return
        res = calcular_item(self.db, self.items[idx], self._margen())
        VentanaDespiece(self.winfo_toplevel(), res.despiece,
                        f"Ítem {self.items[idx].orden} · {self.items[idx].medida_texto}")

    def _indice_seleccionado(self):
        sel = self.tv.selection()
        if not sel:
            messagebox.showinfo("Sin selección", "Elegí un ítem de la lista.", parent=self)
            return None
        return self.tv.index(sel[0])

    def _mostrar_obs_item(self, _evento=None):
        sel = self.tv.selection()
        if not sel:
            self.lbl_obs_item.config(text="")
            return
        item = self.items[self.tv.index(sel[0])]
        texto = item.observaciones.strip().replace("\n", " · ")
        self.lbl_obs_item.config(text=f"Observaciones del ítem {item.orden}: {texto}" if texto else "")

    # =====================================================================
    # Cálculo y presentación
    # =====================================================================

    def _margen(self) -> float:
        return pct_desde_texto(self.var_margen.get(), self.db.parametro_float("margen_pct"))

    def _armar_presupuesto(self) -> Presupuesto:
        for i, item in enumerate(self.items, start=1):
            item.orden = i

        try:
            fecha = date(*reversed([int(x) for x in self.var_fecha.get().split("/")]))
        except (ValueError, TypeError):
            fecha = date.today()

        pres = Presupuesto(
            numero=self.var_numero.get().strip() or self.db.numero_sugerido(),
            fecha=fecha,
            validez_dias=a_int(self.var_validez.get(), 15),
            cliente=Cliente(**{k: v.get().strip() for k, v in self.var_cli.items()}),
            items=list(self.items),
            mano_obra=ManoObra(
                valor_hora=a_float(self.var_mo_hora.get()),
                operarios=max(1, a_int(self.var_mo_oper.get(), 1)),
                horas=a_float(self.var_mo_horas.get()),
                automatica=self.var_mo_auto.get(),
            ),
            logistica=Logistica(
                flete_recepcion=a_float(self.var_flete.get()),
                envio_colocacion=a_float(self.var_envio.get()),
            ),
            descuento_global_tipo=self.var_dto_tipo.get(),
            descuento_global_valor=(pct_desde_texto(self.var_dto_valor.get())
                                    if self.var_dto_tipo.get() == "porcentaje"
                                    else a_float(self.var_dto_valor.get())),
            aplica_iva=self.var_iva.get(),
            iva_pct=pct_desde_texto(self.var_iva_pct.get(), 0.21),
            margen_pct=self._margen(),
            observaciones_generales=self.txt_obs.get("1.0", "end").rstrip(),
            id=self._id_presupuesto,
        )
        return calcular_presupuesto(self.db, pres, self.var_mo_en_item.get())

    def recalcular(self, _evento=None):
        self.presupuesto = self._armar_presupuesto()

        if self.var_mo_auto.get():
            self.var_mo_horas.set(fmt_num(self.presupuesto.mano_obra.horas, 2))

        self.tv.delete(*self.tv.get_children())
        advertencias = []
        for res in self.presupuesto.resultados:
            it = res.item
            opcionales = []
            if it.incluye_premarco:
                opcionales.append("Premarco")
            if it.incluye_mosquitero:
                opcionales.append("Mosquitero")
            self.tv.insert("", "end", values=(
                it.orden, it.descripcion, it.medida_texto, it.hojas, it.cantidad,
                " + ".join(opcionales) or "—",
                fmt_money(res.precio_unitario),
                fmt_pct(it.descuento_pct, 0) if it.descuento_pct else "—",
                fmt_money(res.neto),
            ))
            advertencias.extend(res.despiece.advertencias)

        self._pintar_totales(self.presupuesto)

        if advertencias:
            self.app.estado(f"⚠ {advertencias[0]}"
                            + (f"  (+{len(advertencias) - 1} avisos más)" if len(advertencias) > 1 else ""))
        else:
            self.app.estado(f"{len(self.items)} ítem(s) · "
                            f"{fmt_num(sum(i.m2_total for i in self.items), 2)} m² totales")

    def _pintar_totales(self, pres):
        r = pres.resumen
        lineas = [f"{'Subtotal ítems':<24}{fmt_money(r.subtotal_items_bruto):>16}"]
        if r.descuentos_items:
            lineas.append(f"{'(-) Dto. por ítem':<24}{fmt_money(-r.descuentos_items):>16}")
        if r.mano_obra:
            lineas.append(f"{'(+) Mano de obra':<24}{fmt_money(r.mano_obra):>16}")
        if r.logistica:
            lineas.append(f"{'(+) Logística':<24}{fmt_money(r.logistica):>16}")
        lineas.append(f"{'Subtotal general':<24}{fmt_money(r.subtotal_general):>16}")
        if r.descuento_global:
            lineas.append(f"{'(-) Dto. global':<24}{fmt_money(-r.descuento_global):>16}")
            lineas.append(f"{'Neto':<24}{fmt_money(r.neto):>16}")
        if pres.aplica_iva:
            lineas.append(f"{'(+) IVA ' + fmt_pct(r.iva_pct, 0):<24}{fmt_money(r.iva):>16}")
        else:
            lineas.append(f"{'Sin IVA':<24}{'':>16}")
        lineas.append("─" * 40)
        lineas.append(f"{'TOTAL':<24}{fmt_money(r.total):>16}")

        self.lbl_totales.configure(state="normal")
        self.lbl_totales.delete("1.0", "end")
        self.lbl_totales.insert("1.0", "\n".join(lineas))
        self.lbl_totales.configure(state="disabled")

    def _colocacion_por_m2(self):
        m2 = sum(i.m2_total for i in self.items)
        precio = self.db.parametro_float("log_colocacion_m2", 20000)
        self.var_envio.set(fmt_num(m2 * precio, 2))
        self.recalcular()

    # =====================================================================
    # Presupuesto: nuevo / guardar / cargar / PDF
    # =====================================================================

    def _sugerir_numero(self):
        self.var_numero.set(self.db.numero_sugerido())

    def nuevo_presupuesto(self, preguntar=True):
        if preguntar and self.items and not messagebox.askyesno(
                "Nuevo presupuesto", "Se descartarán los datos en pantalla. ¿Continuar?"):
            return
        self.items.clear()
        self._id_presupuesto = None
        self._sugerir_numero()
        self.var_fecha.set(date.today().strftime("%d/%m/%Y"))
        self.var_validez.set(str(self.db.parametro_int("validez_dias", 15)))
        for var in self.var_cli.values():
            var.set("")
        self.var_dto_valor.set("0")
        self.var_dto_tipo.set("porcentaje")
        self.var_flete.set(fmt_num(self.db.parametro_float("log_recepcion"), 2))
        self.var_envio.set(fmt_num(self.db.parametro_float("log_envio_fijo"), 2))
        self.var_mo_hora.set(fmt_num(self.db.parametro_float("mo_valor_hora"), 2))
        self.var_mo_oper.set(str(self.db.parametro_int("mo_operarios", 1)))
        self.var_margen.set(fmt_num(self.db.parametro_float("margen_pct") * 100, 2))
        self.var_iva.set(bool(self.db.parametro_int("aplica_iva", 1)))
        self.var_iva_pct.set(fmt_num(self.db.parametro_float("iva_pct") * 100, 2))
        self.txt_obs.delete("1.0", "end")
        self.txt_obs.insert("1.0", self.db.parametro("observaciones_defecto", "") or "")
        self.recalcular()

    def guardar(self) -> bool:
        pres = self._armar_presupuesto()
        if not pres.numero:
            messagebox.showwarning("Falta el número", "Ingresá el número de presupuesto.")
            return False
        if not pres.items:
            messagebox.showwarning("Sin ítems", "Agregá al menos una abertura.")
            return False

        cab = {
            "numero": pres.numero,
            "fecha": pres.fecha.isoformat(),
            "validez_dias": pres.validez_dias,
            "cliente_razon_social": pres.cliente.razon_social,
            "cliente_documento": pres.cliente.documento,
            "cliente_contacto": pres.cliente.contacto,
            "cliente_localidad": pres.cliente.localidad,
            "cliente_obra": pres.cliente.obra,
            "cliente_forma_pago": pres.cliente.forma_pago,
            "mo_valor_hora": pres.mano_obra.valor_hora,
            "mo_operarios": pres.mano_obra.operarios,
            "mo_horas": pres.mano_obra.horas,
            "mo_automatica": int(pres.mano_obra.automatica),
            "log_flete_recepcion": pres.logistica.flete_recepcion,
            "log_envio_colocacion": pres.logistica.envio_colocacion,
            "descuento_global_tipo": pres.descuento_global_tipo,
            "descuento_global_valor": pres.descuento_global_valor,
            "aplica_iva": int(pres.aplica_iva),
            "iva_pct": pres.iva_pct,
            "margen_pct": pres.margen_pct,
            "observaciones_generales": pres.observaciones_generales,
            "total": pres.resumen.total,
        }
        items = [{
            "orden": r.item.orden,
            "tipologia_codigo": r.item.tipologia_codigo,
            "tipologia_nombre": r.item.tipologia_nombre,
            "linea_id": r.item.linea_id,
            "linea_nombre": r.item.linea_nombre,
            "color": r.item.color,
            "ancho_mm": r.item.ancho_mm,
            "alto_mm": r.item.alto_mm,
            "hojas": r.item.hojas,
            "cantidad": r.item.cantidad,
            "vidrio_id": r.item.vidrio_id,
            "vidrio_nombre": r.item.vidrio_nombre,
            "incluye_premarco": int(r.item.incluye_premarco),
            "incluye_mosquitero": int(r.item.incluye_mosquitero),
            "descuento_pct": r.item.descuento_pct,
            "observaciones": r.item.observaciones,
            "precio_unitario": r.precio_unitario,
            "neto": r.neto,
        } for r in pres.resultados]

        self._id_presupuesto = self.db.guardar_presupuesto(cab, items, pres.snapshot)
        self.app.refrescar_presupuestos()
        self.app.estado(f"Presupuesto {pres.numero} guardado · Total {fmt_money(pres.resumen.total)}")
        messagebox.showinfo("Guardado", f"Presupuesto {pres.numero} guardado correctamente.")
        return True

    def generar_pdf(self):
        pres = self._armar_presupuesto()
        if not pres.items:
            messagebox.showwarning("Sin ítems", "Agregá al menos una abertura antes de exportar.")
            return

        incluir = bool(self.db.parametro_int("incluir_despiece_pdf", 0))
        ruta = filedialog.asksaveasfilename(
            title="Guardar presupuesto en PDF",
            defaultextension=".pdf",
            initialdir=str(RUTA_SALIDAS),
            initialfile=nombre_sugerido(pres),
            filetypes=[("PDF", "*.pdf")],
        )
        if not ruta:
            return

        try:
            generar_pdf(self.db, pres, ruta, incluir_despiece=incluir)
        except Exception as exc:  # el usuario necesita el motivo, no un traceback
            messagebox.showerror("Error al generar el PDF", str(exc))
            return

        self.app.estado(f"PDF generado: {ruta}")
        if messagebox.askyesno("PDF generado", f"Se guardó en:\n{ruta}\n\n¿Abrirlo ahora?"):
            self._abrir(ruta)

    @staticmethod
    def _abrir(ruta):
        try:
            if sys.platform.startswith("win"):
                os.startfile(ruta)  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.run(["open", ruta], check=False)
            else:
                subprocess.run(["xdg-open", ruta], check=False)
        except OSError as exc:
            messagebox.showwarning("No se pudo abrir", str(exc))

    def cargar_presupuesto(self, pid: int):
        cab, filas = self.db.cargar_presupuesto(pid)
        if cab is None:
            return
        self._id_presupuesto = pid
        self.var_numero.set(cab["numero"])
        try:
            self.var_fecha.set(date.fromisoformat(cab["fecha"]).strftime("%d/%m/%Y"))
        except ValueError:
            self.var_fecha.set(cab["fecha"])
        self.var_validez.set(str(cab["validez_dias"]))

        self.var_cli["razon_social"].set(cab["cliente_razon_social"])
        self.var_cli["documento"].set(cab["cliente_documento"])
        self.var_cli["contacto"].set(cab["cliente_contacto"])
        self.var_cli["localidad"].set(cab["cliente_localidad"])
        self.var_cli["obra"].set(cab["cliente_obra"])
        self.var_cli["forma_pago"].set(cab["cliente_forma_pago"])

        self.var_mo_hora.set(fmt_num(cab["mo_valor_hora"], 2))
        self.var_mo_oper.set(str(cab["mo_operarios"]))
        self.var_mo_horas.set(fmt_num(cab["mo_horas"], 2))
        self.var_mo_auto.set(bool(cab["mo_automatica"]))
        self.var_flete.set(fmt_num(cab["log_flete_recepcion"], 2))
        self.var_envio.set(fmt_num(cab["log_envio_colocacion"], 2))

        self.var_dto_tipo.set(cab["descuento_global_tipo"])
        self.var_dto_valor.set(fmt_num(cab["descuento_global_valor"] * 100, 2)
                               if cab["descuento_global_tipo"] == "porcentaje"
                               else fmt_num(cab["descuento_global_valor"], 2))
        self.var_iva.set(bool(cab["aplica_iva"]))
        self.var_iva_pct.set(fmt_num(cab["iva_pct"] * 100, 2))
        self.var_margen.set(fmt_num(cab["margen_pct"] * 100, 2))

        self.txt_obs.delete("1.0", "end")
        self.txt_obs.insert("1.0", cab["observaciones_generales"] or "")

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
        self.app.estado(f"Presupuesto {cab['numero']} cargado. "
                        f"Los precios se recalcularon con las listas vigentes.")


# =========================================================================
# Diálogo de carga de ítem
# =========================================================================


class DialogoItem(tk.Toplevel):
    """Alta / edición de una abertura, con vista previa de costos en vivo."""

    def __init__(self, parent, db, margen_pct, item: Item | None = None, orden: int = 1):
        super().__init__(parent)
        self.db = db
        self.margen_pct = margen_pct
        self.resultado: Item | None = None
        self._orden = item.orden if item else orden
        self._id = item.id if item else None

        self.title("Editar ítem" if item else "Agregar ítem")
        self.transient(parent)
        self.resizable(False, False)

        cont = ttk.Frame(self, padding=12)
        cont.pack(fill="both", expand=True)
        cont.columnconfigure(1, weight=1)
        cont.columnconfigure(3, weight=1)

        tipologias = db.tipologias()
        self._tips = {f"{t['codigo']} — {t['nombre']}": t for t in tipologias}
        lineas = db.lineas()
        self._lineas = {l["nombre"]: l for l in lineas}
        vidrios = db.vidrios()
        self._vidrios = {v["nombre"]: v for v in vidrios}

        self.var_tip = tk.StringVar()
        self.var_linea = tk.StringVar()
        self.var_color = tk.StringVar()
        self.var_vidrio = tk.StringVar()
        self.var_ancho = tk.StringVar(value="1500")
        self.var_alto = tk.StringVar(value="1100")
        self.var_hojas = tk.StringVar(value="2")
        self.var_cant = tk.StringVar(value="1")
        self.var_premarco = tk.BooleanVar(value=False)
        self.var_mosquitero = tk.BooleanVar(value=False)
        self.var_dto = tk.StringVar(value="0")

        f = 0
        ttk.Label(cont, text="Tipología:").grid(row=f, column=0, sticky="w", pady=3)
        self.cb_tip = ttk.Combobox(cont, textvariable=self.var_tip, state="readonly", width=34,
                                   values=list(self._tips))
        self.cb_tip.grid(row=f, column=1, columnspan=3, sticky="ew", pady=3)
        self.cb_tip.bind("<<ComboboxSelected>>", self._al_cambiar_tipologia)

        f += 1
        ttk.Label(cont, text="Línea:").grid(row=f, column=0, sticky="w", pady=3)
        self.cb_linea = ttk.Combobox(cont, textvariable=self.var_linea, state="readonly", width=20,
                                     values=list(self._lineas))
        self.cb_linea.grid(row=f, column=1, sticky="ew", pady=3)
        self.cb_linea.bind("<<ComboboxSelected>>", self._al_cambiar_linea)

        ttk.Label(cont, text="Color:").grid(row=f, column=2, sticky="w", padx=(12, 0))
        self.cb_color = ttk.Combobox(cont, textvariable=self.var_color, state="readonly", width=20)
        self.cb_color.grid(row=f, column=3, sticky="ew", pady=3)
        self.cb_color.bind("<<ComboboxSelected>>", self._previsualizar)

        f += 1
        ttk.Label(cont, text="Ancho A (mm):").grid(row=f, column=0, sticky="w", pady=3)
        ttk.Entry(cont, textvariable=self.var_ancho, width=12, justify="right").grid(
            row=f, column=1, sticky="w", pady=3)
        ttk.Label(cont, text="Alto H (mm):").grid(row=f, column=2, sticky="w", padx=(12, 0))
        ttk.Entry(cont, textvariable=self.var_alto, width=12, justify="right").grid(
            row=f, column=3, sticky="w", pady=3)

        f += 1
        ttk.Label(cont, text="Hojas (N):").grid(row=f, column=0, sticky="w", pady=3)
        ttk.Spinbox(cont, from_=1, to=8, textvariable=self.var_hojas, width=10,
                    command=self._previsualizar).grid(row=f, column=1, sticky="w", pady=3)
        ttk.Label(cont, text="Cantidad:").grid(row=f, column=2, sticky="w", padx=(12, 0))
        ttk.Spinbox(cont, from_=1, to=999, textvariable=self.var_cant, width=10,
                    command=self._previsualizar).grid(row=f, column=3, sticky="w", pady=3)

        f += 1
        ttk.Label(cont, text="Vidrio:").grid(row=f, column=0, sticky="w", pady=3)
        self.cb_vidrio = ttk.Combobox(cont, textvariable=self.var_vidrio, state="readonly",
                                      width=34, values=list(self._vidrios))
        self.cb_vidrio.grid(row=f, column=1, columnspan=3, sticky="ew", pady=3)
        self.cb_vidrio.bind("<<ComboboxSelected>>", self._previsualizar)

        f += 1
        opciones = ttk.Frame(cont)
        opciones.grid(row=f, column=0, columnspan=4, sticky="w", pady=(8, 3))
        self.chk_premarco = ttk.Checkbutton(opciones, text="Incluye premarco",
                                            variable=self.var_premarco, command=self._previsualizar)
        self.chk_premarco.pack(side="left", padx=(0, 18))
        self.chk_mosquitero = ttk.Checkbutton(opciones, text="Incluye mosquitero",
                                              variable=self.var_mosquitero,
                                              command=self._previsualizar)
        self.chk_mosquitero.pack(side="left", padx=(0, 18))
        ttk.Label(opciones, text="Bonificación del ítem (%):").pack(side="left")
        e = ttk.Entry(opciones, textvariable=self.var_dto, width=7, justify="right")
        e.pack(side="left", padx=4)
        e.bind("<FocusOut>", self._previsualizar)
        e.bind("<Return>", self._previsualizar)

        f += 1
        ttk.Label(cont, text="Observaciones / aclaraciones de este ítem:").grid(
            row=f, column=0, columnspan=4, sticky="w", pady=(10, 2))
        f += 1
        self.txt_obs = tk.Text(cont, height=4, width=64, wrap="word", font=("Segoe UI", 9))
        self.txt_obs.grid(row=f, column=0, columnspan=4, sticky="ew")
        ttk.Label(cont, text="Ej.: vidrio esmerilado · manijón especial · colocación en altura · "
                             "color negro semimate",
                  foreground="#6B7A88", font=("Segoe UI", 8)).grid(
            row=f + 1, column=0, columnspan=4, sticky="w", pady=(2, 6))

        f += 2
        self.lbl_preview = tk.Text(cont, height=7, width=64, font=("Consolas", 9), relief="solid",
                                   borderwidth=1, state="disabled", wrap="none")
        self.lbl_preview.grid(row=f, column=0, columnspan=4, sticky="ew", pady=(4, 0))

        f += 1
        botones = ttk.Frame(cont)
        botones.grid(row=f, column=0, columnspan=4, sticky="e", pady=(10, 0))
        ttk.Button(botones, text="Ver despiece", command=self._ver_despiece).pack(side="left",
                                                                                  padx=(0, 12))
        ttk.Button(botones, text="Cancelar", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(botones, text="Aceptar", command=self._aceptar).pack(side="right")

        for var in (self.var_ancho, self.var_alto, self.var_hojas, self.var_cant):
            var.trace_add("write", lambda *_a: self._previsualizar())

        self._precargar(item)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        self.geometry(f"+{parent.winfo_rootx() + 120}+{parent.winfo_rooty() + 50}")
        self.grab_set()
        self.wait_window(self)

    # -- carga inicial -------------------------------------------------------

    def _precargar(self, item):
        claves_tip = list(self._tips)
        if item:
            for k, t in self._tips.items():
                if t["codigo"] == item.tipologia_codigo:
                    self.var_tip.set(k)
                    break
            else:
                self.var_tip.set(claves_tip[0] if claves_tip else "")
            self.var_linea.set(item.linea_nombre)
            self.var_ancho.set(fmt_num(item.ancho_mm, 0))
            self.var_alto.set(fmt_num(item.alto_mm, 0))
            self.var_hojas.set(str(item.hojas))
            self.var_cant.set(str(item.cantidad))
            self.var_premarco.set(item.incluye_premarco)
            self.var_mosquitero.set(item.incluye_mosquitero)
            self.var_dto.set(fmt_num(item.descuento_pct * 100, 2))
            self.txt_obs.insert("1.0", item.observaciones)
            self._al_cambiar_linea()
            self.var_color.set(item.color)
            self.var_vidrio.set(item.vidrio_nombre)
        else:
            if claves_tip:
                self.var_tip.set(claves_tip[0])
            if self._lineas:
                self.var_linea.set(next(iter(self._lineas)))
            if self._vidrios:
                self.var_vidrio.set(next(iter(self._vidrios)))
            self._al_cambiar_tipologia()
            self._al_cambiar_linea()
        self._previsualizar()

    def _al_cambiar_tipologia(self, _evento=None):
        tip = self._tips.get(self.var_tip.get())
        if not tip:
            return
        self.var_hojas.set(str(tip["hojas_default"]))
        estado_mosq = "normal" if tip["admite_mosquitero"] else "disabled"
        estado_prem = "normal" if tip["admite_premarco"] else "disabled"
        self.chk_mosquitero.configure(state=estado_mosq)
        self.chk_premarco.configure(state=estado_prem)
        if not tip["admite_mosquitero"]:
            self.var_mosquitero.set(False)
        if not tip["admite_premarco"]:
            self.var_premarco.set(False)
        self._previsualizar()

    def _al_cambiar_linea(self, _evento=None):
        linea = self._lineas.get(self.var_linea.get())
        colores = [c["color"] for c in self.db.colores_de_linea(linea["id"])] if linea else []
        self.cb_color["values"] = colores
        if self.var_color.get() not in colores:
            self.var_color.set(colores[0] if colores else "")
        self._previsualizar()

    # -- construcción del Item ----------------------------------------------

    def _construir_item(self) -> Item | None:
        tip = self._tips.get(self.var_tip.get())
        linea = self._lineas.get(self.var_linea.get())
        vidrio = self._vidrios.get(self.var_vidrio.get())
        if not tip or not linea:
            return None
        return Item(
            orden=self._orden,
            tipologia_codigo=tip["codigo"],
            tipologia_nombre=tip["nombre"],
            linea_id=linea["id"],
            linea_nombre=linea["nombre"],
            color=self.var_color.get(),
            ancho_mm=a_float(self.var_ancho.get()),
            alto_mm=a_float(self.var_alto.get()),
            hojas=max(1, a_int(self.var_hojas.get(), 1)),
            cantidad=max(1, a_int(self.var_cant.get(), 1)),
            vidrio_id=vidrio["id"] if vidrio else 0,
            vidrio_nombre=vidrio["nombre"] if vidrio else "",
            incluye_premarco=self.var_premarco.get(),
            incluye_mosquitero=self.var_mosquitero.get(),
            descuento_pct=pct_desde_texto(self.var_dto.get()),
            observaciones=self.txt_obs.get("1.0", "end").rstrip(),
            id=self._id,
        )

    def _previsualizar(self, _evento=None):
        item = self._construir_item()
        if not item or item.ancho_mm <= 0 or item.alto_mm <= 0:
            return
        try:
            res = calcular_item(self.db, item, self.margen_pct)
        except Exception as exc:
            self._escribir_preview(f"No se pudo calcular: {exc}")
            return

        c = res.costos
        d = res.despiece
        modo = "por peso (kg)" if d.aluminio.modo_costeo == "kg" else "por m² de perfil"
        texto = "\n".join([
            f"{'Aluminio (' + modo + ')':<34}{fmt_money(c.aluminio):>18}"
            f"   {fmt_num(d.aluminio.peso_total_kg, 2)} kg",
            f"{'Vidrio':<34}{fmt_money(c.vidrio):>18}"
            f"   {fmt_num(d.vidrio.m2_total, 2)} m²",
            f"{'Accesorios':<34}{fmt_money(c.accesorios):>18}",
            f"{'Premarco':<34}{fmt_money(c.premarco):>18}",
            f"{'Mosquitero':<34}{fmt_money(c.mosquitero):>18}",
            "─" * 54,
            f"{'COSTO UNITARIO':<34}{fmt_money(res.costo_unitario):>18}",
            f"{'PRECIO UNITARIO (margen ' + fmt_pct(self.margen_pct, 0) + ')':<34}"
            f"{fmt_money(res.precio_unitario):>18}",
            f"{'IMPORTE (' + str(item.cantidad) + ' u. - bonif.)':<34}{fmt_money(res.neto):>18}",
        ])
        if d.advertencias:
            texto += "\n⚠ " + d.advertencias[0]
        self._escribir_preview(texto)

    def _escribir_preview(self, texto):
        self.lbl_preview.configure(state="normal")
        self.lbl_preview.delete("1.0", "end")
        self.lbl_preview.insert("1.0", texto)
        self.lbl_preview.configure(state="disabled")

    def _ver_despiece(self):
        item = self._construir_item()
        if not item:
            return
        res = calcular_item(self.db, item, self.margen_pct)
        VentanaDespiece(self, res.despiece, f"{item.tipologia_codigo} · {item.medida_texto}")

    def _aceptar(self):
        item = self._construir_item()
        if item is None:
            messagebox.showwarning("Faltan datos", "Elegí tipología y línea.", parent=self)
            return
        if item.ancho_mm <= 0 or item.alto_mm <= 0:
            messagebox.showwarning("Medidas inválidas", "El ancho y el alto deben ser mayores a 0.",
                                   parent=self)
            return
        if not item.color:
            messagebox.showwarning("Falta el color",
                                   "La línea elegida no tiene colores con precio cargado.",
                                   parent=self)
            return
        self.resultado = item
        self.destroy()
