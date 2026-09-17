# PDF a Markdown (MarkItDown)

Entorno listo para convertir PDFs a archivos `.md` usando
[MarkItDown](https://github.com/microsoft/markitdown) de Microsoft.

## Estructura

```
pdf_a_markdown/
├── .venv/                 entorno virtual con markitdown ya instalado
├── entrada/               <-- copia aca los PDFs a convertir
├── salida/                <-- aca aparecen los .md
├── convertir.py           el script de conversion
├── Convertir PDFs.bat     lanzador (doble clic o arrastrar y soltar)
├── requirements.txt       dependencias
└── README.md              este archivo
```

## Uso

### 1) Doble clic (lo mas simple)

1. Copiá tus PDFs dentro de la carpeta `entrada`.
2. Doble clic en **`Convertir PDFs.bat`**.
3. Los `.md` quedan en `salida`, con el mismo nombre del PDF.

### 2) Arrastrar y soltar

Arrastrá uno o varios PDFs (o una carpeta entera) **sobre** `Convertir PDFs.bat`.
No hace falta que estén en `entrada`. Los `.md` igual salen en `salida`.

### 3) Linea de comandos

```bash
cd "C:\Users\Fede- Para grabar\Documents\Sesion Local - Claude Code\pdf_a_markdown"
.venv\Scripts\python.exe convertir.py
```

Con rutas explícitas:

```bash
.venv\Scripts\python.exe convertir.py "C:\ruta\documento.pdf" "C:\otra\carpeta"
```

## Opciones

| Opción | Qué hace |
|---|---|
| `--forzar` | Reconvierte aunque el `.md` ya exista (por defecto lo saltea). |
| `--salida RUTA` | Manda los `.md` a otra carpeta en vez de `salida`. |
| `--junto` | Deja cada `.md` al lado de su PDF original. |
| `--recursivo` | Al pasar una carpeta, también busca PDFs en las subcarpetas. |

Ejemplo combinado:

```bash
.venv\Scripts\python.exe convertir.py "C:\Manuales" --recursivo --junto --forzar
```

## Qué esperar del resultado

- **PDFs con texto real** (exportados desde Word, InDesign, etc.): funciona bien.
  Saca el texto, respeta el orden de lectura y arma tablas cuando puede.
- **PDFs escaneados** (una foto de una hoja): MarkItDown **no hace OCR**, así que
  el `.md` va a salir vacío o casi vacío. Para esos hace falta OCR aparte
  (Tesseract, o la opción de OCR de Acrobat antes de convertir).
- PDFs con muchas columnas o diagramas pueden quedar con el texto mezclado.
  Suele convenir revisar el `.md` a mano después.

## Otros formatos

El mismo script acepta cualquier archivo suelto que MarkItDown soporte, no solo PDF:
`.docx`, `.pptx`, `.xlsx`, `.html`, `.csv`, `.json`, `.xml`, `.epub`, `.zip`.

```bash
.venv\Scripts\python.exe convertir.py "C:\ruta\presentacion.pptx"
```

(La búsqueda automática dentro de una carpeta sí filtra solo `*.pdf`.)

## Reinstalar el entorno

Si alguna vez se rompe el `.venv`:

```bash
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```
