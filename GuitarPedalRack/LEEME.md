# Guitar Pedal Rack — está compilado y funcionando

## Para probarlo ahora mismo

Abre la carpeta `App` y haz doble clic en **`Guitar Pedal Rack.exe`**.

No hay que instalar nada. El `.exe` son 4,7 MB y solo depende de DLLs que ya
vienen con Windows — puedes copiar la carpeta `App` a un pendrive y funciona en
otro PC tal cual.

---

## ⚠️ Lo PRIMERO que tienes que hacer: elegir la tarjeta de sonido

Al arrancar coge el dispositivo por defecto de Windows, que en tu equipo es la
**salida HDMI**. Para tocar la guitarra:

1. Pulsa **`Audio...`**
2. En *Output* elige tu interfaz de audio (la que tenga la entrada de guitarra)
3. En *Input* elige esa misma interfaz
4. Baja el *Audio buffer size* todo lo que aguante sin chasquidos

La barra de abajo te muestra en todo momento la latencia real en milisegundos.

> **Cuidado con el acople.** Si eliges los altavoces del portátil como salida y
> el micro como entrada, vas a tener un pitido de realimentación. Usa auriculares
> y sube el volumen poco a poco.

---

## Cómo se usa

| Botón | Qué hace |
|---|---|
| **Buscar plugins...** | Vuelve a escanear en busca de VSTs nuevos |
| **+ Añadir pedal** | Menú agrupado por fabricante; añade el pedal al final de la cadena |
| **- Quitar** | Elimina el pedal seleccionado |
| **Subir / Bajar** | Cambia el orden (una distorsión antes o después del delay suena distinto) |
| **Bypass** | El pedal sigue cargado pero el audio lo esquiva. El LED verde se apaga |
| **Guardar / Cargar preset** | Guarda la cadena entera con todos sus mandos en `App\Presets\*.xml` |
| **Doble clic en un pedal** | Abre la interfaz gráfica de ese plugin |

Ya tienes **429 plugins catalogados**, así que "+ Añadir pedal" funciona desde el
primer arranque sin escanear nada.

---

## Lo que verifiqué, y lo que no

Escribí un programa de test aparte (`RackSelfTest.exe`) que ejercita el motor sin
GUI. Ejecútalo cuando quieras con `selftest.bat`. Comprueba, y pasa:

- Con la cadena vacía, la señal sale igual que entra
- Escanea la carpeta VST3 y encuentra los plugins
- Carga un VST real (CHANNEV) y **el audio lo atraviesa** de verdad, sin silencio ni NaN
- Guardar y recargar un preset conserva el plugin y su ruta
- El bypass deja pasar la señal intacta
- Los 427 items del menú apuntan cada uno a su plugin correcto

**Lo que NO está verificado:** no he escuchado el sonido. Sé que las muestras
salen por el otro lado con valores correctos, pero que suene bien con tu guitarra
enchufada solo lo puedes comprobar tú. Tampoco he probado la app durante horas:
para directo, ensáyala antes en casa.

---

## Limitaciones conocidas (decisiones que tomé, no bugs)

**1. Sin ASIO.** El SDK de ASIO es de Steinberg y hay que descargarlo aceptando
su licencia — es una decisión tuya, no mía. Mientras tanto usa **WASAPI en modo
exclusivo**, que da latencias razonables. Si quieres ASIO:

1. Descarga el ASIO SDK de https://www.steinberg.net/developers/
2. Descomprime, por ejemplo en `C:\SDKs\asiosdk`
3. Ejecuta:

```bash
cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DASIO_SDK_PATH="C:/SDKs/asiosdk"
```

4. Vuelve a ejecutar `build.bat`

**2. Solo VST3, no VST2.** VST2 necesita otro SDK de Steinberg que ya ni se
distribuye. Consecuencia práctica: plugins tuyos que son solo `.dll`
(BassGrinderFree, ABPL2, TSE808) **no aparecen**. Los que tienen versión VST3 sí
(TDR Nova, ValhallaSupermassive, CHANNEV, OTT, BC Free Amp...).

**3. Solo 64 bits.** Los plugins de `C:\Program Files (x86)\Common Files\VST3` son
de 32 bits y no cargan en un host de 64. No es arreglable sin un puente.

**4. Cadena lineal.** `Input → pedal → pedal → ... → Output`. No hay envíos
paralelos ni cadenas laterales todavía.

---

## Si quieres tocar el código

```
GuitarPedalRack/
├── App/                      <- el .exe listo para usar
├── Source/
│   ├── Main.cpp              <- arranque, plantilla, no hace falta tocarlo
│   ├── MainComponent.*       <- ventana, botones, callbacks de audio
│   ├── AudioGraphManager.*   <- el AudioProcessorGraph y la cadena
│   ├── PresetManager.*       <- ValueTree -> XML
│   └── SelfTest.cpp          <- el test, no forma parte de la app
├── CMakeLists.txt            <- configuración de compilación
├── build.bat                 <- doble clic: recompila
└── selftest.bat              <- doble clic: compila y corre los tests
```

Después de editar cualquier `.cpp`, doble clic en `build.bat` y en un minuto
tienes el `.exe` nuevo en `build\GuitarPedalRack_artefacts\Release\`.

**No hace falta el Projucer ni Visual Studio.** Tu PC ya tenía las MSVC Build
Tools, y JUCE está clonado en `..\_toolchain\JUCE`. CMake y Ninja salen de las
propias Build Tools.

---

## Tres cosas del código que conviene entender antes de tocarlo

**Propiedad de la memoria.** `graph.addNode(std::move(instance))` transfiere el
plugin al grafo: el grafo lo destruye. Si además guardas un `unique_ptr` al mismo
objeto en otra clase, se libera dos veces y la app crashea. Por eso
`AudioGraphManager` solo guarda `Node::Ptr`, que es un puntero con conteo de
referencias (como las referencias de Python).

**El hilo de audio.** `getNextAudioBlock()` se ejecuta ~100 veces por segundo con
plazo estricto. Ahí no puedes reservar memoria, abrir archivos, ni tocar la GUI:
un `print` mal puesto se oye como un chasquido. Por eso todo cambio en la cadena
va envuelto en `graph.suspendProcessing(true/false)`.

**Los acentos.** `juce::String` interpreta un `const char*` como ASCII, no como
UTF-8. `setButtonText("Añadir")` sale en pantalla como `AÃ±adir`. Hay que
envolverlo: `juce::CharPointer_UTF8("Añadir")`. Me pasó al compilar esto.
