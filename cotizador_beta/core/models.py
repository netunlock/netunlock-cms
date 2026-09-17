"""
Modelos de dominio (dataclasses puras, sin dependencia de la base ni de la GUI).

Se usan como estructuras de transporte entre el motor de cálculo, la interfaz y
el generador de PDF.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any


# ---------------------------------------------------------------------------
# Despiece
# ---------------------------------------------------------------------------


@dataclass
class PiezaCorte:
    """Una pieza de perfil a cortar."""

    perfil_codigo: str
    descripcion: str
    funcion: str
    largo_mm: float
    cantidad: int
    peso_kg_m: float
    #: Largo comercial de la barra de ESTE perfil. Cada perfil se corta de su
    #: propia barra, así que el optimizador no puede usar un valor global.
    largo_barra_mm: int = 6000
    #: Aclaración de la fórmula. Es lo que le da sentido a la función OTRO, que
    #: sola no dice nada: "refuerzo de parante", "tapajunta superior"...
    nota: str = ""
    #: id del perfil en el catálogo, para poder descontar stock sin re-buscarlo.
    perfil_id: int = 0
    #: De qué paño de una tipología compuesta salió ("Corrediza superior").
    #: Vacío en las aberturas simples. Sin esto, la lista de corte de una
    #: compuesta es una pila de largos sin decir a qué parte va cada uno.
    origen: str = ""

    @property
    def funcion_legible(self) -> str:
        """Lo que se imprime en el despiece, la OT y el Excel.

        Para OTRO la función no informa nada, así que manda la nota; para el
        resto la nota va como aclaración entre paréntesis si existe.
        """
        base = self.funcion.replace("_", " ").title()
        if self.funcion.upper() == "OTRO":
            texto = self.nota or base
        else:
            texto = f"{base} ({self.nota})" if self.nota else base
        return f"{self.origen} · {texto}" if self.origen else texto

    @property
    def metros(self) -> float:
        return self.largo_mm * self.cantidad / 1000.0

    @property
    def peso_kg(self) -> float:
        return self.metros * self.peso_kg_m


@dataclass
class BarrasPerfil:
    """Resultado de optimizar el corte de UN perfil sobre sus barras."""

    perfil_codigo: str
    descripcion: str
    largo_barra_mm: int
    barras: list[list[float]] = field(default_factory=list)
    peso_kg_m: float = 0.0

    @property
    def cantidad(self) -> int:
        return len(self.barras)

    @property
    def metros_comprados(self) -> float:
        return self.cantidad * self.largo_barra_mm / 1000.0

    @property
    def metros_utiles(self) -> float:
        return sum(sum(b) for b in self.barras) / 1000.0

    @property
    def recorte_mm(self) -> float:
        """Milímetros que sobran de las barras compradas."""
        return (self.metros_comprados - self.metros_utiles) * 1000.0

    @property
    def desperdicio_pct(self) -> float:
        comprados = self.metros_comprados
        return (comprados - self.metros_utiles) / comprados if comprados else 0.0

    @property
    def peso_comprado_kg(self) -> float:
        return self.metros_comprados * self.peso_kg_m

    @property
    def excede_barra(self) -> bool:
        """Alguna pieza no entra en la barra comercial de este perfil."""
        return any(len(b) == 1 and b[0] > self.largo_barra_mm for b in self.barras)


@dataclass
class DespieceAluminio:
    piezas: list[PiezaCorte] = field(default_factory=list)
    desperdicio_pct: float = 0.0
    precio_kg: float = 0.0
    precio_m2_perfil: float = 0.0
    modo_costeo: str = "kg"  # 'kg' | 'm2'
    m2_abertura: float = 0.0
    #: Problemas detectados al despiezar, como objetos con código y forma de
    #: resolverse. Ver core/avisos.py.
    avisos: list = field(default_factory=list)

    @property
    def advertencias(self) -> list[str]:
        """Los mismos avisos como texto plano.

        Es una propiedad y no un campo para que haya una sola fuente de verdad.
        Todo lo que ya consumía ``advertencias`` —el PDF, la ventana de despiece,
        la orden de trabajo— sigue funcionando sin cambios.
        """
        return [str(a) for a in self.avisos]

    @property
    def metros_totales(self) -> float:
        return sum(p.metros for p in self.piezas)

    @property
    def peso_total_kg(self) -> float:
        return sum(p.peso_kg for p in self.piezas)

    @property
    def peso_con_desperdicio_kg(self) -> float:
        return self.peso_total_kg * (1.0 + self.desperdicio_pct)

    @property
    def costo(self) -> float:
        if self.modo_costeo == "m2":
            return self.m2_abertura * self.precio_m2_perfil
        return self.peso_con_desperdicio_kg * self.precio_kg


@dataclass
class PanoVidrio:
    ancho_mm: float
    alto_mm: float
    cantidad: int
    descripcion: str = ""

    @property
    def m2_unitario(self) -> float:
        return max(0.0, self.ancho_mm) * max(0.0, self.alto_mm) / 1_000_000.0

    @property
    def m2_total(self) -> float:
        return self.m2_unitario * self.cantidad


@dataclass
class DespieceVidrio:
    panos: list[PanoVidrio] = field(default_factory=list)
    tipo: str = ""
    precio_m2: float = 0.0
    desperdicio_pct: float = 0.0
    plancha_ancho_mm: float = 0.0
    plancha_alto_mm: float = 0.0
    #: id en la tabla vidrios, para descontar stock sin volver a buscarlo
    vidrio_id: int = 0

    @property
    def m2_total(self) -> float:
        return sum(p.m2_total for p in self.panos)

    @property
    def m2_con_desperdicio(self) -> float:
        return self.m2_total * (1.0 + self.desperdicio_pct)

    @property
    def costo(self) -> float:
        return self.m2_con_desperdicio * self.precio_m2

    @property
    def planchas_estimadas(self) -> float:
        """Cantidad teórica de planchas necesarias (informativo, sin optimizar corte)."""
        area_plancha = self.plancha_ancho_mm * self.plancha_alto_mm / 1_000_000.0
        if area_plancha <= 0:
            return 0.0
        return self.m2_con_desperdicio / area_plancha


@dataclass
class LineaAccesorio:
    codigo: str
    descripcion: str
    unidad: str
    cantidad: float
    precio_unitario: float
    #: id en la tabla accesorios, para descontar stock sin volver a buscarlo
    accesorio_id: int = 0

    @property
    def total(self) -> float:
        return self.cantidad * self.precio_unitario


@dataclass
class DespieceAccesorios:
    kit_nombre: str = ""
    lineas: list[LineaAccesorio] = field(default_factory=list)
    avisos: list = field(default_factory=list)

    @property
    def advertencias(self) -> list[str]:
        return [str(a) for a in self.avisos]

    @property
    def costo(self) -> float:
        return sum(l.total for l in self.lineas)


@dataclass
class Despiece:
    """Resultado completo del despiece de UNA unidad de abertura."""

    aluminio: DespieceAluminio = field(default_factory=DespieceAluminio)
    vidrio: DespieceVidrio = field(default_factory=DespieceVidrio)
    accesorios: DespieceAccesorios = field(default_factory=DespieceAccesorios)
    ancho_hoja_mm: float = 0.0
    alto_hoja_mm: float = 0.0

    @property
    def avisos(self) -> list:
        return self.aluminio.avisos + self.accesorios.avisos

    @property
    def advertencias(self) -> list[str]:
        return self.aluminio.advertencias + self.accesorios.advertencias


# ---------------------------------------------------------------------------
# Cotización
# ---------------------------------------------------------------------------


@dataclass
class Item:
    """Una abertura dentro del presupuesto."""

    orden: int = 1
    tipologia_codigo: str = "COR2"
    tipologia_nombre: str = ""
    linea_id: int = 0
    linea_nombre: str = ""
    color: str = ""
    ancho_mm: float = 1500.0
    alto_mm: float = 1100.0
    hojas: int = 2
    cantidad: int = 1
    vidrio_id: int = 0
    vidrio_nombre: str = ""
    incluye_premarco: bool = False
    incluye_mosquitero: bool = False
    descuento_pct: float = 0.0
    observaciones: str = ""
    #: Valores de las variables de la tipología para ESTA abertura
    #: ({"PREMARCO": 1.0, "ALTO_FIJO": 400.0}). Lo que no esté acá toma el valor
    #: por defecto de la declaración, así agregar una variable no rompe los
    #: presupuestos ya guardados.
    variables: dict = field(default_factory=dict)
    id: int | None = None

    @property
    def m2_unitario(self) -> float:
        return self.ancho_mm * self.alto_mm / 1_000_000.0

    @property
    def m2_total(self) -> float:
        return self.m2_unitario * self.cantidad

    @property
    def descripcion(self) -> str:
        partes = [self.tipologia_nombre or self.tipologia_codigo]
        if self.linea_nombre:
            partes.append(f"Línea {self.linea_nombre}")
        if self.color:
            partes.append(self.color)
        if self.vidrio_nombre:
            partes.append(self.vidrio_nombre)
        return " · ".join(partes)

    @property
    def medida_texto(self) -> str:
        return f"{self.ancho_mm:.0f} x {self.alto_mm:.0f} mm"


@dataclass
class CostosItem:
    aluminio: float = 0.0
    vidrio: float = 0.0
    accesorios: float = 0.0
    premarco: float = 0.0
    mosquitero: float = 0.0
    mano_obra: float = 0.0

    @property
    def total(self) -> float:
        return (
            self.aluminio
            + self.vidrio
            + self.accesorios
            + self.premarco
            + self.mosquitero
            + self.mano_obra
        )

    def como_dict(self) -> dict[str, float]:
        d = asdict(self)
        d["total"] = self.total
        return d


@dataclass
class ResultadoItem:
    item: Item
    despiece: Despiece
    costos: CostosItem
    margen_pct: float = 0.0

    @property
    def costo_unitario(self) -> float:
        return self.costos.total

    @property
    def precio_unitario(self) -> float:
        """Precio de venta unitario, antes del descuento del renglón."""
        return self.costo_unitario * (1.0 + self.margen_pct)

    @property
    def bruto(self) -> float:
        return self.precio_unitario * self.item.cantidad

    @property
    def descuento(self) -> float:
        return self.bruto * self.item.descuento_pct

    @property
    def neto(self) -> float:
        return self.bruto - self.descuento


@dataclass
class ManoObra:
    valor_hora: float = 0.0
    operarios: int = 1
    horas: float = 0.0
    automatica: bool = True  # horas calculadas a partir de m2

    @property
    def costo(self) -> float:
        return self.valor_hora * self.operarios * self.horas


@dataclass
class Logistica:
    flete_recepcion: float = 0.0
    envio_colocacion: float = 0.0

    @property
    def costo(self) -> float:
        return self.flete_recepcion + self.envio_colocacion


@dataclass
class Cliente:
    razon_social: str = ""
    documento: str = ""  # DNI / CUIT
    contacto: str = ""
    localidad: str = ""
    obra: str = ""
    forma_pago: str = ""


@dataclass
class Empresa:
    razon_social: str = ""
    cuit: str = ""
    direccion: str = ""
    telefono: str = ""
    email: str = ""
    web: str = ""
    logo_path: str = ""
    terminos: str = ""
    validez_dias: int = 15
    prefijo: str = "PRES"
    proximo_numero: int = 1
    relleno_ceros: int = 4

    def formato_numero(self, numero: int) -> str:
        return f"{self.prefijo}-{str(numero).zfill(self.relleno_ceros)}"


@dataclass
class Resumen:
    """Desglose final del presupuesto."""

    subtotal_items_bruto: float = 0.0
    descuentos_items: float = 0.0
    subtotal_items: float = 0.0
    mano_obra: float = 0.0
    logistica: float = 0.0
    subtotal_general: float = 0.0
    descuento_global: float = 0.0
    neto: float = 0.0
    iva_pct: float = 0.0
    iva: float = 0.0
    total: float = 0.0


@dataclass
class Presupuesto:
    numero: str = ""
    fecha: date = field(default_factory=date.today)
    validez_dias: int = 15
    cliente: Cliente = field(default_factory=Cliente)
    items: list[Item] = field(default_factory=list)
    mano_obra: ManoObra = field(default_factory=ManoObra)
    logistica: Logistica = field(default_factory=Logistica)
    descuento_global_tipo: str = "porcentaje"  # 'porcentaje' | 'monto'
    descuento_global_valor: float = 0.0
    aplica_iva: bool = True
    iva_pct: float = 0.21
    margen_pct: float = 0.30
    observaciones_generales: str = ""
    id: int | None = None
    # Rellenados por el motor de cálculo
    resultados: list[ResultadoItem] = field(default_factory=list)
    resumen: Resumen = field(default_factory=Resumen)
    snapshot: dict[str, Any] = field(default_factory=dict)
