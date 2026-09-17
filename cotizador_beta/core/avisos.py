"""
Advertencias del despiece, tipificadas y accionables.

El problema que resuelve
------------------------
Hasta acá una advertencia era una cadena de texto. Se mostraba la primera y se
contaban las demás, así que un presupuesto con doce problemas se veía igual que
uno con uno solo, y para arreglar cualquiera había que salir a buscar a mano el
perfil o el color culpable.

Un aviso ahora sabe **qué** pasó, **dónde** y **cómo se arregla**. La interfaz
puede listarlos todos, contarlos por gravedad y llevarte al lugar exacto —o
resolverlo ahí mismo, cuando lo que falta es un solo número.

Es el caso que ya nos mordió: un cliente cotizó semanas con los pesos cargados en
gramos. El programa lo sabía y lo estaba diciendo; lo decía de una forma que no
se podía accionar.

Compatibilidad
--------------
``DespieceAluminio.advertencias`` sigue existiendo y sigue devolviendo una lista
de cadenas: es una propiedad calculada sobre los avisos. Todo lo que ya la
consumía —el PDF, la ventana de despiece, la orden de trabajo— sigue andando sin
cambios.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Códigos
# ---------------------------------------------------------------------------

#: Impiden costear bien: el número que sale es mentira o está incompleto.
LINEA_SIN_PRECIO   = "LINEA_SIN_PRECIO"
SIN_FORMULAS       = "SIN_FORMULAS"
DESPIECE_GENERICO  = "DESPIECE_GENERICO"
FORMULA_INVALIDA   = "FORMULA_INVALIDA"
PERFIL_SIN_PESO    = "PERFIL_SIN_PESO"
ACCESORIO_SIN_PESO = "ACCESORIO_SIN_PESO"
ACCESORIO_FORMULA  = "ACCESORIO_FORMULA"
PANO_IMPOSIBLE     = "PANO_IMPOSIBLE"

#: El cálculo cierra, pero hay algo que mirar antes de mandar a fabricar.
CORTE_EXCEDE_BARRA = "CORTE_EXCEDE_BARRA"
CORTE_MUY_CORTO    = "CORTE_MUY_CORTO"
SIN_KIT            = "SIN_KIT"
PERFIL_FUERA_CATALOGO = "PERFIL_FUERA_CATALOGO"
PESO_SOSPECHOSO    = "PESO_SOSPECHOSO"

#: Por debajo de esto una pieza de carpintería no existe. Aparece cuando una
#: fórmula condicional deja una medida sin sentido —un paño fijo más alto que la
#: ventana, por ejemplo— y sin este aviso el presupuesto sale mudo con una
#: abertura que no se puede fabricar.
CORTE_MINIMO_PLAUSIBLE = 50.0

DEMASIADAS_PIEZAS = "DEMASIADAS_PIEZAS"

#: Ninguna abertura lleva 500 piezas del mismo perfil. Pasado ese número la
#: fórmula de cantidad está mal, y el optimizador de corte —que es cuadrático—
#: se convierte en un cuelgue: 16.500 piezas ya tardan dos segundos, y una
#: fórmula como "A * H" da un millón y medio.
MAX_PIEZAS_POR_FORMULA = 500

#: Banda plausible para el peso lineal de un perfil de aluminio de carpintería.
#: Un contravidrio liviano ronda 0,15 Kg/m y un umbral pesado no pasa de 2;
#: 8 deja margen de sobra para un perfil estructural. Fuera de esa banda casi
#: siempre hay un error de unidad —el catálogo del extrusor venía en gramos— y
#: eso multiplica el costo del aluminio por mil sin que nada se queje.
PESO_MINIMO_PLAUSIBLE = 0.05
PESO_MAXIMO_PLAUSIBLE = 8.0

ERROR = "error"
ATENCION = "atencion"

#: Cómo se resuelve cada aviso. 'campo' se arregla en el acto pidiendo un número;
#: 'navegar' abre la pantalla donde está el problema.
ARREGLO_CAMPO = "campo"
ARREGLO_NAVEGAR = "navegar"
ARREGLO_NINGUNO = ""


@dataclass
class Aviso:
    """Un problema detectado al despiezar, con todo lo necesario para resolverlo."""

    codigo: str
    severidad: str = ERROR
    mensaje: str = ""
    #: Qué hacer para arreglarlo, en palabras del usuario
    sugerencia: str = ""
    #: Dónde está el problema. La interfaz lo usa para navegar o para editar.
    #: Ej.: {"tipo": "perfil", "linea_id": 1, "codigo": "6200"}
    objeto: dict = field(default_factory=dict)
    #: Cómo se arregla: ARREGLO_CAMPO | ARREGLO_NAVEGAR | ARREGLO_NINGUNO
    arreglo: str = ARREGLO_NINGUNO
    #: Sólo para ARREGLO_CAMPO: qué se le pide al usuario
    campo: dict = field(default_factory=dict)
    #: Qué ítem del presupuesto lo generó. Lo completa la vista, no el motor:
    #: el despiece de una abertura no sabe en qué renglón está.
    item: str = ""

    def __str__(self) -> str:
        return self.mensaje

    @property
    def es_error(self) -> bool:
        return self.severidad == ERROR


def textos(avisos) -> list[str]:
    """Lista de cadenas, para lo que todavía espera ``advertencias``."""
    return [a.mensaje if isinstance(a, Aviso) else str(a) for a in avisos]


def contar(avisos) -> tuple[int, int]:
    """``(errores, atenciones)``."""
    errores = sum(1 for a in avisos if isinstance(a, Aviso) and a.es_error)
    return errores, len(avisos) - errores


def resumen(avisos) -> str:
    """Una línea para la barra de estado."""
    errores, atenciones = contar(avisos)
    partes = []
    if errores:
        partes.append(f"{errores} error{'es' if errores != 1 else ''}")
    if atenciones:
        partes.append(f"{atenciones} aviso{'s' if atenciones != 1 else ''}")
    return " · ".join(partes)


# ---------------------------------------------------------------------------
# Constructores
#
# Uno por situación. Concentrar acá el texto y la sugerencia evita que el mismo
# problema se explique de tres formas distintas según desde dónde salte.
# ---------------------------------------------------------------------------

def linea_sin_precio(linea_id: int, linea_nombre: str, color: str) -> Aviso:
    return Aviso(
        codigo=LINEA_SIN_PRECIO, severidad=ERROR,
        mensaje=f"La línea «{linea_nombre}» no tiene precio cargado en color «{color}».",
        sugerencia="El aluminio se está cotizando en cero. Cargá el $/kg de ese color.",
        objeto={"tipo": "linea_precio", "linea_id": linea_id,
                "linea": linea_nombre, "color": color},
        arreglo=ARREGLO_CAMPO,
        campo={"clave": "precio_kg", "etiqueta": "Precio del aluminio",
               "unidad": "moneda_kg", "tipo": "moneda"})


def sin_formulas(tipologia: str, linea_id: int, linea_nombre: str) -> Aviso:
    return Aviso(
        codigo=SIN_FORMULAS, severidad=ERROR,
        mensaje=f"No hay fórmulas de despiece para la tipología «{tipologia}».",
        sugerencia="Sin fórmulas no hay aluminio: la abertura sale sin perfiles. "
                   "Cargalas en Materiales y Costos → Fórmulas de despiece.",
        objeto={"tipo": "formulas", "tipologia": tipologia,
                "linea_id": linea_id, "linea": linea_nombre},
        arreglo=ARREGLO_NAVEGAR)


def despiece_generico(tipologia: str, tipologia_nombre: str,
                      linea_id: int, linea_nombre: str) -> Aviso:
    """La tipología no tiene fórmulas propias para esta línea y cayó en las genéricas.

    Es el aviso que faltaba y que más confunde cuando falta. El programa arma un
    despiece y un precio que parecen correctos, pero salen de las fórmulas de
    ejemplo que trae la base —con perfiles inventados— en vez del sistema real
    del extrusor. Los avisos de "perfil fuera de catálogo" que aparecen después
    son la consecuencia, no la causa, y hacen buscar el problema donde no está.
    """
    return Aviso(
        codigo=DESPIECE_GENERICO, severidad=ERROR,
        mensaje=f"«{tipologia_nombre or tipologia}» no tiene fórmulas propias en "
                f"«{linea_nombre}»: se está usando el despiece genérico de ejemplo.",
        sugerencia="El precio que sale no corresponde a esta línea. O cargás las "
                   f"fórmulas de «{tipologia}» para «{linea_nombre}», o elegís en "
                   "la abertura una tipología que sí las tenga.",
        objeto={"tipo": "formulas", "tipologia": tipologia,
                "linea_id": linea_id, "linea": linea_nombre},
        arreglo=ARREGLO_NAVEGAR)


def formula_invalida(perfil: str, funcion: str, detalle: str,
                     tipologia: str, linea_id: int, linea_nombre: str) -> Aviso:
    return Aviso(
        codigo=FORMULA_INVALIDA, severidad=ERROR,
        mensaje=f"La fórmula de «{perfil}» ({funcion.replace('_', ' ').title()}) "
                f"no se puede calcular: {detalle}",
        sugerencia="Esa pieza queda afuera del despiece. Revisá la fórmula.",
        objeto={"tipo": "formulas", "tipologia": tipologia, "perfil": perfil,
                "linea_id": linea_id, "linea": linea_nombre},
        arreglo=ARREGLO_NAVEGAR)


def perfil_sin_peso(perfil_id: int, codigo: str, linea_id: int, linea_nombre: str) -> Aviso:
    return Aviso(
        codigo=PERFIL_SIN_PESO, severidad=ERROR,
        mensaje=f"El perfil «{codigo}» no tiene peso lineal cargado.",
        sugerencia="En modo kg el costo sale del peso: esa pieza se cotiza en cero. "
                   "Cargá los Kg/m del catálogo del extrusor.",
        objeto={"tipo": "perfil", "id": perfil_id, "codigo": codigo,
                "linea_id": linea_id, "linea": linea_nombre},
        arreglo=ARREGLO_CAMPO if perfil_id else ARREGLO_NAVEGAR,
        campo={"clave": "peso_kg_m", "etiqueta": "Peso lineal",
               "unidad": "kilos_metro", "tipo": "decimal", "decimales": 3})


def peso_sospechoso(perfil_id: int, codigo: str, peso: float,
                    linea_id: int, linea_nombre: str) -> Aviso:
    """El perfil tiene peso, pero uno que ningún perfil de aluminio tendría.

    Es el aviso que faltaba. Un peso en cero se nota; uno mil veces más grande
    no, porque el programa calcula igual y el número sólo se ve raro cuando ya
    saliste a cotizar. Que sea 'atención' y no 'error' es a propósito: no puede
    frenar a alguien con un perfil legítimamente pesado.
    """
    if peso > PESO_MAXIMO_PLAUSIBLE:
        pista = (f"Si el catálogo del extrusor venía en gramos por metro, el valor "
                 f"correcto sería {peso / 1000:.3f} Kg/m.")
    else:
        pista = (f"Si venía en kilos por barra de 6 m, el valor correcto sería "
                 f"{peso * 6:.3f} Kg/m.")

    return Aviso(
        codigo=PESO_SOSPECHOSO, severidad=ATENCION,
        mensaje=f"El perfil «{codigo}» pesa {peso:,.3f} Kg/m, fuera de lo normal "
                f"({PESO_MINIMO_PLAUSIBLE}–{PESO_MAXIMO_PLAUSIBLE} Kg/m).",
        sugerencia=f"El costo del aluminio sale del peso, así que un error acá se "
                   f"traslada entero al precio. {pista}",
        objeto={"tipo": "perfil", "id": perfil_id, "codigo": codigo,
                "linea_id": linea_id, "linea": linea_nombre},
        arreglo=ARREGLO_CAMPO if perfil_id else ARREGLO_NAVEGAR,
        campo={"clave": "peso_kg_m", "etiqueta": "Peso lineal",
               "unidad": "kilos_metro", "tipo": "decimal", "decimales": 3})


def perfil_fuera_catalogo(codigo: str, linea_id: int, linea_nombre: str) -> Aviso:
    return Aviso(
        codigo=PERFIL_FUERA_CATALOGO, severidad=ATENCION,
        mensaje=f"El perfil «{codigo}» no está en el catálogo de «{linea_nombre}».",
        sugerencia="Se cotiza con el peso de respaldo de la fórmula. El despiece "
                   "sirve para el precio, pero el taller no va a encontrar ese código.",
        objeto={"tipo": "perfil_nuevo", "codigo": codigo,
                "linea_id": linea_id, "linea": linea_nombre},
        arreglo=ARREGLO_NAVEGAR)


def corte_excede_barra(codigo: str, largo: float, barra: int,
                       linea_id: int, linea_nombre: str) -> Aviso:
    return Aviso(
        codigo=CORTE_EXCEDE_BARRA, severidad=ATENCION,
        mensaje=f"«{codigo}» necesita un corte de {largo:.0f} mm y la barra mide {barra} mm.",
        sugerencia="Esa pieza no sale de una barra entera: hay que empalmar, pedir "
                   "barra especial, o revisar si el largo de barra está bien cargado.",
        objeto={"tipo": "perfil", "codigo": codigo,
                "linea_id": linea_id, "linea": linea_nombre},
        arreglo=ARREGLO_NAVEGAR)


def corte_muy_corto(codigo: str, detalle: str, largo: float,
                    tipologia: str, linea_id: int, linea_nombre: str) -> Aviso:
    """Una fórmula devolvió una medida que no es una pieza.

    Pasa cuando las opciones se contradicen: un paño fijo de 900 en una ventana
    de 1000 deja la hoja en 21 mm. El despiece calcula sin quejarse y el
    presupuesto sale con un precio para algo que nadie puede fabricar.
    """
    return Aviso(
        codigo=CORTE_MUY_CORTO, severidad=ERROR,
        mensaje=f"«{codigo}» ({detalle}) queda en {largo:.0f} mm: no es una pieza.",
        sugerencia="Revisá las medidas y las opciones de la abertura. Suele ser "
                   "que una opción se come el espacio de otra —un paño fijo más "
                   "alto de lo que entra, por ejemplo.",
        objeto={"tipo": "formulas", "tipologia": tipologia, "perfil": codigo,
                "linea_id": linea_id, "linea": linea_nombre},
        arreglo=ARREGLO_NAVEGAR)


def demasiadas_piezas(codigo: str, detalle: str, pedidas: int,
                      tipologia: str, linea_id: int, linea_nombre: str) -> Aviso:
    """La fórmula de cantidad devolvió un número imposible.

    Se corta en :data:`MAX_PIEZAS_POR_FORMULA` en vez de intentar despiezarlas:
    el optimizador de corte es cuadrático y con cientos de miles de piezas el
    programa deja de responder. Al usuario le parece que se colgó, y en la
    práctica se colgó.
    """
    return Aviso(
        codigo=DEMASIADAS_PIEZAS, severidad=ERROR,
        mensaje=f"«{codigo}» ({detalle}) pide {pedidas:,} piezas: la fórmula de "
                f"cantidad está mal.",
        sugerencia=f"Se cortó en {MAX_PIEZAS_POR_FORMULA} para que el programa "
                   "siga respondiendo. Revisá la fórmula de cantidad: suele ser "
                   "una multiplicación de más, como usar A*H donde iba N.",
        objeto={"tipo": "formulas", "tipologia": tipologia, "perfil": codigo,
                "linea_id": linea_id, "linea": linea_nombre},
        arreglo=ARREGLO_NAVEGAR)


def pano_imposible(etiqueta: str, tipologia_hijo: str, ancho: float, alto: float,
                   compuesta: str, linea_id: int) -> Aviso:
    """Un paño de una tipología compuesta quedó sin medida.

    Suele ser que las fórmulas de reparto no cierran: el paño fijo se lleva más
    alto del que hay, o una variable quedó en un valor que no deja lugar.
    """
    return Aviso(
        codigo=PANO_IMPOSIBLE, severidad=ERROR,
        mensaje=f"El paño «{etiqueta}» ({tipologia_hijo}) queda en "
                f"{ancho:.0f} × {alto:.0f} mm: no se puede despiezar.",
        sugerencia="Las fórmulas que reparten el hueco no cierran. Revisá las "
                   "medidas de la abertura y las opciones que definen cada paño.",
        objeto={"tipo": "composicion", "tipologia": compuesta, "linea_id": linea_id},
        arreglo=ARREGLO_NAVEGAR)


def accesorio_sin_peso(accesorio_id: int, codigo: str) -> Aviso:
    return Aviso(
        codigo=ACCESORIO_SIN_PESO, severidad=ERROR,
        mensaje=f"El accesorio «{codigo}» está en Kg/m pero no tiene peso lineal.",
        sugerencia="Se cotiza en cero. Cargá los Kg/m que figuran en la lista del proveedor.",
        objeto={"tipo": "accesorio", "id": accesorio_id, "codigo": codigo},
        arreglo=ARREGLO_CAMPO,
        campo={"clave": "peso_kg_m", "etiqueta": "Peso lineal",
               "unidad": "kilos_metro", "tipo": "decimal", "decimales": 3})


def accesorio_no_elegido(clave: str, codigo_por_defecto: str) -> Aviso:
    """El kit espera que se elija un accesorio y la opción quedó vacía."""
    return Aviso(
        codigo=ACCESORIO_FORMULA, severidad=ATENCION,
        mensaje=f"La opción «{clave}» no tiene un accesorio elegido: se usa "
                f"«{codigo_por_defecto}».",
        sugerencia="Elegí el accesorio en las opciones de la abertura, o revisá "
                   "el valor por defecto de esa variable.",
        objeto={"tipo": "kit_item", "codigo": codigo_por_defecto},
        arreglo=ARREGLO_NAVEGAR)


def accesorio_formula(codigo: str, detalle: str) -> Aviso:
    return Aviso(
        codigo=ACCESORIO_FORMULA, severidad=ERROR,
        mensaje=f"La cantidad del accesorio «{codigo}» no se puede calcular: {detalle}",
        sugerencia="Ese accesorio queda afuera del kit. Revisá la fórmula de cantidad.",
        objeto={"tipo": "kit_item", "codigo": codigo},
        arreglo=ARREGLO_NAVEGAR)


def sin_kit(linea_id: int, linea_nombre: str, tipologia: str) -> Aviso:
    return Aviso(
        codigo=SIN_KIT, severidad=ATENCION,
        mensaje=f"No hay kit de accesorios para «{tipologia}» en «{linea_nombre}».",
        sugerencia="Los accesorios se están estimando por hoja con un valor general. "
                   "Armá el kit para que el consumo sea real.",
        objeto={"tipo": "kit", "linea_id": linea_id, "linea": linea_nombre,
                "tipologia": tipologia},
        arreglo=ARREGLO_NAVEGAR)
