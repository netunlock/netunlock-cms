"""
Ventana de sólo lectura con el detalle de corte de una abertura.
"""

from __future__ import annotations

import customtkinter as ctk

from core import formato as F
from core.despiece import optimizar_conjunto
from . import tema
from .componentes import DialogoBase, Tabla, Tarjeta, boton_secundario


class VentanaDespiece(DialogoBase):
    def __init__(self, master, despiece, titulo: str = "", unidades: int = 1):
        # NO modal: es un informe para mirar, no un diálogo que pida una
        # respuesta. Se puede dejar abierto al costado y seguir cotizando.
        super().__init__(master, f"Despiece — {titulo}", ancho=1000, modal=False)
        ancho = min(1040, self.winfo_screenwidth() - 80)
        alto = min(700, self.winfo_screenheight() - 110)
        self.geometry(f"{ancho}x{alto}")
        self.resizable(True, True)
        self.despiece = despiece
        #: Unidades del ítem. Los cortes se muestran por unidad, pero las barras
        #: se optimizan para todas juntas: tres ventanas iguales cuyo parante
        #: mide 1 m salen de una barra de 6, no de tres.
        self.unidades = max(1, int(unidades or 1))

        cont = ctk.CTkFrame(self, fg_color="transparent")
        cont.pack(fill="both", expand=True, padx=18, pady=16)
        cont.columnconfigure(0, weight=1)
        cont.rowconfigure(1, weight=1)

        self._resumen(cont)
        self._detalle(cont)

        pie = ctk.CTkFrame(cont, fg_color="transparent")
        pie.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        if despiece.advertencias:
            ctk.CTkLabel(pie, text="⚠  " + "   ·   ".join(despiece.advertencias),
                         font=tema.fuente(11), text_color=tema.c("alerta"),
                         wraplength=700, justify="left", anchor="w").pack(side="left")
        boton_secundario(pie, "Cerrar", self.destroy, ancho=110).pack(side="right")

    # -- resumen -------------------------------------------------------------

    def _resumen(self, master):
        al, vi, ac = self.despiece.aluminio, self.despiece.vidrio, self.despiece.accesorios
        self.barras_por_perfil = optimizar_conjunto([(al.piezas, self.unidades)])
        barras = sum(b.cantidad for b in self.barras_por_perfil)
        perfiles_distintos = len(self.barras_por_perfil)

        tarjetas = ctk.CTkFrame(master, fg_color="transparent")
        tarjetas.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        for i in range(4):
            tarjetas.columnconfigure(i, weight=1)

        datos = [
            ("Aluminio", F.moneda(al.costo),
             [f"{F.metros(al.metros_totales)} de perfil",
              f"{F.kilos(al.peso_total_kg)} netos",
              f"{F.kilos(al.peso_con_desperdicio_kg)} con {F.porcentaje(al.desperdicio_pct)} de desperdicio",
              f"{barras} barra(s) en {perfiles_distintos} perfil(es)"]),
            ("Vidrio", F.moneda(vi.costo),
             [f"{F.superficie(vi.m2_total)} netos",
              f"{F.superficie(vi.m2_con_desperdicio)} con desperdicio",
              vi.tipo or "—",
              f"{F.numero(vi.planchas_estimadas, 2)} plancha(s)"]),
            ("Accesorios", F.moneda(ac.costo),
             [ac.kit_nombre or "—",
              f"{len(ac.lineas)} renglón(es)"]),
            ("Medida de hoja",
             F.medida(self.despiece.ancho_hoja_mm, self.despiece.alto_hoja_mm),
             [f"Ancho de hoja: {F.milimetros_corte(self.despiece.ancho_hoja_mm)}",
              f"Alto de hoja: {F.milimetros_corte(self.despiece.alto_hoja_mm)}"]),
        ]

        for col, (titulo, valor, detalles) in enumerate(datos):
            tarjeta = Tarjeta(tarjetas)
            tarjeta.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 0))
            ctk.CTkLabel(tarjeta.cuerpo, text=titulo.upper(), font=tema.fuente(10, "bold"),
                         text_color=tema.c("texto_tenue"), anchor="w").pack(anchor="w")
            ctk.CTkLabel(tarjeta.cuerpo, text=valor, font=tema.fuente(18, "bold"),
                         text_color=tema.c("texto"), anchor="w").pack(anchor="w", pady=(2, 6))
            for linea in detalles:
                ctk.CTkLabel(tarjeta.cuerpo, text=linea, font=tema.fuente(10),
                             text_color=tema.c("texto_suave"), anchor="w").pack(anchor="w")

    # -- detalle -------------------------------------------------------------

    def _detalle(self, master):
        pestanias = ctk.CTkTabview(master, fg_color=tema.c("superficie"),
                                   segmented_button_selected_color=tema.c("primario"))
        pestanias.grid(row=1, column=0, sticky="nsew")

        al = self.despiece.aluminio
        hoja = pestanias.add("  Perfiles  ")
        tabla = Tabla(hoja, [("perfil", "Perfil", 110, "w"),
                             ("desc", "Descripción", 250, "w"),
                             ("funcion", "Función", 170, "w"),
                             ("largo", "Largo", 110, "e"),
                             ("piezas", "Piezas", 90, "e"),
                             ("kgm", "Peso lineal", 120, "e"),
                             ("peso", "Peso", 110, "e")], alto=9)
        tabla.pack(fill="both", expand=True, padx=6, pady=6)
        for pieza in al.piezas:
            tabla.agregar((pieza.perfil_codigo, pieza.descripcion,
                           pieza.funcion_legible,
                           F.milimetros_corte(pieza.largo_mm), F.unidades(pieza.cantidad),
                           F.kilos_metro(pieza.peso_kg_m), F.kilos(pieza.peso_kg)))
        tabla.agregar(("TOTAL", "", "", F.metros(al.metros_totales),
                       F.unidades(sum(p.cantidad for p in al.piezas)), "",
                       F.kilos(al.peso_total_kg)), etiquetas=("total",))

        hoja = pestanias.add("  Barras a comprar  ")
        aclaracion = ("Cada perfil se corta de su propia barra. El sobrante de un "
                      "perfil no sirve para otro, por eso se cuentan por separado.")
        if self.unidades > 1:
            aclaracion += (f"\nLas {self.unidades} unidades se optimizan juntas: "
                           "el recorte de una abertura se usa en la siguiente.")
        ctk.CTkLabel(
            hoja, text=aclaracion,
            font=tema.fuente(10), text_color=tema.c("texto_tenue"),
            anchor="w", justify="left").pack(fill="x", padx=10, pady=(8, 0))
        tabla = Tabla(hoja, [("perfil", "Perfil", 110, "w"),
                             ("desc", "Descripción", 250, "w"),
                             ("barra", "Largo de barra", 130, "e"),
                             ("barras", "Barras", 90, "e"),
                             ("utiles", "Metros útiles", 130, "e"),
                             ("recorte", "Recorte", 110, "e"),
                             ("pct", "% recorte", 100, "e")], alto=9)
        tabla.pack(fill="both", expand=True, padx=6, pady=6)
        for b in self.barras_por_perfil:
            tabla.agregar((
                (b.perfil_codigo or "—") + ("  ⚠" if b.excede_barra else ""),
                b.descripcion or "—",
                F.milimetros_corte(float(b.largo_barra_mm or 0)),
                F.unidades(float(b.cantidad or 0)),
                F.metros(float(b.metros_utiles or 0)),
                F.metros(float((b.recorte_mm or 0) / 1000.0)),
                F.porcentaje(float(b.desperdicio_pct or 0))))
        tabla.agregar((
            "TOTAL", "", "",
            F.unidades(sum(b.cantidad for b in self.barras_por_perfil)),
            F.metros(sum(b.metros_utiles for b in self.barras_por_perfil)),
            F.metros(sum(b.recorte_mm for b in self.barras_por_perfil) / 1000.0),
            ""), etiquetas=("total",))

        hoja = pestanias.add("  Vidrios  ")
        tabla = Tabla(hoja, [("tipo", "Tipo de vidrio", 280, "w"),
                             ("medida", "Medida del paño", 190, "center"),
                             ("panos", "Paños", 100, "e"),
                             ("m2u", "m² unitario", 130, "e"),
                             ("m2", "m² total", 130, "e")], alto=9)
        tabla.pack(fill="both", expand=True, padx=6, pady=6)
        for pano in self.despiece.vidrio.panos:
            tabla.agregar(((pano.descripcion or "—"),
                           F.medida(float(pano.ancho_mm or 0), float(pano.alto_mm or 0)),
                           F.unidades(float(pano.cantidad or 0)),
                           F.superficie(float(pano.m2_unitario or 0)),
                           F.superficie(float(pano.m2_total or 0))))

        ac = self.despiece.accesorios
        hoja = pestanias.add(f"  Accesorios  ")
        ctk.CTkLabel(hoja, text=f"Kit aplicado: {ac.kit_nombre or '—'}",
                     font=tema.fuente(11), text_color=tema.c("texto_suave"),
                     anchor="w").pack(fill="x", padx=10, pady=(8, 0))
        tabla = Tabla(hoja, [("codigo", "Código", 120, "w"),
                             ("desc", "Descripción", 320, "w"),
                             ("cant", "Cantidad", 120, "e"),
                             ("pu", "Precio unitario", 150, "e"),
                             ("total", "Importe", 140, "e")], alto=9)
        tabla.pack(fill="both", expand=True, padx=6, pady=6)
        for linea in ac.lineas:
            tabla.agregar((linea.codigo, linea.descripcion,
                           F.cantidad(linea.cantidad, linea.unidad),
                           F.moneda(linea.precio_unitario), F.moneda(linea.total)))
        tabla.agregar(("TOTAL", "", "", "", F.moneda(ac.costo)), etiquetas=("total",))
