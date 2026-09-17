# Parametrizar la línea Módena (Aluar) — guía de referencia

Fuente: catálogo oficial **Aluar División Elaborados — MODENA, sección 06-01 "ventana y
puerta corrediza"** (abril 2001) y la planilla **Módena A-45**. Los pesos son los del
listado de perfiles, sección 02.

---

## 1. La lógica: qué es una "fórmula de despiece"

El programa no sabe nada de aberturas. Sabe resolver una tabla como esta:

| Perfil | Función | Fórmula del largo | Cantidad |
|---|---|---|---|
| 6200 | MARCO_HORIZONTAL | `A - 42` | `2` |
| 6201 | MARCO_VERTICAL | `H` | `2` |

Cuando cotizás una ventana de 1500 × 1100, reemplaza `A = 1500`, `H = 1100`, `N = 2`
y evalúa cada renglón:

```
6200 → 1500 - 42 = 1458 mm × 2 piezas
6201 → 1100        = 1100 mm × 2 piezas
```

Después multiplica cada largo por el **peso nominal kg/m** del perfil y suma. Eso es el
peso del despiece; por el precio del kilo sale el costo del aluminio.

**El "descuento" que pregunta tu cliente es literalmente el número que va restando en la
fórmula.** No hay un campo aparte llamado "descuentos": el `-42` de `A - 42` *es* el
descuento del umbral. Está incorporado en la fórmula de cada perfil, que es lo correcto,
porque cada perfil tiene su propio descuento.

### Variables disponibles

| Variable | Significado |
|---|---|
| `A` | ancho total del marco (mm) |
| `H` | altura total del marco (mm) |
| `N` | cantidad de hojas |
| `AH`, `HH` | ancho / alto de hoja — **sólo en fórmulas de vidrio** |
| `PERIM` | `2*(A+H)` |
| `M2` | `A*H/1000000` |

Funciones: `min`, `max`, `abs`, `redondear`, `techo`, `piso`, `raiz`, `si(cond, a, b)`.

### El encadenamiento AH / HH (esto es lo que casi nadie entiende)

`AH` y `HH` **no se cargan**: los deduce el motor. Toma el largo **más grande** de las
piezas marcadas como `HOJA_HORIZONTAL` y lo llama `AH`; el más grande de las
`HOJA_VERTICAL` y lo llama `HH`. Esos dos valores son los que entran a la fórmula del
vidrio.

```
6204 zócalo/cabezal  HOJA_HORIZONTAL  A/2 - 24   →  AH = A/2 - 24
6203 parante lateral HOJA_VERTICAL    H - 79     →  HH = H - 79
                                                     ↓
                                    vidrio:  ancho = AH + 15
                                             alto  = HH - 32
```

Consecuencia práctica: **si marcás mal la función de un perfil, el vidrio sale mal.**
Es el error más común. La función no es decorativa, alimenta el cálculo del vidrio.

---

## 2. Perfiles Módena — corrediza (cargar en Materiales → Perfiles)

Elegí primero la línea **Módena** en el combo de arriba, y después "+ Nuevo" por cada uno.
El peso sale del catálogo, sección 02.

### Marco y premarco

| Código | Descripción | kg/m |
|---|---|---|
| 6200 | Umbral y dintel marco ventana y puerta corrediza | 1,266 |
| 6201 | Jambas de marco ventana y puerta corrediza | 0,675 |
| 6205 | Premarco | 0,397 |
| 6206 | Tapa premarco | 0,181 |
| 6240 | Umbral y dintel marco de 3 guías | 1,823 |
| 6241 | Jambas marco de 3 guías | 0,975 |

### Hoja — vidrio simple

| Código | Descripción | kg/m |
|---|---|---|
| 6203 | Parante lateral hoja vidrio simple | 0,664 |
| 6204 | Zócalo y cabezal de hoja vidrio simple | 0,705 |
| 6207 | Parante central hoja vidrio simple | 0,613 |
| 6208 | Parante central con tirador | 0,813 |
| 6209 | Zócalo alto hoja vidrio simple puerta corrediza | 1,258 |
| 6239 | Travesaño de hoja vidrio simple puerta corrediza | 0,705 |

### Hoja — DVH

| Código | Descripción | kg/m |
|---|---|---|
| 6248 | Parante lateral de hoja para DVH | 0,635 |
| 6249 | Zócalo y cabezal de hoja para DVH | 0,675 |
| 6250 | Parante central de hoja para DVH | 0,583 |
| 6251 | Parante central con tirador para DVH | 0,783 |
| 6252 | Zócalo alto de hoja para DVH puerta corrediza | 1,215 |
| 6253 | Travesaño de hoja para DVH puerta corrediza | 0,689 |

### Complementos

| Código | Descripción | kg/m |
|---|---|---|
| 6228 | Tope mosquitero | 0,186 |
| 6243 | Guía de cortina común | 0,548 |
| 6244 | Guía de cortina barrio | 0,913 |
| 6245 | Tapa cinta | 0,678 |
| 6246 | Encuentro central de 4 hojas | 0,291 |
| 6255 | Bastidor mosquitero | 0,424 |
| 6256 | Travesaño mosquitero | 0,508 |
| 6267 | Marco de vidrio repartido corrediza | 0,383 |
| 6268 | Travesaño de vidrio repartido corrediza | 0,429 |

---

## 3. Fórmulas de corte — VC, ventana corrediza 2 hojas, vidrio simple

Tabla oficial Aluar 06-01. Cargar en **Materiales → Fórmulas de despiece**, con
Tipología = `COR2` y Línea = `Módena`.

| # | Perfil | Función | Fórmula del largo | Cantidad | Corte |
|---|---|---|---|---|---|
| 1 | 6200 | MARCO_HORIZONTAL | `A - 42` | `2` | 90-90 |
| 2 | 6201 | MARCO_VERTICAL | `H` | `2` | 90-90 |
| 3 | 6203 | HOJA_VERTICAL | `H - 79` | `2` | 90-90 |
| 4 | 6207 | HOJA_VERTICAL | `H - 79` | `1` | 90-90 |
| 5 | 6208 | HOJA_VERTICAL | `H - 79` | `1` | 90-90 |
| 6 | 6204 | HOJA_HORIZONTAL | `A / 2 - 24` | `4` | 90-90 |

Premarco (opcional, agregar como función `PREMARCO`):

| Perfil | Fórmula | Cantidad | Corte |
|---|---|---|---|
| 6205 | `H + 36` | `2` | 45-45 |
| 6205 | `A + 36` | `2` | 45-45 |
| 6206 | `H + 53` | `2` | 45-45 |
| 6206 | `A + 53` | `2` | 45-45 |

Mosquitero (opcional, función `OTRO`):

| Perfil | Fórmula | Cantidad | Corte |
|---|---|---|---|
| 6255 | `A / 2 - 7` | `2` | 45-45 |
| 6255 | `H - 88` | `2` | 45-45 |
| 6256 | `A / 2 - 70` | `1` | 90-90 |

### Los mismos cortes en DVH

Idénticas fórmulas, sólo cambia el código de perfil:

| Vidrio simple | DVH | Fórmula |
|---|---|---|
| 6203 | 6248 | `H - 79` |
| 6204 | 6249 | `A / 2 - 24` |
| 6207 | 6250 | `H - 79` |
| 6208 | 6251 | `H - 79` |

El marco (6200 / 6201) **no cambia** entre vidrio simple y DVH.

### Puerta corrediza (PC)

Igual que la ventana, pero el zócalo inferior es el alto y suma un travesaño:

| Perfil | Función | Fórmula | Cantidad |
|---|---|---|---|
| 6204 (cabezal solamente) | HOJA_HORIZONTAL | `A / 2 - 24` | `2` |
| 6209 zócalo alto | HOJA_HORIZONTAL | `A / 2 - 24` | `2` |
| 6239 travesaño | OTRO | `A / 2 - 67` | `2` |

En DVH: 6252 (zócalo alto) y 6253 (travesaño).

### 3 hojas (VPC3H) — ojo acá

**No sirve generalizar con `A/N`.** El marco de 3 guías es otro perfil y los descuentos
de las hojas laterales y la central son distintos:

| Perfil | Fórmula | Cantidad |
|---|---|---|
| 6241 jambas marco 3 guías | `H` | `2` |
| 6240 umbral y dintel 3 guías | `A - 42` | `2` |
| 6204 zócalo/cabezal laterales | `A / 3 - 7` | `4` |
| 6204 zócalo/cabezal central | `A / 3 + 1` | `2` |
| 6209 zócalo alto laterales | `A / 3 - 7` | `2` |
| 6209 zócalo alto central | `A / 3 + 1` | `1` |

Fijate que la hoja central lleva `+1` y las laterales `-7`. Por eso **cada cantidad de
hojas va como tipología separada** (`COR2`, `COR3`, `COR4`), nunca como una fórmula
única con `N`.

---

## 4. Fórmula del vidrio

Botón **"Fórmulas de vidrio…"** dentro de la pestaña de fórmulas.

```
ancho    = AH + 15
alto     = HH - 32
cantidad = N
```

**Estos dos números hay que calibrarlos.** Salen de medir el dibujo: la cara del
zócalo/cabezal es de 23,5 mm y el engargolado entra unos 7,5 mm por lado. El catálogo
dice que *el hueco para vidrio simple es de 11 mm y para DVH de 25 mm*, pero el
engargolado real depende del burlete que uses (B29 = 2 mm, B30 = 3 mm, B31 = 4 mm de
cuña).

**Método seguro:** agarrá una ventana Módena que ya hayas fabricado, medí el vidrio real,
y despejá la constante:

```
constante_ancho = vidrio_ancho_real - (A/2 - 24)
constante_alto  = vidrio_alto_real  - (H - 79)
```

Ese par de números te sirve para toda la línea. Es 5 minutos de trabajo y te deja el
vidrio exacto para siempre.

---

## 5. Módena A-45 (corte a 45°) — es otra línea

La planilla A-45 usa perfiles de la serie 99xxx, que **no** están en el catálogo Módena
clásico. Si tu cliente trabaja con esta variante, hay que cargarla como una línea aparte:

| Perfil | Descripción | Fórmula | Cantidad | Corte |
|---|---|---|---|---|
| 99306 | Umbral y dintel marco | `A` | `2` | 45-45 |
| 99306 | Jamba marco | `H` | `2` | 45-45 |
| 99307 | Suplemento parante central | `H - 80` | `2` | 90-90 |
| 99308 | Zócalo y cabezal de hoja (VS) | `A / 2 - 10` | `4` | 45-45 |
| 99308 | Parante lateral y central de hoja (VS) | `H - 80` | `4` | 45-45 |
| 99309 | Zócalo y cabezal de hoja (DVH) | `A / 2 - 10` | `4` | 45-45 |
| 99309 | Parante lateral y central de hoja (DVH) | `H - 80` | `4` | 45-45 |

Diferencia clave con el Módena clásico: al ser **corte a 45°**, el marco se corta a la
medida exterior completa (`A` y `H`, sin descuento), porque las inglete se encuentran en
la esquina. En el Módena a 90° el umbral lleva `A - 42` porque entra *entre* las jambas.

> La planilla original lista "umbral y dintel = H" y "jamba = A", que está invertido
> respecto de la convención (`A` = ancho, `H` = altura). Es un error de la tabla o del
> orden de columnas. Verificalo contra un corte real antes de darlo por bueno.

Accesorios A-45: escuadra marco E83/8 o E83/10, escuadra hoja E97, escuadra alineación
E98, felpa 7×5, burlete hoja B29/30/31, ruedas R48/R49, cruce de hoja T126, tope bloqueo
T127, tapón hermeticidad T129, tapón desagüe marco T130, tapón desagüe T131, tapa
tornillo T90.

---

## 6. Orden de carga (importante para el video)

El campo **Perfil** de la pestaña de fórmulas es un **desplegable que se llena con los
perfiles de esa línea**. Si el 6200 no está cargado en Perfiles, no aparece en la lista.

Por eso el orden es obligatorio:

1. **Materiales → Líneas y precios** → línea Módena, precio por kilo y color.
2. **Materiales → Perfiles** → elegir Módena, cargar 6200, 6201, 6203, 6204, 6207, 6208
   con su kg/m.
3. **Materiales → Tipologías** → confirmar que existe `COR2`.
4. **Materiales → Fórmulas de despiece** → Tipología `COR2` + Línea Módena → cargar los
   6 renglones.
5. Botón **"Probar despiece…"** → 1500 × 1100, 2 hojas.
6. Botón **"Fórmulas de vidrio…"** → cargar ancho/alto.
7. Botón **"Copiar a otra línea…"** → duplicar a Módena DVH y sólo cambiar los códigos.

---

## 7. Verificación con números

Ventana corrediza 2 hojas, **A = 1500, H = 1100**:

| Perfil | Fórmula | Largo | Piezas | Metros | kg/m | Peso |
|---|---|---|---|---|---|---|
| 6200 | `A - 42` | 1458 | 2 | 2,916 | 1,266 | 3,692 |
| 6201 | `H` | 1100 | 2 | 2,200 | 0,675 | 1,485 |
| 6203 | `H - 79` | 1021 | 2 | 2,042 | 0,664 | 1,356 |
| 6207 | `H - 79` | 1021 | 1 | 1,021 | 0,613 | 0,626 |
| 6208 | `H - 79` | 1021 | 1 | 1,021 | 0,813 | 0,830 |
| 6204 | `A / 2 - 24` | 726 | 4 | 2,904 | 0,705 | 2,047 |
| | | | | **12,104 m** | | **10,036 kg** |

Con 5 % de desperdicio → 10,54 kg. A $12.300/kg → **$129.600 de aluminio**.

Vidrio: `AH = 726`, `HH = 1021` → 741 × 989 mm × 2 paños = 1,466 m².

Si al apretar "Probar despiece…" te da esto, la línea quedó bien cargada.
