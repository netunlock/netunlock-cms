# Costuras del beta sobre producción

Este archivo es el contrato del entorno beta: **toda diferencia con
`cotizador_aberturas/` tiene que estar listada acá**. Si `comparar_produccion.py`
marca un archivo que no figura en esta lista, algo se ensució y hay que revisarlo.

```bash
python tools/comparar_produccion.py
```

- **Producción:** `cotizador_aberturas/` — v3.0.0, esquema v4, congelada.
- **Beta:** esta carpeta — v3.1.0-beta, esquema v8.
- **Datos:** cada carpeta tiene su propio `datos/cotizador.db`. No se cruzan.

---

## Regla de oro

Ninguna costura cambia el comportamiento por defecto. Cada parámetro nuevo tiene
un valor por omisión que reproduce exactamente lo de producción, y eso se
verifica corriendo `python -m tools.prueba_rapida`, que tiene que seguir dando
`TODO OK` sin tocar una sola aserción.

---

## Archivos NUEVOS

No tocan nada existente; se pueden borrar y el beta vuelve a ser producción.

| Archivo | Qué es |
|---|---|
| `core/variables.py` | Todo el sistema de variables por tipología (1.1), incluido el renombrado seguro |
| `core/composicion.py` | Tipologías compuestas: paños, ciclos y validación (3.1) |
| `core/avisos.py` | Avisos tipificados del despiece (1.3) |
| `ui/dialogo_variables.py` | El bloque de opciones en el diálogo de abertura (1.1) |
| `ui/panel_avisos.py` | La lista accionable y el contador (1.3) |
| `ui/ventana_barras.py` | Barras a comprar del presupuesto consolidado |
| `reports/taller.py` | Diagramas de corte, etiquetas y listas por rubro (Fase 2) |
| `core/vigilante.py` | Detecta cuelgues de la interfaz y vuelca la pila |
| `COSTURAS.md` | Este archivo |
| `tools/comparar_produccion.py` | Control de deriva contra producción |
| `core/optimizar_vidrio.py` | Optimizador 2D de corte de vidrio (nesting sobre planchas) |
| `tools/escenario_stock.py` | Deja la base en un estado conocido para probar el stock |
| `core/catalogo_mdt.py` | Los dos catálogos MDT: perfiles, tipologías, medidas de corte, vidrios, accesorios y kits |
| `tools/precios_demo.py` | Lista de precios de demostración para grabar la pantalla |
| `core/prueba.py` | Los 3 días de prueba gratuita de la versión pública |
| `reports/marca_prueba.py` | El sello rojo de "versión de prueba" sobre todo lo que se imprime, mientras no haya licencia |

---

## Archivos MODIFICADOS

### `core/despiece.py` — la costura del motor

Tres firmas ganan un parámetro opcional. **Es el único cambio sobre el motor.**

```python
RESERVADAS = frozenset({"A", "H", "N", "AH", "HH", "PERIM", "M2"})   # nuevo

def contexto_base(ancho_mm, alto_mm, hojas, variables=None)          # + variables
def despiece_aluminio(db, ..., hojas, variables=None)                # + variables
def calcular_despiece(db, ..., vidrio_id, variables=None)            # + variables
```

`contexto_base()` mezcla las variables recibidas en el diccionario que ya
devolvía. Con `variables=None` el resultado es idéntico byte a byte al de
producción.

`RESERVADAS` protege los nombres del motor: una variable llamada `A` se ignora en
vez de pisar el ancho de la abertura. Un valor no numérico entra como `0.0` en
lugar de reventar el despiece.

> **El motor de fórmulas (`core/formula_engine.py`) NO se tocó.** No hizo falta:
> `evaluar()` resuelve cualquier nombre que esté en el contexto, y `validar()` ya
> recibía las variables como parámetro. La costura estaba puesta.

Y emite **avisos tipados** en lugar de cadenas: cada `advertencias.append(f"...")`
pasó a ser `avisos.append(av.algo(...))`. Se agregaron dos detecciones que antes
no existían, las dos salidas de probar con el catálogo real de MDT:

- `PESO_SOSPECHOSO` — el peso lineal cae fuera de 0,05–8 Kg/m. Es el catálogo
  cargado en gramos, que multiplica el costo del aluminio por mil.
- `CORTE_MUY_CORTO` — una fórmula devuelve menos de 50 mm. Pasa cuando dos
  opciones se contradicen (un paño fijo de 900 en una ventana de 1000 deja la
  hoja en 21 mm) y antes el presupuesto salía mudo con una abertura infabricable.

#### Optimización consolidada de barras

```python
def escalar(piezas, veces)                      # nuevo
def optimizar_conjunto(grupos)                  # nuevo: [(piezas, unidades), ...]
def barras_de_presupuesto(resultados)           # nuevo
def _clave_de_perfil(pieza)                     # nuevo: agrupa por (perfil_id, código)
```

`optimizar_por_perfil()` pasó a agrupar por **(id de catálogo, código)** y no
sólo por código: dos líneas pueden usar el mismo código para perfiles distintos,
y mezclarlos haría comprar barras que no existen.

Esto corrige un error de compra que estaba en tres lugares: `core/stock.py`
descontaba las barras de una unidad multiplicadas por la cantidad,
`core/ordenes.py` congelaba lo mismo y `reports/orden_trabajo.py` lo volvía a
multiplicar al imprimir. Diez ventanas iguales pedían 60 barras cuando se
necesitan 22.

El snapshot de la OT lleva ahora la marca `barras_totalizadas`, así que las
órdenes emitidas antes del cambio se siguen leyendo como se emitieron.

#### Tipologías compuestas

```python
def calcular_despiece(..., variables=None, _profundidad=0)   # + _profundidad
def _despiece_compuesto(...)                                 # nuevo
```

`calcular_despiece()` detecta si la tipología es compuesta y delega. Cada paño
se resuelve llamándose a sí misma con la medida que le toca, y el resultado se
suma al despiece propio de la compuesta (marco perimetral y acople).

Dos decisiones que están en el código y conviene no revertir sin pensarlo:

- **Los paños NO heredan las variables de la compuesta.** Cada uno resuelve las
  suyas con sus valores por defecto. Dos tipologías pueden usar el mismo nombre
  para cosas distintas: heredar `ALTO_FIJO` hacía que la corrediza generara un
  paño fijo adentro del suyo. El conjunto gobierna a sus paños por las fórmulas
  de ancho, alto y hojas de la composición, que sí ven sus variables.
- **Tope de profundidad y detección de ciclos.** `composicion.crearia_ciclo()`
  se consulta al guardar, y `PROFUNDIDAD_MAXIMA` corta por las dudas: un ciclo
  no se detecta cotizando, cuelga el programa cotizando.

#### Frenos contra el cuelgue

```python
av.MAX_PIEZAS_POR_FORMULA = 500      # una fórmula de cantidad equivocada
MAX_PIEZAS_A_EMPAQUETAR  = 20_000    # tope del optimizador, que es cuadrático
```

Una fórmula como `cantidad = A * H` pide 1.650.000 piezas. El optimizador de
corte es cuadrático, así que el programa dejaba de responder y desde afuera eso
es un cuelgue. Ahora se corta en 500 con el aviso `DEMASIADAS_PIEZAS`, y por
encima de 20.000 piezas el empaquetado se estima por metros en lugar de acomodar
pieza por pieza: el número sirve igual para comprar y la aplicación responde.

`ui/vista_despiece.py` agrega `self.esperar()`: `DialogoBase` toma el foco con
`grab_set()`, así que sin esperar el que la abría seguía su curso y podía dejar
otra ventana detrás de la modal — y eso también se ve como un cuelgue.

### `core/models.py` — el valor viaja con la abertura

```python
@dataclass
class Item:
    ...
    variables: dict = field(default_factory=dict)     # nuevo

@dataclass
class DespieceAluminio:
    ...
    avisos: list = field(default_factory=list)        # reemplaza al campo advertencias

    @property
    def advertencias(self) -> list[str]:              # ahora es propiedad
        return [str(a) for a in self.avisos]
```

Lo mismo en `DespieceAccesorios`, y `Despiece` gana la propiedad `avisos`.

`advertencias` dejó de ser un campo y pasó a ser una propiedad calculada: hay una
sola fuente de verdad y **todo lo que ya la consumía sigue andando sin cambios**
— el PDF, la ventana de despiece, la orden de trabajo y `tools/prueba_rapida`.

### `core/calculo.py` — dónde se resuelven

```python
from . import variables as variables_tipologia        # nuevo

# en calcular_item():
variables=variables_tipologia.resolver(db, item)      # nuevo argumento

# en presupuesto_desde_db():
variables=variables_tipologia.leer_json(_columna(fila, "variables_json", ""))

def _columna(fila, nombre, por_defecto=None)          # helper nuevo
```

`_columna()` lee columnas que pueden no existir todavía: si alguien abre con el
beta una base v4 sin migrar, devuelve el valor por omisión en lugar de romper.

### `core/database.py` — esquema v5

```python
ESQUEMA_VERSION = 5
MIGRACIONES[5] = [...]     # tabla + columna + 3 índices
```

Y el mismo contenido en `ESQUEMA`, para las bases nuevas.

Sólo `CREATE TABLE`, `ADD COLUMN` e índices: cumple las reglas de migración del
proyecto y respalda antes de aplicar.

Los dos índices únicos son **parciales** a propósito. En SQLite dos `NULL` son
distintos entre sí, así que un `UNIQUE(tipologia_codigo, linea_id, clave)` dejaría
entrar dos variables genéricas con el mismo nombre.

### `ui/vista_cotizacion.py` — persistencia y contador

```python
from core import avisos as avisos_mod                                   # nuevo
from core import variables as variables_tipologia                       # nuevo

self._avisos: list = []          # avisos del último recálculo
self.zona_badge / self._badge    # contador en la cabecera de "Aberturas"

def _pintar_badge(self)          # nuevo
def ver_avisos(self)             # nuevo

# en el dict de cada ítem al guardar:
"variables_json": variables_tipologia.escribir_json(r.item.variables)   # nuevo
```

En `recalcular()` se junta `resultado.despiece.avisos` de cada ítem y se les
completa el campo `item`: el motor no sabe en qué renglón está.

Y el bloque de variables dentro de `DialogoItem`:

```python
from .dialogo_variables import BloqueVariables, resumen_opciones   # nuevo

self.bloque_variables = BloqueVariables(...)   # se muestra sólo si hay variables
def _refrescar_variables(self, valores=None)   # nuevo
variables=self.bloque_variables.valores()      # en _construir_item()
```

`_cambiar_tipologia()` y `_cambiar_linea()` lo redibujan, porque el juego de
opciones es otro. La columna Opcionales suma las variables activas.

### `ui/vista_materiales.py` — ABM de variables y navegación

```python
def ir_a(self, objeto: dict) -> None      # nuevo: abre la pestaña con los filtros puestos
def _panel_variables(self, hoja)          # nuevo: ABM colgado de Tipologías
def _actualizar_ayuda_formulas(self, tip) # nuevo: lista las variables disponibles
def seleccionar_donde(self, columna, valor) -> bool    # nuevo, en PanelABM

# en el guardado de fórmulas:
validar(datos[clave], V.nombres(self.db, tip, lid))    # + segundo argumento
```

Ese segundo argumento de `validar()` es lo único que hacía falta para que la
pantalla acepte `si(PREMARCO, H + 36, 0)`. El motor de fórmulas no se tocó.

La pestaña Tipologías pasó a ser maestro-detalle: la tipología a la izquierda,
sus opciones a la derecha. Borrar una variable en uso avisa antes.

### `ui/componentes.py` — un accesor que faltaba

```python
def datos_de_filas(self) -> list[dict]    # nuevo, en Tabla
```

### `VERSION`

`3.0.0` → `3.1.0-beta`

---

### `core/optimizar_vidrio.py` — el corte de vidrio de verdad

El vidrio no se compra por metro cuadrado suelto: viene en **planchas de medida
fija** y hay que acomodar los paños adentro. Antes el sistema informaba los m²
con desperdicio, que sirve para cotizar pero no le dice nada al que corta.

```python
optimizar(panos, ancho_plancha, alto_plancha, tipo="",
          sierra=3.0, borde=5.0, permitir_rotar=True) -> PlanDeCorte
planes_de_presupuesto(db, pres, permitir_rotar=True) -> list[PlanDeCorte]
```

El algoritmo es de **franjas con guillotina**: los paños se ordenan de mayor a
menor altura y se apoyan de izquierda a derecha en bandas horizontales. Es la
familia que corresponde porque el vidrio se corta de lado a lado: un nesting
más apretado que produzca un corte imposible no sirve para nada.

Dos refinamientos sobre la versión de libro:

* **Sobrante de arriba.** Un paño de 1450 dentro de una franja de 1800 deja
  350 mm a lo largo de toda la plancha. Ese hueco se anota como una franja más
  y recibe paños bajos. Sigue siendo cortable: franja, columna, y recién ahí el
  corte que separa el paño del sobrante.
* **Se prueban las dos orientaciones.** Parar todo a vertical suele ganar por
  mucho (24 paños de 828×427 entran en una plancha parados y necesitan dos
  acostados) pero con medidas revueltas a veces pierde. Correr las dos cuesta
  milisegundos, así que se corren las dos y queda la que gasta menos planchas.

Cada tipo de vidrio se optimiza por separado: un float 4 y un DVH no se mezclan
en la misma plancha, son productos distintos.

Medido sobre 400 paños: 34 planchas, 90,8 % de aprovechamiento, 20 ms.

### Accesorio elegible al cargar la abertura — esquema v6 → v7

Una corrediza lleva rueda simple o doble según el peso de la hoja, y cierre de
embutir o multipunto según la prestación. Eran dos kits casi iguales, o dos
tipologías. Ahora es **una opción del ítem**.

```python
# core/database.py
ESQUEMA_VERSION = 7
MIGRACIONES[7] = ["ALTER TABLE kit_items ADD COLUMN variable_clave TEXT DEFAULT ''"]

# core/variables.py
TIPOS = ("bool", "numero", "opcion", "accesorio")      # + accesorio
def opciones_de_accesorio(db, filtro) -> list[tuple[str, float]]   # nuevo

# core/despiece.py, dentro de despiece_accesorios()
clave = _clave(fila, "variable_clave", "") or ""
if clave and clave in ctx:
    elegido = db.query_one("SELECT * FROM accesorios WHERE id = ?", (int(ctx[clave]),))
    ...   # reemplaza código, descripción, unidad, precio y peso del renglón

# core/avisos.py
def accesorio_no_elegido(clave, codigo_por_defecto) -> Aviso      # nuevo
```

El contexto del motor **sigue siendo numérico**: lo que guarda la variable es el
*id* del accesorio, que es un número como cualquier otro. No hay tipo nuevo en el
motor de fórmulas y no se tocó una línea de `formula_engine.py`.

El accesorio fijo del renglón queda como valor por defecto: si la variable no
está declarada para esa tipología —una banderola no lleva rueda— el kit se
comporta exactamente como antes.

En la interfaz: `ui/dialogo_variables.py` usa el mismo combo que el tipo
`opcion` (las dos ramas terminan en una lista de pares etiqueta/número), y
`ui/vista_materiales.py` suma la columna "Lo elige" al ABM de kits y ofrece sólo
las variables de tipo `accesorio` de esa tipología.

### `reports/taller.py` — los planos de plancha

```python
from reportlab.platypus import (KeepTogether, PageBreak, ...)   # + PageBreak

VIDRIO_FONDO / VIDRIO_BORDE                 # colores del paño
def _dibujo_plancha(plancha, ancho_dibujo) -> Drawing     # nuevo
def _seccion_planchas(db, pres)                           # nuevo
```

El dibujo invierte la Y: el origen del `Drawing` de ReportLab está abajo a la
izquierda y el del plan de corte arriba a la izquierda.

Los paños girados se marcan con «90°» y no con una flecha de giro: las fuentes
base del PDF no la tienen y en el papel sale un cuadradito negro.

### `tools/escenario_stock.py` — condiciones de prueba

`--aplicar` deja aluminio, vidrio y accesorios con cantidades conocidas: de cada
tres artículos, uno sobra, uno está justo y uno falta. `--limpiar` lo saca sin
tocar el stock real.

Todo va a un depósito aparte, `PRUEBA`, y mientras el escenario está puesto ese
pasa a ser el depósito por defecto, porque el sistema consulta y descuenta contra
**uno solo** a la vez. `--limpiar` devuelve el que había.

También da de alta las variantes del catálogo Aluar (E83/E97/E98, R48/R49,
H123/H130, topes, desagües, burletes, premarco y mosquitero), declara
`RODAMIENTO` y `CIERRE` en las corredizas y engancha los renglones del kit.

### `tools/generar_manual.py` — el manual al día

El manual se había quedado en la 2.x: no contaba ni el inventario ni las órdenes
de trabajo, que ya estaban en la 3.0.0.

```python
_contador = {"h1": 0, "h2": 0}      # antes sólo h1
def h2(texto)                       # ahora numera solo
```

Los subtítulos tenían el número escrito a mano (`h2("3.1  Encabezado")`), así que
insertar un capítulo en el medio desfasaba todos los de abajo. Ahora lo pone la
función, y las referencias cruzadas del texto nombran el capítulo en vez de su
número, que es lo único que no se rompe al reordenar.

Capítulos nuevos: **Los papeles del taller** (con el plano de corte de vidrio y
su ilustración), **Inventario** y **Órdenes de trabajo**. Secciones nuevas:
*Opciones de la tipología* (en Armar un presupuesto y en Materiales), *El
contador de advertencias*, y los botones que faltaban en la barra de la lista de
aberturas.

La ilustración `recursos/manual/corte_vidrio.png` sale de dibujar una plancha
real con `taller._dibujo_plancha()`: es exactamente lo que el taller va a ver
impreso, no un dibujo aparte que se despega del programa.

### `build_exe.py` — las herramientas de desarrollo, afuera

```python
EXCLUIR += ["tools.escenario_stock", "tools.comparar_produccion",
            "tools.prueba_rapida"]
```

No se pueden disparar desde la interfaz, pero escriben en la base del usuario.
Un paquete de cliente no las lleva.

### `build_portable.py` — dos bugs que salían a la luz recién al compilar

**1. La prueba de portabilidad dejaba una base a medio sembrar.**

`probar()` cortaba el programa apenas aparecía `datos/cotizador.db`, y ese
archivo existe desde que sqlite abre la conexión —o sea, en plena siembra—.
La carpeta quedaba con 5 líneas, 37 perfiles y **cero** tipologías, vidrios y
accesorios. Como `sembrar()` sólo corre si la base es nueva o no tiene líneas,
esa base nunca se completaba: quien copiara la carpeta al pendrive se
encontraba un programa que no cotiza.

El zip salía limpio porque `comprimir()` saltea `datos/`. El problema era la
**carpeta**, que es justo lo que el propio script te dice que copies.

```python
def _siembra_completa(base) -> bool     # nuevo
    # mira vidrio_formulas, que es LO ULTIMO que escribe seed_data.sembrar()
```

No alcanza con mirar líneas o tipologías: se cargan al principio y las 221
fórmulas de despiece siguen entrando después. Y al terminar, `probar()` borra
`datos/` y `salidas/`: la carpeta tiene que quedar idéntica al zip.

Verificado descomprimiendo el zip en una carpeta virgen y abriendo el .exe como
lo haría el usuario: arranca en 5,6 s sin pedir activación, siembra las 221
fórmulas y las 16 de vidrio, deja la base en el esquema v7 junto al programa y
no toca la de `%LOCALAPPDATA%`.

**2. Un mensaje de progreso volteaba la compilación.**

`_log("  + core/rutas.py → datos junto al .exe")` levantaba
`UnicodeEncodeError`: la consola de Windows en español es cp1252 y no tiene la
flecha. Un minuto y medio de compilación perdido por un caracter de adorno.
Los dos scripts piden ahora UTF-8 en stdout y stderr, con `errors="replace"`
si no se puede. `build_exe.py` tenía el mismo agujero y se salvaba de casualidad
por no usar ningún caracter fuera de cp1252.

### `ui/componentes.py` — la ventana que existía y no se veía

`Ver despiece` y `Barras a comprar` no abrían nada. No era un cuelgue ni un
error: la ventana se creaba, tenía geometría y contenido, y `winfo_exists()`
daba 1 — pero `winfo_ismapped()` daba 0. Estaba **sin mapear**, o sea invisible.

Al crear un `Toplevel`, CustomTkinter lo esconde para pintarle la barra de
título de Windows y lo vuelve a mostrar con un `after()` propio, y cada
`geometry()` y cada `resizable()` dispara ese ciclo otra vez. Midiendo la
cronología del mapeo: la ventana aparecía a los **294 ms** y volvía a
esconderse a los **767 ms**, cuando ya nadie la estaba mirando.

```python
VIGILAR_CADA_MS = 120
VIGILAR_TICKS = 15
def _asegurar_visible(self, tick=0)     # nuevo, llamado al final de _presentar()
```

No alcanzaba con un `deiconify()` ni con dejar de mirar apenas se ve: hay que
controlar durante todo el arranque —1,8 s— y volver a mostrarla las veces que
haga falta. Después la vigilancia se apaga sola.

**Por qué no había saltado antes:** un diálogo **modal** lo disimula, porque
`grab_set()` fuerza a la ventana a aparecer. El bug sólo afecta a las ventanas
`modal=False`, que son justamente las dos que se pasaron a no modales para que
no parecieran un cuelgue. Se cambió una cosa por la otra sin que la prueba lo
notara, porque la prueba miraba que la ventana **existiera**, no que se **viera**.
Ahora `scratchpad/prueba_ventanas.py` mira `winfo_ismapped()`.

### `core/prueba.py` — los 3 días de prueba

La versión que se baja de la web entra sin pedir nada y funciona completa
**tres días**. Cuando se terminan, la pantalla de activación dice a dónde
escribir. No es una traba: es que la persona pruebe con sus presupuestos y, si
le sirve, tenga a mano cómo seguir.

```python
DIAS = 3
CONTACTO = "cotizadoraberturas@gmail.com"
def estado(ahora=None, iniciar=True) -> EstadoPrueba
```

Se engancha en `licencia.estado_actual()`, **después** de verificar el reloj y
sólo cuando no hay licencia instalada. Ese orden importa: los días se cuentan
contra la hora que `core.reloj` considera confiable —que ya cruza la marca
local firmada, la fecha de la base, la de la licencia y la hora de internet— y
no contra el reloj del sistema, que es justamente lo que alguien tocaría.

El inicio se firma con HMAC usando la misma clave derivada del equipo que usa
`reloj`. Editar el archivo invalida la firma, y una prueba sin firma válida se
trata como vencida: si no se puede saber cuándo empezó, no se regala tiempo.
La cuenta además está topeada —`max(0, transcurridos)`— para que una fecha
anterior al inicio dé cero días y no días de más; la prueba no puede depender
de que otro módulo la proteja.

`prueba.dat` queda en `%APPDATA%\Roaming`, junto a `licencia.lic` y no con la
base: borrar la carpeta de datos no reinicia la prueba.

**Lo que no pretende.** Quien borre la carpeta de Roaming empieza otros tres
días. Se podría esconder marcas por el sistema y no se hace: eso es lo que hace
un programa que uno no quiere tener instalado. Quien se toma ese trabajo no iba
a comprar igual.

### `core/seed_data.py` — se fue el catálogo de mentira

`sembrar()` cargaba cinco líneas inventadas (Módena, Herrero, A30 New, Ekonal,
Módena Plus) con perfiles, tipologías, vidrios y accesorios de precio
inventado. Servían cuando el programa no traía ningún catálogo real. Hoy trae
los dos de MDT completos, y en algo que se baja de internet un precio inventado
es peor que ningún precio: quien lo abre no sabe si ese número es de verdad.

```python
def sembrar(db)            # empresa y parámetros. Nada más.
def sembrar_muestra(db)    # las líneas de ejemplo — SÓLO la regresión
```

Una instalación nueva queda con **248 perfiles, 30 tipologías, 363 fórmulas,
11 vidrios y 38 accesorios**, todo MDT y todo en $0. Cero fórmulas genéricas,
así que el aviso "despiece genérico" ya no puede aparecer por datos de fábrica.

`sembrar_muestra()` existe porque `tools.prueba_rapida` compara contra totales
fijos: necesita datos que no cambien y precios que no cambien, y los catálogos
MDT están en $0 a propósito. Es idempotente —saltea vidrios y accesorios que ya
estén— porque corre después de la siembra MDT, que trae algunos con el mismo
nombre.

### `recursos/entrega/`

Todo lo que está acá **viaja al cliente**. Se sumó `Manual de Usuario.pdf` y
`Novedades 3.1.0-beta.txt`.

### `core/catalogo_mdt.py` — los catálogos del fabricante adentro del programa

Hasta acá el programa venía con un juego de datos de muestra y cada uno cargaba
su línea a mano. Ahora trae los dos catálogos de **MDT — Metales del Talar**
completos, sacados de los PDF oficiales:

| | Clásica (06-15) | Actual (10-19) |
|---|---|---|
| perfiles con su peso | 142 | 106 |
| tipologías | 14 | 16 |
| medidas de corte | 108 | 255 |

**De dónde sale cada dato.** Los perfiles salen de la sección *Listado de
Perfiles*. En Actual esa tabla tiene capa de texto: se leyó directo y se cotejó
contra el PDF con coordenadas —41 de 41 pesos iguales—. En Clásica las páginas
005, 006, 008, 009 y 010 son imágenes escaneadas, así que se leyeron mirando la
página renderizada. Las medidas de corte salen de las tablas *Dimensiones de
corte de perfiles* y **se copian tal cual**: el catálogo escribe `H+36` y
`(A/2)-25`, que es exactamente lo que entiende `formula_engine`, así que no hay
traducción de por medio donde se pueda colar un error. Las 363 se evaluaron con
el motor antes de escribirlas: ninguna falla y ninguna da un largo absurdo.

**Lo que hubo que resolver.** El catálogo lista **alternativas en la misma
tabla** —marco recto, curvo y de 75 mm uno debajo del otro; perfil para vidrio
simple y para DVH— distinguidas por unas columnas A/B/C que el PDF convertido
pierde. Cargadas de una, el despiece cortaba las tres y un paño fijo de 900×1200
pesaba 23 kg en vez de 8. Se agrupan las filas por el **puesto** que ocupan
(jamba de marco, zócalo de hoja) y por si salen del ancho o del alto: la primera
queda activa y las demás con **cantidad 0** y una nota que dice de qué son
alternativa. Cantidad 0 no borra nada —el renglón sigue en la pantalla de
fórmulas con su medida— y alcanza con ponerle la cantidad para usar ese perfil.
Son 83 renglones.

Otros 7 apuntan a perfiles que estos catálogos citan pero no listan: dos remiten
al catálogo *Complementarios* y a dos el fabricante les dejó la celda del peso
vacía. Van también en cantidad 0 con el motivo escrito, porque sin peso no se
puede costear y poner un número a ojo es peor que no ponerlo.

**Y la corrección documentada.** Varias tablas de marco traen las jambas con
medida A y el umbral con H, al revés de como el mismo catálogo da el premarco
dos filas más arriba. Se cargan corregidas —jamba del alto, umbral y dintel del
ancho— y el renglón queda con la aclaración a la vista. Son 10.

**Precios: todo en $0.** Ni perfil, ni vidrio, ni accesorio. El catálogo del
fabricante no los publica y cada carpintería compra a su lista. Lo que sí entra
completo son los **kits**, con sus cantidades por fórmula, así el presupuesto
sale con sus renglones de accesorio desde el primer día y lo único que falta es
el precio.

### `core/database.py` — la siembra de los catálogos

```python
from .catalogo_mdt import sembrar_mdt, ya_sembrado
if not ya_sembrado(self):
    sembrar_mdt(self)
```

Va en `__init__` y no en `MIGRACIONES` a propósito: lo que carga son **datos**,
no esquema, y las migraciones tienen prohibido ejecutar Python. Corriéndolo en
cada arranque, una instalación que viene de una versión anterior recibe los
catálogos con la actualización. `sembrar_mdt()` no pisa nada que el usuario haya
tocado —usa el código como identidad y sólo reemplaza las fórmulas de las
tipologías MDT, que son datos del fabricante—, así que se puede correr las veces
que sea. Cuesta unos 6 s la primera vez y 0,01 s las siguientes.

**La marca de siembra completa.** `sembrar_mdt()` deja un parámetro
`catalogo_mdt_version` en el **mismo commit** que los datos, y `ya_sembrado()`
mira eso y no las tablas. Contar filas no sirve: siempre hay algo que se escribe
después, y si el programa se corta en el medio la base queda a medias pero
parece completa. Con la marca, una siembra interrumpida vuelve a correr sola en
el próximo arranque. Se descubrió en la prueba del build portable, que cortaba
el programa apenas veía el primer kit MDT y daba verde con 12 kits de 30.

---

### `reports/marca_prueba.py` — el sello, y por qué reemplaza a más candados

Los 3 días de prueba se reinician borrando la carpeta del usuario. Se podía
esconder marcas por el registro y por medio disco para impedirlo; no se hizo.
Eso es lo que hace un programa que uno no quiere tener instalado, y además
siempre pierde: quien sabe borrar una carpeta aprende a borrar dos.

El sello ataca el otro lado. A un carpintero no le sirve **usar** el programa:
le sirve **mandarle el presupuesto a un cliente**. Un PDF cruzado de rojo con
"VERSIÓN DE PRUEBA" no se le manda a nadie. Reiniciar la prueba deja de tener
sentido: se puede abrir el programa para siempre y no sale un solo papel
presentable.

**Un solo enganche, en los seis documentos.** Todos los informes se arman con
`SimpleDocTemplate` + `doc.build()`, así que alcanza con un `canvasmaker`:

```python
# reports/pdf_generator.py, taller.py (×4), orden_trabajo.py
doc.build(historia, canvasmaker=marca_prueba.lienzo())
```

`lienzo()` devuelve el `Canvas` normal de ReportLab cuando hay licencia, así que
el que pagó no arrastra ni una línea de código de más. El armado del documento
no se toca: los `onFirstPage`/`onLaterPages` del presupuesto siguen siendo los
de siempre.

**Se sella en `showPage()` y NO en `save()`.** ReportLab hace
`if self._code: self.showPage()` antes de guardar; dibujar en `save()` volvía
"con contenido" a una página ya vacía y salía **una hoja de más al final**, en
blanco y cruzada de rojo. Con `showPage()` solo, la última página igual pasa por
ahí.

**El paso de la rejilla sale de `stringWidth()`**, no a ojo: puesto a ojo las
repeticiones se pisan entre ellas y no se lee ni la marca ni lo que hay debajo.
Y va repetido, no una vez en el medio: una marca única se recorta con cualquier
visor, catorce cruzadas no.

**El Excel** no se puede cruzar en diagonal. El aviso va en las dos primeras
filas de cada hoja, en rojo, y en el encabezado y el pie de impresión.
`_sellar()` corre al final de `exportar()` y corrige el `freeze_panes`, que
quedaba tres filas más arriba de la fila de títulos.

**Al activar, se apaga en el acto.** `hace_falta()` recuerda 30 s para no
revisar la licencia una vez por PDF; `licencia.instalar()` limpia esa memoria,
así el primer documento después de poner la clave ya sale limpio sin cerrar el
programa.

**Si no se puede determinar el estado, se sella.** Es la opción que no regala
nada, y el peor caso es un PDF marcado de más en una instalación rota.

La **versión portable** no lleva sello: su `estado_actual()` parcheado devuelve
una licencia perpetua y `es_prueba` queda en `False`.

---

### `core/prueba.py` — la fecha, anotada dos veces

La fecha de inicio va en la carpeta del usuario **y** en la tabla `parametros`
de la propia base. Vale siempre la más vieja de las dos, y la que sobrevive
repone a la que falte:

```python
fechas = [f for f in (del_archivo, de_la_base) if f is not None]
inicio = min(fechas) if fechas else None
```

Borrar Roaming ya no reinicia nada. Borrar también la base sí, pero se lleva
puesto todo lo cargado —presupuestos, precios, fórmulas, órdenes—, que es
justamente lo que nadie quiere perder después de tres días de trabajo.

Las dos copias están a la vista, en lugares donde el programa ya guarda cosas.
No hay marcas escondidas en el registro ni archivos sueltos por el disco.

**`sincronizar()`, llamado desde `App.__init__`.** El control de licencia corre
**antes** de que exista `cotizador.db`, así que en el primerísimo arranque la
copia de la base no se puede escribir. `App` la repone apenas abre la base.

---

### Premarco y contramarco de MDT Actual: opciones de cada abertura

Las 15 tipologías de la línea Actual que traen premarco y contramarco en su tabla
de corte (todas menos AC-PPOST) los cortaban y los cobraban **siempre**, los
llevara la obra o no. Y el tilde «Incluye premarco» sumaba encima `premarco_m2`:
un AC-PF de 900×1200 salía con las piezas MT-0205 en el despiece con y sin tilde,
y tildado sumaba además $ 6.480 de premarco por m². Medido el 14/09/2026 sobre la
3.3.0.

#### `core/catalogo_mdt.py` — catálogo versión 2

```python
VERSION_CATALOGO = 2
PERFILES_CONTRAMARCO_ACTUAL = ("MT-0206", "MT-0906")
OPCIONES_MONTAJE = [...]          # PREMARCO y CONTRAMARCO: bool, arrancan en 0
def opcion_de_renglon(linea, perfil, funcion) -> str
def formulas_de_fabrica(linea, perfil, funcion, formula, cantidad) -> tuple[str, str]
def opciones_por_tipologia() -> dict[str, list[str]]
def _declarar_opciones(db, linea_id) -> dict
def version_sembrada(db) -> int
def _actualizar_a_v2(db) -> dict
ACTUALIZACIONES = {2: _actualizar_a_v2}
def actualizar_mdt(db, anterior) -> dict
```

`FORMULAS_MDT` **no se tocó**: sigue guardando la medida tal cual la publica el
fabricante. La condición se agrega al sembrar, con dos reglas en lugar de una
lista a mano: función `PREMARCO` → opción PREMARCO; función `OTRO` con perfil
MT-0206 o MT-0906 → opción CONTRAMARCO. Son 63 renglones:

    MT-0205   H+36   x 2    ->    si(PREMARCO, H+36, 0)    si(PREMARCO, 2, 0)

Se condicionan **largo y cantidad**, así la opción sigue mandando aunque alguien
edite una de las dos columnas. Las 8 alternativas quedan en cantidad 0 con el
largo condicionado: quien siga su nota ("poné la cantidad si usás este perfil")
tiene la opción gobernando esa pieza igual. Las dos opciones se declaran para la
línea MDT Actual y arrancan **destildadas**: nada se corta ni se cobra si no se
elige.

**Una base ya sembrada no se resiembra.** Con la versión 1, subir
`VERSION_CATALOGO` borraba y volvía a cargar todas las fórmulas MDT; simulado,
una alternativa que el usuario había puesto en cantidad 2 volvía a 0. Ahora
`sembrar_mdt()` tiene dos caminos: sin marca siembra todo como antes; con una
marca anterior aplica `ACTUALIZACIONES`, con respaldo previo
(`cotizador_previo_catalogo_v2_*.db`) y todo en un commit junto con la marca.

`_actualizar_a_v2()` reconoce cada renglón por tipología, perfil, función y
orden, y reescribe **cada columna sólo si todavía tiene el valor de la versión 1**:

| Lo que hizo el usuario | Qué pasa |
|---|---|
| nada | largo y cantidad pasan a la versión 2 |
| le puso cantidad a una alternativa | se condiciona el largo; su cantidad queda |
| corrigió un largo | su largo queda; se condiciona la cantidad |
| borró el renglón | no se recrea |
| declaró PREMARCO a mano | queda la suya |
| tenía opciones genéricas en esa tipología | se copian a la línea antes de declarar las nuevas: lo de la línea pisa a lo genérico y, si no, se las escondería a sus fórmulas |

Las columnas editadas se informan en el resumen que devuelve. Correr el paso dos
veces no cambia nada.

**Verificado sobre bases temporales y copias.** Base nueva: 30 opciones, 63
renglones condicionados y las 363 fórmulas validan con sus variables. Con las dos
opciones prendidas, los 90 despieces (30 tipologías × 3 medidas) son **idénticos**
a los de la versión 1; apagadas, son la versión 1 sin esas piezas. Una base v1 con
seis ediciones del usuario: las seis respetadas. Copias de las dos bases de
trabajo: 63 renglones actualizados, ninguno editado, 30 opciones.
`tools.prueba_rapida`: TODO OK con el mismo TOTAL ($ 2.780.975,62).

#### La casilla «Incluye premarco» manda — variables, cálculo e interfaz

Con PREMARCO declarado habría **dos** casillas para lo mismo: «Incluye premarco»
arriba y «Lleva premarco» en Opciones de la tipología. El PDF ("Con premarco" /
"Sin premarco") y la orden de trabajo leen la primera, así que podía salir un
presupuesto que dice "Sin premarco" mientras el taller lo corta. Se decidió que
mande la casilla de siempre.

```python
# core/variables.py (archivo nuevo del beta)
VINCULADAS = {"PREMARCO": "incluye_premarco"}
# resolver(): una vinculada que el ítem no traiga elegida toma el valor de su casilla

# ui/dialogo_variables.py (archivo nuevo del beta)
# BloqueVariables.construir() y resumen_opciones() saltean las vinculadas

# core/calculo.py
FUNCION_PREMARCO = "PREMARCO"                          # nuevo
def costo_premarco(db, item, despiece=None)            # + despiece
premarco=costo_premarco(db, item, despiece)            # en calcular_item()

# ui/vista_cotizacion.py, en DialogoItem._precargar()
contexto = variables_tipologia.resolver(self.db, item)          # nuevo
if "PREMARCO" in contexto:
    self.chk_premarco.set(bool(contexto["PREMARCO"]))

# ui/vista_materiales.py, «Probar despiece»
variables=V.valores_por_defecto(self.db, tip, lid)               # nuevo argumento
```

- **`costo_premarco()`** ya no suma `premarco_m2` ni `premarco_ml` cuando el
  despiece trae piezas de función PREMARCO: ese premarco ya se cobra con el
  aluminio, por peso. Con `despiece=None` se comporta como producción, y una
  línea que no corta premarco —las de muestra de la regresión— lo sigue cobrando
  por parámetro: `prueba_rapida` da el mismo TOTAL. Es la corrección del doble
  cobro, y es la única diferencia de comportamiento fuera de las tipologías
  con opciones.
- **Una abertura guardada con PREMARCO elegido aparte** —quien siguió el ejemplo
  del manual antes de este cambio— se respeta: `resolver()` usa ese valor, y el
  diálogo abre con la casilla según lo que de verdad corta. Guardada de nuevo,
  queda expresada con la casilla.
- **«Probar despiece»** llamaba al despiece sin variables. Con las fórmulas
  condicionadas marcaba ocho "Variable desconocida" en AC-PF; ahora usa los
  valores por defecto de la tipología.

**Verificado:** AC-PF 900×1200 da 6 piezas (5,78 kg) sin tilde, 8 (7,20 kg) con
tilde y 10 (8,01 kg, lo mismo que antes) con tilde y contramarco, siempre con
`costos.premarco = 0`. Las 15 tipologías con tilde: piezas de premarco y nada por
m². Módena COR2 con tilde: $ 9.900 por m² y $ 23.400 en modo ml, como antes. El
presupuesto de la portable (copia): sus dos AC-COR2 pasan de 14 piezas a 10 sin
tilde, y a 12 tildadas. En el diálogo real (`DialogoItem`, abierto y cerrado
desde un script): el bloque de opciones de AC-PF muestra sólo «Lleva
contramarco», la vista previa no agrega un renglón "Premarco", una abertura
guardada con PREMARCO aparte abre tildada, y una Clásica sin opciones sigue
cobrando el premarco por m².

#### `tools/generar_manual.py` — el texto de las casillas

«Incluye premarco» ya no dice sólo "suma el costo por m²": explica que, si la
línea corta el premarco con sus perfiles, lo agrega al despiece. El ejemplo de
opción bool pasó de «Lleva premarco» a «Lleva contramarco», y en Materiales se
avisa que una opción con clave PREMARCO no aparece en la abertura porque la
decide esa casilla. **El PDF del manual no se regeneró.**

Quedaron afuera y se corrigieron en la versión 3 (sección siguiente): AC-PPOST
(su tabla se cargó con el premarco como marco y todo lo demás en cantidad 0) y las
alternativas que quedaron las dos activas (AC-BAND hoja recta y curva, AC-PF
travesaño recto y curvo). El mismo doble cobro con «Incluye mosquitero», en 14
corredizas de las dos líneas, se corrigió en la versión 4 (sección «Mosquitero de
las corredizas MDT»).

---

### Tablas de AC-PPOST, AC-BAND y AC-PF: catálogo versión 3

Medido el 14/09/2026 sobre la versión 2: tres tipologías de MDT Actual cortaban
piezas que no van juntas. Un AC-PF de 900×1200 salía con cuatro travesaños
(5,78 kg en lugar de 3,05). Un AC-BAND cortaba la hoja de borde recto **y** la
de borde curvo, más el travesaño y el acople de la versión combinada con paño
fijo. Y una AC-PPOST de 1600×2050 cortaba sólo 1,9 kg de premarco, cargado como
marco: sin marco, sin hojas y sin celosía.

**La causa.** Cada tabla de corte trae una columna de cantidad por variante
(A/B/C/D) que el PDF convertido perdió. La carga agrupó las filas por nombre de
pieza y dejó activa la primera de cada nombre: "borde recto" y "borde curvo" son
nombres distintos, así que quedaron las dos, y en AC-PPOST todo quedó como
alternativa de la primera fila. Se rehicieron contra las págs. 044, 063 y 093
—las columnas se leyeron con las coordenadas del texto y se cotejaron con la
página renderizada— y contra los detalles de las págs. 028, 067, 071 y 094.

#### `core/catalogo_mdt.py` — catálogo versión 3

```python
VERSION_CATALOGO = 3                                   # 4 desde el mosquitero
TIPOLOGIAS_CORREGIDAS_V3 = ("AC-PF", "AC-BAND", "AC-PPOST")
_FORMULAS_V2_CORREGIDAS = [...]    # esas tres tablas como las sembró la v2, congeladas
def aclaracion_de_fabrica(nota, corte) -> str          # sembrar_mdt la armaba en línea
def opciones_por_tipologia(solo=None, formulas=None)   # + formulas
def _declarar_opciones(db, solo=None, formulas=None, tipologias=None)
def _formulas_v2() -> list[tuple]
def _columnas_de_fabrica(renglon) -> dict
def _actualizar_a_v3(db) -> dict
ACTUALIZACIONES = {2: _actualizar_a_v2, 3: _actualizar_a_v3}
def _sumar_resumen(total, parcial)                     # actualizar_mdt suma los pasos
```

Lo que cambia en `FORMULAS_MDT`, sólo en esas tres tipologías:

| Tipología | Antes | Ahora |
|---|---|---|
| AC-PF (A 75 mm · B curvo · C recto) | travesaños MT-0270 y MT-0264, horizontal y vertical, los cuatro en 1 | los cuatro en 0, con nota: opcional y uno solo; el MT-0264 sólo con el marco curvo |
| AC-BAND (A ventiluz recto · B ventiluz curvo · C banderola recto · D banderola curvo) | hojas MT-0227 y MT-0236 activas; travesaño MT-0221 y acople MT-0213 en 1 | activa sólo la A (MT-0227); B, C y D alternativas con la nota corregida; travesaño y acople en 0, "sólo combinada con paño fijo", y el acople con largo A (el catálogo dice H y va horizontal); se agregan los zócalos de MT-2210 y MT-1211, que faltaban |
| AC-PPOST (A 1 hoja · B 2 hojas) | MT-0205 ×2 como marco y 19 renglones en 0 | la tabla entera: 21 renglones corregidos y 6 que faltaban (jambas del contramarco H+27, MT-2695 de 2 hojas, terminales MT-2706 y MT-2707) |

Los criterios de AC-PPOST, confirmados por Federico:

- **Una tipología para 1 y 2 hojas.** La cantidad mira N, las «Hojas (N)» de la
  abertura: `si(N == 1, 2, 4)` es "2 con una hoja, 4 con dos". N = 1 corta la
  columna A y 2 o más, la B. La tipología arranca en 2.
- **Tablillas deducidas.** El catálogo dice "determinar cantidad según altura del
  postigón". Por hoja, `piso((H-360)/67)` con la nota MEDIDA DEDUCIDA: 67 mm es
  el paso de encastre a encastre de la MT-2705, medido a escala en la pág. 028, y
  360 mm lo que ocupan el adaptador (H−219, con cara de 23 mm) y los terminales en
  el corte de la pág. 094. A verificar en el taller.
- **Travesaños opcionales en 0**, como las demás alternativas: la pág. 094 lo
  dibuja como «Opción con travesaño». Mismo criterio en AC-PF.

Premarco y contramarco de AC-PPOST entran por las dos reglas de la versión 2:
quedan 67 renglones condicionados y 32 opciones (16 tipologías × 2). Con
«Incluye premarco» tildado, `costo_premarco()` ya no suma `premarco_m2` encima,
porque el despiece trae piezas PREMARCO.

**Una base ya sembrada no se resiembra.** `_actualizar_a_v3()` sigue el contrato
de la versión 2, columna por columna (función, largo, cantidad y nota):

| Lo que hizo el usuario | Qué pasa |
|---|---|
| nada | el renglón pasa a la versión 3 |
| editó una columna que la corrección cambia | queda la suya y se informa |
| editó una columna que la corrección no cambia | queda la suya, sin aviso |
| borró un renglón | no se recrea |
| rehízo la tabla a mano (ningún renglón conserva la nota de fábrica) | la tipología no se toca: ni correcciones, ni renglones nuevos, ni opciones; se informa |

- Un renglón se reconoce por tipología, perfil y **orden**, porque la función es
  una de las columnas que se corrigen. Por eso los renglones que faltaban van al
  final (AC-BAND 19 y 20, AC-PPOST 22 a 27) y los existentes no se renumeran.
- `_actualizar_a_v2()` ahora trabaja sobre `_formulas_v2()`, así hace lo mismo
  que antes. Las dos bases de trabajo siguen en la versión 1 y van a pasar a la
  última —hoy la 4— en un solo arranque, con un respaldo
  `cotizador_previo_catalogo_v4_*.db` y un commit.
- `actualizar_mdt()` suma los resúmenes de los pasos en vez de quedarse con el
  del último.

**Cómo se terminó.** La sesión que corrigió estas tablas se cortó por el límite de
uso el 14/09/2026 a las 15:36, con `FORMULAS_MDT`, el docstring y esta sección ya
escritos pero sin ninguna de las funciones del bloque de arriba. A la misma hora,
otra sesión dejaba a medias el mosquitero en el mismo archivo, también como
"versión 3". Se completaron el 16/09 en una sola sesión: estas tablas quedaron como
versión 3, siguiendo este contrato, y el mosquitero pasó a la 4.
`_FORMULAS_V2_CORREGIDAS` no se escribió a mano: se generó desde el `.pyc` de
`catalogo_mdt` de las 14:26, que guardaba el archivo tal cual era en la versión 2.
`_declarar_opciones` difiere en un detalle de lo que se había planeado: ya no
recibe la línea, porque la resuelve por tipología (la versión 4 declara también en
Clásica).

**Verificado sobre bases temporales y copias.** `_formulas_v2()` es exactamente la
tabla de la versión 2, y fuera de las tres tipologías `FORMULAS_MDT` no cambió.
Base nueva: las 371 fórmulas validan con sus variables, 67 renglones condicionados
y 32 opciones; AC-PF 900×1200 pesa 3,05 kg, AC-BAND 900×600 4,64 kg y una AC-PPOST
de 1600×2050 con 2 hojas 39,54 kg, con 25 tablillas por hoja. Una base v2: 37
renglones corregidos y 8 agregados, las tres tablas iguales a las de una base nueva
y el resto de las dos líneas sin tocar; una segunda pasada no cambia nada. Con
ediciones: una cantidad que choca con la corrección queda y se informa, un largo
que la corrección no cambia queda sin aviso, un renglón borrado no vuelve y una
tabla rehecha a mano no se toca. Copias de las dos bases de trabajo, de la versión
1 a la 3: 63 + 37 renglones, 8 agregados, ninguno editado, 32 opciones.
`tools.prueba_rapida`: TODO OK con el mismo TOTAL ($ 2.780.975,62).

Quedan afuera, anotados: **AC-POST** (ventana postigón, pág. 090) tiene el mismo
error —corta el zócalo de 1 hoja y el de 2 a la vez, carga 2 tablillas que el
catálogo no da y le faltan el MT-2695 de 2 hojas y los terminales—; y **AC-PREB1
y AC-PREB2** no tienen las jambas del contramarco H+27 (págs. 073 y 078): con la
opción tildada cortan sólo el dintel. Van en otra versión, con estos criterios.

---

### Mosquitero de las corredizas MDT: catálogo versión 4

Las corredizas de las dos líneas cortaban **siempre** el mosquitero que trae su
tabla de corte, y el tilde «Incluye mosquitero» sumaba encima `mosquitero_m2`.
Medido el 14/09/2026 sobre la versión 2: una AC-COR2 de 1500×1100 cortaba 3
renglones de mosquitero (2,52 kg) con y sin tilde, y tildada sumaba además
$ 14.850; una CL-COR2, 1 renglón (0,44 kg) y lo mismo. Doble cobro, en 14
corredizas.

Y un efecto que no se veía: esos renglones estaban cargados como `HOJA_*` y
`MARCO_*`, y `medidas_de_hoja()` toma el `HOJA_HORIZONTAL` más largo como ancho de
hoja. El zócalo del mosquitero es más largo que el de la hoja, así que en cinco
tipologías el vidrio salía del mosquitero (ventana de 1500×1100, puerta de
1800×2050):

| Tipología | Vidrio sacado del mosquitero | Vidrio de la hoja |
|---|---|---|
| AC-COR2 | 683×961 ×2 | 665×961 ×2 |
| AC-COR4 | 320×961 ×4 | 302×961 ×4 |
| CL-COR2 | 646×977 ×2 | 595×977 ×2 |
| CL-PCOR2 | 796×1924 ×2 | 740×1924 ×2 |
| CL-DUO3 | 1440×965 ×3 | 1440×1040 ×3 |

CL-DUO3 queda con el alto de la abertura porque su tabla no tiene cargados los
parantes de hoja; antes lo tapaba el mosquitero. No es de este cambio.

Decidido con Federico:

- Cuentan como mosquitero la hoja, el travesaño y el tope: MT-0255, MT-0256 y
  MT-0228 en Actual; MT-0905, MT-1110, MT-0005 y MT-1203 en Clásica. Sólo en
  corredizas: CL-PMOSQ es una puerta mosquitero, ahí el mosquitero es la abertura.
- Las piezas pasan a una función propia, `MOSQUITERO`.
- La casilla arranca destildada, como la de premarco: una abertura guardada sin
  tilde deja de cortarlo al recalcular.
- Lo que el despiece no trae —la tela— se cobra por m² con un parámetro nuevo que
  arranca en $ 0.
- Las guías de cortina y la tapa cinta van en un paso aparte (ver al final).

#### `core/catalogo_mdt.py` — catálogo versión 4

```python
VERSION_CATALOGO = 4
PERFILES_MOSQUITERO = {"Actual": (...), "Clásica": (...)}
FUNCION_MOSQUITERO = "MOSQUITERO"
OPCIONES_CORREDIZA = [...]         # MOSQUITERO: bool, arranca en 0, vinculada
CLAVES_V2 = ("PREMARCO", "CONTRAMARCO")                 # las que declaran la v2 y la v3
def opcion_de_renglon(linea, tipologia, perfil, funcion) -> str               # + tipologia
def formulas_de_fabrica(linea, tipologia, perfil, funcion, formula, cantidad) # + tipologia
def funcion_de_fabrica(linea, tipologia, perfil, funcion) -> str
def _actualizar_a_v4(db) -> dict
ACTUALIZACIONES = {2: _actualizar_a_v2, 3: _actualizar_a_v3, 4: _actualizar_a_v4}
```

Una tercera regla, y no una lista a mano: renglón de una **corrediza** con un
**perfil de mosquitero de su línea** → largo y cantidad condicionados, y función
`MOSQUITERO`. Son 33 renglones, 27 activos, en 16 corredizas: las 14 que lo
cortaban, más CL-COR4 y CL-CORPR, que lo tienen sólo en cantidad 0.

    MT-0255   HOJA_HORIZONTAL   (A/2)-7   x 2
      ->      MOSQUITERO        si(MOSQUITERO, (A/2)-7, 0)   si(MOSQUITERO, 2, 0)

MOSQUITERO se declara en esas 16 tipologías, cada una en su línea: hasta ahora
`_declarar_opciones` sólo declaraba en Actual. `_actualizar_a_v4()` sigue el
contrato de los pasos anteriores; un renglón se reconoce por tipología, línea,
perfil y orden, sin la función, que es una de las columnas que cambian:

| Lo que hizo el usuario | Qué pasa |
|---|---|
| nada | largo, cantidad y función pasan a la versión 4 |
| corrigió un largo | su largo queda y se informa; cantidad y función se actualizan |
| le cambió la función | queda la suya y se informa; largo y cantidad se condicionan |
| le puso cantidad a una alternativa | su cantidad queda, sin aviso (la v4 no cambia esa columna), y el largo condicionado la gobierna |
| borró el renglón | no se recrea |
| declaró MOSQUITERO a mano | queda la suya |
| tenía opciones genéricas en esa tipología | se copian a la línea antes de declarar |

#### La casilla «Incluye mosquitero» manda — variables, cálculo, esquema e interfaz

```python
# core/variables.py
VINCULADAS = {"PREMARCO": "incluye_premarco", "MOSQUITERO": "incluye_mosquitero"}

# core/despiece.py
FUNCIONES_CONOCIDAS                    # + "MOSQUITERO", que no cuenta para AH ni HH

# core/calculo.py
FUNCION_MOSQUITERO = "MOSQUITERO"                        # nuevo
def costo_mosquitero(db, item, despiece=None)            # + despiece
mosquitero=costo_mosquitero(db, item, despiece)          # en calcular_item()

# core/database.py — esquema v8 (y core/seed_data.py para las bases nuevas)
ESQUEMA_VERSION = 8
MIGRACIONES[8]       # INSERT OR IGNORE de mosquitero_tela_m2 = 0, grupo Opcionales

# ui/vista_cotizacion.py, en DialogoItem._precargar()
if "MOSQUITERO" in contexto:
    self.chk_mosquitero.set(bool(contexto["MOSQUITERO"]))
```

- **`costo_mosquitero()`**: si el despiece trae piezas `MOSQUITERO`, el aluminio
  ya va por peso y se suma sólo la tela, `mosquitero_tela_m2` por m²; si no, el
  mosquitero entero, `mosquitero_m2`, como siempre. Con `despiece=None` se
  comporta como producción, y una línea que no corta el mosquitero —las de muestra
  de la regresión, o AC-COR3 y AC-DESP, que no lo traen en su tabla— lo sigue
  cobrando por m²: `prueba_rapida` da el mismo TOTAL.
- **El parámetro** entra por migración de esquema, que es como entran los
  parámetros nuevos (`INSERT OR IGNORE`): uno que el usuario ya tuviera no se pisa.
- **La casilla**: MOSQUITERO no aparece en el bloque de opciones, y una abertura
  guardada con MOSQUITERO elegido aparte abre tildada; guardada de nuevo, queda
  expresada con la casilla. Una corrediza de Clásica, cuya única opción es la
  vinculada, no muestra un bloque vacío.
- La ayuda de «Función» en Materiales nombra MOSQUITERO, y el manual
  (`tools/generar_manual.py`) explica la casilla, la opción vinculada y la tela.
  **El PDF del manual no se regeneró.**

**Impacto en lo guardado.** PRES-0001 de la portable (copia) tiene dos AC-COR2 sin
tilde: recalculado baja de $ 2.472.040,68 a **$ 2.252.963,25** (−$ 219.077,43),
porque cada una deja de cortar 2,9 y 2,7 kg de mosquitero y el vidrio queda 18 mm
más angosto. Tildadas, salen $ 3.421 menos que hoy sin tilde, y ya no suman el m².
El PDF que se reimprime desde el snapshot no cambia.

**Verificado sobre bases temporales y copias**, con las dos bases reales sin
cambios (mismo hash antes y después):

- Base nueva: 33 renglones `MOSQUITERO` (27 activos) en las 16 corredizas, ningún
  perfil de mosquitero de corrediza con otra función, CL-PMOSQ intacta, 16
  declaraciones y 48 opciones, y todas las fórmulas válidas.
- Contra la línea de base de la versión 2 (27 tipologías × 3 medidas × con y sin
  premarco y contramarco × con y sin tilde: 324 casos): con tilde, las mismas
  piezas con función `MOSQUITERO`; sin tilde, las mismas sin el mosquitero.
  Vidrio, felpa y costos cambian sólo donde corresponde, y no aparece ningún aviso
  nuevo.
- Con la tela a $ 5.000: una AC-COR2 de 1500×1100 tildada suma $ 8.250; AC-COR3,
  AC-DESP y CL-CORPR, que no cortan mosquitero, $ 14.850.
- Una base v3 pasa a la 4 con 33 renglones y 16 opciones, queda igual a una base
  nueva y una segunda pasada no cambia nada. Seis ediciones del usuario,
  respetadas; un parámetro de tela que ya existía, sin pisar; una base v2 pasa por
  la 3 y la 4 en un arranque.
- Copias de las dos bases de trabajo, de la versión 1 a la 4: 63 + 37 + 33
  renglones, 8 agregados, ninguno editado, 48 opciones, y fórmulas y opciones
  idénticas a las de una base nueva.
- El `DialogoItem` real, abierto y cerrado desde un script sobre la copia de la
  portable: la casilla abre según lo guardado, AC-COR2 muestra sólo «Lleva
  contramarco» y la vista previa suma la tela sólo si tiene precio.
- `tools.prueba_rapida`: TODO OK con el mismo TOTAL ($ 2.780.975,62).

Quedan afuera, anotados:

- **Guías de cortina y tapa cinta.** MT-0243 y MT-0920 (guías) y MT-0921 (tapa
  cinta) se cortan siempre en 10 tipologías. No hay doble cobro, porque no existe
  casilla ni parámetro de cortina. Van a ir como opción «Lleva cortina de
  enrollar», destildada y visible, en otra versión, después de revisar esos
  renglones contra el catálogo: en Actual la guía figura sólo para 4 hojas (págs.
  097 y 102) y en Clásica es «(*) ajustar según diseño», con tapa cinta y soporte
  (pág. 068).
- **Corredizas cargadas mezclando variantes**, el mismo error que la versión 3
  corrigió en otras tres tablas: AC-COR2 corta a la vez parantes de vidrio simple y
  de DVH, CL-COR2 mezcla marco liviano, marco de tres guías y vidrio repartido, y
  CL-PCOR3 está incompleta. AC-PCOR2 y AC-PCOR4 cargan los travesaños de hoja
  MT-0239 y MT-0253 como `HOJA_HORIZONTAL` con H-79, como figura en la pág. 102: el
  vidrio sale de 1911 mm de ancho en una puerta de 1800.
- La base de `cotizador_beta/datos` pasa sola de la versión 1 a la 4 la próxima
  vez que se abra el beta desde fuentes, con los respaldos
  `cotizador_previo_v8_*.db` y `cotizador_previo_catalogo_v4_*.db`. La de la
  portable, recién con un portable nuevo, que no se compiló.

---

## Todavía NO está hecho

**Fase 1 cerrada.** 1.1 y 1.3 están completos, de la base a la interfaz.

Lo que queda anotado, menor:

De 1.1:

- ~~El tipo `accesorio` para las variables.~~ **Hecho** (esquema v7). Faltan
  `perfil` y `vidrio`, que son el mismo mecanismo aplicado a los otros dos
  catálogos.
- Las variables no viajan al PDF ni a la orden de trabajo como bloque propio:
  aparecen en la descripción del ítem a través de la columna Opcionales.

De 1.3:

- Los avisos no viajan al PDF ni a la orden de trabajo como objetos: ahí siguen
  yendo como texto, que es lo que esas salidas necesitan.
- `ir_a()` deja la pestaña y la fila seleccionadas, pero no abre el editor.
