"""
Precarga inicial de la base.

Los precios de líneas, colores, vidrios y costos operativos salen de la planilla
"Cotizador de Aberturas.xlsx" (hoja *Precios Base*).

Los ``precio_kg`` NO estaban en la planilla (que costea a $/m² de abertura): se
derivaron para que un paño testigo dé un costo equivalente al del método por m².
Están marcados como estimativos y deben reemplazarse por el precio real de
proveedor. Lo mismo aplica a los ``peso_kg_m`` de cada perfil.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Líneas de aluminio  (nombre, modo_costeo, descripción)
# ---------------------------------------------------------------------------

LINEAS = [
    ("Módena", "kg", "Corrediza y abrir - perfilería reforzada"),
    ("Herrero", "kg", "Línea económica de reposición"),
    ("A30 New", "kg", "Abrir / batiente de altas prestaciones"),
    ("Módena Plus (DVH)", "kg", "Módena con cámara para DVH"),
    ("Ekonal", "kg", "Línea económica corrediza"),
]

#: Quién extruye cada línea (informativo, para el catálogo).
EXTRUSORAS = {
    "Módena": "Aluar",
    "Módena Plus (DVH)": "Aluar",
    "Herrero": "Aluar",
    "A30 New": "Aluar",
    "Ekonal": "Aluar",
}

#: Palabra en la descripción -> familia de catálogo. Se evalúa en orden, así que
#: 'premarco' y 'contravidrio' van antes que 'marco' y 'vidrio'.
FAMILIAS_POR_TEXTO = [
    ("premarco", "Premarcos"),
    ("contravidrio", "Contravidrios"),
    ("marco", "Marcos"),
    ("hoja", "Hojas"),
    ("refuerzo", "Refuerzos"),
    ("mosquitero", "Mosquiteros"),
    ("zócalo", "Hojas"),
    ("travesaño", "Hojas"),
    ("junquillo", "Contravidrios"),
    ("tapajunta", "Terminaciones"),
    ("adaptador", "Terminaciones"),
]


def familia_de(descripcion: str) -> str:
    """Familia de catálogo deducida de la descripción del perfil."""
    texto = (descripcion or "").lower()
    for palabra, familia in FAMILIAS_POR_TEXTO:
        if palabra in texto:
            return familia
    return "Varios"

# (linea, color, precio_kg, precio_m2_perfil)   -> precio_m2_perfil sale del Excel
PRECIOS_LINEA = [
    ("Módena", "Natural", 12300, 62000),
    ("Módena", "Blanco", 13500, 68000),
    ("Módena", "Negro", 14300, 72000),
    ("Módena", "Anodizado Bronce", 14900, 75000),
    ("Herrero", "Natural", 9500, 48000),
    ("Herrero", "Blanco", 10500, 53000),
    ("A30 New", "Natural", 13900, 70000),
    ("A30 New", "Blanco", 15300, 77000),
    ("A30 New", "Negro", 16100, 81000),
    ("Módena Plus (DVH)", "Natural", 17500, 88000),
    ("Módena Plus (DVH)", "Blanco", 18900, 95000),
    ("Módena Plus (DVH)", "Imitación Madera", 21900, 110000),
    ("Ekonal", "Natural", 9000, 45000),
    ("Ekonal", "Blanco", 9900, 50000),
]

# ---------------------------------------------------------------------------
# Perfiles  (linea, codigo, descripcion, peso_kg_m)
# ---------------------------------------------------------------------------

PERFILES = [
    # --- Módena: códigos y pesos del catálogo Aluar División Elaborados,
    #     sección 02 "listado de perfiles" (abril 2001).
    ("Módena", "6200", "Umbral y dintel marco ventana y puerta corrediza", 1.266),
    ("Módena", "6201", "Jambas de marco ventana y puerta corrediza", 0.675),
    ("Módena", "6203", "Parante lateral hoja vidrio simple corrediza", 0.664),
    ("Módena", "6204", "Zócalo y cabezal de hoja vidrio simple corrediza", 0.705),
    ("Módena", "6205", "Premarco", 0.397),
    ("Módena", "6206", "Tapa premarco", 0.181),
    ("Módena", "6207", "Parante central hoja vidrio simple corrediza", 0.613),
    ("Módena", "6208", "Parante central con tirador hoja vidrio simple", 0.813),
    ("Módena", "6209", "Zócalo alto hoja vidrio simple puerta corrediza", 1.258),
    ("Módena", "6210", "Marco ventana de abrir con cámara compensadora", 0.789),
    ("Módena", "6211", "Hoja ventana de abrir con cámara compensadora", 0.848),
    ("Módena", "6212", "Contravidrio 36 mm", 0.316),
    ("Módena", "6214", "Jambas y cabezal hoja puerta de rebatir", 1.088),
    ("Módena", "6215", "Hoja ventana de abrir doble contacto / banderola", 0.864),
    ("Módena", "6216", "Marco vent. abrir DC / banderola / ventiluz / PF recto", 0.726),
    ("Módena", "6217", "Contravidrio 29 mm", 0.294),
    ("Módena", "6218", "Travesaño hoja puerta de rebatir", 1.150),
    ("Módena", "6219", "Zócalo hoja puerta de rebatir", 1.647),
    ("Módena", "6220", "Contravidrio exterior puerta de rebatir", 0.176),
    ("Módena", "6221", "Travesaño angosto paño fijo", 0.767),
    ("Módena", "6222", "Travesaño ancho paño fijo", 0.842),
    ("Módena", "6223", "Encuentro central ventana de abrir 2 hojas c/cámara", 0.921),
    ("Módena", "6224", "Encuentro central vent. abrir 2 hojas DC / puerta rebatir", 0.794),
    ("Módena", "6227", "Hoja ventiluz", 0.864),
    ("Módena", "6225", "Contravidrio recto 22 mm", 0.257),
    ("Módena", "6226", "Contravidrio recto 15 mm", 0.211),
    ("Módena", "6228", "Tope mosquitero ventana y puerta corrediza", 0.186),
    ("Módena", "6238", "Contravidrio recto 8 mm", 0.189),
    ("Módena", "6239", "Travesaño hoja vidrio simple puerta corrediza", 0.705),
    ("Módena", "6240", "Umbral y dintel marco de 3 guías corrediza", 1.823),
    ("Módena", "6241", "Jambas marco de 3 guías corrediza", 0.975),
    ("Módena", "6246", "Encuentro central de 4 hojas corrediza", 0.291),
    ("Módena", "6255", "Bastidor mosquitero", 0.424),
    ("Módena", "6256", "Travesaño mosquitero", 0.508),
    # --- Herrero corrediza
    ("Herrero", "HE-MS", "Marco superior corrediza", 0.720),
    ("Herrero", "HE-MI", "Marco inferior / riel", 0.840),
    ("Herrero", "HE-MJ", "Jamba de marco", 0.700),
    ("Herrero", "HE-HV", "Parante de hoja", 0.520),
    ("Herrero", "HE-HH", "Travesaño de hoja", 0.560),
    ("Herrero", "HE-CV", "Contravidrio", 0.150),
    ("Herrero", "HE-MRC", "Marco perimetral abrir", 0.760),
    ("Herrero", "HE-HAB", "Hoja de abrir", 0.680),
    ("Herrero", "HE-PM", "Premarco", 0.480),
    # --- A30 New (abrir)
    ("A30 New", "A30-MRC", "Marco perimetral", 0.960),
    ("A30 New", "A30-HAB", "Hoja de abrir", 0.880),
    ("A30 New", "A30-CV", "Contravidrio", 0.210),
    ("A30 New", "A30-PM", "Premarco", 0.600),
    ("A30 New", "A30-MS", "Marco superior corrediza", 0.900),
    ("A30 New", "A30-MI", "Marco inferior / riel", 1.020),
    ("A30 New", "A30-MJ", "Jamba de marco", 0.870),
    ("A30 New", "A30-HV", "Parante de hoja", 0.660),
    ("A30 New", "A30-HH", "Travesaño de hoja", 0.690),
    # --- Módena Plus (DVH): misma perfilería de marco que Módena; cambia la hoja.
    ("Módena Plus (DVH)", "6200", "Umbral y dintel marco ventana y puerta corrediza", 1.266),
    ("Módena Plus (DVH)", "6201", "Jambas de marco ventana y puerta corrediza", 0.675),
    ("Módena Plus (DVH)", "6205", "Premarco", 0.397),
    ("Módena Plus (DVH)", "6206", "Tapa premarco", 0.181),
    ("Módena Plus (DVH)", "6248", "Parante lateral de hoja para DVH corrediza", 0.635),
    ("Módena Plus (DVH)", "6249", "Zócalo y cabezal de hoja para DVH corrediza", 0.675),
    ("Módena Plus (DVH)", "6250", "Parante central de hoja para DVH corrediza", 0.583),
    ("Módena Plus (DVH)", "6251", "Parante central con tirador hoja para DVH", 0.783),
    ("Módena Plus (DVH)", "6252", "Zócalo alto de hoja para DVH puerta corrediza", 1.215),
    ("Módena Plus (DVH)", "6253", "Travesaño de hoja para DVH puerta corrediza", 0.689),
    ("Módena Plus (DVH)", "6255", "Bastidor mosquitero", 0.424),
    ("Módena Plus (DVH)", "6256", "Travesaño mosquitero", 0.508),
    # --- Ekonal
    ("Ekonal", "EK-MS", "Marco superior corrediza", 0.680),
    ("Ekonal", "EK-MI", "Marco inferior / riel", 0.790),
    ("Ekonal", "EK-MJ", "Jamba de marco", 0.660),
    ("Ekonal", "EK-HV", "Parante de hoja", 0.490),
    ("Ekonal", "EK-HH", "Travesaño de hoja", 0.520),
    ("Ekonal", "EK-CV", "Contravidrio", 0.140),
    ("Ekonal", "EK-PM", "Premarco", 0.450),
    ("Ekonal", "EK-MRC", "Marco perimetral abrir", 0.720),
    ("Ekonal", "EK-HAB", "Hoja de abrir", 0.640),
]

# ---------------------------------------------------------------------------
# Vidrios  (Excel, hoja Precios Base A20:B26)
# (nombre, tipo, espesor, precio_m2, plancha_ancho, plancha_alto, desperdicio)
# ---------------------------------------------------------------------------

VIDRIOS = [
    ("Float 3mm", "Float", 3.0, 18000, 3600, 2500, 0.10),
    ("Float 4mm", "Float", 4.0, 21000, 3600, 2500, 0.10),
    ("Float 6mm", "Float", 6.0, 29000, 3600, 2500, 0.10),
    ("Laminado 3+3", "Laminado", 6.0, 42000, 3600, 2500, 0.12),
    ("DVH 4/9/4", "DVH", 17.0, 55000, 3210, 2250, 0.12),
    ("DVH 4/12/4", "DVH", 20.0, 60000, 3210, 2250, 0.12),
    ("Esmerilado 4mm", "Float", 4.0, 27000, 3600, 2500, 0.10),
]

# ---------------------------------------------------------------------------
# Accesorios  (codigo, descripcion, unidad, precio)
# ---------------------------------------------------------------------------

ACCESORIOS = [
    ("RUE-STD", "Rueda simple para hoja corrediza", "u", 2800),
    ("RUE-REF", "Rueda reforzada (puerta balcón)", "u", 4600),
    ("CIE-CRE", "Cierre a cremona / uñeta corrediza", "u", 7200),
    ("CIE-EMB", "Cierre embutido para hoja de abrir", "u", 15500),
    ("BRZ-ABR", "Brazo de rebatir / compás", "u", 9800),
    ("BIS-ABR", "Bisagra de abrir reforzada", "u", 5400),
    ("MAN-STD", "Manija estándar", "u", 8900),
    ("MAN-JON", "Manijón para puerta balcón", "u", 26000),
    ("FEL-6X7", "Felpa 6x7 mm", "ml", 950),
    ("BUR-CUÑ", "Burlete de cuña / junquillo", "ml", 1250),
    ("BUR-EPD", "Burlete perimetral EPDM", "ml", 1850),
    ("ESC-45", "Escuadra de armado 45°", "u", 1600),
    ("TOR-KIT", "Kit de tornillería y sellado por hoja", "u", 2400),
    ("SIL-NEU", "Sellador siliconado neutro", "u", 9500),
    ("MOS-KIT", "Kit de mosquitero corredizo (perfilería + tela)", "m2", 9000),
]

# (kit, linea, tipologia, [(codigo_accesorio, formula_cantidad)])
KITS = [
    (
        "Kit corrediza Módena",
        "Módena",
        "COR2",
        [
            ("RUE-STD", "2*N"),
            ("CIE-CRE", "1"),
            ("MAN-STD", "N"),
            ("FEL-6X7", "2*N*(HH+AH)/1000"),
            ("BUR-CUÑ", "2*N*(HH+AH)/1000"),
            ("ESC-45", "4*N"),
            ("TOR-KIT", "N"),
        ],
    ),
    (
        "Kit corrediza Herrero",
        "Herrero",
        "COR2",
        [
            ("RUE-STD", "2*N"),
            ("CIE-CRE", "1"),
            ("FEL-6X7", "2*N*(HH+AH)/1000"),
            ("ESC-45", "4*N"),
            ("TOR-KIT", "N"),
        ],
    ),
    (
        "Kit puerta balcón Módena",
        "Módena",
        "PBAL2",
        [
            ("RUE-REF", "2*N"),
            ("CIE-CRE", "1"),
            ("MAN-JON", "1"),
            ("FEL-6X7", "2*N*(HH+AH)/1000"),
            ("BUR-CUÑ", "2*N*(HH+AH)/1000"),
            ("ESC-45", "4*N"),
            ("TOR-KIT", "N"),
        ],
    ),
    (
        "Kit abrir A30 New",
        "A30 New",
        "BAT1",
        [
            ("BIS-ABR", "3*N"),
            ("CIE-EMB", "N"),
            ("MAN-STD", "N"),
            ("BUR-EPD", "2*N*(HH+AH)/1000"),
            ("ESC-45", "4*N"),
            ("TOR-KIT", "N"),
        ],
    ),
]

# ---------------------------------------------------------------------------
# Tipologías
# (codigo, nombre, hojas, mosquitero, premarco, esquema, horas_por_m2)
# ---------------------------------------------------------------------------

TIPOLOGIAS = [
    ("COR2", "Ventana Corrediza 2 hojas", 2, 1, 1, "corrediza", 0.85),
    ("COR3", "Ventana Corrediza 3 hojas", 3, 1, 1, "corrediza", 0.95),
    ("COR4", "Ventana Corrediza 4 hojas", 4, 1, 1, "corrediza", 1.05),
    ("PBAL2", "Puerta Balcón corrediza 2 hojas", 2, 1, 1, "corrediza", 1.10),
    ("PBAL4", "Puerta Balcón corrediza 4 hojas", 4, 1, 1, "corrediza", 1.30),
    ("FIJO", "Paño Fijo", 1, 0, 1, "fijo", 0.45),
    ("BAT1", "Ventana Batiente / Rebatible 1 hoja", 1, 1, 1, "batiente", 0.90),
    ("BAT2", "Ventana Batiente 2 hojas", 2, 1, 1, "batiente", 1.10),
    ("BAND", "Banderola / Ventiluz", 1, 1, 1, "banderola", 0.70),
    ("PBAT1", "Puerta Batiente 1 hoja", 1, 0, 1, "puerta_batiente", 1.20),
    ("PVENT", "Puerta Ventana (abrir)", 2, 1, 1, "batiente", 1.25),
]

# ---------------------------------------------------------------------------
# Fórmulas de despiece: Tipologias_Formulas
# (tipologia, linea|None, perfil, funcion, formula_largo, cantidad, orden)
#
# El peso_kg_m se toma del perfil cargado en la tabla `perfiles`; sólo se guarda
# aquí como respaldo cuando el perfil no existe.
# ---------------------------------------------------------------------------

FORMULAS = [
    # ===== HERRERO CORREDIZA (fórmulas del enunciado: hoja = H-35 ; (A+12)/N)
    ("COR2", "Herrero", "HE-MS", "MARCO_HORIZONTAL", "A", "1", 1),
    ("COR2", "Herrero", "HE-MI", "MARCO_HORIZONTAL", "A", "1", 2),
    ("COR2", "Herrero", "HE-MJ", "MARCO_VERTICAL", "H", "2", 3),
    ("COR2", "Herrero", "HE-HV", "HOJA_VERTICAL", "H - 35", "2*N", 4),
    ("COR2", "Herrero", "HE-HH", "HOJA_HORIZONTAL", "(A + 12) / N", "2*N", 5),
    ("COR3", "Herrero", "HE-MS", "MARCO_HORIZONTAL", "A", "1", 1),
    ("COR3", "Herrero", "HE-MI", "MARCO_HORIZONTAL", "A", "1", 2),
    ("COR3", "Herrero", "HE-MJ", "MARCO_VERTICAL", "H", "2", 3),
    ("COR3", "Herrero", "HE-HV", "HOJA_VERTICAL", "H - 35", "2*N", 4),
    ("COR3", "Herrero", "HE-HH", "HOJA_HORIZONTAL", "(A + 18) / N", "2*N", 5),

    # ===== MÓDENA CORREDIZA
    # Tabla oficial Aluar, sección 06-01 "ventana y puerta corrediza".
    # Los descuentos (-42, -79, -24) son los del fabricante, no estimaciones.
    # Cada cantidad de hojas va como tipología separada porque los descuentos
    # cambian: en 3 hojas las laterales llevan -7 y la central +1.
    ("COR2", "Módena", "6200", "MARCO_HORIZONTAL", "A - 42", "2", 1),
    ("COR2", "Módena", "6201", "MARCO_VERTICAL", "H", "2", 2),
    ("COR2", "Módena", "6203", "HOJA_VERTICAL", "H - 79", "2", 3),
    ("COR2", "Módena", "6207", "HOJA_VERTICAL", "H - 79", "1", 4),
    ("COR2", "Módena", "6208", "HOJA_VERTICAL", "H - 79", "1", 5),
    ("COR2", "Módena", "6204", "HOJA_HORIZONTAL", "A / 2 - 24", "4", 6),

    ("COR3", "Módena", "6240", "MARCO_HORIZONTAL", "A - 42", "2", 1),
    ("COR3", "Módena", "6241", "MARCO_VERTICAL", "H", "2", 2),
    ("COR3", "Módena", "6203", "HOJA_VERTICAL", "H - 79", "2", 3),
    ("COR3", "Módena", "6207", "HOJA_VERTICAL", "H - 79", "2", 4),
    ("COR3", "Módena", "6208", "HOJA_VERTICAL", "H - 79", "2", 5),
    ("COR3", "Módena", "6204", "HOJA_HORIZONTAL", "A / 3 - 7", "4", 6),
    ("COR3", "Módena", "6204", "HOJA_HORIZONTAL", "A / 3 + 1", "2", 7),

    ("COR4", "Módena", "6240", "MARCO_HORIZONTAL", "A - 42", "2", 1),
    ("COR4", "Módena", "6241", "MARCO_VERTICAL", "H", "2", 2),
    ("COR4", "Módena", "6203", "HOJA_VERTICAL", "H - 79", "4", 3),
    ("COR4", "Módena", "6246", "HOJA_VERTICAL", "H - 79", "2", 4),
    ("COR4", "Módena", "6207", "HOJA_VERTICAL", "H - 79", "2", 5),
    ("COR4", "Módena", "6204", "HOJA_HORIZONTAL", "A / 4 - 7", "8", 6),

    # Puerta balcón: el zócalo inferior es el alto (6209) y suma travesaño (6239).
    ("PBAL2", "Módena", "6200", "MARCO_HORIZONTAL", "A - 42", "2", 1),
    ("PBAL2", "Módena", "6201", "MARCO_VERTICAL", "H", "2", 2),
    ("PBAL2", "Módena", "6203", "HOJA_VERTICAL", "H - 79", "2", 3),
    ("PBAL2", "Módena", "6207", "HOJA_VERTICAL", "H - 79", "1", 4),
    ("PBAL2", "Módena", "6208", "HOJA_VERTICAL", "H - 79", "1", 5),
    ("PBAL2", "Módena", "6204", "HOJA_HORIZONTAL", "A / 2 - 24", "2", 6),
    ("PBAL2", "Módena", "6209", "HOJA_HORIZONTAL", "A / 2 - 24", "2", 7),
    ("PBAL2", "Módena", "6239", "OTRO", "A / 2 - 67", "2", 8),

    # ===== MÓDENA PLUS (DVH)
    # Mismos cortes que Módena; sólo cambian los códigos de la hoja.
    ("COR2", "Módena Plus (DVH)", "6200", "MARCO_HORIZONTAL", "A - 42", "2", 1),
    ("COR2", "Módena Plus (DVH)", "6201", "MARCO_VERTICAL", "H", "2", 2),
    ("COR2", "Módena Plus (DVH)", "6248", "HOJA_VERTICAL", "H - 79", "2", 3),
    ("COR2", "Módena Plus (DVH)", "6250", "HOJA_VERTICAL", "H - 79", "1", 4),
    ("COR2", "Módena Plus (DVH)", "6251", "HOJA_VERTICAL", "H - 79", "1", 5),
    ("COR2", "Módena Plus (DVH)", "6249", "HOJA_HORIZONTAL", "A / 2 - 24", "4", 6),

    ("PBAL2", "Módena Plus (DVH)", "6200", "MARCO_HORIZONTAL", "A - 42", "2", 1),
    ("PBAL2", "Módena Plus (DVH)", "6201", "MARCO_VERTICAL", "H", "2", 2),
    ("PBAL2", "Módena Plus (DVH)", "6248", "HOJA_VERTICAL", "H - 79", "2", 3),
    ("PBAL2", "Módena Plus (DVH)", "6250", "HOJA_VERTICAL", "H - 79", "1", 4),
    ("PBAL2", "Módena Plus (DVH)", "6251", "HOJA_VERTICAL", "H - 79", "1", 5),
    ("PBAL2", "Módena Plus (DVH)", "6249", "HOJA_HORIZONTAL", "A / 2 - 24", "2", 6),
    ("PBAL2", "Módena Plus (DVH)", "6252", "HOJA_HORIZONTAL", "A / 2 - 24", "2", 7),
    ("PBAL2", "Módena Plus (DVH)", "6253", "OTRO", "A / 2 - 67", "2", 8),

    # ===== MÓDENA — ABRIR, BANDEROLA, PAÑO FIJO Y PUERTA DE REBATIR
    # Secciones 08-01 (doble contacto), 09-01 (banderola/ventiluz),
    # 10-01 (paño fijo) y 12-01 (puerta de rebatir) del catálogo Aluar.
    ("BAT1", "Módena", "6216", "MARCO_VERTICAL", "H", "2", 1),
    ("BAT1", "Módena", "6216", "MARCO_HORIZONTAL", "A", "2", 2),
    ("BAT1", "Módena", "6215", "HOJA_VERTICAL", "H - 39", "2", 3),
    ("BAT1", "Módena", "6215", "HOJA_HORIZONTAL", "A - 39", "2", 4),

    ("BAT2", "Módena", "6216", "MARCO_VERTICAL", "H", "2", 1),
    ("BAT2", "Módena", "6216", "MARCO_HORIZONTAL", "A", "2", 2),
    ("BAT2", "Módena", "6215", "HOJA_VERTICAL", "H - 39", "4", 3),
    ("BAT2", "Módena", "6215", "HOJA_HORIZONTAL", "A / 2 - 23", "4", 4),
    ("BAT2", "Módena", "6224", "OTRO", "H - 94", "1", 5),

    ("PVENT", "Módena", "6216", "MARCO_VERTICAL", "H", "2", 1),
    ("PVENT", "Módena", "6216", "MARCO_HORIZONTAL", "A", "2", 2),
    ("PVENT", "Módena", "6215", "HOJA_VERTICAL", "H - 39", "4", 3),
    ("PVENT", "Módena", "6215", "HOJA_HORIZONTAL", "A / 2 - 23", "4", 4),
    ("PVENT", "Módena", "6224", "OTRO", "H - 94", "1", 5),

    ("BAND", "Módena", "6216", "MARCO_VERTICAL", "H", "2", 1),
    ("BAND", "Módena", "6216", "MARCO_HORIZONTAL", "A", "2", 2),
    ("BAND", "Módena", "6215", "HOJA_VERTICAL", "H - 39", "2", 3),
    ("BAND", "Módena", "6215", "HOJA_HORIZONTAL", "A - 39", "2", 4),

    ("FIJO", "Módena", "6216", "MARCO_VERTICAL", "H", "2", 1),
    ("FIJO", "Módena", "6216", "MARCO_HORIZONTAL", "A", "2", 2),

    # Puerta de rebatir: sin umbral, sólo dintel. El zócalo 6219 y el travesaño
    # 6218 van a 90-90 entre las jambas de hoja, por eso el descuento mayor.
    ("PBAT1", "Módena", "6216", "MARCO_VERTICAL", "H", "2", 1),
    ("PBAT1", "Módena", "6216", "MARCO_HORIZONTAL", "A", "1", 2),
    ("PBAT1", "Módena", "6214", "HOJA_VERTICAL", "H - 24", "2", 3),
    ("PBAT1", "Módena", "6214", "HOJA_HORIZONTAL", "A - 39", "1", 4),
    ("PBAT1", "Módena", "6219", "OTRO", "A - 192", "1", 5),
    ("PBAT1", "Módena", "6218", "OTRO", "A - 192", "1", 6),

    # ===== A30 NEW - BATIENTE
    ("BAT1", "A30 New", "A30-MRC", "MARCO_HORIZONTAL", "A", "2", 1),
    ("BAT1", "A30 New", "A30-MRC", "MARCO_VERTICAL", "H", "2", 2),
    ("BAT1", "A30 New", "A30-HAB", "HOJA_HORIZONTAL", "(A - 90) / N", "2*N", 3),
    ("BAT1", "A30 New", "A30-HAB", "HOJA_VERTICAL", "H - 90", "2*N", 4),
    ("BAT1", "A30 New", "A30-CV", "CONTRAVIDRIO", "(A - 90) / N - 20", "2*N", 5),
    ("BAT1", "A30 New", "A30-CV", "CONTRAVIDRIO", "H - 110", "2*N", 6),
    ("BAT2", "A30 New", "A30-MRC", "MARCO_HORIZONTAL", "A", "2", 1),
    ("BAT2", "A30 New", "A30-MRC", "MARCO_VERTICAL", "H", "2", 2),
    ("BAT2", "A30 New", "A30-HAB", "HOJA_HORIZONTAL", "(A - 100) / N", "2*N", 3),
    ("BAT2", "A30 New", "A30-HAB", "HOJA_VERTICAL", "H - 90", "2*N", 4),

    # ===== GENÉRICAS (linea NULL): sirven de respaldo para cualquier línea
    ("FIJO", None, "MARCO", "MARCO_HORIZONTAL", "A", "2", 1),
    ("FIJO", None, "MARCO", "MARCO_VERTICAL", "H", "2", 2),
    ("FIJO", None, "CONTRAVIDRIO", "CONTRAVIDRIO", "A - 90", "2", 3),
    ("FIJO", None, "CONTRAVIDRIO", "CONTRAVIDRIO", "H - 90", "2", 4),
    ("COR2", None, "MARCO_SUP", "MARCO_HORIZONTAL", "A", "2", 1),
    ("COR2", None, "MARCO_LAT", "MARCO_VERTICAL", "H", "2", 2),
    ("COR2", None, "HOJA_VERT", "HOJA_VERTICAL", "H - 45", "2*N", 3),
    ("COR2", None, "HOJA_HORIZ", "HOJA_HORIZONTAL", "(A + 20) / N", "2*N", 4),
    ("COR3", None, "MARCO_SUP", "MARCO_HORIZONTAL", "A", "2", 1),
    ("COR3", None, "MARCO_LAT", "MARCO_VERTICAL", "H", "2", 2),
    ("COR3", None, "HOJA_VERT", "HOJA_VERTICAL", "H - 45", "2*N", 3),
    ("COR3", None, "HOJA_HORIZ", "HOJA_HORIZONTAL", "(A + 30) / N", "2*N", 4),
    ("COR4", None, "MARCO_SUP", "MARCO_HORIZONTAL", "A", "2", 1),
    ("COR4", None, "MARCO_LAT", "MARCO_VERTICAL", "H", "2", 2),
    ("COR4", None, "HOJA_VERT", "HOJA_VERTICAL", "H - 45", "2*N", 3),
    ("COR4", None, "HOJA_HORIZ", "HOJA_HORIZONTAL", "(A + 40) / N", "2*N", 4),
    ("PBAL2", None, "MARCO_SUP", "MARCO_HORIZONTAL", "A", "2", 1),
    ("PBAL2", None, "MARCO_LAT", "MARCO_VERTICAL", "H", "2", 2),
    ("PBAL2", None, "HOJA_VERT", "HOJA_VERTICAL", "H - 45", "2*N", 3),
    ("PBAL2", None, "HOJA_HORIZ", "HOJA_HORIZONTAL", "(A + 20) / N", "2*N", 4),
    ("PBAL4", None, "MARCO_SUP", "MARCO_HORIZONTAL", "A", "2", 1),
    ("PBAL4", None, "MARCO_LAT", "MARCO_VERTICAL", "H", "2", 2),
    ("PBAL4", None, "HOJA_VERT", "HOJA_VERTICAL", "H - 45", "2*N", 3),
    ("PBAL4", None, "HOJA_HORIZ", "HOJA_HORIZONTAL", "(A + 40) / N", "2*N", 4),
    ("BAT1", None, "MARCO", "MARCO_HORIZONTAL", "A", "2", 1),
    ("BAT1", None, "MARCO", "MARCO_VERTICAL", "H", "2", 2),
    ("BAT1", None, "HOJA", "HOJA_HORIZONTAL", "(A - 90) / N", "2*N", 3),
    ("BAT1", None, "HOJA", "HOJA_VERTICAL", "H - 90", "2*N", 4),
    ("BAT2", None, "MARCO", "MARCO_HORIZONTAL", "A", "2", 1),
    ("BAT2", None, "MARCO", "MARCO_VERTICAL", "H", "2", 2),
    ("BAT2", None, "HOJA", "HOJA_HORIZONTAL", "(A - 100) / N", "2*N", 3),
    ("BAT2", None, "HOJA", "HOJA_VERTICAL", "H - 90", "2*N", 4),
    ("BAND", None, "MARCO", "MARCO_HORIZONTAL", "A", "2", 1),
    ("BAND", None, "MARCO", "MARCO_VERTICAL", "H", "2", 2),
    ("BAND", None, "HOJA", "HOJA_HORIZONTAL", "A - 90", "2*N", 3),
    ("BAND", None, "HOJA", "HOJA_VERTICAL", "H - 90", "2*N", 4),
    ("PBAT1", None, "MARCO", "MARCO_HORIZONTAL", "A", "2", 1),
    ("PBAT1", None, "MARCO", "MARCO_VERTICAL", "H", "2", 2),
    ("PBAT1", None, "HOJA", "HOJA_HORIZONTAL", "(A - 90) / N", "2*N", 3),
    ("PBAT1", None, "HOJA", "HOJA_VERTICAL", "H - 90", "2*N", 4),
    ("PVENT", None, "MARCO", "MARCO_HORIZONTAL", "A", "2", 1),
    ("PVENT", None, "MARCO", "MARCO_VERTICAL", "H", "2", 2),
    ("PVENT", None, "HOJA", "HOJA_HORIZONTAL", "(A - 100) / N", "2*N", 3),
    ("PVENT", None, "HOJA", "HOJA_VERTICAL", "H - 90", "2*N", 4),
]

# ---------------------------------------------------------------------------
# Plantillas de tipologías fijas y de abrir.
#
# Estas tipologías comparten la misma lógica de despiece en todas las líneas y
# sólo cambia el prefijo del código de perfil, así que se generan por expansión
# en lugar de repetir la tabla línea por línea. Si una combinación
# (tipología, línea) ya está declarada explícitamente en FORMULAS, se respeta esa.
# ---------------------------------------------------------------------------

PREFIJOS_LINEA = {
    "Módena": "MD",
    "Herrero": "HE",
    "A30 New": "A30",
    "Módena Plus (DVH)": "MDP",
    "Ekonal": "EK",
}

# tipologia -> [(sufijo_perfil, funcion, formula_largo, cantidad, orden)]
PLANTILLAS = {
    "FIJO": [
        ("MRC", "MARCO_HORIZONTAL", "A", "2", 1),
        ("MRC", "MARCO_VERTICAL", "H", "2", 2),
        ("CV", "CONTRAVIDRIO", "A - 90", "2", 3),
        ("CV", "CONTRAVIDRIO", "H - 90", "2", 4),
    ],
    "BAT1": [
        ("MRC", "MARCO_HORIZONTAL", "A", "2", 1),
        ("MRC", "MARCO_VERTICAL", "H", "2", 2),
        ("HAB", "HOJA_HORIZONTAL", "(A - 90) / N", "2*N", 3),
        ("HAB", "HOJA_VERTICAL", "H - 90", "2*N", 4),
        ("CV", "CONTRAVIDRIO", "(A - 90) / N - 20", "2*N", 5),
        ("CV", "CONTRAVIDRIO", "H - 110", "2*N", 6),
    ],
    "BAT2": [
        ("MRC", "MARCO_HORIZONTAL", "A", "2", 1),
        ("MRC", "MARCO_VERTICAL", "H", "2", 2),
        ("HAB", "HOJA_HORIZONTAL", "(A - 100) / N", "2*N", 3),
        ("HAB", "HOJA_VERTICAL", "H - 90", "2*N", 4),
        ("CV", "CONTRAVIDRIO", "(A - 100) / N - 20", "2*N", 5),
        ("CV", "CONTRAVIDRIO", "H - 110", "2*N", 6),
    ],
    "BAND": [
        ("MRC", "MARCO_HORIZONTAL", "A", "2", 1),
        ("MRC", "MARCO_VERTICAL", "H", "2", 2),
        ("HAB", "HOJA_HORIZONTAL", "A - 90", "2*N", 3),
        ("HAB", "HOJA_VERTICAL", "H - 90", "2*N", 4),
        ("CV", "CONTRAVIDRIO", "A - 110", "2*N", 5),
        ("CV", "CONTRAVIDRIO", "H - 110", "2*N", 6),
    ],
    "PBAT1": [
        ("MRC", "MARCO_HORIZONTAL", "A", "2", 1),
        ("MRC", "MARCO_VERTICAL", "H", "2", 2),
        ("HAB", "HOJA_HORIZONTAL", "(A - 90) / N", "2*N", 3),
        ("HAB", "HOJA_VERTICAL", "H - 90", "2*N", 4),
        ("CV", "CONTRAVIDRIO", "(A - 90) / N - 20", "2*N", 5),
        ("CV", "CONTRAVIDRIO", "H - 110", "2*N", 6),
    ],
    "PVENT": [
        ("MRC", "MARCO_HORIZONTAL", "A", "2", 1),
        ("MRC", "MARCO_VERTICAL", "H", "2", 2),
        ("HAB", "HOJA_HORIZONTAL", "(A - 100) / N", "2*N", 3),
        ("HAB", "HOJA_VERTICAL", "H - 90", "2*N", 4),
        ("CV", "CONTRAVIDRIO", "(A - 100) / N - 20", "2*N", 5),
        ("CV", "CONTRAVIDRIO", "H - 110", "2*N", 6),
    ],
}


def _expandir_plantillas():
    """Genera las filas de FORMULAS que faltan a partir de PLANTILLAS."""
    ya_definidas = {(t, l) for t, l, *_resto in FORMULAS if l}
    codigos_validos = {(linea, cod) for linea, cod, _d, _p in PERFILES}

    generadas = []
    for tipologia, piezas in PLANTILLAS.items():
        for linea, prefijo in PREFIJOS_LINEA.items():
            if (tipologia, linea) in ya_definidas:
                continue
            filas = []
            for sufijo, funcion, largo, cantidad, orden in piezas:
                codigo = f"{prefijo}-{sufijo}"
                if (linea, codigo) not in codigos_validos:
                    filas = []  # falta algún perfil: se deja la fórmula genérica
                    break
                filas.append((tipologia, linea, codigo, funcion, largo, cantidad, orden))
            generadas.extend(filas)
    return generadas


FORMULAS += _expandir_plantillas()

# Fórmulas de vidrio: (tipologia, linea|None, ancho, alto, cantidad)
# AH = ancho de hoja, HH = alto de hoja (los calcula el motor de despiece).
FORMULAS_VIDRIO = [
    ("COR2", "Herrero", "AH - 55", "HH - 55", "N"),
    # Módena: AH = A/2-24 es la luz entre parantes y HH = H-79 el alto de hoja.
    # El vidrio suma el engargolado horizontal (7,5 mm por lado) y descuenta la
    # cara del zócalo y del cabezal (23,5 mm cada uno).
    # Verificar contra una hoja real: el engargolado cambia con el burlete
    # (B29 = 2 mm, B30 = 3 mm, B31 = 4 mm de cuña).
    ("COR2", "Módena", "AH + 15", "HH - 32", "N"),
    ("COR2", "Módena Plus (DVH)", "AH + 15", "HH - 32", "N"),
    ("PBAL2", "Módena", "AH + 15", "HH - 32", "N"),
    ("PBAL2", "Módena Plus (DVH)", "AH + 15", "HH - 32", "N"),
    ("COR2", None, "AH - 60", "HH - 60", "N"),
    ("COR3", None, "AH - 60", "HH - 60", "N"),
    ("COR4", None, "AH - 60", "HH - 60", "N"),
    ("PBAL2", None, "AH - 62", "HH - 62", "N"),
    ("PBAL4", None, "AH - 62", "HH - 62", "N"),
    ("FIJO", None, "A - 110", "H - 110", "1"),
    ("BAT1", None, "AH - 70", "HH - 70", "N"),
    ("BAT2", None, "AH - 70", "HH - 70", "N"),
    ("BAND", None, "AH - 70", "HH - 70", "N"),
    ("PBAT1", None, "AH - 70", "HH - 70", "N"),
    ("PVENT", None, "AH - 70", "HH - 70", "N"),
]

# ---------------------------------------------------------------------------
# Parámetros generales (clave, valor, descripción, grupo)
# ---------------------------------------------------------------------------

PARAMETROS = [
    # -- Mano de obra
    ("mo_valor_hora", 9000, "Valor de la hora-hombre ($)", "Mano de obra"),
    ("mo_operarios", 2, "Cantidad de operarios asignados", "Mano de obra"),
    ("mo_horas_por_m2", 0.85, "Horas estimadas por m² (para autocompletar)", "Mano de obra"),
    ("mo_por_m2_directo", 15000, "Alternativa: costo de fabricación por m² ($)", "Mano de obra"),
    # -- Logística
    ("log_recepcion", 0, "Costo de flete / recepción de materiales ($)", "Logística"),
    ("log_colocacion_m2", 20000, "Colocación en obra por m² ($) - sugerido", "Logística"),
    ("log_envio_fijo", 0, "Costo fijo de envío a obra ($)", "Logística"),
    # -- Opcionales
    ("premarco_modo", "m2", "Cálculo de premarco: 'm2' o 'ml' (perímetro)", "Opcionales"),
    ("premarco_m2", 6000, "Premarco por m² de abertura ($)", "Opcionales"),
    ("premarco_ml", 4500, "Premarco por metro lineal de perímetro ($)", "Opcionales"),
    ("mosquitero_m2", 9000, "Mosquitero por m² ($)", "Opcionales"),
    ("accesorios_por_hoja", 12000, "Accesorios por hoja si no hay kit definido ($)", "Opcionales"),
    # -- Comerciales
    ("margen_pct", 0.30, "Margen de ganancia sobre el costo (0.30 = 30%)", "Comercial"),
    ("iva_pct", 0.21, "Alícuota de IVA (0.21 = 21%)", "Comercial"),
    ("aplica_iva", 1, "Facturar con IVA por defecto (1 = sí)", "Comercial"),
    ("validez_dias", 15, "Validez de la oferta en días", "Comercial"),
    # -- Técnicos
    ("desperdicio_aluminio_pct", 0.05, "Desperdicio de barra de aluminio (0.05 = 5%)", "Técnico"),
    ("desperdicio_vidrio_pct", 0.10, "Desperdicio de plancha de vidrio (0.10 = 10%)", "Técnico"),
    ("modo_costeo_default", "kg", "Modo de costeo por defecto: 'kg' o 'm2'", "Técnico"),
    ("moneda", "$", "Símbolo monetario", "Técnico"),
    ("incluir_despiece_pdf", 0, "Adjuntar anexo de despiece en el PDF (1 = sí)", "Técnico"),
]

TERMINOS_DEFECTO = (
    "Forma de pago: 50% de anticipo al confirmar el pedido y 50% contra entrega.\n"
    "Los precios están sujetos a modificación sin previo aviso por variación de costos.\n"
    "El plazo de entrega comienza a regir a partir de la acreditación del anticipo."
)

OBSERVACIONES_DEFECTO = (
    "El precio no incluye albañilería, sellado exterior ni retiro de escombros.\n"
    "Plazo de entrega: 15 días hábiles a partir del anticipo del 50%.\n"
    "Garantía de perfiles y accesorios por 5 años contra defectos de fabricación.\n"
    "Las medidas deben ser verificadas en obra antes de la fabricación."
)


def sembrar(db) -> None:
    """Carga los datos iniciales. Se ejecuta una sola vez, al crear la base."""

    # --- Empresa
    db.execute(
        "INSERT OR IGNORE INTO empresa (id, razon_social, terminos, validez_dias, prefijo, "
        "proximo_numero, relleno_ceros) VALUES (1, ?, ?, 15, 'PRES', 1, 4)",
        ("Mi Carpintería de Aluminio", TERMINOS_DEFECTO),
    )

    # --- Parámetros
    for clave, valor, desc, grupo in PARAMETROS:
        db.set_parametro(clave, valor, desc, grupo)
    db.set_parametro("observaciones_defecto", OBSERVACIONES_DEFECTO,
                     "Observaciones generales precargadas en cada presupuesto", "Comercial")

    # --- Líneas y precios
    ids_linea: dict[str, int] = {}
    for nombre, modo, desc in LINEAS:
        ids_linea[nombre] = db.insertar(
            "lineas", {"nombre": nombre, "descripcion": desc, "modo_costeo": modo,
                       "extrusora": EXTRUSORAS.get(nombre, ""), "activo": 1}
        )

    for linea, color, precio_kg, precio_m2 in PRECIOS_LINEA:
        db.insertar(
            "linea_precios",
            {
                "linea_id": ids_linea[linea],
                "color": color,
                "precio_kg": precio_kg,
                "precio_m2_perfil": precio_m2,
                "activo": 1,
            },
        )

    # --- Perfiles
    for linea, codigo, desc, peso in PERFILES:
        db.insertar(
            "perfiles",
            {
                "linea_id": ids_linea[linea],
                "codigo": codigo,
                "descripcion": desc,
                "peso_kg_m": peso,
                "largo_barra_mm": 6000,
                "familia": familia_de(desc),
            },
        )

    # --- Vidrios
    for nombre, tipo, esp, precio, pa, ph, desp in VIDRIOS:
        db.insertar(
            "vidrios",
            {
                "nombre": nombre,
                "tipo": tipo,
                "espesor_mm": esp,
                "precio_m2": precio,
                "plancha_ancho_mm": pa,
                "plancha_alto_mm": ph,
                "precio_plancha": round(precio * pa * ph / 1_000_000, 2),
                "desperdicio_pct": desp,
                "activo": 1,
            },
        )

    # --- Accesorios
    ids_acc: dict[str, int] = {}
    for codigo, desc, unidad, precio in ACCESORIOS:
        ids_acc[codigo] = db.insertar(
            "accesorios",
            {"codigo": codigo, "descripcion": desc, "unidad": unidad, "precio": precio, "activo": 1},
        )

    # --- Tipologías
    for codigo, nombre, hojas, mosq, prem, esquema, horas in TIPOLOGIAS:
        db.insertar(
            "tipologias",
            {
                "codigo": codigo,
                "nombre": nombre,
                "hojas_default": hojas,
                "admite_mosquitero": mosq,
                "admite_premarco": prem,
                "esquema": esquema,
                "horas_por_m2": horas,
                "activo": 1,
            },
        )

    # --- Kits de accesorios
    for nombre, linea, tipologia, items in KITS:
        kit_id = db.insertar(
            "kits",
            {
                "nombre": nombre,
                "linea_id": ids_linea[linea],
                "tipologia_codigo": tipologia,
                "descripcion": f"Kit precargado para {tipologia}",
                "activo": 1,
            },
        )
        for codigo_acc, formula in items:
            db.insertar(
                "kit_items",
                {"kit_id": kit_id, "accesorio_id": ids_acc[codigo_acc], "cantidad_formula": formula},
            )

    # --- Fórmulas de despiece
    pesos = {
        (linea, cod): peso for linea, cod, _desc, peso in PERFILES
    }
    for tipologia, linea, perfil, funcion, largo, cant, orden in FORMULAS:
        db.insertar(
            "tipologia_formulas",
            {
                "tipologia_codigo": tipologia,
                "linea_id": ids_linea[linea] if linea else None,
                "perfil_codigo": perfil,
                "funcion": funcion,
                "formula_largo": largo,
                "cantidad_piezas": cant,
                "peso_kg_m": pesos.get((linea, perfil), 0.65),
                "orden": orden,
            },
        )

    for tipologia, linea, ancho, alto, cantidad in FORMULAS_VIDRIO:
        db.insertar(
            "vidrio_formulas",
            {
                "tipologia_codigo": tipologia,
                "linea_id": ids_linea[linea] if linea else None,
                "formula_ancho": ancho,
                "formula_alto": alto,
                "formula_cantidad": cantidad,
            },
        )
