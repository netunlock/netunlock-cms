"""
Optimizador de corte de vidrio: acomodar paños sobre planchas.

Por qué es otro problema que el de los perfiles
-----------------------------------------------
Un perfil se corta a lo largo: es una dimensión, y alcanza con ir llenando la
barra. Una plancha de vidrio es un rectángulo, y hay que ubicar cada paño en
un lugar del plano. Es *bin packing* en dos dimensiones.

Corte guillotina
----------------
El vidrio no se corta como el papel: la máquina raya de lado a lado y parte la
plancha entera. Cada corte atraviesa lo que tenga delante, así que no se puede
acomodar cualquier figura: los paños tienen que quedar en **franjas**.

Por eso se usa el algoritmo de estantes (*shelf*, o FFDH — first-fit decreasing
height), que es justamente lo que produce un plan cortable:

1. Los paños se ordenan de mayor a menor altura.
2. Se abre una franja del alto del primero y se van poniendo paños a lo ancho.
3. Cuando no entra más, se abre la franja siguiente abajo.
4. Cuando no entra otra franja, se empieza una plancha nueva.

Un optimizador que acomode mejor pero produzca cortes imposibles no sirve para
nada: el vidriero no lo puede ejecutar.

Rotación
--------
Un paño se puede girar 90° si el vidrio no tiene dirección. Los que la tienen
—laminados con dibujo, serigrafiados, algunos DVH con cámara orientada— no.
Por eso ``permitir_rotar`` es una opción y no una decisión nuestra.

Sierra
------
Entre paño y paño se pierde el ancho del corte. Son unos milímetros, pero sobre
una plancha con doce paños son centímetros: ignorarlos es entregar un plan que
no cierra en la mesa.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Pérdida por corte, en mm. El vidrio se raya y se parte, así que es menor que
#: en una sierra de aluminio, pero no es cero.
SIERRA_DEFECTO = 3.0

#: Margen de plancha que no se usa: los bordes vienen golpeados de fábrica.
BORDE_DEFECTO = 5.0

#: Un hueco con menos de esto de ancho o de alto no va a recibir ningún paño
#: de una abertura: se descarta para no llenar la búsqueda de retazos inútiles.
SOBRANTE_MINIMO = 150.0


@dataclass
class PanoUbicado:
    """Un paño ya colocado sobre la plancha, con su lugar exacto."""

    x: float
    y: float
    ancho: float
    alto: float
    descripcion: str = ""
    posicion: str = ""
    rotado: bool = False

    @property
    def m2(self) -> float:
        return self.ancho * self.alto / 1_000_000.0


@dataclass
class PlanchaCortada:
    ancho: float
    alto: float
    tipo: str = ""
    panos: list[PanoUbicado] = field(default_factory=list)

    @property
    def m2_plancha(self) -> float:
        return self.ancho * self.alto / 1_000_000.0

    @property
    def m2_usado(self) -> float:
        return sum(p.m2 for p in self.panos)

    @property
    def aprovechamiento(self) -> float:
        return self.m2_usado / self.m2_plancha if self.m2_plancha else 0.0

    @property
    def desperdicio_pct(self) -> float:
        return 1.0 - self.aprovechamiento


@dataclass
class PlanDeCorte:
    """Resultado completo para un tipo de vidrio."""

    tipo: str
    planchas: list[PlanchaCortada] = field(default_factory=list)
    sin_ubicar: list[tuple] = field(default_factory=list)

    @property
    def cantidad(self) -> int:
        return len(self.planchas)

    @property
    def m2_compradas(self) -> float:
        return sum(p.m2_plancha for p in self.planchas)

    @property
    def m2_usados(self) -> float:
        return sum(p.m2_usado for p in self.planchas)

    @property
    def aprovechamiento(self) -> float:
        return self.m2_usados / self.m2_compradas if self.m2_compradas else 0.0


# ---------------------------------------------------------------------------
# El algoritmo
# ---------------------------------------------------------------------------

class _Franja:
    """Una banda de la plancha donde los paños se van apoyando de izquierda a derecha.

    Hay dos clases de franja y las dos se tratan igual:

    * la **principal**, que ocupa todo el ancho útil de la plancha;
    * el **sobrante de arriba**, el hueco que deja un paño bajo dentro de una
      franja alta. Sin esto, una franja de 1800 con paños de 1450 tira 350 mm de
      alto a lo largo de toda la plancha.

    Las dos se pueden cortar con sierra de vidrio: primero el corte horizontal
    que separa la franja, después el vertical que separa la columna, y recién
    dentro de esa columna el horizontal que separa el paño del sobrante. Todos
    son cortes de lado a lado del pedazo que se está cortando, que es la única
    forma en que se corta el vidrio.
    """

    __slots__ = ("x0", "ancho", "y", "alto", "x_libre")

    def __init__(self, x0: float, ancho: float, y: float, alto: float):
        self.x0 = x0        # dónde empieza, medido desde el borde útil
        self.ancho = ancho  # cuánto ancho tiene disponible en total
        self.y = y
        self.alto = alto
        self.x_libre = 0.0  # cuánto ya se ocupó, desde x0


def _empaquetar(panos, ancho_plancha: float, alto_plancha: float,
                tipo: str, sierra: float, borde: float,
                permitir_rotar: bool, parar_todas: bool) -> PlanDeCorte:
    """Una pasada del empaquetado, con una orientación de entrada dada.

    ``parar_todas`` gira cada paño para que quede más alto que ancho antes de
    empezar. Suele convenir —las franjas salen más parejas— pero no siempre, así
    que :func:`optimizar` prueba las dos y se queda con la que sale mejor.
    """
    plan = PlanDeCorte(tipo=tipo)

    util_ancho = max(0.0, ancho_plancha - 2 * borde)
    util_alto = max(0.0, alto_plancha - 2 * borde)
    if util_ancho <= 0 or util_alto <= 0:
        return plan

    # Se expande cada medida a piezas sueltas y se ordena por altura
    # decreciente: es lo que hace que las franjas queden parejas y sobre menos.
    piezas = []
    for ancho, alto, cantidad, descripcion, posicion in panos:
        for _ in range(int(cantidad)):
            piezas.append([float(ancho), float(alto), descripcion, posicion])

    def encaja(p) -> tuple[float, float, bool] | None:
        """Devuelve (ancho, alto, rotado) usable, o None si no entra ni girado."""
        a, h = p[0], p[1]
        if a <= util_ancho and h <= util_alto:
            return a, h, False
        if permitir_rotar and h <= util_ancho and a <= util_alto:
            return h, a, True
        return None

    # Las que no entran en una plancha ni girándolas se apartan y se avisa:
    # meterlas a la fuerza daría un plan que no se puede cortar.
    utiles = []
    for p in piezas:
        medida = encaja(p)
        if medida is None:
            plan.sin_ubicar.append((p[0], p[1], p[2], p[3]))
        else:
            # Se guarda ya orientada como conviene: alto mayor primero ayuda a
            # que las franjas salgan más parejas.
            a, h, rot = medida
            if (parar_todas and permitir_rotar and h < a
                    and a <= util_alto and h <= util_ancho):
                a, h, rot = h, a, not rot
            utiles.append([a, h, p[2], p[3], rot])

    utiles.sort(key=lambda p: (-p[1], -p[0]))

    # Cada plancha lleva sus franjas: las principales, en orden, y los sobrantes
    # que van apareciendo arriba de los paños bajos.
    planchas: list[tuple[PlanchaCortada, list[_Franja], list[_Franja]]] = []

    def apoyar(plancha, franja, a, h, descripcion, posicion, rotado, sobrantes):
        """Pone el paño en esa franja y anota el hueco que deja arriba."""
        separacion = sierra if franja.x_libre > 0 else 0.0
        x_rel = franja.x0 + franja.x_libre + separacion
        plancha.panos.append(PanoUbicado(
            x=borde + x_rel, y=borde + franja.y, ancho=a, alto=h,
            descripcion=descripcion, posicion=posicion, rotado=rotado))
        franja.x_libre += separacion + a

        # El hueco de arriba sólo se anota si da para algo. Un sobrante de 20 mm
        # no va a recibir ningún paño y ensucia la búsqueda.
        sobra = franja.alto - h - sierra
        if sobra >= SOBRANTE_MINIMO and a >= SOBRANTE_MINIMO:
            sobrantes.append(_Franja(x_rel, a, franja.y + h + sierra, sobra))

    for a, h, descripcion, posicion, rotado in utiles:
        colocado = False

        for plancha, franjas, sobrantes in planchas:
            # Mejor ajuste por altura: entre todas las franjas donde entra, la
            # que menos alto desperdicia. Así un paño bajo cae en un sobrante y
            # no en una franja alta, que es donde tienen que ir los altos.
            mejor, desperdicio_mejor = None, None
            for franja in franjas + sobrantes:
                if h > franja.alto:
                    continue
                separacion = sierra if franja.x_libre > 0 else 0.0
                if franja.x_libre + separacion + a > franja.ancho:
                    continue
                sobra = franja.alto - h
                if desperdicio_mejor is None or sobra < desperdicio_mejor:
                    mejor, desperdicio_mejor = franja, sobra

            if mejor is not None:
                apoyar(plancha, mejor, a, h, descripcion, posicion, rotado, sobrantes)
                colocado = True
                break

            # ¿se puede abrir una franja principal nueva más abajo?
            usado = franjas[-1].y + franjas[-1].alto if franjas else 0.0
            separacion = sierra if franjas else 0.0
            if usado + separacion + h <= util_alto:
                franja = _Franja(0.0, util_ancho, usado + separacion, h)
                franjas.append(franja)
                apoyar(plancha, franja, a, h, descripcion, posicion, rotado, sobrantes)
                colocado = True
                break

        if not colocado:
            plancha = PlanchaCortada(ancho=ancho_plancha, alto=alto_plancha, tipo=tipo)
            franja = _Franja(0.0, util_ancho, 0.0, h)
            huecos: list[_Franja] = []
            apoyar(plancha, franja, a, h, descripcion, posicion, rotado, huecos)
            planchas.append((plancha, [franja], huecos))

    plan.planchas = [p for p, _f, _s in planchas]
    return plan


def optimizar(panos, ancho_plancha: float, alto_plancha: float,
              tipo: str = "", sierra: float = SIERRA_DEFECTO,
              borde: float = BORDE_DEFECTO,
              permitir_rotar: bool = True) -> PlanDeCorte:
    """Acomoda los paños sobre planchas y devuelve el plan de corte.

    ``panos`` es un iterable de ``(ancho, alto, cantidad, descripcion, posicion)``.

    Se prueban las dos formas de entrar —girando todo a vertical y dejando cada
    paño como viene— y queda la que gasta menos planchas. Parar todo suele ganar
    por bastante (24 paños de 828x427 entran en una plancha parados y necesitan
    dos acostados), pero con medidas revueltas a veces pierde, y probar las dos
    cuesta milisegundos: no hay razón para adivinar.
    """
    hecho = _empaquetar(panos, ancho_plancha, alto_plancha, tipo, sierra, borde,
                        permitir_rotar, parar_todas=True)
    if not permitir_rotar:
        return hecho

    otro = _empaquetar(panos, ancho_plancha, alto_plancha, tipo, sierra, borde,
                       permitir_rotar, parar_todas=False)
    # Primero manda la cantidad de planchas, que es lo que se paga. El
    # aprovechamiento desempata cuando salen las mismas.
    if (otro.cantidad, -otro.aprovechamiento) < (hecho.cantidad, -hecho.aprovechamiento):
        return otro
    return hecho


# ---------------------------------------------------------------------------
# Desde un presupuesto
# ---------------------------------------------------------------------------

def planes_de_presupuesto(db, pres, permitir_rotar: bool = True) -> list[PlanDeCorte]:
    """Un plan de corte por cada tipo de vidrio del presupuesto.

    Cada tipo se optimiza por separado: no se pueden mezclar un float 4 y un DVH
    en la misma plancha, son productos distintos.
    """
    por_tipo: dict[int, dict] = {}
    for res in pres.resultados:
        vidrio = res.despiece.vidrio
        if not vidrio.panos:
            continue
        reg = por_tipo.setdefault(vidrio.vidrio_id or 0, {
            "tipo": vidrio.tipo,
            "ancho": vidrio.plancha_ancho_mm or 3600,
            "alto": vidrio.plancha_alto_mm or 2500,
            "panos": [],
        })
        for pano in vidrio.panos:
            reg["panos"].append((pano.ancho_mm, pano.alto_mm,
                                 pano.cantidad * res.item.cantidad,
                                 vidrio.tipo, f"P{res.item.orden}"))

    planes = []
    for reg in por_tipo.values():
        planes.append(optimizar(reg["panos"], reg["ancho"], reg["alto"],
                                tipo=reg["tipo"], permitir_rotar=permitir_rotar))
    planes.sort(key=lambda p: p.tipo)
    return planes
