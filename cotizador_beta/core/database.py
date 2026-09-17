"""
Capa de persistencia (SQLite).

Un único archivo ``datos/cotizador.db`` guarda materiales, fórmulas de despiece,
parámetros, datos de la empresa y el historial de presupuestos.

La primera ejecución crea el esquema y siembra la base con los valores tomados
de la planilla "Cotizador de Aberturas.xlsx" del usuario.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from . import rutas
from .seed_data import sembrar

# Se mantienen los nombres antiguos como alias para no romper imports existentes
RUTA_DATOS = rutas.DATOS
RUTA_SALIDAS = rutas.SALIDAS
RUTA_DB = rutas.RUTA_DB

#: Versión del esquema que espera ESTA versión del código.
#: Al subirla hay que agregar el paso correspondiente en MIGRACIONES.
ESQUEMA_VERSION = 8

#: Pasos de migración: {version_destino: [sentencias SQL]}
#:
#: Reglas para que una actualización nunca pierda datos del cliente:
#:   * Sólo ALTER TABLE ADD COLUMN, CREATE TABLE, CREATE INDEX, UPDATE e
#:     INSERT OR IGNORE (para sembrar parámetros nuevos sin pisar los del usuario).
#:   * Nunca DROP TABLE ni DROP COLUMN sobre datos del usuario.
#:   * Toda columna nueva lleva DEFAULT, para que las filas viejas queden válidas.
#:   * Antes de migrar se hace una copia de seguridad automática.
MIGRACIONES: dict[int, list[str]] = {
    2: [
        "ALTER TABLE presupuestos ADD COLUMN estado TEXT DEFAULT 'Borrador'",
        "ALTER TABLE presupuestos ADD COLUMN creado TEXT DEFAULT ''",
        "ALTER TABLE presupuestos ADD COLUMN actualizado TEXT DEFAULT ''",
        "CREATE INDEX IF NOT EXISTS ix_pres_estado ON presupuestos (estado)",
    ],
    # v3: el listado de perfiles pasa a ser también un catálogo consultable.
    3: [
        "ALTER TABLE perfiles ADD COLUMN familia TEXT DEFAULT ''",
        "ALTER TABLE perfiles ADD COLUMN imagen TEXT DEFAULT ''",
        "ALTER TABLE perfiles ADD COLUMN notas TEXT DEFAULT ''",
        "ALTER TABLE lineas ADD COLUMN extrusora TEXT DEFAULT ''",
    ],
    # v4: stock, órdenes de trabajo, imagen por tipología, accesorios por peso
    # y aclaración de texto en las fórmulas con función OTRO.
    4: [
        # -- fórmulas: qué es ese "OTRO"
        "ALTER TABLE tipologia_formulas ADD COLUMN nota TEXT DEFAULT ''",

        # -- imagen propia de la abertura, para el PDF
        "ALTER TABLE tipologias ADD COLUMN imagen TEXT DEFAULT ''",

        # -- accesorios vendidos por peso: la fórmula da metros y el precio es $/kg
        "ALTER TABLE accesorios ADD COLUMN peso_kg_m REAL DEFAULT 0",

        # -- inventario
        """CREATE TABLE IF NOT EXISTS stock (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo          TEXT NOT NULL,               -- perfil | vidrio | accesorio
            referencia_id INTEGER NOT NULL,            -- id en perfiles/vidrios/accesorios
            deposito      TEXT DEFAULT 'Principal',
            cantidad      REAL DEFAULT 0,
            unidad        TEXT DEFAULT 'u',
            minimo        REAL DEFAULT 0,              -- punto de reposición
            actualizado   TEXT DEFAULT '',
            UNIQUE (tipo, referencia_id, deposito)
        )""",
        """CREATE TABLE IF NOT EXISTS stock_movimientos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha         TEXT NOT NULL,
            tipo          TEXT NOT NULL,
            referencia_id INTEGER NOT NULL,
            deposito      TEXT DEFAULT 'Principal',
            cantidad      REAL NOT NULL,               -- + ingreso · - egreso
            motivo        TEXT DEFAULT 'ajuste',       -- compra|consumo|ajuste|anulacion|inicial
            documento     TEXT DEFAULT '',             -- N° de presupuesto u OT que lo generó
            nota          TEXT DEFAULT ''
        )""",
        "CREATE INDEX IF NOT EXISTS ix_stock_ref ON stock (tipo, referencia_id)",
        "CREATE INDEX IF NOT EXISTS ix_mov_ref ON stock_movimientos (tipo, referencia_id)",
        "CREATE INDEX IF NOT EXISTS ix_mov_doc ON stock_movimientos (documento)",

        # -- órdenes de trabajo: una por abertura presupuestada
        """CREATE TABLE IF NOT EXISTS ordenes_trabajo (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            numero             TEXT UNIQUE NOT NULL,
            presupuesto_id     INTEGER REFERENCES presupuestos(id) ON DELETE SET NULL,
            presupuesto_numero TEXT DEFAULT '',
            item_orden         INTEGER DEFAULT 1,
            descripcion        TEXT DEFAULT '',
            cliente            TEXT DEFAULT '',
            obra               TEXT DEFAULT '',
            cantidad           INTEGER DEFAULT 1,
            fecha              TEXT NOT NULL,
            entrega            TEXT DEFAULT '',
            estado             TEXT DEFAULT 'Pendiente',
            responsable        TEXT DEFAULT '',
            notas              TEXT DEFAULT '',
            snapshot_json      TEXT DEFAULT '{}',      -- despiece congelado
            stock_descontado   INTEGER DEFAULT 0,
            creado             TEXT DEFAULT ''
        )""",
        "CREATE INDEX IF NOT EXISTS ix_ot_presupuesto ON ordenes_trabajo (presupuesto_id)",
        "CREATE INDEX IF NOT EXISTS ix_ot_estado ON ordenes_trabajo (estado)",

        # -- parámetros nuevos (INSERT OR IGNORE: no pisa lo que el usuario ya tenga)
        "INSERT OR IGNORE INTO parametros (clave, valor, descripcion, grupo) VALUES "
        "('mostrar_consumo_pdf', '0', "
        "'Mostrar kilos de aluminio y m² de vidrio en el PDF (1 = sí)', 'Comercial')",
        "INSERT OR IGNORE INTO parametros (clave, valor, descripcion, grupo) VALUES "
        "('mostrar_consumo_pantalla', '1', "
        "'Mostrar consumos en la pantalla de cotización (1 = sí)', 'Comercial')",
        "INSERT OR IGNORE INTO parametros (clave, valor, descripcion, grupo) VALUES "
        "('usar_stock', '0', 'Activar el control de inventario (1 = sí)', 'Stock')",
        "INSERT OR IGNORE INTO parametros (clave, valor, descripcion, grupo) VALUES "
        "('stock_deposito_default', 'Principal', 'Depósito por defecto', 'Stock')",
        "INSERT OR IGNORE INTO parametros (clave, valor, descripcion, grupo) VALUES "
        "('stock_permite_negativo', '1', "
        "'Permitir que el stock quede en negativo al consumir (1 = sí)', 'Stock')",
        "INSERT OR IGNORE INTO parametros (clave, valor, descripcion, grupo) VALUES "
        "('ot_prefijo', 'OT', 'Prefijo de las órdenes de trabajo', 'Producción')",
        "INSERT OR IGNORE INTO parametros (clave, valor, descripcion, grupo) VALUES "
        "('ot_proximo_numero', '1', 'Próximo número de orden de trabajo', 'Producción')",
    ],
    # v5: variables por tipología. Opciones tipadas que entran al contexto del
    # motor de fórmulas junto a A, H y N, para que el despiece pueda ser
    # condicional sin que el usuario escriba una fórmula nueva.
    5: [
        """CREATE TABLE IF NOT EXISTS tipologia_variables (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            tipologia_codigo TEXT NOT NULL,
            linea_id         INTEGER REFERENCES lineas(id) ON DELETE CASCADE,
            -- NULL = la variable vale para la tipología en todas las líneas
            clave            TEXT NOT NULL,        -- el nombre en las fórmulas: PREMARCO
            etiqueta         TEXT NOT NULL,        -- lo que lee el usuario
            tipo             TEXT NOT NULL DEFAULT 'bool',  -- bool | numero | opcion
            opciones         TEXT DEFAULT '',      -- JSON [["Simple",0],["Multipunto",1]]
            valor_default    TEXT DEFAULT '0',
            minimo           REAL DEFAULT 0,       -- sólo tipo 'numero'
            maximo           REAL DEFAULT 0,       -- 0 = sin tope
            ayuda            TEXT DEFAULT '',
            activo           INTEGER DEFAULT 1,
            orden            INTEGER DEFAULT 0
        )""",
        # Los valores elegidos para CADA abertura viajan con el ítem
        "ALTER TABLE presupuesto_items ADD COLUMN variables_json TEXT DEFAULT '{}'",
        "CREATE INDEX IF NOT EXISTS ix_tv_tipologia "
        "ON tipologia_variables (tipologia_codigo, linea_id)",
        # Van DOS índices parciales y no un UNIQUE común: en SQLite dos NULL son
        # distintos entre sí, así que un UNIQUE(tipologia, linea_id, clave)
        # dejaría colar dos variables genéricas con el mismo nombre.
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_tv_unica_generica "
        "ON tipologia_variables (tipologia_codigo, clave) WHERE linea_id IS NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_tv_unica_linea "
        "ON tipologia_variables (tipologia_codigo, linea_id, clave) "
        "WHERE linea_id IS NOT NULL",
    ],
    # v6: tipologías compuestas. Una tipología puede estar formada por otras,
    # cada una ocupando un paño cuya medida sale de una fórmula.
    6: [
        """CREATE TABLE IF NOT EXISTS tipologia_composicion (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            tipologia_codigo TEXT NOT NULL,      -- la compuesta
            linea_id         INTEGER REFERENCES lineas(id) ON DELETE CASCADE,
            orden            INTEGER DEFAULT 0,  -- de arriba abajo o de izq. a der.
            tipologia_hijo   TEXT NOT NULL,      -- la que va en ese paño
            etiqueta         TEXT DEFAULT '',    -- "Corrediza superior"
            formula_ancho    TEXT NOT NULL DEFAULT 'A',
            formula_alto     TEXT NOT NULL DEFAULT 'H',
            formula_hojas    TEXT NOT NULL DEFAULT 'N',
            activo           INTEGER DEFAULT 1
        )""",
        "CREATE INDEX IF NOT EXISTS ix_tc_tipologia "
        "ON tipologia_composicion (tipologia_codigo, linea_id)",
    ],
    # v7: el accesorio de un kit puede elegirse al cargar la abertura.
    # Una corrediza lleva rueda simple o doble según el peso de la hoja, cierre
    # de embutir o multipunto según la prestación. Eran kits distintos para la
    # misma tipología; ahora es una opción del ítem.
    7: [
        "ALTER TABLE kit_items ADD COLUMN variable_clave TEXT DEFAULT ''",
    ],
    # v8: las corredizas MDT cortan el mosquitero con sus perfiles (catálogo MDT
    # versión 4), así que ya no se cobra entero por m². Lo que el despiece no
    # trae —la tela— se cobra con este parámetro, que arranca en $ 0.
    8: [
        "INSERT OR IGNORE INTO parametros (clave, valor, descripcion, grupo) VALUES "
        "('mosquitero_tela_m2', '0', "
        "'Tela de mosquitero por m² ($), si la línea corta sus perfiles', 'Opcionales')",
    ],
}

#: Estados por los que pasa una orden de trabajo en el taller.
ESTADOS_OT = ("Pendiente", "En fabricación", "Terminada", "Entregada", "Anulada")

#: Qué se puede inventariar. La clave es el valor de ``stock.tipo``.
TIPOS_STOCK = ("perfil", "vidrio", "accesorio")

ESTADOS_PRESUPUESTO = ("Borrador", "Enviado", "Aprobado", "Rechazado", "Facturado")


ESQUEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS parametros (
    clave       TEXT PRIMARY KEY,
    valor       TEXT NOT NULL,
    descripcion TEXT DEFAULT '',
    grupo       TEXT DEFAULT 'General'
);

CREATE TABLE IF NOT EXISTS empresa (
    id             INTEGER PRIMARY KEY CHECK (id = 1),
    razon_social   TEXT DEFAULT '',
    cuit           TEXT DEFAULT '',
    direccion      TEXT DEFAULT '',
    telefono       TEXT DEFAULT '',
    email          TEXT DEFAULT '',
    web            TEXT DEFAULT '',
    logo_path      TEXT DEFAULT '',
    terminos       TEXT DEFAULT '',
    validez_dias   INTEGER DEFAULT 15,
    prefijo        TEXT DEFAULT 'PRES',
    proximo_numero INTEGER DEFAULT 1,
    relleno_ceros  INTEGER DEFAULT 4
);

CREATE TABLE IF NOT EXISTS lineas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT UNIQUE NOT NULL,
    descripcion TEXT DEFAULT '',
    modo_costeo TEXT DEFAULT 'kg',          -- 'kg' (despiece) | 'm2' (precio por m2 de abertura)
    extrusora   TEXT DEFAULT '',            -- Aluar, Hydro, Rehau... informativo
    activo      INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS linea_precios (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    linea_id         INTEGER NOT NULL REFERENCES lineas(id) ON DELETE CASCADE,
    color            TEXT NOT NULL,
    precio_kg        REAL DEFAULT 0,
    precio_m2_perfil REAL DEFAULT 0,
    activo           INTEGER DEFAULT 1,
    UNIQUE (linea_id, color)
);

CREATE TABLE IF NOT EXISTS perfiles (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    linea_id       INTEGER REFERENCES lineas(id) ON DELETE CASCADE,
    codigo         TEXT NOT NULL,
    descripcion    TEXT DEFAULT '',
    peso_kg_m      REAL DEFAULT 0,
    largo_barra_mm INTEGER DEFAULT 6000,
    familia        TEXT DEFAULT '',         -- agrupador de catálogo: Marcos, Hojas, Contravidrios...
    imagen         TEXT DEFAULT '',         -- nombre de archivo dentro de datos/imagenes_perfiles
    notas          TEXT DEFAULT '',
    UNIQUE (linea_id, codigo)
);

CREATE TABLE IF NOT EXISTS vidrios (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre            TEXT UNIQUE NOT NULL,
    tipo              TEXT DEFAULT 'Float',
    espesor_mm        REAL DEFAULT 4,
    precio_m2         REAL DEFAULT 0,
    plancha_ancho_mm  INTEGER DEFAULT 3600,
    plancha_alto_mm   INTEGER DEFAULT 2500,
    precio_plancha    REAL DEFAULT 0,
    desperdicio_pct   REAL DEFAULT 0.10,
    activo            INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS accesorios (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo      TEXT UNIQUE NOT NULL,
    descripcion TEXT DEFAULT '',
    unidad      TEXT DEFAULT 'u',           -- u | jgo | ml | m2 | kg | kg/m
    precio      REAL DEFAULT 0,
    -- Sólo para unidad 'kg/m': la fórmula del kit da METROS y el precio es $/kg,
    -- así que el costo sale de metros * peso_kg_m * precio. Es la forma de
    -- cotizar un accesorio extruido que el proveedor vende por peso.
    peso_kg_m   REAL DEFAULT 0,
    activo      INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS kits (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre            TEXT NOT NULL,
    linea_id          INTEGER REFERENCES lineas(id) ON DELETE CASCADE,
    tipologia_codigo  TEXT DEFAULT '',
    descripcion       TEXT DEFAULT '',
    activo            INTEGER DEFAULT 1,
    UNIQUE (linea_id, tipologia_codigo, nombre)
);

CREATE TABLE IF NOT EXISTS kit_items (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    kit_id           INTEGER NOT NULL REFERENCES kits(id) ON DELETE CASCADE,
    accesorio_id     INTEGER NOT NULL REFERENCES accesorios(id) ON DELETE CASCADE,
    cantidad_formula TEXT DEFAULT '1',
    -- Si apunta a una variable de tipo 'accesorio', el accesorio que entra al
    -- kit es el que se elige al cargar la abertura y no el fijo de arriba. Una
    -- corrediza lleva rueda simple o doble según el peso de la hoja: es la
    -- misma tipología con una opción, no dos kits distintos.
    variable_clave   TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tipologias (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo            TEXT UNIQUE NOT NULL,
    nombre            TEXT NOT NULL,
    hojas_default     INTEGER DEFAULT 2,
    admite_mosquitero INTEGER DEFAULT 1,
    admite_premarco   INTEGER DEFAULT 1,
    esquema           TEXT DEFAULT 'corrediza',  -- clave de dibujo para el PDF
    -- Imagen propia de la abertura (archivo dentro de datos/imagenes_perfiles).
    -- Si está cargada, reemplaza al esquema vectorial en el PDF.
    imagen            TEXT DEFAULT '',
    horas_por_m2      REAL DEFAULT 0.85,
    activo            INTEGER DEFAULT 1
);

-- Tabla pedida en el enunciado: Tipologias_Formulas
CREATE TABLE IF NOT EXISTS tipologia_formulas (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    tipologia_codigo TEXT NOT NULL,
    linea_id         INTEGER REFERENCES lineas(id) ON DELETE CASCADE,  -- NULL = vale para todas
    perfil_codigo    TEXT NOT NULL,
    funcion          TEXT NOT NULL,       -- MARCO_HORIZONTAL, MARCO_VERTICAL, HOJA_HORIZONTAL, ...
    formula_largo    TEXT NOT NULL,
    cantidad_piezas  TEXT NOT NULL DEFAULT '1',
    peso_kg_m        REAL DEFAULT 0,
    -- Aclaración libre. Es lo que vuelve legible a la función OTRO, que por sí
    -- sola no dice nada: "refuerzo de parante", "tapajunta superior"...
    nota             TEXT DEFAULT '',
    orden            INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS vidrio_formulas (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    tipologia_codigo TEXT NOT NULL,
    linea_id         INTEGER REFERENCES lineas(id) ON DELETE CASCADE,
    formula_ancho    TEXT NOT NULL DEFAULT 'AH - 60',
    formula_alto     TEXT NOT NULL DEFAULT 'HH - 60',
    formula_cantidad TEXT NOT NULL DEFAULT 'N'
);

CREATE TABLE IF NOT EXISTS presupuestos (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    numero                  TEXT UNIQUE NOT NULL,
    fecha                   TEXT NOT NULL,
    validez_dias            INTEGER DEFAULT 15,
    cliente_razon_social    TEXT DEFAULT '',
    cliente_documento       TEXT DEFAULT '',
    cliente_contacto        TEXT DEFAULT '',
    cliente_localidad       TEXT DEFAULT '',
    cliente_obra            TEXT DEFAULT '',
    cliente_forma_pago      TEXT DEFAULT '',
    mo_valor_hora           REAL DEFAULT 0,
    mo_operarios            INTEGER DEFAULT 1,
    mo_horas                REAL DEFAULT 0,
    mo_automatica           INTEGER DEFAULT 1,
    log_flete_recepcion     REAL DEFAULT 0,
    log_envio_colocacion    REAL DEFAULT 0,
    descuento_global_tipo   TEXT DEFAULT 'porcentaje',
    descuento_global_valor  REAL DEFAULT 0,
    aplica_iva              INTEGER DEFAULT 1,
    iva_pct                 REAL DEFAULT 0.21,
    margen_pct              REAL DEFAULT 0.30,
    observaciones_generales TEXT DEFAULT '',
    total                   REAL DEFAULT 0,
    snapshot_json           TEXT DEFAULT '{}',
    estado                  TEXT DEFAULT 'Borrador',
    creado                  TEXT DEFAULT '',
    actualizado             TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS presupuesto_items (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    presupuesto_id     INTEGER NOT NULL REFERENCES presupuestos(id) ON DELETE CASCADE,
    orden              INTEGER DEFAULT 1,
    tipologia_codigo   TEXT DEFAULT '',
    tipologia_nombre   TEXT DEFAULT '',
    linea_id           INTEGER DEFAULT 0,
    linea_nombre       TEXT DEFAULT '',
    color              TEXT DEFAULT '',
    ancho_mm           REAL DEFAULT 0,
    alto_mm            REAL DEFAULT 0,
    hojas              INTEGER DEFAULT 2,
    cantidad           INTEGER DEFAULT 1,
    vidrio_id          INTEGER DEFAULT 0,
    vidrio_nombre      TEXT DEFAULT '',
    incluye_premarco   INTEGER DEFAULT 0,
    incluye_mosquitero INTEGER DEFAULT 0,
    descuento_pct      REAL DEFAULT 0,
    observaciones      TEXT DEFAULT '',
    precio_unitario    REAL DEFAULT 0,
    neto               REAL DEFAULT 0,
    -- Valores de las variables de la tipología elegidos para ESTA abertura.
    -- Van como JSON y no como tabla aparte porque se leen y se escriben siempre
    -- junto al ítem, nunca por separado.
    variables_json     TEXT DEFAULT '{}'
);

-- ---------------------------------------------------------------------------
-- Variables por tipología (v5)
-- ---------------------------------------------------------------------------
--
-- Declaran las opciones de una tipología. Sus valores entran al contexto del
-- motor de fórmulas junto a A, H y N, así el despiece se vuelve condicional
-- sin que el usuario tenga que escribir una fórmula nueva:
--
--     si(PREMARCO, H + 36, 0)      largo
--     si(PREMARCO, 2, 0)           cantidad
--
-- Una pieza de largo cero ya se descarta, así que "no lleva premarco" no
-- necesita ningún caso especial.

-- ---------------------------------------------------------------------------
-- Tipologías compuestas (v6)
-- ---------------------------------------------------------------------------
--
-- Una tipología puede estar formada por otras: la corrediza con paño fijo abajo
-- es una COR2 arriba y un FIJO abajo, separados por un perfil de acople.
--
-- Cada paño recibe su medida por fórmula, evaluada en el contexto de la
-- compuesta (A, H, N y sus variables). Así las medidas cierran por construcción
-- en vez de negociarse entre dos aberturas independientes:
--
--     orden 1   FIJO   ancho = A   alto = ALTO_FIJO
--     orden 2   COR2   ancho = A   alto = H - ALTO_FIJO - 45
--
-- Los perfiles propios de la compuesta —el marco perimetral y el acople— van
-- en tipologia_formulas como los de cualquier otra tipología.

CREATE TABLE IF NOT EXISTS tipologia_composicion (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    tipologia_codigo TEXT NOT NULL,
    linea_id         INTEGER REFERENCES lineas(id) ON DELETE CASCADE,
    orden            INTEGER DEFAULT 0,
    tipologia_hijo   TEXT NOT NULL,
    etiqueta         TEXT DEFAULT '',
    formula_ancho    TEXT NOT NULL DEFAULT 'A',
    formula_alto     TEXT NOT NULL DEFAULT 'H',
    formula_hojas    TEXT NOT NULL DEFAULT 'N',
    activo           INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS tipologia_variables (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    tipologia_codigo TEXT NOT NULL,
    linea_id         INTEGER REFERENCES lineas(id) ON DELETE CASCADE,
    -- NULL = la variable vale para la tipología en todas las líneas
    clave            TEXT NOT NULL,        -- el nombre en las fórmulas: PREMARCO
    etiqueta         TEXT NOT NULL,        -- lo que lee el usuario
    tipo             TEXT NOT NULL DEFAULT 'bool',   -- bool | numero | opcion
    opciones         TEXT DEFAULT '',      -- JSON [["Simple",0],["Multipunto",1]]
    valor_default    TEXT DEFAULT '0',
    minimo           REAL DEFAULT 0,       -- sólo tipo 'numero'
    maximo           REAL DEFAULT 0,       -- 0 = sin tope
    ayuda            TEXT DEFAULT '',
    activo           INTEGER DEFAULT 1,
    orden            INTEGER DEFAULT 0
);

-- ---------------------------------------------------------------------------
-- Inventario (opcional: se activa con el parámetro 'usar_stock')
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS stock (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo          TEXT NOT NULL,               -- perfil | vidrio | accesorio
    referencia_id INTEGER NOT NULL,            -- id en perfiles/vidrios/accesorios
    deposito      TEXT DEFAULT 'Principal',
    cantidad      REAL DEFAULT 0,
    unidad        TEXT DEFAULT 'u',
    minimo        REAL DEFAULT 0,              -- punto de reposición
    actualizado   TEXT DEFAULT '',
    UNIQUE (tipo, referencia_id, deposito)
);

-- Libro mayor del inventario: el saldo de 'stock' se puede reconstruir sumando
-- estos movimientos. Nunca se borra un movimiento; una anulación es otro
-- movimiento de signo contrario.
CREATE TABLE IF NOT EXISTS stock_movimientos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha         TEXT NOT NULL,
    tipo          TEXT NOT NULL,
    referencia_id INTEGER NOT NULL,
    deposito      TEXT DEFAULT 'Principal',
    cantidad      REAL NOT NULL,               -- + ingreso · - egreso
    motivo        TEXT DEFAULT 'ajuste',       -- compra|consumo|ajuste|anulacion|inicial
    documento     TEXT DEFAULT '',             -- N° de presupuesto u OT que lo generó
    nota          TEXT DEFAULT ''
);

-- ---------------------------------------------------------------------------
-- Órdenes de trabajo: una por abertura presupuestada
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ordenes_trabajo (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    numero             TEXT UNIQUE NOT NULL,
    presupuesto_id     INTEGER REFERENCES presupuestos(id) ON DELETE SET NULL,
    presupuesto_numero TEXT DEFAULT '',
    item_orden         INTEGER DEFAULT 1,
    descripcion        TEXT DEFAULT '',
    cliente            TEXT DEFAULT '',
    obra               TEXT DEFAULT '',
    cantidad           INTEGER DEFAULT 1,
    fecha              TEXT NOT NULL,
    entrega            TEXT DEFAULT '',
    estado             TEXT DEFAULT 'Pendiente',
    responsable        TEXT DEFAULT '',
    notas              TEXT DEFAULT '',
    -- Despiece congelado al emitirla: la OT que está en el taller no cambia
    -- porque después se toque una fórmula o un precio.
    snapshot_json      TEXT DEFAULT '{}',
    stock_descontado   INTEGER DEFAULT 0,
    creado             TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS ix_tf_tipologia ON tipologia_formulas (tipologia_codigo, linea_id);
CREATE INDEX IF NOT EXISTS ix_vf_tipologia ON vidrio_formulas (tipologia_codigo, linea_id);
CREATE INDEX IF NOT EXISTS ix_pi_presupuesto ON presupuesto_items (presupuesto_id);
CREATE INDEX IF NOT EXISTS ix_stock_ref ON stock (tipo, referencia_id);
CREATE INDEX IF NOT EXISTS ix_mov_ref ON stock_movimientos (tipo, referencia_id);
CREATE INDEX IF NOT EXISTS ix_mov_doc ON stock_movimientos (documento);
CREATE INDEX IF NOT EXISTS ix_ot_presupuesto ON ordenes_trabajo (presupuesto_id);
CREATE INDEX IF NOT EXISTS ix_ot_estado ON ordenes_trabajo (estado);
CREATE INDEX IF NOT EXISTS ix_tv_tipologia ON tipologia_variables (tipologia_codigo, linea_id);

-- Van DOS índices parciales y no un UNIQUE común: en SQLite dos NULL son
-- distintos entre sí, así que UNIQUE(tipologia, linea_id, clave) dejaría colar
-- dos variables genéricas con el mismo nombre.
CREATE UNIQUE INDEX IF NOT EXISTS ix_tv_unica_generica
    ON tipologia_variables (tipologia_codigo, clave) WHERE linea_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ix_tv_unica_linea
    ON tipologia_variables (tipologia_codigo, linea_id, clave) WHERE linea_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_tc_tipologia
    ON tipologia_composicion (tipologia_codigo, linea_id);
"""


class DB:
    """Acceso a la base. Instanciar una sola vez y compartir."""

    def __init__(self, ruta: Path | str | None = None):
        rutas.asegurar_carpetas()
        self.ruta = Path(ruta) if ruta else RUTA_DB
        nueva = not self.ruta.exists()
        self.cx = sqlite3.connect(self.ruta)
        self.cx.row_factory = sqlite3.Row

        # CREATE TABLE IF NOT EXISTS: en una base existente no toca nada.
        self.cx.executescript(ESQUEMA)
        self.cx.commit()

        self.migraciones_aplicadas: list[int] = []
        if nueva:
            self.cx.execute(f"PRAGMA user_version = {ESQUEMA_VERSION}")
            self.cx.commit()
        else:
            self.migrar()

        if nueva or not self.query("SELECT 1 FROM lineas LIMIT 1"):
            sembrar(self)

        # Los catálogos MDT (Clásica y Actual) se aseguran en cada arranque, no
        # sólo al crear la base: así una instalación que viene de una versión
        # anterior los recibe con la actualización, igual que una migración,
        # pero sin ser una migración —lo que carga son datos, no esquema—.
        # sembrar_mdt() no pisa nada que el usuario haya tocado.
        from .catalogo_mdt import sembrar_mdt, ya_sembrado
        if not ya_sembrado(self):
            sembrar_mdt(self)

    # -- versionado del esquema ----------------------------------------------

    @property
    def version_esquema(self) -> int:
        version = self.cx.execute("PRAGMA user_version").fetchone()[0]
        # Las bases creadas por la primera versión no llevaban user_version.
        return version or 1

    def respaldar(self, etiqueta: str = "auto") -> Path | None:
        """Copia la base a ``datos/copias`` antes de una operación riesgosa."""
        if not self.ruta.exists():
            return None
        rutas.asegurar_carpetas()
        sello = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino = rutas.COPIAS / f"cotizador_{etiqueta}_{sello}.db"
        try:
            self.cx.commit()
            shutil.copy2(self.ruta, destino)
        except OSError:
            return None
        self._purgar_copias()
        return destino

    @staticmethod
    def _purgar_copias(conservar: int = 10) -> None:
        try:
            copias = sorted(rutas.COPIAS.glob("cotizador_*.db"),
                            key=lambda p: p.stat().st_mtime, reverse=True)
            for vieja in copias[conservar:]:
                vieja.unlink(missing_ok=True)
        except OSError:
            pass

    def migrar(self) -> list[int]:
        """Lleva la base a ESQUEMA_VERSION conservando todos los datos.

        Devuelve la lista de versiones aplicadas. Es idempotente: si la base ya
        está al día no hace nada.
        """
        actual = self.version_esquema
        if actual >= ESQUEMA_VERSION:
            return []

        self.respaldar(f"previo_v{ESQUEMA_VERSION}")

        aplicadas = []
        for destino in range(actual + 1, ESQUEMA_VERSION + 1):
            for sentencia in MIGRACIONES.get(destino, []):
                try:
                    self.cx.execute(sentencia)
                except sqlite3.OperationalError as exc:
                    # 'duplicate column name' aparece si la migración ya corrió
                    # a medias; el resto sí es un error real.
                    if "duplicate column" not in str(exc).lower():
                        raise
            self.cx.execute(f"PRAGMA user_version = {destino}")
            self.cx.commit()
            aplicadas.append(destino)

        self.migraciones_aplicadas = aplicadas
        return aplicadas

    # -- utilidades genéricas -------------------------------------------------

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self.cx.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        return self.cx.execute(sql, params).fetchone()

    def execute(self, sql: str, params: tuple = ()) -> int:
        cur = self.cx.execute(sql, params)
        self.cx.commit()
        return cur.lastrowid

    def executemany(self, sql: str, filas) -> None:
        self.cx.executemany(sql, filas)
        self.cx.commit()

    def insertar(self, tabla: str, datos: dict) -> int:
        cols = ", ".join(datos)
        marcas = ", ".join("?" for _ in datos)
        return self.execute(f"INSERT INTO {tabla} ({cols}) VALUES ({marcas})", tuple(datos.values()))

    def actualizar(self, tabla: str, id_: int, datos: dict) -> None:
        sets = ", ".join(f"{c} = ?" for c in datos)
        self.execute(f"UPDATE {tabla} SET {sets} WHERE id = ?", (*datos.values(), id_))

    def borrar(self, tabla: str, id_: int) -> None:
        self.execute(f"DELETE FROM {tabla} WHERE id = ?", (id_,))

    def cerrar(self) -> None:
        self.cx.close()

    # -- parámetros -----------------------------------------------------------

    def parametro(self, clave: str, por_defecto=None):
        fila = self.query_one("SELECT valor FROM parametros WHERE clave = ?", (clave,))
        return fila["valor"] if fila else por_defecto

    def parametro_float(self, clave: str, por_defecto: float = 0.0) -> float:
        try:
            return float(self.parametro(clave, por_defecto))
        except (TypeError, ValueError):
            return por_defecto

    def parametro_int(self, clave: str, por_defecto: int = 0) -> int:
        try:
            return int(float(self.parametro(clave, por_defecto)))
        except (TypeError, ValueError):
            return por_defecto

    def set_parametro(self, clave: str, valor, descripcion: str = "", grupo: str = "General") -> None:
        self.execute(
            "INSERT INTO parametros (clave, valor, descripcion, grupo) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
            (clave, str(valor), descripcion, grupo),
        )

    def parametros_por_grupo(self) -> dict[str, list[sqlite3.Row]]:
        agrupado: dict[str, list[sqlite3.Row]] = {}
        for fila in self.query("SELECT * FROM parametros ORDER BY grupo, clave"):
            agrupado.setdefault(fila["grupo"], []).append(fila)
        return agrupado

    # -- empresa y numeración -------------------------------------------------

    def empresa(self) -> sqlite3.Row:
        fila = self.query_one("SELECT * FROM empresa WHERE id = 1")
        if fila is None:
            self.execute("INSERT INTO empresa (id) VALUES (1)")
            fila = self.query_one("SELECT * FROM empresa WHERE id = 1")
        return fila

    def guardar_empresa(self, datos: dict) -> None:
        self.empresa()  # asegura que exista la fila
        sets = ", ".join(f"{c} = ?" for c in datos)
        self.execute(f"UPDATE empresa SET {sets} WHERE id = 1", tuple(datos.values()))

    def numero_sugerido(self) -> str:
        emp = self.empresa()
        numero = emp["proximo_numero"] or 1
        while self.query_one("SELECT 1 FROM presupuestos WHERE numero = ?", (self._fmt(numero),)):
            numero += 1
        return self._fmt(numero)

    def _fmt(self, numero: int) -> str:
        emp = self.empresa()
        return f"{emp['prefijo']}-{str(numero).zfill(emp['relleno_ceros'] or 4)}"

    def avanzar_numeracion(self, numero_usado: str) -> None:
        """Si el número usado sigue el patrón, adelanta el correlativo."""
        emp = self.empresa()
        prefijo = f"{emp['prefijo']}-"
        if numero_usado.startswith(prefijo):
            cola = numero_usado[len(prefijo):]
            if cola.isdigit() and int(cola) >= (emp["proximo_numero"] or 1):
                self.execute("UPDATE empresa SET proximo_numero = ? WHERE id = 1", (int(cola) + 1,))

    def numero_ot_sugerido(self) -> str:
        """Correlativo de órdenes de trabajo, con su propio prefijo y contador.

        Va aparte del de presupuestos: un presupuesto de seis aberturas genera
        seis OT, y mezclarlos dejaría huecos raros en la numeración comercial.
        """
        prefijo = self.parametro("ot_prefijo", "OT") or "OT"
        numero = self.parametro_int("ot_proximo_numero", 1) or 1
        while self.query_one("SELECT 1 FROM ordenes_trabajo WHERE numero = ?",
                             (f"{prefijo}-{numero:05d}",)):
            numero += 1
        return f"{prefijo}-{numero:05d}"

    def avanzar_numeracion_ot(self, numero_usado: str) -> None:
        prefijo = f"{self.parametro('ot_prefijo', 'OT') or 'OT'}-"
        if numero_usado.startswith(prefijo):
            cola = numero_usado[len(prefijo):]
            if cola.isdigit() and int(cola) >= self.parametro_int("ot_proximo_numero", 1):
                self.set_parametro("ot_proximo_numero", int(cola) + 1,
                                   "Próximo número de orden de trabajo", "Producción")

    # -- catálogos ------------------------------------------------------------

    def lineas(self, solo_activas: bool = True) -> list[sqlite3.Row]:
        sql = "SELECT * FROM lineas"
        if solo_activas:
            sql += " WHERE activo = 1"
        return self.query(sql + " ORDER BY nombre")

    def linea(self, linea_id: int) -> sqlite3.Row | None:
        return self.query_one("SELECT * FROM lineas WHERE id = ?", (linea_id,))

    def colores_de_linea(self, linea_id: int) -> list[sqlite3.Row]:
        return self.query(
            "SELECT * FROM linea_precios WHERE linea_id = ? AND activo = 1 ORDER BY color",
            (linea_id,),
        )

    def precio_linea(self, linea_id: int, color: str) -> sqlite3.Row | None:
        return self.query_one(
            "SELECT * FROM linea_precios WHERE linea_id = ? AND color = ?", (linea_id, color)
        )

    def vidrios(self, solo_activos: bool = True) -> list[sqlite3.Row]:
        sql = "SELECT * FROM vidrios"
        if solo_activos:
            sql += " WHERE activo = 1"
        return self.query(sql + " ORDER BY nombre")

    def vidrio(self, vidrio_id: int) -> sqlite3.Row | None:
        return self.query_one("SELECT * FROM vidrios WHERE id = ?", (vidrio_id,))

    def accesorios(self, solo_activos: bool = True) -> list[sqlite3.Row]:
        sql = "SELECT * FROM accesorios"
        if solo_activos:
            sql += " WHERE activo = 1"
        return self.query(sql + " ORDER BY codigo")

    def tipologias(self, solo_activas: bool = True) -> list[sqlite3.Row]:
        sql = "SELECT * FROM tipologias"
        if solo_activas:
            sql += " WHERE activo = 1"
        return self.query(sql + " ORDER BY nombre")

    def tipologia(self, codigo: str) -> sqlite3.Row | None:
        return self.query_one("SELECT * FROM tipologias WHERE codigo = ?", (codigo,))

    def perfil(self, linea_id: int, codigo: str) -> sqlite3.Row | None:
        return self.query_one(
            "SELECT * FROM perfiles WHERE linea_id = ? AND codigo = ?", (linea_id, codigo)
        )

    # -- fórmulas -------------------------------------------------------------

    def formulas_despiece(self, tipologia_codigo: str, linea_id: int) -> list[sqlite3.Row]:
        """Fórmulas específicas de la línea; si no hay, las genéricas (linea_id NULL)."""
        especificas = self.query(
            "SELECT * FROM tipologia_formulas WHERE tipologia_codigo = ? AND linea_id = ? "
            "ORDER BY orden, id",
            (tipologia_codigo, linea_id),
        )
        if especificas:
            return especificas
        return self.query(
            "SELECT * FROM tipologia_formulas WHERE tipologia_codigo = ? AND linea_id IS NULL "
            "ORDER BY orden, id",
            (tipologia_codigo,),
        )

    def formula_vidrio(self, tipologia_codigo: str, linea_id: int) -> sqlite3.Row | None:
        fila = self.query_one(
            "SELECT * FROM vidrio_formulas WHERE tipologia_codigo = ? AND linea_id = ?",
            (tipologia_codigo, linea_id),
        )
        if fila:
            return fila
        return self.query_one(
            "SELECT * FROM vidrio_formulas WHERE tipologia_codigo = ? AND linea_id IS NULL",
            (tipologia_codigo,),
        )

    def kit_para(self, linea_id: int, tipologia_codigo: str) -> sqlite3.Row | None:
        fila = self.query_one(
            "SELECT * FROM kits WHERE linea_id = ? AND tipologia_codigo = ? AND activo = 1",
            (linea_id, tipologia_codigo),
        )
        if fila:
            return fila
        return self.query_one(
            "SELECT * FROM kits WHERE linea_id = ? AND (tipologia_codigo = '' OR tipologia_codigo IS NULL) "
            "AND activo = 1",
            (linea_id,),
        )

    def items_de_kit(self, kit_id: int) -> list[sqlite3.Row]:
        return self.query(
            "SELECT ki.*, a.id AS accesorio_id, a.codigo, a.descripcion, a.unidad, "
            "a.precio, a.peso_kg_m "
            "FROM kit_items ki JOIN accesorios a ON a.id = ki.accesorio_id "
            "WHERE ki.kit_id = ? ORDER BY ki.id",
            (kit_id,),
        )

    # -- duplicar una línea completa ------------------------------------------

    def duplicar_linea(self, linea_id: int, nombre_nuevo: str) -> int:
        """Clona una línea entera: precios, perfiles, fórmulas y kits.

        Sirve para dar de alta un sistema parecido a otro (la variante DVH de una
        línea, la misma perfilería de otra extrusora) sin volver a cargar cientos
        de renglones. Devuelve el id de la línea nueva.

        Se copia **todo lo que cuelga de la línea**; lo que es global (vidrios,
        accesorios, tipologías) se comparte y no se duplica. Las fórmulas
        genéricas (``linea_id IS NULL``) tampoco se copian: siguen aplicando a la
        línea nueva por sí solas.
        """
        original = self.linea(linea_id)
        if original is None:
            raise ValueError("La línea de origen no existe.")

        nombre_nuevo = (nombre_nuevo or "").strip()
        if not nombre_nuevo:
            raise ValueError("Hay que darle un nombre a la línea nueva.")
        if self.query_one("SELECT 1 FROM lineas WHERE nombre = ?", (nombre_nuevo,)):
            raise ValueError(f"Ya existe una línea llamada «{nombre_nuevo}».")

        nueva_id = self.insertar("lineas", {
            "nombre": nombre_nuevo,
            "descripcion": original["descripcion"],
            "modo_costeo": original["modo_costeo"],
            "extrusora": original["extrusora"],
            "activo": 1,
        })

        for fila in self.query("SELECT * FROM linea_precios WHERE linea_id = ?", (linea_id,)):
            self.insertar("linea_precios", {
                "linea_id": nueva_id, "color": fila["color"],
                "precio_kg": fila["precio_kg"],
                "precio_m2_perfil": fila["precio_m2_perfil"],
                "activo": fila["activo"]})

        for fila in self.query("SELECT * FROM perfiles WHERE linea_id = ?", (linea_id,)):
            self.insertar("perfiles", {
                "linea_id": nueva_id, "codigo": fila["codigo"],
                "descripcion": fila["descripcion"], "peso_kg_m": fila["peso_kg_m"],
                "largo_barra_mm": fila["largo_barra_mm"], "familia": fila["familia"],
                # La imagen se comparte: es el mismo dibujo de sección y no tiene
                # sentido duplicar el archivo en disco.
                "imagen": fila["imagen"], "notas": fila["notas"]})

        for fila in self.query(
                "SELECT * FROM tipologia_formulas WHERE linea_id = ?", (linea_id,)):
            self.insertar("tipologia_formulas", {
                "tipologia_codigo": fila["tipologia_codigo"], "linea_id": nueva_id,
                "perfil_codigo": fila["perfil_codigo"], "funcion": fila["funcion"],
                "formula_largo": fila["formula_largo"],
                "cantidad_piezas": fila["cantidad_piezas"],
                "peso_kg_m": fila["peso_kg_m"], "nota": fila["nota"],
                "orden": fila["orden"]})

        for fila in self.query("SELECT * FROM vidrio_formulas WHERE linea_id = ?", (linea_id,)):
            self.insertar("vidrio_formulas", {
                "tipologia_codigo": fila["tipologia_codigo"], "linea_id": nueva_id,
                "formula_ancho": fila["formula_ancho"], "formula_alto": fila["formula_alto"],
                "formula_cantidad": fila["formula_cantidad"]})

        for kit in self.query("SELECT * FROM kits WHERE linea_id = ?", (linea_id,)):
            kit_nuevo = self.insertar("kits", {
                "nombre": kit["nombre"], "linea_id": nueva_id,
                "tipologia_codigo": kit["tipologia_codigo"],
                "descripcion": kit["descripcion"], "activo": kit["activo"]})
            for item in self.query("SELECT * FROM kit_items WHERE kit_id = ?", (kit["id"],)):
                self.insertar("kit_items", {
                    "kit_id": kit_nuevo, "accesorio_id": item["accesorio_id"],
                    "cantidad_formula": item["cantidad_formula"]})

        return nueva_id

    def resumen_linea(self, linea_id: int) -> dict[str, int]:
        """Cuántos registros cuelgan de una línea. Para avisar antes de duplicar."""
        def contar(sql: str) -> int:
            fila = self.query_one(sql, (linea_id,))
            return fila[0] if fila else 0

        return {
            "colores": contar("SELECT COUNT(*) FROM linea_precios WHERE linea_id = ?"),
            "perfiles": contar("SELECT COUNT(*) FROM perfiles WHERE linea_id = ?"),
            "formulas": contar("SELECT COUNT(*) FROM tipologia_formulas WHERE linea_id = ?"),
            "formulas_vidrio": contar("SELECT COUNT(*) FROM vidrio_formulas WHERE linea_id = ?"),
            "kits": contar("SELECT COUNT(*) FROM kits WHERE linea_id = ?"),
        }

    # -- presupuestos ---------------------------------------------------------

    def listar_presupuestos(self, filtro: str = "") -> list[sqlite3.Row]:
        if filtro:
            patron = f"%{filtro}%"
            return self.query(
                "SELECT * FROM presupuestos WHERE numero LIKE ? OR cliente_razon_social LIKE ? "
                "ORDER BY id DESC",
                (patron, patron),
            )
        return self.query("SELECT * FROM presupuestos ORDER BY id DESC")

    def guardar_presupuesto(self, cab: dict, items: list[dict], snapshot: dict) -> int:
        """Inserta o reemplaza (por número) un presupuesto completo."""
        existente = self.query_one("SELECT id FROM presupuestos WHERE numero = ?", (cab["numero"],))
        cab = dict(cab)
        cab["snapshot_json"] = json.dumps(snapshot, ensure_ascii=False, default=str)
        cab["actualizado"] = datetime.now().isoformat(timespec="seconds")
        if existente:
            pid = existente["id"]
            self.actualizar("presupuestos", pid, cab)
            self.execute("DELETE FROM presupuesto_items WHERE presupuesto_id = ?", (pid,))
        else:
            cab.setdefault("creado", cab["actualizado"])
            cab.setdefault("estado", "Borrador")
            pid = self.insertar("presupuestos", cab)
        for it in items:
            it = dict(it)
            it["presupuesto_id"] = pid
            self.insertar("presupuesto_items", it)
        self.avanzar_numeracion(cab["numero"])
        return pid

    def cargar_presupuesto(self, pid: int) -> tuple[sqlite3.Row, list[sqlite3.Row]]:
        cab = self.query_one("SELECT * FROM presupuestos WHERE id = ?", (pid,))
        items = self.query(
            "SELECT * FROM presupuesto_items WHERE presupuesto_id = ? ORDER BY orden, id", (pid,)
        )
        return cab, items
