# Cotizador de Aberturas de Aluminio — v3.0

Aplicación de escritorio para **cotización, despiece y cálculo** de aberturas de aluminio.
Interfaz moderna con CustomTkinter, dos temas de trabajo, licenciamiento por PC,
exportación a PDF profesional y actualizaciones que no tocan los datos del cliente.

---

## 1. Instalación y ejecución

```bash
pip install -r requirements.txt
```

```bash
python main.py
```

En Windows también podés hacer doble clic en **`Cotizador.bat`**.

| Librería | Para qué |
|---|---|
| `customtkinter` | Interfaz gráfica moderna |
| `reportlab` | PDF y esquemas vectoriales |
| `openpyxl` | Importar precios desde Excel (opcional) |

En Linux además: `sudo apt install python3-tk`.

Verificación sin abrir la interfaz:

```bash
python -m tools.prueba_rapida
```

---

## 2. Estructura del proyecto

```
cotizador_aberturas/
├── main.py  VERSION  requirements.txt  Cotizador.bat   ← código
│
├── core/                       Lógica de negocio (sin dependencia de la GUI)
│   ├── formato.py              Formateo estricto de unidades   ← única fuente de verdad
│   ├── rutas.py                Separación código / datos de usuario
│   ├── licencia.py             HWID + verificación RSA de licencias
│   ├── config.py               Preferencias (tema, escala)
│   ├── models.py               Item, Despiece, Presupuesto, Resumen…
│   ├── database.py             Esquema SQLite + MIGRACIONES
│   ├── seed_data.py            Precarga inicial (precios del Excel del usuario)
│   ├── formula_engine.py       Evaluador seguro de fórmulas paramétricas
│   ├── despiece.py             Motor de despiece
│   ├── calculo.py              Costos, márgenes, descuentos, IVA
│   ├── stock.py                Inventario opcional (saldos + libro mayor)
│   ├── ordenes.py              Órdenes de trabajo con despiece congelado
│   └── clave_publica.py        Clave pública de licenciamiento (generada)
│
├── ui/
│   ├── tema.py                 Paletas Claro / Silver + estilo de tablas
│   ├── componentes.py          CampoUnidad, Tabla, Tarjeta, diálogos
│   ├── app.py                  Ventana principal y navegación
│   ├── vista_cotizacion.py     Módulo 2
│   ├── vista_materiales.py     Módulo 1
│   ├── vista_presupuestos.py   Historial y estados
│   ├── vista_empresa.py        Módulo 3
│   ├── vista_ajustes.py        Tema, licencia, respaldos, actualizaciones
│   ├── vista_despiece.py       Detalle de corte
│   ├── vista_ordenes.py        Seguimiento de producción
│   ├── vista_stock.py          Inventario
│   └── licencia_ui.py          Activación y panel de licencia
│
├── reports/                    pdf_generator.py · esquemas.py · orden_trabajo.py
├── tools/                      importar_excel · importar_catalogo · importar_json
│                               exportar_materiales · generar_claves · keygen
│                               actualizar · prueba_rapida
│
├── datos/      ⚠️ NUNCA se sobrescribe   (cotizador.db · licencia.lic · ajustes.json · copias/)
└── salidas/    ⚠️ NUNCA se sobrescribe   (PDF generados)
```

---

## 3. Temas de trabajo

Se cambian desde la barra lateral o desde **Ajustes → Apariencia**, **en caliente**, sin reiniciar.

| | **Modo Claro** | **Modo Silver** |
|---|---|---|
| Fondo | `#EEF1F5` blanco/gris claro | `#2B2D42` slate |
| Superficie | `#FFFFFF` | `#3D405B` |
| Acento | `#1B3A57` azul | `#8D99AE` silver |
| Para qué | Máximo contraste, oficina | Jornadas largas en taller: baja la luminancia sin llegar al negro puro |

Ambas paletas viven en un único archivo de tema donde el índice 0 es Claro y el 1 es Silver;
`set_appearance_mode()` reevalúa esas tuplas en todos los widgets ya creados, por eso el
cambio es instantáneo. Las tablas (`ttk.Treeview`, que no es un widget de CustomTkinter) se
repintan aparte desde `ui/tema.py`.

También se puede ajustar el **tamaño de la interfaz** (90 % a 125 %) para pantallas grandes.

---

## 4. Formateo estricto de unidades

Todo número que se muestra —en pantalla, en las tablas y en el PDF— pasa por
`core/formato.py`. Convención argentina: **miles con punto, decimales con coma**.

| Magnitud | Función | Resultado |
|---|---|---|
| Moneda | `moneda(125400.5)` | `$ 125.400,50` |
| Horas | `horas(8)` · `horas(2.5)` | `8 hrs` · `2,5 hrs` |
| Peso | `kilos(14.2)` | `14,2 Kgs` |
| Peso lineal | `kilos_metro(0.85)` | `0,850 Kg / m` |
| Piezas | `unidades(4)` | `4 uds.` |
| Medidas | `medida(1200, 1500)` | `1200 x 1500 mm` |
| Superficie | `superficie(2.4567)` | `2,46 m²` |
| Porcentaje | `porcentaje(0.21)` | `21 %` |

Las medidas en mm **no llevan separador de miles**: en un plano `1500 mm` se lee mejor
que `1.500 mm`.

**Cada campo de carga muestra su unidad dentro del control**: `$ / Kg` como prefijo,
`mm` · `hrs` · `Kgs` · `uds.` · `%` como sufijo. El operario nunca tiene que adivinar
en qué unidad está cargando.

La lectura inversa tolera lo que el usuario realmente escribe: `$ 125.400,50`, `1.500`,
`2,5 hrs`, `21 %` se interpretan todos correctamente. En particular, **`1.500` se lee como
mil quinientos**, no como 1,5 — un error de tres órdenes de magnitud en un precio.

---

## 5. Licenciamiento por suscripción

### Cómo funciona

Cada equipo tiene un **código HWID** de 16 caracteres (`00C0-5CF4-A01D-964C`) derivado de
identificadores físicos: serial de la placa base, serial del **disco 0**, UUID del sistema y
`MachineGuid` de Windows. Se exigen al menos dos fuentes reales; se descartan los seriales de
relleno (`Default string`, `To be filled by O.E.M.`), porque si no todas las PC con placas
genéricas compartirían HWID.

> Se toma el **disco 0** y no "el primero que aparezca": si no, enchufar un pendrive podría
> cambiar el HWID y romperle la licencia al cliente.

La licencia autoriza **un equipo hasta una fecha**. Renovar es emitir una clave nueva con la
fecha corrida; no hay que desinstalar nada.

### Firma Ed25519, no HMAC

La aplicación lleva sólo la **clave pública**, que verifica pero no firma. La **privada** vive
en `~/.cotizador_emisor/`, fuera de la carpeta del proyecto.

> **Por qué no HMAC.** Con HMAC la misma clave valida y firma, así que tendría que viajar
> dentro del `.exe`. Un ejecutable de PyInstaller se desempaqueta con `pyinstxtractor` en
> minutos: cualquiera podría extraerla y fabricar un *keygen*. Con firma asimétrica eso es
> imposible sin la privada.
>
> **Por qué Ed25519 y no RSA.** La firma ocupa 64 bytes en vez de 256. Eso es lo que permite
> que la licencia entre en una clave de texto pegable por WhatsApp; con RSA serían ~410
> caracteres.
>
> **Límite honesto.** Ningún esquema impide que alguien modifique el programa para saltear la
> verificación. Lo que esto detiene es la fabricación y reventa de licencias.

La implementación de Ed25519 (`core/ed25519.py`, sin dependencias) está verificada contra los
**vectores de prueba oficiales del RFC 8032**.

### Puesta en marcha (una sola vez)

```bash
python -m tools.generar_claves
```

Genera `core/clave_publica.py` (viaja con la app) y `~/.cotizador_emisor/clave_privada.json`
(sólo tu PC). **Guardá una copia de seguridad de la privada**: si la perdés, no podés emitir
ni renovar licencias.

### Emitir y renovar

```bash
python -m tools.keygen
```

Modo interactivo: pegás el código de equipo, ponés los días (30 por defecto) y devuelve una
clave de una línea para mandar por WhatsApp:

```
COTIZ-AIEYWAF3IH2YVZHKXWPWX6UOUSVGYPEURPMUCU6E6CU7YNC3AGJL4BGX…
```

115 caracteres, sólo mayúsculas y dígitos: sin símbolos que WhatsApp mangule ni ambigüedad de
mayúsculas. Al validarla se toleran espacios, saltos de línea y minúsculas.

Si el cliente **renueva antes de vencer**, los días se suman sobre el saldo en lugar de
perderse.

```bash
python -m tools.keygen --hwid 00C0-5CF4-A01D-964C --cliente "Aberturas del Sur" --dias 30
python -m tools.keygen --vencimientos      # a quién hay que cobrarle este mes
python -m tools.keygen --listar            # historial de emisiones
```

### Anti-manipulación de reloj

`core/reloj.py` impide estirar la suscripción atrasando la fecha de Windows:

1. **Anclas locales.** Se guarda la última hora de uso en
   `%APPDATA%/CotizadorAberturas/last_run.dat`, **firmada** con una clave derivada del HWID, y
   se toman además las fechas de modificación de la base de datos y del archivo de licencia.
   La referencia es la mayor de las tres. Borrar `last_run.dat` no alcanza: quedan las otras.
2. **Hora de red.** Se pide el header `Date` a Google o Cloudflare (HEAD, 2 s de timeout). Si
   difiere del sistema en más de una hora, **manda la de red**.
3. **Tolerancia de 12 horas**, para no bloquear por un cambio de huso o de horario de verano.

> Alcance honesto: si el cliente bloquea internet sólo se pierde el chequeo externo, las
> anclas locales siguen activas. Y la clave que firma la marca está dentro del programa, así
> que alguien con conocimiento puede recalcularla. Esto detiene el fraude realista —"atraso la
> fecha de Windows y sigo usando el sistema"—, no a un atacante decidido.

### Qué pasa en cada escenario

| Situación | Resultado |
|---|---|
| Clave correcta en su PC | Abre normalmente |
| La misma clave en otra PC | Rechazada |
| Un carácter cambiado de la clave | Rechazada |
| Clave firmada con claves propias (keygen) | Rechazada |
| Suscripción vencida | Pide renovación al abrir |
| Faltan 7 días o menos | Abre y avisa |
| Reloj atrasado 40 días | Ventana "Revisá la fecha del equipo" |
| `last_run.dat` editado a mano | Se descarta y se usan las otras anclas |

## 6. Compilar el ejecutable comercial

```bash
pip install pyinstaller
```

```bash
python build_exe.py --version 2.1.0
```

Produce `../entregas/CotizadorAberturas_v2.1.0.zip`. El cliente lo descomprime y ejecuta el
`.exe` de adentro — **no necesita Python instalado**.

### Qué verifica el script sobre el binario ya construido

| Chequeo | Por qué |
|---|---|
| `tools/keygen.py` no está en el paquete | Es tu herramienta de emisión |
| Sin referencias a `tools.keygen` ni `cotizador_emisor` | Excluir un módulo que nunca se importa no prueba nada por sí solo |
| **Los bytes de tu clave privada no aparecen en ningún archivo** | Es lo único que realmente hay que proteger |
| El ejecutable arranca y se mantiene abierto | Si faltara un módulo, moriría al iniciar |

La última es la que vale: buscar textos dentro del `.exe` no sirve porque PyInstaller comprime
el código con zlib. Sólo arrancarlo prueba que el paquete está completo.

### onedir vs onefile

Por defecto usa **`--onedir`**. Con `--onefile` PyInstaller descomprime CustomTkinter +
ReportLab a una carpeta temporal **en cada arranque**: 3–6 segundos cada vez que abren el
programa. Onedir arranca en menos de un segundo y se entrega igual de simple, como `.zip`.

```bash
python build_exe.py --onefile            # un solo archivo, arranque lento
python build_exe.py --consola            # deja la consola visible, para depurar
```

### Dónde quedan los datos del cliente

Al detectar que corre empaquetado (`sys.frozen`), la aplicación manda base de datos, respaldos
y PDF a `%LOCALAPPDATA%\CotizadorAberturas`, y la licencia a
`%APPDATA%\CotizadorAberturas`. Un ejecutable instalado en `C:\Program Files` no puede
escribir junto a sí mismo.

Los recursos empaquetados (el archivo `VERSION`) se leen desde `sys._MEIPASS`, que en modo
onedir es `_internal/` y **no** la carpeta del `.exe`.

---

## 7. Actualizaciones sin perder datos

La regla es una sola: **se reemplaza el programa, nunca los datos**.

```
Se reemplaza:  el código (o la carpeta entera del .exe)
Nunca se toca: datos/ · salidas/ · licencia.lic · ajustes.json · instalado.flag
```

### Dos tipos de paquete, uno por cada tipo de instalación

| Instalación | Paquete que sirve | Cómo se arma |
|---|---|---|
| Corre desde los `.py` | **código**: `main.py` + `core/ ui/ reports/ tools/` | `python -m tools.empaquetar --version 2.2.0` |
| Corre desde el `.exe` | **programa**: `CotizadorAberturas.exe` + `_internal/` | `python build_exe.py --version 2.2.0` |

Adentro del `.exe` **no hay archivos `.py`**: el código va compilado en el binario y en
`_internal/`. Copiar `.py` junto al ejecutable no cambia nada — el importador congelado
nunca los mira. Por eso el `.exe` se actualiza con el mismo `.zip` que se le entrega a un
cliente nuevo, y `tools/actualizar.py` rechaza con un mensaje explícito el paquete que no
corresponde en vez de fingir que instaló algo.

### Instalar en la PC del cliente

**Ajustes → Instalar actualización desde archivo .zip**, sin descomprimir nada.

Sobre una instalación de código:

1. Respalda la base y la carpeta de programa en `datos/copias/`.
2. Reemplaza sólo los archivos de código.
3. Conserva `core/clave_publica.py` si el paquete no trajera una.
4. Si algo falla a mitad de camino, **revierte** al respaldo.

Sobre el `.exe`, Windows no deja reemplazar una carpeta con el programa abierto, así que:

1. Descomprime la versión nueva **al lado** de la instalación (`…_nuevo`).
2. Lanza un `.bat` con su ventanita, que espera a que el proceso cierre.
3. Renombra la vieja, pone la nueva en su lugar, borra la vieja y **relanza el programa**.
4. Si el `move` no entra (antivirus, otra ventana abierta), deja todo como estaba y avisa.

Si el programa está en `C:\Program Files` no puede reemplazarse a sí mismo: el chequeo de
escritura corta antes de tocar nada y pide moverlo a una carpeta del usuario.

También por línea de comandos: `python -m tools.actualizar paquete.zip`

> Las versiones **anteriores a la 2.2.0** no saben instalar un paquete de programa: ese
> primer salto se hace a mano, reemplazando la carpeta (los datos están en
> `%LOCALAPPDATA%\CotizadorAberturas`, así que no se pierde nada). Está explicado para el
> cliente en `recursos/entrega/Como actualizar.txt`, que viaja dentro del `.zip`.

### Migraciones de base de datos

`core/database.py` lleva `ESQUEMA_VERSION` y un diccionario `MIGRACIONES`. Al abrir, la app
compara con `PRAGMA user_version` y aplica los pasos que falten, **después de respaldar**.

Reglas para que una actualización nunca pierda datos:

- Sólo `ALTER TABLE ADD COLUMN`, `CREATE TABLE`, `CREATE INDEX`, `UPDATE` e
  `INSERT OR IGNORE` (para sembrar parámetros nuevos sin pisar los del usuario).
- Nunca `DROP TABLE` ni `DROP COLUMN` sobre datos del usuario.
- Toda columna nueva lleva `DEFAULT`, para que las filas viejas queden válidas.

Para agregar una migración en la próxima versión:

```python
ESQUEMA_VERSION = 5

MIGRACIONES = {
    2: [...], 3: [...], 4: [...],
    5: ["ALTER TABLE presupuestos ADD COLUMN vendedor TEXT DEFAULT ''"],
}
```

#### Historial del esquema

| Versión | Qué agregó |
|---|---|
| **v2** | Estado y fechas en los presupuestos |
| **v3** | El listado de perfiles pasa a ser catálogo: `familia`, `imagen`, `notas`, y `extrusora` en las líneas |
| **v4** | Stock, órdenes de trabajo, `nota` en las fórmulas, `imagen` por tipología y `peso_kg_m` en accesorios |

Un cliente que viene de la v2 salta a la v4 en un solo arranque: las migraciones se
aplican en cadena y cada una respalda antes de tocar nada.

### Dónde viven los datos

Por defecto en `<proyecto>/datos` y `<proyecto>/salidas` (modo portable: la app entera se
puede llevar en un pendrive). Si instalás el programa en `C:\Program Files`, creá un
archivo vacío `instalado.flag` junto a `main.py`: los datos pasan a
`%LOCALAPPDATA%\CotizadorAberturas` y se migran solos la primera vez. También se puede
forzar con la variable de entorno `COTIZADOR_DATOS`.

---

## 8. Los módulos

### Módulo 1 · Materiales y Costos

| Sub-pestaña | Contenido |
|---|---|
| **Líneas y precios** | Líneas con su modo de costeo, extrusora, colores, `$ / Kg` y `$ / m²` |
| **Perfiles** | Catálogo por línea: familia, peso `Kg / m`, largo de barra, dibujo y notas |
| **Vidrios** | Tipo, espesor, `$ / m²`, plancha base y % de desperdicio |
| **Accesorios** | Ruedas, cierres, felpas, burletes, escuadras en `u`, `jgo`, `ml`, `m2`, `kg` o `kg/m` |
| **Kits** | Kit por línea + tipología, con cantidades **por fórmula** (`2*N`) |
| **Tipologías** | Hojas por defecto, esquema o imagen propia, `hrs` de fabricación por m² |
| **Fórmulas de despiece** | La tabla `Tipologias_Formulas`, con aclaración de texto por renglón |
| **Costos operativos** | Hora-hombre, operarios, logística, premarco, mosquitero, margen, IVA, stock |

#### Accesorios vendidos por peso (`kg/m`)

Un accesorio extruido que el proveedor factura por kilo se carga con unidad **`kg/m`**:
la fórmula del kit da **metros**, el campo *Peso lineal* los convierte en kilos y el
*Precio* es el `$ / kg` de la lista. El despiece muestra el consumo ya en kilos, para que
el renglón cierre como todos los demás (`cantidad × precio = importe`) y el listado de
compras hable en la unidad de la factura.

La unidad manda también sobre el redondeo: `u` y `jgo` suben al entero siguiente (media
rueda no existe); `ml`, `m2`, `kg` y `kg/m` admiten decimales.

#### Duplicar un sistema

**Líneas y precios → Duplicar sistema…** clona una línea entera: colores con sus precios,
perfiles, fórmulas de despiece, fórmulas de vidrio y kits. Sirve para dar de alta la
variante DVH de una línea, o la misma perfilería de otra extrusora, sin recargar cientos de
renglones.

Lo que es global —vidrios, accesorios y tipologías— se comparte, no se duplica. Las
fórmulas genéricas (`linea_id IS NULL`) tampoco se copian: siguen aplicando a la línea
nueva por sí solas.

#### La aclaración de la función `OTRO`

Cada renglón de fórmula puede llevar una **aclaración de texto**, y con la función `OTRO`
es obligatoria: `OTRO` sola no le dice nada al operario que tiene la orden en la mano. En
el despiece, en el PDF y en la orden de trabajo se imprime la aclaración en lugar del
nombre de la función; en las demás funciones aparece entre paréntesis.

#### El catálogo de perfiles

Cada perfil guarda además **familia** (Marcos, Hojas, Contravidrios…), un **dibujo de la
sección** y **notas**. Al elegir un perfil de la lista, la ficha de la derecha muestra el
dibujo con el peso y el largo de barra: el programa sirve de catálogo consultable, no sólo
de tabla de precios.

Las imágenes se copian a `datos/imagenes_perfiles` y en la base queda **sólo el nombre del
archivo**: la base no se infla, el respaldo sigue siendo chico y el dibujo sobrevive aunque
se borre el original.

#### Importar el catálogo de otra extrusora

**Perfiles → Importar catálogo…** lee un `.xlsx` cualquiera y carga los perfiles de la línea
elegida. No exige un formato: busca las columnas por el título (`Código`, `Perfil`, `Kg/m`,
`Peso`, `Largo de barra`…), saltea las filas de encabezado, toma los títulos de sección como
familia y entiende tanto `1,266` como `0.675 kg`, gramos por metro y largos en metros.

Trabaja en dos pasos: primero **analiza y muestra** qué encontró y qué filas descarta (sin
peso, peso absurdo, código repetido), y recién si aceptás escribe. Nunca borra perfiles
existentes: actualiza los que coinciden por código y agrega los nuevos, respetando el dibujo
que ya hubieras cargado a mano.

#### Importar un catálogo completo en JSON

El Excel carga perfiles; el **JSON carga un sistema entero**. Un solo archivo puede traer
líneas con sus colores, perfiles, fórmulas de corte, fórmulas de vidrio y kits, más los
vidrios, accesorios y tipologías globales. El botón **Importar JSON…** está en *Líneas y
precios*, *Vidrios* y *Accesorios* — es el mismo importador, entra por donde te quede a mano.

```json
{
  "catalogo": "Metales del Talar — Sistema Actual",
  "vidrios":    [{"nombre": "DVH 4/12/4", "tipo": "DVH", "precio_m2": 44516.77}],
  "accesorios": [{"codigo": "RUE-STD", "unidad": "u", "precio": 2800}],
  "lineas": [{
    "nombre": "Actual", "extrusora": "Metales del Talar", "modo_costeo": "kg",
    "colores":  [{"color": "Blanco", "precio_kg": 15300}],
    "perfiles": [{"codigo": "MT-0200", "peso_kg_m": 1.266, "largo_barra_mm": 6150,
                  "imagen": "dibujos/MT-0200.jpg"}],
    "formulas": [{"tipologia": "COR2", "perfil": "MT-0200",
                  "funcion": "MARCO_HORIZONTAL", "largo": "A - 42", "cantidad": "2"}],
    "kits":     [{"nombre": "Kit corrediza", "tipologia": "COR2",
                  "items": [{"accesorio": "RUE-STD", "cantidad": "2*N"}]}]
  }]
}
```

Todas las secciones son opcionales: un archivo con sólo `vidrios` o sólo `accesorios` es
válido, y es justamente el caso de **"llegó lista de precios nueva"**, que es lo que más se
repite. Reimportar el mismo archivo es idempotente.

**Funciona con catálogo o sin él.** Si una fórmula nombra un perfil que no está cargado, se
importa igual y el despiece cotiza con el peso de respaldo del propio renglón; el aviso
queda en el informe. Lo mismo con un kit que nombra un accesorio inexistente: se salta ese
ítem y el resto del kit entra.

Las rutas de imagen se resuelven **relativas al propio `.json`**, así el paquete que manda
el extrusor es una carpeta con el archivo y los dibujos al lado. Las imágenes de perfil van
a la ficha del catálogo; las de tipología **reemplazan al esquema vectorial** en el
presupuesto y en la orden de trabajo, que es la forma de representar una abertura compuesta
que el dibujo automático no sabe armar.

También desde la consola, sin abrir la interfaz:

```bash
python -m tools.importar_json catalogo.json            # analiza, no escribe
python -m tools.importar_json catalogo.json --aplicar  # importa
```

```bash
python -m tools.importar_catalogo catalogo.xlsx        # analiza y muestra
```

### Módulo 2 · Cotización

Cliente, ítems con A × H en mm, hojas, cantidad, vidrio, checkboxes de premarco y
mosquitero, bonificación por renglón y observaciones libres por ítem. El diálogo de carga
muestra **el costo en vivo** mientras se completan las medidas.

Mano de obra como `$ valor hora × operarios × hrs`, logística separada en flete y
colocación, descuento global en `%` o `$`, y facturación con o sin IVA.

Los presupuestos tienen **estado** (Borrador · Enviado · Aprobado · Rechazado · Facturado)
para seguimiento comercial.

#### Qué ve el cliente y qué no

El consumo de material —kilos de aluminio y m² de vidrio— **se calcula siempre**: el costeo
en modo `kg` depende de él. Pero es información de taller, y le dice al cliente final
exactamente con qué ir a pedir el mismo trabajo a otro lado. Por eso su visibilidad se
controla desde *Costos operativos*:

| Parámetro | Por defecto | Qué apaga |
|---|---|---|
| `mostrar_consumo_pdf` | `0` (oculto) | La línea "Aluminio: … · Vidrio: …" del PDF |
| `mostrar_consumo_pantalla` | `1` (visible) | Las columnas Peso y Vidrio de la tabla y el resumen de la barra inferior |

El anexo técnico de despiece sigue siendo aparte (`incluir_despiece_pdf`), y también viene
apagado.

#### Materiales a Excel

**Materiales a Excel** genera la planilla de compras del presupuesto, con seis hojas:
*Resumen*, *Perfiles*, *Barras*, *Vidrios*, *Accesorios* y *Cortes*.

La hoja **Barras** consolida todas las aberturas antes de optimizar, no ítem por ítem: si
dos ventanas usan el mismo perfil, el recorte de una sirve para la otra, y contarlas por
separado hace comprar barras de más. La hoja **Cortes** es la que va al taller, agrupada por
abertura y con la aclaración de cada pieza.

```bash
python -m tools.exportar_materiales PRES-0007 -o compras.xlsx
```

### Módulo 3 · Órdenes de trabajo

Desde la cotización, **Emitir OT** crea una orden por cada abertura del presupuesto. Un ítem
con cantidad 3 genera **una** orden de cantidad 3: es el mismo trabajo repetido y el taller
lo corta junto.

Cada orden **congela su despiece** en un `snapshot_json`. Si mañana se corrige una fórmula o
cambia el precio del aluminio, el presupuesto se recalcula pero la hoja que está en la mesa
de corte sigue diciendo lo mismo que cuando se emitió.

El PDF de la OT es deliberadamente distinto del presupuesto: **sin precios**, con el número
de orden grande arriba, medidas de corte, paños de vidrio, accesorios, casilleros para
tildar y un pie de firmas (cortó / armó / controló).

Ciclo de vida: `Pendiente → En fabricación → Terminada → Entregada`, con `Anulada` como
salida en cualquier punto. Numeración propia (`OT-00001`), separada de la comercial: un
presupuesto de seis aberturas genera seis órdenes y mezclarlas dejaría huecos raros en la
numeración de presupuestos.

### Módulo 4 · Inventario

**Opcional**: mientras el parámetro `usar_stock` esté en `0`, el módulo no interviene en
ningún cálculo y la aplicación se comporta igual que antes. El stock **informa, no cotiza**:
ninguna función de inventario puede cambiar un precio ni frenar un presupuesto.

Dos tablas, como en cualquier inventario serio. `stock` guarda el saldo por
(tipo, referencia, depósito) y es un caché; `stock_movimientos` es el libro mayor, y de él
se puede reconstruir todo con **Recalcular saldos**. Nunca se borra un movimiento: deshacer
un consumo es asentar otro de signo contrario.

Cada tipo se lleva en la unidad en la que se compra, no en la que se consume:

| Tipo | Unidad | Por qué |
|---|---|---|
| Perfil | **barras** | Gastar 9,5 m de un perfil no son 9,5 unidades de depósito: son 2 barras. El consumo pasa por el optimizador de corte. |
| Vidrio | **m²** con desperdicio | Es lo que factura la vidriería |
| Accesorio | su propia unidad | `u`, `jgo`, `ml`, `m2`, `kg` |

El material se descuenta **al emitir la orden de trabajo** y vuelve al depósito **al
anularla**. Cambiar de Pendiente a En fabricación no mueve nada: el material ya salió.

Si `stock_permite_negativo` está en `0` y algo no alcanza, no se descuenta nada y la orden
queda emitida con un aviso — media orden descontada es peor que ninguna, y frenar la
producción por el inventario sería peor todavía.

### Módulo 5 · Empresa

Razón social, CUIT, dirección, teléfono, logo, términos y condiciones, observaciones
precargadas y **numeración correlativa** (prefijo + número + dígitos), con el número
editable a mano en cada presupuesto.

---

## 9. El motor de despiece

Cada fila de `Tipologias_Formulas` describe una pieza de corte:

`[Tipologia · Linea · Perfil_Codigo · Funcion · Formula_Largo · Cantidad_Piezas · Peso_Kg_M]`

Variables: `A` (ancho mm) · `H` (alto mm) · `N` (hojas) · `AH` / `HH` (medidas de hoja, para
el vidrio) · `PERIM` · `M2`.
Funciones: `min`, `max`, `abs`, `redondear`, `techo`, `piso`, `raiz`, `si(cond, a, b)`.

Las expresiones se evalúan recorriendo el AST de Python con lista blanca de nodos: **no se
usa `eval()`**, así que una fórmula mal escrita da un mensaje de error y no un agujero de
seguridad.

Precargado (las fórmulas del enunciado):

| Línea | Alto de hoja | Ancho de hoja |
|---|---|---|
| Herrero corrediza | `H - 35` | `(A + 12) / N` |
| Módena corrediza | `H - 48` | `(A + 26) / N` |
| Módena Plus (DVH) | `H - 52` | `(A + 28) / N` |

```
MetrosTotales = Σ (Largo_pieza × Cantidad_piezas) / 1000
PesoTotal     = Σ (Metros_pieza × Peso_Kg_M)
CostoAluminio = PesoTotal × (1 + %desperdicio) × Precio por Kg

Ancho_vidrio  = f(AH)   ·   Alto_vidrio = f(HH)
Superficie    = Ancho_vidrio × Alto_vidrio × Cantidad_paños
CostoVidrio   = Superficie × (1 + %desperdicio) × Precio por m²
```

### Dos modos de costeo del aluminio

- **`kg`** — por el peso del despiece (`Kgs × $ / Kg`). Es el del enunciado y refleja el
  consumo real de material.
- **`m2`** — por m² de abertura (`m² × $ / m²`). Es el criterio de la planilla Excel
  original, útil para comparar o para líneas cuyo despiece todavía no cargaste.

Ambos conviven en el mismo presupuesto, línea por línea.

### Desglose final

```
  Subtotal ítems
- Descuentos por ítem
= Subtotal ítems neto
+ Mano de obra      ($ hora × operarios × hrs)
+ Logística         (flete + colocación)
= Subtotal general
- Descuento global  (% o $)
= Neto
+ IVA
= TOTAL
```

---

## 10. Precarga y relación con la planilla Excel

La base viene sembrada con los datos de **`Cotizador de Aberturas.xlsx`**: líneas y colores
con su `$ / m²`, vidrios con su `$ / m²`, y los costos operativos (mano de obra 15.000 $/m²,
instalación 20.000 $/m², accesorios 12.000 $/hoja, mosquitero 9.000 $/m², premarco
6.000 $/m², margen 30 %, IVA 21 %).

> ⚠️ **Datos a reemplazar antes de usar en producción.**
> La planilla **no tiene** precio por kilo ni peso de perfil, que es lo que necesita el
> despiece. Los `precio_kg` y `peso_kg_m` precargados son **estimaciones** calibradas para
> que una ventana testigo dé un costo equivalente al del método por m² (Módena Blanco ≈
> 13.500 $/Kg). Cargá los valores reales de tu proveedor y del catálogo del extrusor, y
> verificá las deducciones de junquillo contra la tabla del fabricante antes de cortar.

**Herramientas → Importar precios desde Excel** relee la hoja *Precios Base* y actualiza
líneas, colores, vidrios, tipologías y parámetros. Busca los bloques por su título, no por
número de fila, así que sigue funcionando si agregás filas.

---

## 11. El PDF

Encabezado con logo y número · datos del cliente · tabla de ítems con **esquema vectorial**
proporcional a la medida real, descripción técnica, opcionales y observaciones por ítem ·
**observaciones generales y cuadro de totales lado a lado** (así el TOTAL nunca queda
huérfano en la página siguiente) · términos y condiciones · firmas.

**Anexo técnico opcional:** poniendo `incluir_despiece_pdf` en `1` (Materiales → Costos
operativos), agrega el listado de corte ítem por ítem y un **consolidado de materiales para
compras** con perfiles agrupados por largo, m² de vidrio y accesorios totalizados.

---

## 12. Atajos

| Atajo | Acción |
|---|---|
| `Ctrl + N` | Nuevo presupuesto |
| `Ctrl + S` | Guardar |
| `Ctrl + P` | Exportar a PDF |
| Doble clic | Editar el ítem o abrir el presupuesto |

---

## 13. Notas de implementación

- **Ventana adaptativa.** El tamaño se calcula a partir del monitor: en las notebooks de
  1366×768 habituales en el rubro, una ventana fija de 1440×880 dejaría los totales fuera
  de pantalla.
- **Historial con recálculo.** Al reabrir un presupuesto se recalculan los precios con las
  listas vigentes; el cálculo original queda congelado en `snapshot_json` para auditoría.
- **Respaldos automáticos** antes de cada migración, actualización o restauración, con
  rotación de las últimas 10 copias en `datos/copias/`.
- **Optimización de corte.** `core/despiece.optimizar_barras()` implementa *first-fit
  decreasing* sobre barras de 6 m: estima cuántas barras comprar, no reemplaza a un
  optimizador de producción.
- **Todo editable desde la interfaz.** Líneas, perfiles, vidrios, accesorios, kits,
  tipologías, fórmulas y parámetros. No hace falta tocar código para agregar una línea
  nueva o cambiar una deducción.

