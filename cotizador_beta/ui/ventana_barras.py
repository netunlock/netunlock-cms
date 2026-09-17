"""
Barras a comprar para el presupuesto entero.

Es la vista que faltaba. El despiece de cada abertura dice cuántas barras lleva
*esa* abertura; sumarlas es comprar de más, porque el recorte de una sirve para
la siguiente cuando es el mismo perfil.

La ventana muestra el número real —el consolidado— y al lado lo que saldría
sumando abertura por abertura, para que la diferencia sea visible. En un
presupuesto de seis ventanas parecidas esa diferencia son barras de verdad.
"""

from __future__ import annotations

import customtkinter as ctk

from core import formato as F
from core.despiece import barras_de_presupuesto, optimizar_conjunto
from . import tema
from .componentes import DialogoBase, Tabla, boton_fantasma, boton_secundario


class VentanaBarras(DialogoBase):

    def __init__(self, master, app, presupuesto):
        # Informe, no diálogo: se deja abierto mientras se sigue cotizando.
        super().__init__(master, "Barras a comprar — presupuesto completo",
                         ancho=980, modal=False)
        self.app = app
        self.presupuesto = presupuesto

        ancho = min(1000, self.winfo_screenwidth() - 80)
        alto = min(640, self.winfo_screenheight() - 120)
        self.geometry(f"{ancho}x{alto}")
        self.resizable(True, True)

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.pack(fill="both", expand=True, padx=18, pady=16)
        cont.columnconfigure(0, weight=1)
        cont.rowconfigure(2, weight=1)

        self._calcular()
        self._encabezado(cont)
        self._tabla(cont)
        self._pie(cont)

    # -- datos ---------------------------------------------------------------

    def _calcular(self):
        resultados = self.presupuesto.resultados
        self.consolidado = barras_de_presupuesto(resultados)

        # Lo mismo pero abertura por abertura, que es lo que se compraría sin
        # consolidar. Sirve para mostrar la diferencia, no para comprar.
        self.por_separado: dict[str, int] = {}
        for res in resultados:
            for b in optimizar_conjunto([(res.despiece.aluminio.piezas,
                                          res.item.cantidad)]):
                self.por_separado[b.perfil_codigo] = (
                    self.por_separado.get(b.perfil_codigo, 0) + b.cantidad)

        self.total_consolidado = sum(b.cantidad for b in self.consolidado)
        self.total_separado = sum(self.por_separado.values())

    # -- construcción --------------------------------------------------------

    def _encabezado(self, master):
        barra = ctk.CTkFrame(master, fg_color="transparent")
        barra.grid(row=0, column=0, sticky="ew", pady=(0, 4))

        ahorro = self.total_separado - self.total_consolidado
        ctk.CTkLabel(
            barra, text=f"{self.total_consolidado} barra(s)",
            font=tema.fuente(20, "bold"), text_color=tema.c("texto")).pack(side="left")
        ctk.CTkLabel(
            barra, text=f"en {len(self.consolidado)} perfil(es) distintos",
            font=tema.fuente(12), text_color=tema.c("texto_suave")).pack(
                side="left", padx=(10, 0))

        if ahorro > 0:
            ctk.CTkLabel(
                barra,
                text=f"{ahorro} barra(s) menos que cotizando abertura por abertura",
                font=tema.fuente(12, "bold"),
                text_color=tema.c("ok")).pack(side="right")

        ctk.CTkLabel(
            master,
            text="El recorte de una abertura se usa en la siguiente cuando es el "
                 "mismo perfil. Por eso el total no es la suma de los despieces.",
            font=tema.fuente(11), text_color=tema.c("texto_tenue"),
            anchor="w", justify="left", wraplength=900).grid(row=1, column=0,
                                                             sticky="ew", pady=(0, 10))

    def _tabla(self, master):
        self.tabla = Tabla(
            master,
            [("perfil", "Perfil", 110, "w"), ("desc", "Descripción", 240, "w"),
             ("barra", "Largo de barra", 120, "e"),
             ("barras", "Barras", 80, "e"),
             ("sueltas", "Sin consolidar", 110, "e"),
             ("utiles", "Metros útiles", 110, "e"),
             ("recorte", "Recorte", 100, "e"),
             ("pct", "% recorte", 90, "e"),
             ("peso", "Peso comprado", 120, "e")],
            alto=14, scroll_horizontal=True)
        self.tabla.grid(row=2, column=0, sticky="nsew")

        filas = []
        for b in self.consolidado:
            sueltas = self.por_separado.get(b.perfil_codigo, b.cantidad)
            filas.append((
                (b.perfil_codigo + ("  ⚠" if b.excede_barra else ""),
                 b.descripcion or "—",
                 F.milimetros_corte(b.largo_barra_mm),
                 F.unidades(b.cantidad),
                 F.unidades(sueltas) if sueltas != b.cantidad else "—",
                 F.metros(b.metros_utiles),
                 F.metros(b.recorte_mm / 1000.0),
                 F.porcentaje(b.desperdicio_pct),
                 F.kilos(b.peso_comprado_kg)),
                {"id": b.perfil_codigo},
                # Un recorte por encima del 60% suele significar que conviene
                # agrupar ese perfil con otra obra antes de comprar.
                ("alerta",) if b.desperdicio_pct > 0.60 else ()))

        filas.append((
            ("TOTAL", "", "", F.unidades(self.total_consolidado),
             F.unidades(self.total_separado),
             F.metros(sum(b.metros_utiles for b in self.consolidado)),
             F.metros(sum(b.recorte_mm for b in self.consolidado) / 1000.0),
             "", F.kilos(sum(b.peso_comprado_kg for b in self.consolidado))),
            {"id": "TOTAL"}, ("total",)))
        self.tabla.cargar(filas)

    def _pie(self, master):
        pie = ctk.CTkFrame(master, fg_color="transparent")
        pie.grid(row=3, column=0, sticky="ew", pady=(12, 0))

        muy_recortados = [b for b in self.consolidado if b.desperdicio_pct > 0.60]
        if muy_recortados:
            ctk.CTkLabel(
                pie,
                text=f"⚠  {len(muy_recortados)} perfil(es) con más del 60 % de recorte. "
                     "Conviene juntarlos con otra obra antes de comprar.",
                font=tema.fuente(11), text_color=tema.c("alerta"),
                anchor="w", wraplength=640, justify="left").pack(side="left")

        boton_fantasma(pie, "Cerrar", self.destroy, ancho=100).pack(side="right")
        boton_secundario(pie, "Copiar", self._copiar, ancho=100).pack(
            side="right", padx=8)

    def _copiar(self):
        lineas = ["Barras a comprar"]
        for b in self.consolidado:
            lineas.append(f"{b.perfil_codigo}\t{b.largo_barra_mm} mm\t{b.cantidad}")
        lineas.append(f"TOTAL\t\t{self.total_consolidado}")
        try:
            self.clipboard_clear()
            self.clipboard_append("\n".join(lineas))
            self.app.estado("Listado de barras copiado al portapapeles.")
        except Exception:
            pass
