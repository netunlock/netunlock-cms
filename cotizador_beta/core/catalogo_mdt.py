# -*- coding: utf-8 -*-
"""
Catálogos MDT — Metales del Talar: Sistema Clásica y Sistema Actual.

De dónde salen estos datos
--------------------------
De los dos catálogos oficiales del fabricante:

    Sistema Clásica   06-15, 128 páginas
    Sistema Actual    10-19, 178 páginas

* **Perfiles** — de la sección "Listado de Perfiles". En el catálogo Actual esa
  tabla tiene capa de texto y se leyó directo; se cotejó contra el PDF con
  coordenadas y coincidieron los 41 pesos comparables. En Clásica las páginas
  005, 006 y 008 son imágenes escaneadas y se leyeron mirando la página.

* **Medidas de corte** — de las tablas "Dimensiones de corte de perfiles". Las
  medidas se copian tal cual las da el fabricante: el catálogo usa A y H, que es
  exactamente lo que entiende el motor de fórmulas, así que no hay traducción de
  por medio donde se pueda colar un error.

Las dos correcciones que sí se hicieron
---------------------------------------
1. Varias tablas de marco traen **jambas con medida A y umbral/dintel con H**,
   al revés de como el mismo catálogo da el premarco dos filas más arriba. Se
   carga corregido —jamba sale del alto, umbral y dintel del ancho— y el renglón
   queda con la aclaración puesta.
2. Los perfiles que el catálogo marca en rojo como "Baja" se cargan igual, con
   la nota, porque el taller puede tener stock; pero se sabe que están
   discontinuados.

Premarco y contramarco son opciones (versión 2 del catálogo)
------------------------------------------------------------
Las tablas de la línea Actual traen el premarco y el contramarco junto al marco.
Cargadas tal cual, toda abertura de la línea los cortaba y los cobraba, los
llevara la obra o no. ``FORMULAS_MDT`` sigue guardando la medida como la publica
el fabricante; la condición se agrega encima, al sembrar, en
:func:`formulas_de_fabrica`:

    MT-0205   H+36   x 2    ->    si(PREMARCO, H+36, 0)    si(PREMARCO, 2, 0)

y cada tipología afectada declara las dos opciones en ``tipologia_variables``.
Una base que ya estaba sembrada no se resiembra: :func:`_actualizar_a_v2` cambia
sólo los renglones que siguen como los dejó la fábrica.

Tres tablas corregidas (versión 3 del catálogo)
-----------------------------------------------
Cada tabla de corte del catálogo tiene una columna de cantidad por variante
(A, B, C, D: marco recto o curvo, ventiluz o banderola, 1 o 2 hojas). La carga
original perdió esas columnas y agrupó las filas por nombre de pieza, así que en
tres tipologías quedaron activas piezas que no van juntas:

* AC-PF cortaba cuatro travesaños, que son opcionales y uno es del paño curvo;
* AC-BAND cortaba a la vez la hoja de borde recto y la de borde curvo, más el
  travesaño y el acople que sólo lleva combinada con un paño fijo;
* AC-PPOST cortaba sólo el premarco, cargado como marco, y nada más.

Se corrigieron contra las págs. 044, 063 y 093 del catálogo. AC-PPOST usa N
(las hojas de la abertura) para elegir entre sus columnas de 1 y 2 hojas, y su
cantidad de tablillas es MEDIDA DEDUCIDA. :func:`_actualizar_a_v3` lleva la
corrección a las bases ya sembradas sin pisar lo que el usuario editó.

El mosquitero de las corredizas también (versión 4)
---------------------------------------------------
Las corredizas de las dos líneas traen la hoja del mosquitero en su tabla, y se
cortaba siempre. La casilla «Incluye mosquitero» sumaba encima el mosquitero por
m²: se cobraba dos veces. Desde la versión 4 esos renglones —reconocidos por
perfil, en :data:`PERFILES_MOSQUITERO`— quedan condicionados a MOSQUITERO, que
decide la casilla, y pasan a la función ``MOSQUITERO``:

    MT-0255   HOJA_HORIZONTAL   (A/2)-7   x 2
      ->      MOSQUITERO        si(MOSQUITERO, (A/2)-7, 0)   si(MOSQUITERO, 2, 0)

Con su propia función, ``calculo.costo_mosquitero`` sabe que el despiece ya lo
trae, y ``despiece.medidas_de_hoja`` deja de tomar el zócalo del mosquitero como
ancho de hoja para el vidrio. :func:`_actualizar_a_v4` lleva las bases ya
sembradas, con el mismo cuidado que las versiones 2 y 3.

Qué NO trae
-----------
Precios. Ni de perfil, ni de vidrio, ni de accesorio: el catálogo del fabricante
no los publica y cada carpintería compra a su lista. Todo entra en **$0** y se
carga desde *Materiales y Costos*. Los kits y los vidrios quedan declarados y
elegibles para que el despiece salga completo desde el primer presupuesto.
"""

from __future__ import annotations

#: Largo de barra de las dos líneas, en mm. El catálogo da 6000, 6030 y 6150
#: según el perfil; 6000 es el que se compra y el que conviene como valor por
#: defecto. Se corrige por perfil desde Materiales y Costos si hace falta.
LARGO_BARRA = 6000

#: Las dos líneas que se dan de alta. (nombre, extrusora, descripción)
LINEAS_MDT = [
    ("MDT Clásica", "Metales del Talar",
     "Sistema Clásica — serie 900 / reforzada, Dúo y estándar"),
    ("MDT Actual", "Metales del Talar",
     "Sistema Actual — corredizas a 90° y 45°, rebatir, paño fijo"),
]

#: (código, kg/m, descripción, nota). Páginas 005 a 008 del catálogo Clásica.
PERFILES_CLASICA = [
    ("MT-0001", 0.907, 'Marco reforzado', ''),
    ("MT-0002", 0.505, 'Travesaño hoja corrediza', ''),
    ("MT-0003", 0.564, 'Parante lateral hoja corrediza', ''),
    ("MT-0004", 0.497, 'Parante central hoja corrediza', ''),
    ("MT-0005", 0.408, 'Hoja mosquitero', ''),
    ("MT-0006", 0.267, 'Tablilla postigón', ''),
    ("MT-0007", 0.697, 'Marco paño fijo', ''),
    ("MT-0010", 0.629, 'Marco puerta de rebatir', ''),
    ("MT-0011", 1.688, 'Travesaño puerta de rebatir', ''),
    ("MT-0017", 1.048, 'Umbral de puerta corrediza', ''),
    ("MT-0019", 0.381, 'Cierre central hojas corrediza', ''),
    ("MT-0023", 0.362, 'Tapa travesaño inferior', ''),
    ("MT-0024", 0.578, 'Marco puerta vaivén', ''),
    ("MT-0039", 1.285, 'Batiente puerta de rebatir', ''),
    ("MT-0040", 0.140, 'Tapacanto puerta de rebatir', 'Baja (discontinuado en el catálogo)'),
    ("MT-0042", 0.475, 'Cierre central puerta de rebatir', ''),
    ("MT-0049", 0.518, 'Acople tapajunta 75mm', 'Baja (discontinuado en el catálogo)'),
    ("MT-0053", 0.694, 'Parante lateral hoja corrediza', ''),
    ("MT-0054", 0.670, 'Parante central', ''),
    ("MT-0127", 0.378, 'Tablilla fija para postigón', ''),
    ("MT-0145", 1.326, 'Marco doble de abrir', ''),
    ("MT-0153", 0.186, 'Tablilla fija para postigón', ''),
    ("MT-0185", 1.339, 'Columna acople recto', ''),
    ("MT-0186", 1.204, 'Columna acople curvo', ''),
    ("MT-0187", 0.518, 'Apoyo rótula', ''),
    ("MT-0421", 0.729, 'Umbral y dintel hoja a 45°', ''),
    ("MT-0422", 0.313, 'Encuentro central hoja', ''),
    ("MT-0505", 0.481, 'Bastidor aireador', ''),
    ("MT-0507", 0.111, 'Contravidrio', 'Baja (discontinuado en el catálogo)'),
    ("MT-0509", 0.840, 'Hoja puerta de rebatir', ''),
    ("MT-0510", 1.207, 'Travesaño puerta de rebatir', ''),
    ("MT-0511", 0.103, 'Tapacanto puerta de rebatir', 'Baja (discontinuado en el catálogo)'),
    ("MT-0519", 0.262, 'Cierre central puerta de rebatir', ''),
    ("MT-0524", 0.672, 'Marco puerta de rebatir bisagra encolizada', ''),
    ("MT-0527", 0.581, 'Travesaño puerta de rebatir', ''),
    ("MT-0599", 0.605, 'Travesaño mosquitero', ''),
    ("MT-0687", 0.724, 'Travesaño paño fijo', ''),
    ("MT-0690", 0.486, 'Marco para hojas corredizas', ''),
    ("MT-0691", 1.323, 'Marco de tres guías', ''),
    ("MT-0805", 0.197, 'Contravidrio', ''),
    ("MT-0806", 0.116, 'Contravidrio', ''),
    ("MT-0808", 1.326, 'Travesaño hoja', ''),
    ("MT-0811", 0.761, 'Marco de puerta encolizada', 'Baja (discontinuado en el catálogo)'),
    ("MT-0812", 1.377, 'Travesaño inferior y superior', ''),
    ("MT-0813", 1.210, 'Batiente de hoja', ''),
    ("MT-0814", 0.270, 'Tapacanto central', ''),
    ("MT-0815", 0.189, 'Tapacanto vaivén', ''),
    ("MT-0822", 0.429, 'Batiente mosquitero', ''),
    ("MT-0824", 0.907, 'Parante puerta', ''),
    ("MT-0825", 0.429, 'Premarco simple 75 mm', ''),
    ("MT-0826", 0.259, 'Tablilla postigón', ''),
    ("MT-0829", 0.197, 'Contramarco', ''),
    ("MT-0839", 0.913, 'Parante puerta 36mm', ''),
    ("MT-0840", 0.926, 'Travesaño puerta', ''),
    ("MT-0841", 0.543, 'Marco puerta', ''),
    ("MT-0845", 1.069, 'Marco perimetral hoja', ''),
    ("MT-0846", 0.335, 'Marco de postigón para puerta', ''),
    ("MT-0850", 0.837, 'Premarco', ''),
    ("MT-0851", 0.224, 'Contramarco', ''),
    ("MT-0853", 0.829, 'Parante lateral reforzado', ''),
    ("MT-0854", 0.726, 'Parante central reforzado moderno', ''),
    ("MT-0901", 0.743, 'Marco liviano corrediza', ''),
    ("MT-0902", 0.432, 'Travesaño hoja corrediza', ''),
    ("MT-0903", 0.462, 'Parante lateral hoja corrediza', ''),
    ("MT-0904", 0.410, 'Parante central', ''),
    ("MT-0905", 0.313, 'Hoja mosquitero', ''),
    ("MT-0906", 0.186, 'Contramarco', ''),
    ("MT-0907", 0.524, 'Marco perimetral paño fijo', ''),
    ("MT-0908", 0.151, 'Contravidrio universal', ''),
    ("MT-0913", 0.621, 'Batiente hoja rebatir 25 mm', ''),
    ("MT-0914", 0.524, 'Marco ventana proyectante o banderola', ''),
    ("MT-0915", 0.281, 'Bisagra ventana proyectante o banderola', ''),
    ("MT-0916", 0.761, 'Marco ventana proyectante o banderola', ''),
    ("MT-0917", 0.513, 'Hoja inferior ventana banderola', ''),
    ("MT-0918", 0.513, 'Hoja superior ventana proyectante', ''),
    ("MT-0919", 0.273, 'Adaptador para DVH h. corredizas', ''),
    ("MT-0920", 0.419, 'Guía cortina común', ''),
    ("MT-0921", 0.413, 'Tapa cinta', ''),
    ("MT-0922", 0.478, 'Soporte tapa cinta', ''),
    ("MT-0925", 0.251, 'Porta contravidrio simple', ''),
    ("MT-0932", 0.243, 'Solapa central', ''),
    ("MT-0934", 0.192, 'Encuentro central puerta de rebatir', ''),
    ("MT-0944", 0.810, 'Travesaño reforzado', ''),
    ("MT-0945", 0.464, 'Marco dos guías con tapajunta', ''),
    ("MT-0949", 0.381, 'Acople tapajunta 75 mm', ''),
    ("MT-0950", 0.651, 'Marco recto', ''),
    ("MT-0951", 0.645, 'Parante hoja', ''),
    ("MT-0952", 0.621, 'Parante hoja recto', ''),
    ("MT-0953", 0.626, 'Marco inclinado', ''),
    ("MT-0954", 0.697, 'Premarco', 'Baja (discontinuado en el catálogo)'),
    ("MT-0960", 0.667, 'Puerta 35 mm - Travesaño angosto', ''),
    ("MT-0963", 0.494, 'Parante hoja postigón', ''),
    ("MT-0965", 1.069, 'Marco unificado postigón corrediza', ''),
    ("MT-0966", 0.189, 'Perfil de acople', ''),
    ("MT-0967", 0.429, 'Marco simple de 31mm', ''),
    ("MT-0969", 1.166, 'Marco unificado cuatro guías', ''),
    ("MT-0970", 0.367, 'Vidrio repartido', ''),
    ("MT-0971", 0.348, 'Travesaño vidrio repartido', ''),
    ("MT-0972", 0.224, 'Perimetral vidrio repartido', ''),
    ("MT-0973", 0.359, 'Marco paño fijo', ''),
    ("MT-0976", 0.389, 'Parante hoja de postigón', ''),
    ("MT-0978", 0.583, 'Batiente reforzado postigón', ''),
    ("MT-0979", 0.626, 'Marco puerta', ''),
    ("MT-0987", 1.312, 'Columna acople 45°', ''),
    ("MT-0988", 0.869, 'Columna rótula', ''),
    ("MT-0990", 0.486, 'Travesaño de mosquitero', ''),
    ("MT-0994", 0.929, 'Travesaño paño fijo', ''),
    ("MT-1110", 0.211, 'Hoja mosquitero', ''),
    ("MT-1148", 0.737, 'Guía cortina regulable', ''),
    ("MT-1573", 0.135, 'Hoja mosquitero fijo', ''),
    ("MT-1868", 1.053, 'Travesaño puerta de rebatir', ''),
    ("MT-2428", 0.381, 'Travesaño hoja corrediza', ''),
    ("MT-2582", 0.872, 'Hoja de rebatir', ''),
    ("MT-2610", 0.594, 'Marco liviano corrediza', ''),
    ("MT-2681", 0.294, 'Solapa central celosía', ''),
    ("MT-2682", 1.207, 'Batiente ancho puerta 36mm', ''),
    ("MT-2686", 0.302, 'Marco hoja secundaria puerta 36mm', ''),
    ("MT-2687", 0.243, 'Asiento tablilla MT-2688', ''),
    ("MT-2690", 0.116, 'Base moldura puerta placa', 'Baja (discontinuado en el catálogo)'),
    ("MT-2691", 0.159, 'Moldura puerta placa', ''),
    ("MT-2692", 0.162, 'Moldura puerta placa', ''),
    ("MT-2693", 0.786, 'Hoja celosía regulable', ''),
    ("MT-2694", 0.362, 'Hoja secundaria para marco MT-2686', ''),
    ("MT-2695", 0.173, 'Adaptador terminal celosía regulable', ''),
    ("MT-2696", 1.026, 'Batiente puerta de rebatir 36mm', ''),
    ("MT-2705", 0.529, 'Tablilla celosía regulable', ''),
    ("MT-2706", 0.305, 'Terminal corto celosía regulable', ''),
    ("MT-2707", 0.448, 'Terminal largo celosía regulable', ''),
    ("MT-2708", 0.151, 'Calce tapaluz celosía regulable', ''),
    ("MT-2721", 1.328, 'Travesaño reforzado celosía regulable', ''),
    ("MT-2722", 0.988, 'Travesaño celosía regulable', ''),
    ("MT-2733", 0.483, 'Batiente puerta rebatir', ''),
    ("MT-2734", 0.632, 'Batiente hoja', ''),
    ("MT-2740", 0.740, 'Marco puerta 36mm y celosía regulable', ''),
    ("MT-2765", 0.435, 'Adaptador celosía regulable', ''),
    ("MT-2794", 0.208, 'Contramarco', ''),
    ("MT-2901", 0.259, 'Contramarco', ''),
    ("MT-2907", 0.211, 'Tapajuntas puerta 44mm', ''),
    ("MT-2963", 0.359, 'Parante lateral hoja corrediza', ''),
    ("MT-2964", 0.338, 'Parante central', ''),
    ("MT-2965", 0.556, 'Marco puerta 2"', ''),
    ("MT-2966", 0.551, 'Marco de puerta 1,5"', ''),
]

#: (código, kg/m, descripción, nota). Listado de perfiles del catálogo Actual.
PERFILES_ACTUAL = [
    ("MT-0200", 1.266, 'Umbral y dintel corrediza', ""),
    ("MT-0201", 0.662, 'Jamba de marco', ""),
    ("MT-0202", 0.716, 'Marco 75 mm', ""),
    ("MT-0203", 0.651, 'Parante lateral de hoja para vidrio simple', ""),
    ("MT-0204", 0.705, 'Zócalo y cabezal de hoja', ""),
    ("MT-0205", 0.327, 'Premarco', ""),
    ("MT-0206", 0.184, 'Contramarco', ""),
    ("MT-0207", 0.613, 'Parante central vidrio simple', ""),
    ("MT-0208", 0.802, 'Parante central con asa vidrio simple', ""),
    ("MT-0209", 1.256, 'Zócalo alto', ""),
    ("MT-0210", 0.786, 'Marco ventana de abrir', ""),
    ("MT-0211", 0.848, 'Hoja ventana de abrir', ""),
    ("MT-0212", 0.313, 'Contravidrio 36mm', ""),
    ("MT-0213", 0.257, 'Perfil de acople plano', ""),
    ("MT-0214", 1.088, 'Jamba y cabezal hoja de puerta de rebatir', ""),
    ("MT-0215", 0.861, 'Hoja de abrir doble contacto', ""),
    ("MT-0216", 0.726, 'Marco ventana de abrir', ""),
    ("MT-0217", 0.292, 'Contravidrio 29mm', ""),
    ("MT-0218", 1.085, 'Travesaño hoja puerta de rebatir', ""),
    ("MT-0219", 1.647, 'Zócalo hoja puerta de rebatir', ""),
    ("MT-0220", 0.176, 'Contravidrio exterior puerta de rebatir', ""),
    ("MT-0221", 0.767, 'Travesaño angosto paño fijo', ""),
    ("MT-0222", 0.840, 'Travesaño ancho paño fijo', ""),
    ("MT-0223", 0.915, 'Encuentro central con cámara compensadora', ""),
    ("MT-0224", 0.780, 'Encuentro central de abrir', ""),
    ("MT-0225", 0.257, 'Contravidrio recto 22 mm', ""),
    ("MT-0226", 0.211, 'Contravidrio', ""),
    ("MT-0227", 0.864, 'Hoja Ventiluz', ""),
    ("MT-0228", 0.186, 'Tope mosquitero corrediza', ""),
    ("MT-0229", 0.764, 'Paño fijo curvo', ""),
    ("MT-0230", 0.213, 'Contravidrio curvo 29mm', ""),
    ("MT-0231", 0.159, 'Contravidrio curvo 15mm', ""),
    ("MT-0232", 0.181, 'Contravidrio curvo 22mm', ""),
    ("MT-0233", 0.135, 'Contravidrio curvo 8mm', ""),
    ("MT-0234", 0.886, 'Hoja curva de abrir con cámara compensadora', ""),
    ("MT-0235", 0.902, 'Hoja curva ventana de abrir doble contacto', ""),
    ("MT-0236", 0.902, 'Hoja ventiluz curva', ""),
    ("MT-0237", 0.181, 'Contravidrio curvo', ""),
    ("MT-0238", 0.184, 'Contravidrio 8mm', ""),
    ("MT-0239", 0.724, 'Travesaño hoja corrediza v. simple', ""),
    ("MT-0240", 1.652, 'Umbral y dintel marco tres guías', ""),
    ("MT-0241", 0.969, 'Jamba de marco de tres guías', ""),
    ("MT-0243", 0.545, 'Guía de cortina común', ""),
    ("MT-0244", 0.896, 'Guía de cortina barrio', ""),
    ("MT-0245", 0.613, 'Tapa cinta', ""),
    ("MT-0246", 0.286, 'Encuentro central corrediza 4 hojas (90º)', ""),
    ("MT-0248", 0.608, 'Parante lateral de hoja para DVH', ""),
    ("MT-0249", 0.632, 'Zócalo y cabezal de hoja para DVH', ""),
    ("MT-0250", 0.567, 'Parante central de hoja para DVH', ""),
    ("MT-0252", 1.188, 'Zócalo alto de hoja para DVH', ""),
    ("MT-0253", 0.667, 'Travesaño de hoja para DVH', ""),
    ("MT-0254", 0.289, 'Bisagra tapa cinta', ""),
    ("MT-0255", 0.389, 'Mosquitero', ""),
    ("MT-0256", 0.446, 'Travesaño mosquitero', ""),
    ("MT-0257", 0.235, 'Contravidrio curvo', ""),
    ("MT-0258", 1.061, 'Hoja ventana proyectante recta', ""),
    ("MT-0259", 0.748, 'Marco ventana proyectante', ""),
    ("MT-0260", 1.099, 'Hoja ventana proyectante curva', ""),
    ("MT-0261", 1.274, 'Columna de acople reforzada', ""),
    ("MT-0262", 0.680, 'Perfil de acople a 90°', ""),
    ("MT-0263", 1.550, 'Zócalo alto paño fijo', ""),
    ("MT-0264", 0.713, 'Travesaño paño fijo curvo', ""),
    ("MT-0265", 0.535, 'Columna acople 135°', ""),
    ("MT-0266", 0.383, 'Marco vidrio repartido de rebatir', ""),
    ("MT-0267", 0.348, 'Perimetral de vidrio repartido para corredizas', ""),
    ("MT-0268", 0.424, 'Travesaño vidrio repartido para corredizas', ""),
    ("MT-0269", 0.667, 'Zócalo bajo para paño fijo', ""),
    ("MT-0270", 0.653, 'Travesaño paño fijo', ""),
    ("MT-0272", 0.486, 'Adaptador para celosia', ""),
    ("MT-0273", 1.431, 'Travesaño postigón de rebatir', ""),
    ("MT-0274", 0.953, 'Hoja postigón de rebatir', ""),
    ("MT-0275", 0.883, 'Hoja postigón de rebatir', ""),
    ("MT-0276", 1.291, 'Travesaño postigón de rebatir', ""),
    ("MT-0277", 0.518, 'Tablilla regulable postigón', ""),
    ("MT-0280", 1.193, 'Marco a 45°', ""),
    ("MT-0281", 1.058, 'Marco ventana Guillotina', ""),
    ("MT-0282", 0.140, 'Tapa compensador Marco guillotina', ""),
    ("MT-0283", 0.537, 'Hoja ventana Guillotina', ""),
    ("MT-0284", 1.647, 'Marco de 3 guías corte a 45º', ""),
    ("MT-0315", 0.381, 'Solapa central', ""),
    ("MT-0316", 0.794, 'Refuerzo parante central', ""),
    ("MT-0324", 0.208, 'Encuentro central corrediza 4 hojas', ""),
    ("MT-0325", 0.824, 'Hoja perimetral para vidrio simple', ""),
    ("MT-0383", 0.797, 'Hoja perimetral para DVH', ""),
    ("MT-0415", 0.200, 'Contramarco', ""),
    ("MT-0906", 0.186, 'Contramarco', ""),
    ("MT-0995", 0.932, 'Revestimiento 7mm', ""),
    ("MT-1211", 0.999, 'Hoja ventana de abrir DVH sin contravidrios', ""),
    ("MT-1223", 1.280, 'Zócalo puerta', ""),
    ("MT-1257", 1.183, 'Hoja proyectante recta DVH', ""),
    ("MT-1258", 1.169, 'Hoja ventana proyectante recta', ""),
    ("MT-1272", 1.085, 'Travesaño puerta', ""),
    ("MT-1273", 1.185, 'Jamba', ""),
    ("MT-2220", 0.545, 'Premarco 56mm', ""),
    ("MT-2690", 0.100, 'Base moldura puerta placa', ""),
    ("MT-2691", 0.159, 'Moldura puerta placa', ""),
    ("MT-2692", 0.162, 'Moldura puerta placa', ""),
    ("MT-2695", 0.173, 'Adaptador hoja regulable', ""),
    ("MT-2705", 0.529, 'Tablilla celosia regulable', ""),
    ("MT-2706", 0.305, 'Terminal corto celosia', ""),
    ("MT-2707", 0.448, 'Terminal largo celosia', ""),
    ("MT-2708", 0.151, 'Tapaluz', ""),
    ("MT-3202", 0.348, 'Contramarco', ""),
    ("MT-6090", 0.159, 'Pasador', ""),
    ("MT-6535", 0.166, 'Contravidrio recto interior 15mm corte 45°', ""),
    ("MT-6329", 0.150, 'Contravidrio', ""),
]

#: Tipologías de cada línea, con su esquema y su cantidad de hojas.
#: (línea, código, nombre, esquema, hojas)
TIPOLOGIAS_MDT = [
    ('MDT Clásica', "CL-PF", 'Paño fijo serie 900', "fijo", 1),
    ('MDT Clásica', "CL-REB2", 'Ventana de rebatir 2 hojas serie 900', "batiente", 2),
    ('MDT Clásica', "CL-PMOSQ", 'Puerta mosquitero de rebatir 1 hoja', "batiente", 1),
    ('MDT Clásica', "CL-POST", 'Postigón de rebatir', "batiente", 2),
    ('MDT Clásica', "CL-COR2", 'Ventana corrediza 2 hojas a 90°', "corrediza", 2),
    ('MDT Clásica', "CL-COR4", 'Ventana corrediza 4 hojas a 90°', "corrediza", 4),
    ('MDT Clásica', "CL-PCOR2", 'Puerta corrediza 2 hojas a 90°', "corrediza", 2),
    ('MDT Clásica', "CL-COR3", 'Ventana corrediza 3 hojas a 90°', "corrediza", 3),
    ('MDT Clásica', "CL-PCOR3", 'Puerta corrediza 3 hojas a 90°', "corrediza", 3),
    ('MDT Clásica', "CL-CORPC", 'Corrediza 2 hojas con postigón corredizo', "corrediza", 2),
    ('MDT Clásica', "CL-CORPR", 'Corrediza 2 hojas con postigón de rebatir', "corrediza", 2),
    ('MDT Clásica', "CL-DUO2", 'Ventana corrediza Dúo 2 hojas a 45°', "corrediza", 2),
    ('MDT Clásica', "CL-DUO3", 'Ventana corrediza Dúo 3 hojas a 45°', "corrediza", 3),
    ('MDT Clásica', "CL-CORE2", 'Ventana corrediza estándar 2 hojas', "corrediza", 2),
    ('MDT Actual', "AC-PF", 'Paño fijo', "fijo", 1),
    ('MDT Actual', "AC-REB2", 'Ventana de rebatir 2 hojas', "batiente", 2),
    ('MDT Actual', "AC-REB1", 'Ventana de rebatir 1 hoja', "batiente", 1),
    ('MDT Actual', "AC-BAND", 'Banderola / Ventiluz', "banderola", 1),
    ('MDT Actual', "AC-PREB1", 'Puerta de rebatir 1 hoja', "puerta_batiente", 1),
    ('MDT Actual', "AC-PREB2", 'Puerta de rebatir 2 hojas', "puerta_batiente", 2),
    ('MDT Actual', "AC-DESP", 'Ventana desplazable', "corrediza", 2),
    ('MDT Actual', "AC-POST", 'Ventana postigón de rebatir', "batiente", 2),
    ('MDT Actual', "AC-PPOST", 'Puerta postigón de rebatir', "puerta_batiente", 2),
    ('MDT Actual', "AC-COR2", 'Ventana corrediza 2 hojas a 90°', "corrediza", 2),
    ('MDT Actual', "AC-COR4", 'Ventana corrediza 4 hojas a 90°', "corrediza", 4),
    ('MDT Actual', "AC-PCOR2", 'Puerta corrediza 2 hojas a 90°', "corrediza", 2),
    ('MDT Actual', "AC-PCOR4", 'Puerta corrediza 4 hojas a 90°', "corrediza", 4),
    ('MDT Actual', "AC-COR3", 'Ventana y puerta corrediza 3 hojas', "corrediza", 3),
    ('MDT Actual', "AC-COR245", 'Ventana corrediza 2 hojas a 45°', "corrediza", 2),
    ('MDT Actual', "AC-PCOR245", 'Puerta corrediza 2 hojas a 45°', "corrediza", 2),
]

#: (línea, tipología, perfil, función, fórmula, cantidad, corte, nota, orden).
#: La fórmula es la medida de corte tal cual la publica el fabricante.
FORMULAS_MDT = [
    ("Clásica", "CL-PF", "MT-0907", "MARCO_VERTICAL", "H", 2, "45-45", 'Marco perimetral paño fijo', 1),
    ("Clásica", "CL-PF", "MT-0907", "MARCO_HORIZONTAL", "A", 2, "", 'Marco perimetral paño fijo', 2),
    ("Clásica", "CL-PF", "MT-0971", "MARCO_HORIZONTAL", "A-44", 1, "90-90", 'Travesaño vidrio repartido', 3),
    ("Clásica", "CL-PF", "MT-0973", "MARCO_VERTICAL", "H", 2, "45-45", 'Marco paño fijo', 4),
    ("Clásica", "CL-PF", "MT-0973", "MARCO_HORIZONTAL", "A", 2, "45-45", 'Marco paño fijo', 5),
    ("Clásica", "CL-PF", "MT-0960", "MARCO_HORIZONTAL", "A-44", 1, "90-90", 'Travesaño angosto', 6),
    ("Clásica", "CL-PF", "MT-0994", "MARCO_HORIZONTAL", "A-44", 1, "90-90", 'Travesaño paño fijo', 7),
    ("Clásica", "CL-REB2", "MT-0902", "MARCO_HORIZONTAL", "A-112", 2, "90-90", '', 1),
    ("Clásica", "CL-REB2", "MT-0902", "HOJA_HORIZONTAL", "A", 4, "90-90", 'Zócalo / Cabezal', 2),
    ("Clásica", "CL-REB2", "MT-0967", "MARCO_VERTICAL", "H", 2, "45-45", 'Marco simple de 31 mm', 3),
    ("Clásica", "CL-REB2", "MT-0932", "OTRO", "H-52", 2, "90-90", 'Encuentro central', 4),
    ("Clásica", "CL-PMOSQ", "MT-0967", "MARCO_VERTICAL", "H", 2, "45-90", 'Marco simple 31 mm', 1),
    ("Clásica", "CL-PMOSQ", "MT-0967", "MARCO_HORIZONTAL", "A", 1, "45-45", 'Marco simple 31 mm', 2),
    ("Clásica", "CL-PMOSQ", "MT-0822", "MARCO_VERTICAL", "H-33", 2, "90-45", 'Batiente de mosquitero', 3),
    ("Clásica", "CL-PMOSQ", "MT-0822", "MARCO_VERTICAL", "H-52", 0, "45-45", 'Batiente de mosquitero · alternativa de MT-0822: poné la cantidad si usás este perfil', 4),
    ("Clásica", "CL-PMOSQ", "MT-0599", "MARCO_HORIZONTAL", "A-88", 1, "90-90", 'Travesaño', 5),
    ("Clásica", "CL-POST", "MT-0967", "MARCO_VERTICAL", "H", 2, "45-45", 'Marco simple 31mm', 1),
    ("Clásica", "CL-POST", "MT-0967", "MARCO_HORIZONTAL", "A", 2, "45-45", 'Marco simple 31mm', 2),
    ("Clásica", "CL-POST", "MT-0976", "HOJA_VERTICAL", "H-56", 4, "", 'Parante hoja de postigón', 3),
    ("Clásica", "CL-POST", "MT-0932", "OTRO", "H-56", 2, "90-90", 'Solapa central', 4),
    ("Clásica", "CL-POST", "MT-0902", "HOJA_HORIZONTAL", "A-115", 2, "", 'Zócalo y cabezal', 5),
    ("Clásica", "CL-POST", "MT-0006", "MARCO_HORIZONTAL", "A-102", 2, "90-90", 'Tablilla postigón', 6),
    ("Clásica", "CL-POST", "MT-0902", "MARCO_HORIZONTAL", "(A/2)-92", 4, "90-90", '', 7),
    ("Clásica", "CL-POST", "MT-0006", "MARCO_HORIZONTAL", "(A/2)-74", 0, "90-90", 'Tablilla postigón · alternativa de MT-0006: poné la cantidad si usás este perfil', 8),
    ("Clásica", "CL-COR2", "MT-2610", "MARCO_VERTICAL", "H", 2, "45-45", 'Marco liviano corrediza', 1),
    ("Clásica", "CL-COR2", "MT-0901", "MARCO_VERTICAL", "H", 0, "45-45", 'Marco liviano corrediza · alternativa de MT-2610: poné la cantidad si usás este perfil', 2),
    ("Clásica", "CL-COR2", "MT-2428", "HOJA_HORIZONTAL", "(A/2)-95", 1, "90-90", 'Travesaño de hoja corrediza', 3),
    ("Clásica", "CL-COR2", "MT-0902", "HOJA_HORIZONTAL", "(A/2)-100", 1, "90-90", 'Travesaño hoja corrediza', 4),
    ("Clásica", "CL-COR2", "MT-2963", "HOJA_VERTICAL", "H-63", 2, "90-90", 'Parante lateral', 5),
    ("Clásica", "CL-COR2", "MT-2964", "HOJA_VERTICAL", "H-63", 2, "90-90", 'Parante central', 6),
    ("Clásica", "CL-COR2", "MT-1203", "HOJA_VERTICAL", "H-69", 0, "45-45", 'Hoja mosquitero -Parante · no figura en el listado de este catálogo (ver Complementarios): poné el peso y la cantidad para usarlo', 7),
    ("Clásica", "CL-COR2", "MT-0905", "HOJA_HORIZONTAL", "(A/2)-44", 2, "45-45", 'Hoja mosquitero-Zócalo y cabezal', 8),
    ("Clásica", "CL-COR2", "MT-0920", "MARCO_VERTICAL", "H-115", 1, "90-90", 'Guia cortina común', 9),
    ("Clásica", "CL-COR2", "MT-0691", "MARCO_VERTICAL", "H", 1, "45-45", 'Marco de tres guias, jambas', 10),
    ("Clásica", "CL-COR2", "MT-0691", "MARCO_HORIZONTAL", "A", 2, "45-45", 'Marco de tres guías, umbral y dintel', 11),
    ("Clásica", "CL-COR2", "MT-0944", "MARCO_HORIZONTAL", "(A/2)-100", 1, "90-90", 'Travesaño reforzado', 12),
    ("Clásica", "CL-COR2", "MT-0972", "MARCO_HORIZONTAL", "(A/2)-103", 2, "45-45", 'Perimetral vidrio repartido', 13),
    ("Clásica", "CL-COR2", "MT-1982", "HOJA_HORIZONTAL", "A", 0, "90-90", 'Zócalo de cortina (Cat. "Complementarios) · no figura en el listado de este catálogo (ver Complementarios): poné el peso y la cantidad para usarlo', 14),
    ("Clásica", "CL-COR4", "MT-2610", "MARCO_VERTICAL", "H", 2, "45-45", 'Marco liviano corrediza', 1),
    ("Clásica", "CL-COR4", "MT-0901", "MARCO_VERTICAL", "H", 0, "45-45", 'Marco liviano corrediza · alternativa de MT-2610: poné la cantidad si usás este perfil', 2),
    ("Clásica", "CL-COR4", "MT-2963", "HOJA_VERTICAL", "H-63", 2, "90-90", 'Parante lateral', 3),
    ("Clásica", "CL-COR4", "MT-2964", "HOJA_VERTICAL", "H-63", 2, "90-90", 'Parante central', 4),
    ("Clásica", "CL-COR4", "MT-1203", "HOJA_VERTICAL", "H-69", 0, "45-45", 'Hoja mosquitero -Parante · no figura en el listado de este catálogo (ver Complementarios): poné el peso y la cantidad para usarlo', 5),
    ("Clásica", "CL-COR4", "MT-0920", "MARCO_VERTICAL", "H-115", 1, "90-90", 'Guia cortina común', 6),
    ("Clásica", "CL-COR4", "MT-0691", "MARCO_VERTICAL", "H", 1, "45-45", 'Marco de tres guias, jambas', 7),
    ("Clásica", "CL-COR4", "MT-0691", "MARCO_HORIZONTAL", "A", 2, "45-45", 'Marco de tres guías, umbral y dintel', 8),
    ("Clásica", "CL-COR4", "MT-1982", "HOJA_HORIZONTAL", "A", 0, "90-90", 'Zócalo de cortina (Cat. "Complementarios) · no figura en el listado de este catálogo (ver Complementarios): poné el peso y la cantidad para usarlo', 9),
    ("Clásica", "CL-PCOR2", "MT-0001", "MARCO_VERTICAL", "H", 2, "45-45", 'Marco reforzado', 1),
    ("Clásica", "CL-PCOR2", "MT-0001", "MARCO_HORIZONTAL", "A", 2, "", 'Marco reforzado', 2),
    ("Clásica", "CL-PCOR2", "MT-2610", "MARCO_VERTICAL", "H", 2, "45-45", 'Marco liviano corrediza', 3),
    ("Clásica", "CL-PCOR2", "MT-2610", "MARCO_HORIZONTAL", "A", 2, "45-45", 'Marco liviano corrediza', 4),
    ("Clásica", "CL-PCOR2", "MT-0053", "HOJA_VERTICAL", "H-66", 2, "90-90", 'Parante lateral reforzado', 5),
    ("Clásica", "CL-PCOR2", "MT-0054", "HOJA_VERTICAL", "H-66", 2, "90-90", 'Parante central reforzado', 6),
    ("Clásica", "CL-PCOR2", "MT-0901", "MARCO_VERTICAL", "H", 0, "45-45", 'Marco liviano corrediza · alternativa de MT-2610: poné la cantidad si usás este perfil', 7),
    ("Clásica", "CL-PCOR2", "MT-0901", "MARCO_HORIZONTAL", "A", 0, "45-45", 'Marco liviano corrediza · alternativa de MT-2610: poné la cantidad si usás este perfil', 8),
    ("Clásica", "CL-PCOR2", "MT-0902", "HOJA_HORIZONTAL", "(A/2)-100", 1, "90-90", 'Travesaño hoja corrediza', 9),
    ("Clásica", "CL-PCOR2", "MT-0905", "HOJA_VERTICAL", "H-75", 2, "45-45", 'Hoja mosquitero -parantes', 10),
    ("Clásica", "CL-PCOR2", "MT-0905", "HOJA_HORIZONTAL", "(A/2)-44", 2, "45-45", 'Hoja mosquitero -zocalo y cabezal', 11),
    ("Clásica", "CL-PCOR2", "MT-0017", "MARCO_HORIZONTAL", "A", 1, "90-90", 'Umbral de puerta corrediza', 12),
    ("Clásica", "CL-PCOR2", "MT-0971", "MARCO_VERTICAL", "H-60", 2, "90-90", 'Travesaño vidrio repartido', 13),
    ("Clásica", "CL-PCOR2", "MT-0972", "MARCO_HORIZONTAL", "(A/2)-103", 2, "45-45", 'Perimetral vidrio repartido', 14),
    ("Clásica", "CL-COR3", "MT-0691", "MARCO_VERTICAL", "H", 2, "", 'Marco de tres guías, jambas  [medida corregida: el catálogo la trae invertida]', 1),
    ("Clásica", "CL-COR3", "MT-0903", "HOJA_VERTICAL", "H-66", 2, "90-90", 'Parante lateral hoja corrediza', 2),
    ("Clásica", "CL-COR3", "MT-0904", "HOJA_VERTICAL", "H-66", 4, "90-90", 'Parante central', 3),
    ("Clásica", "CL-COR3", "MT-0944", "MARCO_HORIZONTAL", "(A/3)-72", 4, "90-90", 'Travesaño reforzado', 4),
    ("Clásica", "CL-COR3", "MT-0905", "HOJA_VERTICAL", "H-75", 2, "45-45", 'Hoja mosquitero-Parante', 5),
    ("Clásica", "CL-COR3", "MT-0921", "MARCO_VERTICAL", "H-115", 2, "90-90", 'Tapa cinta', 6),
    ("Clásica", "CL-COR3", "MT-0972", "MARCO_HORIZONTAL", "(A/3)-67", 2, "45-45", 'Perimetral vidrio repartido', 7),
    ("Clásica", "CL-PCOR3", "MT-0691", "MARCO_VERTICAL", "H", 2, "45-45", 'Marco de tres guías, jambas', 1),
    ("Clásica", "CL-PCOR3", "MT-0003", "HOJA_VERTICAL", "H-66", 2, "90-90", 'Parante lateral hoja corrediza', 2),
    ("Clásica", "CL-PCOR3", "MT-0944", "MARCO_HORIZONTAL", "(A/3)-72", 4, "90-90", 'Travesaño reforzado', 3),
    ("Clásica", "CL-PCOR3", "MT-0005", "HOJA_VERTICAL", "H-75", 2, "45-45", 'Hoja mosquitero-Parante', 4),
    ("Clásica", "CL-PCOR3", "MT-0921", "MARCO_VERTICAL", "H-115", 2, "90-90", 'Tapa cinta', 5),
    ("Clásica", "CL-PCOR3", "MT-0972", "MARCO_HORIZONTAL", "(A/3)-67", 2, "45-45", 'Perimetral vidrio repartido', 6),
    ("Clásica", "CL-CORPC", "MT-0969", "MARCO_VERTICAL", "H", 2, "45-45", 'Marco unificado rebatir', 1),
    ("Clásica", "CL-CORPC", "MT-0969", "MARCO_HORIZONTAL", "A", 2, "45-45", 'Marco unificado rebatir', 2),
    ("Clásica", "CL-CORPC", "MT-0904", "HOJA_VERTICAL", "H-66", 4, "90-90", 'Parante central', 3),
    ("Clásica", "CL-CORPC", "MT-0903", "HOJA_VERTICAL", "H-66", 4, "90-90", 'Parante lateral', 4),
    ("Clásica", "CL-CORPC", "MT-0902", "HOJA_HORIZONTAL", "(A/2)-100", 8, "90-90", 'Zócalo y cabezal', 5),
    ("Clásica", "CL-CORPC", "MT-0006", "MARCO_HORIZONTAL", "(A/2)-82", 2, "90-90", 'Tablilla postigón', 6),
    ("Clásica", "CL-CORPC", "MT-0905", "HOJA_VERTICAL", "H-75", 2, "45-45", 'Parante mosquitero', 7),
    ("Clásica", "CL-CORPC", "MT-0905", "HOJA_HORIZONTAL", "(A/2)-44", 0, "45-45", 'Zócalo y cabezal · alternativa de MT-0902: poné la cantidad si usás este perfil', 8),
    ("Clásica", "CL-CORPR", "MT-0965", "MARCO_VERTICAL", "H", 2, "45-45", 'Marco unificado postigón corredizo', 1),
    ("Clásica", "CL-CORPR", "MT-0965", "MARCO_HORIZONTAL", "A", 2, "45-45", 'Marco unificado postigón corredizo', 2),
    ("Clásica", "CL-CORPR", "MT-0976", "HOJA_VERTICAL", "H-56", 4, "90-90", 'Parante hoja de postigón', 3),
    ("Clásica", "CL-CORPR", "MT-0932", "OTRO", "H-56", 2, "90-90", 'Solapa central', 4),
    ("Clásica", "CL-CORPR", "MT-0902", "HOJA_HORIZONTAL", "(A/2)-92", 4, "90-90", 'Zócalo y cabezal', 5),
    ("Clásica", "CL-CORPR", "MT-0006", "MARCO_HORIZONTAL", "(A/2)-74", 2, "90-90", 'Tablilla postigón', 6),
    ("Clásica", "CL-CORPR", "MT-0904", "HOJA_VERTICAL", "H-66", 2, "90-90", 'Parante central', 7),
    ("Clásica", "CL-CORPR", "MT-0903", "HOJA_VERTICAL", "H-66", 2, "90-90", 'Parante lateral', 8),
    ("Clásica", "CL-CORPR", "MT-0902", "HOJA_HORIZONTAL", "(A/2)-100", 0, "90-90", 'Zócalo y cabezal · alternativa de MT-0902: poné la cantidad si usás este perfil', 9),
    ("Clásica", "CL-CORPR", "MT-0905", "HOJA_HORIZONTAL", "(A/2)-44", 0, "45-45", 'Zócalo y cabezal · alternativa de MT-0902: poné la cantidad si usás este perfil', 10),
    ("Clásica", "CL-DUO2", "MT-0901", "MARCO_VERTICAL", "H", 2, "", 'Marco liviano corrediza', 1),
    ("Clásica", "CL-DUO2", "MT-0901", "MARCO_HORIZONTAL", "A", 2, "45-45", 'Marco liviano corrediza', 2),
    ("Clásica", "CL-DUO2", "MT-0421", "HOJA_VERTICAL", "H-66", 4, "45-45", 'Parante lateral hoja corrediza', 3),
    ("Clásica", "CL-DUO2", "MT-0421", "MARCO_HORIZONTAL", "(A/2)-5", 4, "45-45", 'Umbral y dintel hoja corrediza', 4),
    ("Clásica", "CL-DUO2", "MT-0422", "HOJA_VERTICAL", "H-66", 2, "", 'Parante central', 5),
    ("Clásica", "CL-DUO2", "MT-0905", "HOJA_VERTICAL", "H-75", 2, "45-45", 'Hoja mosquitero-Parante', 6),
    ("Clásica", "CL-DUO2", "MT-0921", "MARCO_VERTICAL", "H-115", 2, "90-90", 'Tapa cinta', 7),
    ("Clásica", "CL-DUO3", "MT-0691", "MARCO_HORIZONTAL", "A-66", 2, "", 'Marco de tres guías, umbral y dintel  [medida corregida: el catálogo la trae invertida]', 1),
    ("Clásica", "CL-DUO3", "MT-0421", "MARCO_HORIZONTAL", "(A/3)+20", 6, "45-45", 'Umbral y dintel hoja corrediza', 2),
    ("Clásica", "CL-DUO3", "MT-0905", "HOJA_VERTICAL", "H-75", 2, "45-45", 'Hoja mosquitero-Parante', 3),
    ("Clásica", "CL-DUO3", "MT-0921", "MARCO_VERTICAL", "H-115", 2, "90-90", 'Tapa cinta', 4),
    ("Clásica", "CL-CORE2", "MT-2610", "MARCO_VERTICAL", "H", 2, "45-45", 'Marco de dos guías, jambas', 1),
    ("Clásica", "CL-CORE2", "MT-2610", "MARCO_HORIZONTAL", "A", 2, "", 'Marco de dos guías, umbral y dintel', 2),
    ("Clásica", "CL-CORE2", "MT-2963", "HOJA_VERTICAL", "H-63", 2, "45-45", 'Parante lateral hoja corrediza', 3),
    ("Clásica", "CL-CORE2", "MT-2964", "HOJA_VERTICAL", "H-63", 4, "90-90", 'Parante central', 4),
    ("Clásica", "CL-CORE2", "MT-1110", "HOJA_VERTICAL", "H-75", 2, "45-45", 'Hoja mosquitero-Parante', 5),
    ("Actual", "AC-PF", "MT-0205", "PREMARCO", "H+36", 2, "45-45", 'Jambas premarco', 1),
    ("Actual", "AC-PF", "MT-0205", "PREMARCO", "A+36", 2, "45-45", 'Umbral y dintel premarco', 2),
    ("Actual", "AC-PF", "MT-2220", "PREMARCO", "H+35", 0, "45-45", 'Jambas premarco · alternativa de MT-0205: poné la cantidad si usás este perfil', 3),
    ("Actual", "AC-PF", "MT-2220", "PREMARCO", "A+35", 0, "45-45", 'Umbral y dintel premarco · alternativa de MT-0205: poné la cantidad si usás este perfil', 4),
    ("Actual", "AC-PF", "MT-0206", "OTRO", "H+53", 2, "45-45", 'Jambas contramarco', 5),
    ("Actual", "AC-PF", "MT-0206", "OTRO", "A+53", 2, "45-45", 'Umbal y dintel contramarco', 6),
    ("Actual", "AC-PF", "MT-0906", "OTRO", "H+55", 0, "45-45", 'Jambas contramarco · alternativa de MT-0206: poné la cantidad si usás este perfil', 7),
    ("Actual", "AC-PF", "MT-0906", "OTRO", "A+55", 0, "45-45", 'Umbal y dintel contramarco · alternativa de MT-0206: poné la cantidad si usás este perfil', 8),
    ("Actual", "AC-PF", "MT-0216", "MARCO_VERTICAL", "H", 2, "45-45", 'Jambas marco recto  [medida corregida: el catálogo la trae invertida]', 9),
    ("Actual", "AC-PF", "MT-0216", "MARCO_HORIZONTAL", "A", 2, "45-45", 'Umbral y dintel marco recto  [medida corregida: el catálogo la trae invertida]', 10),
    ("Actual", "AC-PF", "MT-0229", "MARCO_VERTICAL", "H", 0, "45-45", 'Jambas marco curvo  [medida corregida: el catálogo la trae invertida] · alternativa de MT-0216: poné la cantidad si usás este perfil', 11),
    ("Actual", "AC-PF", "MT-0229", "MARCO_HORIZONTAL", "A", 0, "45-45", 'Umbral y dintel marco curvo  [medida corregida: el catálogo la trae invertida] · alternativa de MT-0216: poné la cantidad si usás este perfil', 12),
    ("Actual", "AC-PF", "MT-0202", "MARCO_VERTICAL", "H", 0, "45-45", 'Jambas marco 75 mm  [medida corregida: el catálogo la trae invertida] · alternativa de MT-0216: poné la cantidad si usás este perfil', 13),
    ("Actual", "AC-PF", "MT-0202", "MARCO_HORIZONTAL", "A", 0, "45-45", 'Umbral y dintel marco 75 mm  [medida corregida: el catálogo la trae invertida] · alternativa de MT-0216: poné la cantidad si usás este perfil', 14),
    # Travesaños de AC-PF (pág. 044). Son opcionales y van en cantidad 0: la nota
    # del catálogo aclara que sus medidas valen para UN solo travesaño, y el
    # MT-0264 es sólo del paño fijo curvo. Hasta la versión 2 se cortaban cuatro
    # (horizontal y vertical, recto y curvo). Corregido en la versión 3.
    ("Actual", "AC-PF", "MT-0270", "HOJA_HORIZONTAL", "A-51", 0, "90-90", 'Travesaño horizontal · opcional: poné 1 si lleva travesaño; la medida vale para uno solo (con dos, replantearla)', 15),
    ("Actual", "AC-PF", "MT-0270", "HOJA_VERTICAL", "H-51", 0, "90-90", 'Travesaño vertical · opcional: poné 1 si lleva travesaño; la medida vale para uno solo (con dos, replantearla)', 16),
    ("Actual", "AC-PF", "MT-0221", "HOJA_HORIZONTAL", "A-51", 0, "90-90", 'Travesaño horizontal angosto · alternativa de MT-0270: poné la cantidad si usás este perfil', 17),
    ("Actual", "AC-PF", "MT-0221", "HOJA_VERTICAL", "H-51", 0, "90-90", 'Travesaño vertical angosto · alternativa de MT-0270: poné la cantidad si usás este perfil', 18),
    ("Actual", "AC-PF", "MT-0222", "HOJA_HORIZONTAL", "A-51", 0, "90-90", 'Travesaño horizontal ancho · alternativa de MT-0270: poné la cantidad si usás este perfil', 19),
    ("Actual", "AC-PF", "MT-0222", "HOJA_VERTICAL", "H-51", 0, "90-90", 'Travesaño vertical ancho · alternativa de MT-0270: poné la cantidad si usás este perfil', 20),
    ("Actual", "AC-PF", "MT-0264", "HOJA_HORIZONTAL", "A-51", 0, "90-90", 'Travesaño horizontal PF curvo · sólo con el marco curvo MT-0229 · alternativa de MT-0270: poné la cantidad si usás este perfil', 21),
    ("Actual", "AC-PF", "MT-0264", "HOJA_VERTICAL", "H-51", 0, "90-90", 'Travesaño vertical PF curvo · sólo con el marco curvo MT-0229 · alternativa de MT-0270: poné la cantidad si usás este perfil', 22),
    ("Actual", "AC-REB2", "MT-0205", "PREMARCO", "H+36", 2, "45-45", 'Jambas premarco', 1),
    ("Actual", "AC-REB2", "MT-0205", "PREMARCO", "A+36", 2, "45-45", 'Umbral y dintel premarco', 2),
    ("Actual", "AC-REB2", "MT-0206", "OTRO", "H+54", 2, "45-45", 'Jambas contramarco', 3),
    ("Actual", "AC-REB2", "MT-0206", "OTRO", "A+54", 2, "45-45", 'Umbral y dintel contramarco', 4),
    ("Actual", "AC-REB2", "MT-0216", "MARCO_VERTICAL", "H", 2, "45-45", 'Jambas de marco', 5),
    ("Actual", "AC-REB2", "MT-0216", "MARCO_HORIZONTAL", "A", 2, "45-45", 'Umbral y dintel de marco', 6),
    ("Actual", "AC-REB2", "MT-0215", "MARCO_VERTICAL", "H-39", 2, "45-45", 'Jambas de hoja', 7),
    ("Actual", "AC-REB2", "MT-0215", "HOJA_HORIZONTAL", "A-39", 2, "45-45", 'Zócalo y cabezal de hoja', 8),
    ("Actual", "AC-REB2", "MT-0215", "HOJA_HORIZONTAL", "(A/2)-23", 0, "45-45", 'Zócalo y cabezal de hoja · alternativa de MT-0215: poné la cantidad si usás este perfil', 9),
    ("Actual", "AC-REB2", "MT-0224", "OTRO", "H-94", 2, "90-90", 'Encuentro central de hoja', 10),
    ("Actual", "AC-REB2", "MT-2220", "PREMARCO", "H+36", 0, "45-45", 'Jambas premarco · alternativa de MT-0205: poné la cantidad si usás este perfil', 11),
    ("Actual", "AC-REB2", "MT-2220", "PREMARCO", "A+36", 0, "45-45", 'Umbral y dintel premarco · alternativa de MT-0205: poné la cantidad si usás este perfil', 12),
    ("Actual", "AC-REB2", "MT-0906", "OTRO", "H+54", 0, "45-45", 'Jambas contramarco · alternativa de MT-0206: poné la cantidad si usás este perfil', 13),
    ("Actual", "AC-REB2", "MT-0206", "OTRO", "A+54", 0, "45-45", 'Umbral y dintel contramarco · alternativa de MT-0206: poné la cantidad si usás este perfil', 14),
    ("Actual", "AC-REB2", "MT-0202", "MARCO_VERTICAL", "H", 0, "45-45", 'Jambas de marco · alternativa de MT-0216: poné la cantidad si usás este perfil', 15),
    ("Actual", "AC-REB2", "MT-0202", "MARCO_HORIZONTAL", "A", 0, "45-45", 'Umbral y dintel de marco · alternativa de MT-0216: poné la cantidad si usás este perfil', 16),
    ("Actual", "AC-REB2", "MT-0215", "MARCO_VERTICAL", "H-47", 0, "45-45", 'Jambas de hoja · alternativa de MT-0215: poné la cantidad si usás este perfil', 17),
    ("Actual", "AC-REB2", "MT-0215", "HOJA_HORIZONTAL", "A-47", 0, "45-45", 'Zócalo y cabezal de hoja · alternativa de MT-0215: poné la cantidad si usás este perfil', 18),
    ("Actual", "AC-REB2", "MT-0215", "HOJA_HORIZONTAL", "(A/2)-27", 0, "45-45", 'Zócalo y cabezal de hoja · alternativa de MT-0215: poné la cantidad si usás este perfil', 19),
    ("Actual", "AC-REB2", "MT-0224", "OTRO", "H-102", 0, "90-90", 'Encuentro central de hoja · alternativa de MT-0224: poné la cantidad si usás este perfil', 20),
    ("Actual", "AC-REB1", "MT-2220", "PREMARCO", "H+36", 2, "45-45", 'Jambas premarco', 1),
    ("Actual", "AC-REB1", "MT-2220", "PREMARCO", "A+36", 2, "45-45", 'Umbral y dintel premarco', 2),
    ("Actual", "AC-REB1", "MT-0906", "OTRO", "H+54", 2, "45-45", 'Jambas contramarco', 3),
    ("Actual", "AC-REB1", "MT-0206", "OTRO", "A+54", 2, "45-45", 'Umbral y dintel contramarco', 4),
    ("Actual", "AC-REB1", "MT-0202", "MARCO_VERTICAL", "H", 2, "45-45", 'Jambas de marco', 5),
    ("Actual", "AC-REB1", "MT-0202", "MARCO_HORIZONTAL", "A", 2, "45-45", 'Umbral y dintel de marco', 6),
    ("Actual", "AC-REB1", "MT-0215", "MARCO_VERTICAL", "H-47", 2, "45-45", 'Jambas de hoja', 7),
    ("Actual", "AC-REB1", "MT-0215", "HOJA_HORIZONTAL", "A-47", 2, "45-45", 'Zócalo y cabezal de hoja', 8),
    ("Actual", "AC-REB1", "MT-0215", "HOJA_HORIZONTAL", "(A/2)-27", 0, "45-45", 'Zócalo y cabezal de hoja · alternativa de MT-0215: poné la cantidad si usás este perfil', 9),
    ("Actual", "AC-REB1", "MT-0224", "OTRO", "H-102", 2, "90-90", 'Encuentro central de hoja', 10),
    ("Actual", "AC-BAND", "MT-0205", "PREMARCO", "H+36", 2, "45-45", 'Jambas premarco', 1),
    ("Actual", "AC-BAND", "MT-0205", "PREMARCO", "A+36", 2, "45-45", 'Umbral y dintel premarco', 2),
    ("Actual", "AC-BAND", "MT-0206", "OTRO", "H+54", 2, "45-45", 'Jambas contramarco', 3),
    ("Actual", "AC-BAND", "MT-0206", "OTRO", "A+54", 2, "45-45", 'Umbal y dintel contramarco', 4),
    ("Actual", "AC-BAND", "MT-0216", "MARCO_VERTICAL", "H", 2, "45-45", 'Jambas de marco', 5),
    ("Actual", "AC-BAND", "MT-0216", "MARCO_HORIZONTAL", "A", 2, "45-45", 'Umbral y dintel marco', 6),
    # Hojas de AC-BAND (pág. 063). La tabla tiene cuatro columnas: A ventiluz
    # borde recto, B ventiluz borde curvo, C banderola borde recto y D banderola
    # borde curvo. Queda activa la A y las otras tres son alternativas: hasta la
    # versión 2 se cortaban a la vez la hoja recta y la curva. El travesaño y el
    # acople sólo se usan combinada con un paño fijo (págs. 067 y 071), y los
    # zócalos de MT-2210 y MT-1211 faltaban. Corregido en la versión 3.
    ("Actual", "AC-BAND", "MT-0227", "MARCO_VERTICAL", "H-39", 2, "45-45", 'Jambas de hoja ventiluz borde recto', 7),
    ("Actual", "AC-BAND", "MT-0227", "HOJA_HORIZONTAL", "A-39", 2, "45-45", 'Zócalo y cabezal de hoja ventiluz borde recto', 8),
    ("Actual", "AC-BAND", "MT-0236", "MARCO_VERTICAL", "H-39", 0, "45-45", 'Jambas de hoja ventiluz borde curvo · alternativa de MT-0227: poné la cantidad si usás este perfil', 9),
    ("Actual", "AC-BAND", "MT-0236", "HOJA_HORIZONTAL", "A-39", 0, "45-45", 'Zócalo y cabezal de hoja ventiluz borde curvo · alternativa de MT-0227: poné la cantidad si usás este perfil', 10),
    ("Actual", "AC-BAND", "MT-0215", "MARCO_VERTICAL", "H-39", 0, "45-45", 'Jambas de hoja banderola borde recto · alternativa de MT-0227: poné la cantidad si usás este perfil', 11),
    ("Actual", "AC-BAND", "MT-0215", "HOJA_HORIZONTAL", "A-39", 0, "45-45", 'Zócalo y cabezal de hoja banderola borde recto · alternativa de MT-0227: poné la cantidad si usás este perfil', 12),
    ("Actual", "AC-BAND", "MT-0235", "MARCO_VERTICAL", "H-39", 0, "45-45", 'Jambas de hoja banderola borde curvo · alternativa de MT-0227: poné la cantidad si usás este perfil', 13),
    ("Actual", "AC-BAND", "MT-0235", "HOJA_HORIZONTAL", "A-39", 0, "45-45", 'Zócalo y cabezal de hoja banderola borde curvo · alternativa de MT-0227: poné la cantidad si usás este perfil', 14),
    ("Actual", "AC-BAND", "MT-2210", "MARCO_VERTICAL", "H-39", 0, "45-45", 'Jambas de hoja banderola borde curvo v/s  [medida corregida: el catálogo la trae invertida] · el catálogo no publica su peso por metro: poné el peso y la cantidad para usarlo', 15),
    ("Actual", "AC-BAND", "MT-1211", "MARCO_VERTICAL", "H-39", 0, "45-45", 'Jambas de hoja banderola borde curvo DVH  [medida corregida: el catálogo la trae invertida] · alternativa de MT-0227: poné la cantidad si usás este perfil', 16),
    ("Actual", "AC-BAND", "MT-0221", "HOJA_HORIZONTAL", "A-34", 0, "90-90", 'Travesaño horizontal angosto · sólo combinada con paño fijo en un mismo marco (corte 11-11, pág. 071): poné la cantidad si la combinás', 17),
    ("Actual", "AC-BAND", "MT-0213", "MARCO_HORIZONTAL", "A", 0, "90-90", 'Acople plano  [medida corregida: el catálogo dice H, pero el acople va horizontal entre la ventiluz y el paño fijo] · sólo combinada con paño fijo en dos marcos (corte 9-9, pág. 067): poné la cantidad si la combinás', 18),
    ("Actual", "AC-BAND", "MT-2210", "HOJA_HORIZONTAL", "A-39", 0, "45-45", 'Zócalo y cabezal de hoja banderola borde curvo v/s · el catálogo no publica su peso por metro: poné el peso y la cantidad para usarlo', 19),
    ("Actual", "AC-BAND", "MT-1211", "HOJA_HORIZONTAL", "A-39", 0, "45-45", 'Zócalo y cabezal de hoja banderola borde curvo DVH · alternativa de MT-0227: poné la cantidad si usás este perfil', 20),
    ("Actual", "AC-PREB1", "MT-0205", "PREMARCO", "H+18", 2, "45-90", 'Jambas premarco', 1),
    ("Actual", "AC-PREB1", "MT-0205", "PREMARCO", "A+36", 2, "45-45", 'Dintel premarco', 2),
    ("Actual", "AC-PREB1", "MT-0206", "OTRO", "A+54", 1, "45-45", 'Dintel contramarco', 3),
    ("Actual", "AC-PREB1", "MT-0216", "MARCO_VERTICAL", "H", 2, "45-90", 'Jambas marco', 4),
    ("Actual", "AC-PREB1", "MT-0216", "MARCO_HORIZONTAL", "A", 1, "45-45", 'Dintel marco', 5),
    ("Actual", "AC-PREB1", "MT-0214", "MARCO_VERTICAL", "H-24", 2, "45-90", 'Jambas de hojas', 6),
    ("Actual", "AC-PREB1", "MT-1273", "MARCO_VERTICAL", "H-24", 0, "45-90", 'Jambas de hojas · alternativa de MT-0214: poné la cantidad si usás este perfil', 7),
    ("Actual", "AC-PREB1", "MT-0214", "HOJA_HORIZONTAL", "A-39", 1, "45-45", 'Cabezal de hoja', 8),
    ("Actual", "AC-PREB1", "MT-1273", "HOJA_HORIZONTAL", "A-39", 0, "45-45", 'Cabezal de hoja · alternativa de MT-0214: poné la cantidad si usás este perfil', 9),
    ("Actual", "AC-PREB1", "MT-1272", "HOJA_HORIZONTAL", "A-192", 1, "90-90", 'Travesaño de hoja', 10),
    ("Actual", "AC-PREB1", "MT-0218", "HOJA_HORIZONTAL", "A-192", 0, "90-90", 'Travesaño de hoja · alternativa de MT-1272: poné la cantidad si usás este perfil', 11),
    ("Actual", "AC-PREB1", "MT-0219", "HOJA_HORIZONTAL", "A-192", 1, "90-90", 'Zócalo de hoja', 12),
    ("Actual", "AC-PREB1", "MT-1223", "HOJA_HORIZONTAL", "A-192", 0, "90-90", 'Zócalo de hoja · alternativa de MT-0219: poné la cantidad si usás este perfil', 13),
    ("Actual", "AC-PREB2", "MT-0205", "PREMARCO", "H+18", 2, "45-90", 'Jambas premarco', 1),
    ("Actual", "AC-PREB2", "MT-0205", "PREMARCO", "A+36", 1, "45-45", 'Dintel premarco', 2),
    ("Actual", "AC-PREB2", "MT-0206", "OTRO", "A+54", 2, "45-45", 'Dintel contramarco', 3),
    ("Actual", "AC-PREB2", "MT-0216", "MARCO_VERTICAL", "H", 2, "45-90", 'Jambas marco', 4),
    ("Actual", "AC-PREB2", "MT-0216", "MARCO_HORIZONTAL", "A", 1, "45-45", 'Dintel marco', 5),
    ("Actual", "AC-PREB2", "MT-0214", "MARCO_VERTICAL", "H-24", 2, "45-90", 'Jambas de hojas', 6),
    ("Actual", "AC-PREB2", "MT-1273", "MARCO_VERTICAL", "H-24", 0, "45-90", 'Jambas de hojas · alternativa de MT-0214: poné la cantidad si usás este perfil', 7),
    ("Actual", "AC-PREB2", "MT-0214", "HOJA_HORIZONTAL", "(A/2)-23", 2, "45-45", 'Cabezal hoja', 8),
    ("Actual", "AC-PREB2", "MT-1273", "HOJA_HORIZONTAL", "(A/2)-23", 2, "45-45", 'Cabezal de hoja', 9),
    ("Actual", "AC-PREB2", "MT-1272", "HOJA_HORIZONTAL", "(A/2)-175", 2, "90-90", 'Travesaño de hoja', 10),
    ("Actual", "AC-PREB2", "MT-0218", "HOJA_HORIZONTAL", "(A/2)-175", 0, "90-90", 'Travesaño de hoja · alternativa de MT-1272: poné la cantidad si usás este perfil', 11),
    ("Actual", "AC-PREB2", "MT-0219", "HOJA_HORIZONTAL", "(A/2)-175", 2, "90-90", 'Zócalo de hoja', 12),
    ("Actual", "AC-PREB2", "MT-1223", "HOJA_HORIZONTAL", "(A/2)-175", 0, "90-90", 'Zócalo de hoja · alternativa de MT-0219: poné la cantidad si usás este perfil', 13),
    ("Actual", "AC-PREB2", "MT-0224", "OTRO", "H-52", 1, "90-90", 'Encuentro central de hojas', 14),
    ("Actual", "AC-DESP", "MT-0205", "PREMARCO", "H+36", 2, "45-45", 'Jambas premarco', 1),
    ("Actual", "AC-DESP", "MT-0205", "PREMARCO", "A+36", 2, "45-45", 'Umbral y dintel premarco', 2),
    ("Actual", "AC-DESP", "MT-0206", "OTRO", "H+53", 2, "45-45", 'Jambas contramarco', 3),
    ("Actual", "AC-DESP", "MT-0206", "OTRO", "A+53", 2, "45-45", 'Umbal y dintel contramarco', 4),
    ("Actual", "AC-DESP", "MT-0259", "MARCO_VERTICAL", "H", 2, "45-45", 'Jambas marco', 5),
    ("Actual", "AC-DESP", "MT-0259", "MARCO_HORIZONTAL", "A", 2, "45-45", 'Umbral y dintel marco', 6),
    ("Actual", "AC-DESP", "MT-1257", "MARCO_VERTICAL", "H-33", 2, "45-45", 'Jambas de hoja', 7),
    ("Actual", "AC-DESP", "MT-1257", "HOJA_HORIZONTAL", "A-33", 2, "45-45", 'Zócalo y cabezal de hoja', 8),
    ("Actual", "AC-DESP", "MT-0260", "MARCO_VERTICAL", "H-33", 0, "45-45", 'Jambas de hoja · alternativa de MT-1257: poné la cantidad si usás este perfil', 9),
    ("Actual", "AC-DESP", "MT-0260", "HOJA_HORIZONTAL", "A-33", 0, "45-45", 'Zócalo y cabezal de hoja · alternativa de MT-1257: poné la cantidad si usás este perfil', 10),
    ("Actual", "AC-POST", "MT-0205", "PREMARCO", "H+36", 2, "45-45", 'Jambas premarco', 1),
    ("Actual", "AC-POST", "MT-0205", "PREMARCO", "A+36", 2, "45-45", 'Dintel premarco', 2),
    ("Actual", "AC-POST", "MT-0206", "OTRO", "H+54", 2, "45-45", 'Jambas contramarco', 3),
    ("Actual", "AC-POST", "MT-0206", "OTRO", "A+54", 2, "45-45", 'Dintel umbral contramarco', 4),
    ("Actual", "AC-POST", "MT-0216", "MARCO_VERTICAL", "H", 2, "45-45", 'Jambas de marco', 5),
    ("Actual", "AC-POST", "MT-0216", "MARCO_HORIZONTAL", "A", 2, "45-45", 'Dintel marco', 6),
    ("Actual", "AC-POST", "MT-0274", "MARCO_VERTICAL", "H-40", 2, "45-45", 'Jambas de hoja', 7),
    ("Actual", "AC-POST", "MT-0274", "HOJA_HORIZONTAL", "A-40", 2, "45-45", 'Zócalo y cabezal de hoja', 8),
    ("Actual", "AC-POST", "MT-0274", "MARCO_HORIZONTAL", "(A/2)-23", 2, "45-45", '', 9),
    ("Actual", "AC-POST", "MT-0224", "OTRO", "H-94", 1, "90-90", 'Encuentro central', 10),
    ("Actual", "AC-POST", "MT-2705", "MARCO_HORIZONTAL", "A-163", 2, "90-90", 'Tablilla', 11),
    ("Actual", "AC-POST", "MT-2705", "MARCO_HORIZONTAL", "(A/2)-146", 0, "90-90", 'alternativa de MT-0274: poné la cantidad si usás este perfil', 12),
    ("Actual", "AC-POST", "MT-2695", "MARCO_HORIZONTAL", "A-150", 2, "90-90", 'Adaptador terminal celosia regulable', 13),
    # AC-PPOST — Puerta postigón de rebatir (pág. 093). Hasta la versión 2 se
    # cortaban sólo dos piezas del PREMARCO, cargadas como marco, y todo lo demás
    # estaba en 0 como "alternativa de MT-0205". Corregida en la versión 3:
    #
    # * La tabla trae dos columnas: postigón de 1 hoja y de 2 hojas. Un solo
    #   juego de renglones sirve para las dos porque la cantidad mira N, las
    #   «Hojas (N)» de la abertura: con N = 1 corta la columna de 1 hoja y con
    #   2 o más, la de 2. si(N == 1, 2, 4) se lee "2 con una hoja, 4 con dos".
    # * Premarco (MT-0205) y contramarco (MT-0206) quedan como opciones de la
    #   abertura, por las mismas dos reglas que el resto de la línea.
    # * El travesaño va en 0: el detalle de la pág. 094 lo dibuja como
    #   «Opción con travesaño».
    # * Las tablillas el catálogo no las cuenta ("según altura del postigón"):
    #   la cantidad es MEDIDA DEDUCIDA, con el paso de encastre a encastre de la
    #   MT-2705 (67 mm, pág. 028) y lo que ocupan el adaptador y los terminales
    #   en el corte de la pág. 094 (360 mm).
    # * Los renglones que faltaban van al final (orden 22 a 27): así una base ya
    #   sembrada los recibe sin renumerar los que tiene.
    ("Actual", "AC-PPOST", "MT-0205", "PREMARCO", "H+18", 2, "45-90", 'Jambas premarco', 1),
    ("Actual", "AC-PPOST", "MT-0205", "PREMARCO", "A+36", 1, "45-45", 'Dintel premarco', 2),
    ("Actual", "AC-PPOST", "MT-0206", "OTRO", "A+54", 1, "45-45", 'Dintel contramarco', 3),
    ("Actual", "AC-PPOST", "MT-0216", "MARCO_VERTICAL", "H", 2, "45-90", 'Jambas marco', 4),
    ("Actual", "AC-PPOST", "MT-0216", "MARCO_HORIZONTAL", "A", 1, "45-45", 'Dintel marco', 5),
    ("Actual", "AC-PPOST", "MT-0214", "MARCO_VERTICAL", "H-24", "si(N == 1, 2, 4)", "45-90", 'Jambas de hojas · 2 por hoja', 6),
    ("Actual", "AC-PPOST", "MT-0214", "HOJA_HORIZONTAL", "A-39", "si(N == 1, 1, 0)", "45-45", 'Cabezal de hoja · postigón de 1 hoja', 7),
    ("Actual", "AC-PPOST", "MT-0214", "HOJA_HORIZONTAL", "(A/2)-23", "si(N == 1, 0, 2)", "45-45", 'Cabezal de hoja · postigón de 2 hojas', 8),
    ("Actual", "AC-PPOST", "MT-0218", "HOJA_HORIZONTAL", "A-192", 0, "90-90", 'Travesaño de hoja · postigón de 1 hoja · opcional («Opción con travesaño», pág. 094): poné 1 si lo lleva', 9),
    ("Actual", "AC-PPOST", "MT-0218", "HOJA_HORIZONTAL", "(A/2)-175", 0, "90-90", 'Travesaño de hoja · postigón de 2 hojas · opcional («Opción con travesaño», pág. 094): poné 2 si lo lleva', 10),
    ("Actual", "AC-PPOST", "MT-0219", "HOJA_HORIZONTAL", "A-192", "si(N == 1, 1, 0)", "90-90", 'Zócalo de hoja · postigón de 1 hoja', 11),
    ("Actual", "AC-PPOST", "MT-0219", "HOJA_HORIZONTAL", "(A/2)-175", "si(N == 1, 0, 2)", "90-90", 'Zócalo de hoja · postigón de 2 hojas', 12),
    ("Actual", "AC-PPOST", "MT-0224", "OTRO", "H-52", "si(N == 1, 0, 1)", "90-90", 'Encuentro central de hojas · sólo postigón de 2 hojas', 13),
    ("Actual", "AC-PPOST", "MT-0272", "OTRO", "H-219", "si(N == 1, 2, 4)", "45-45", 'Jambas adaptador celosía · 2 por hoja', 14),
    ("Actual", "AC-PPOST", "MT-0272", "OTRO", "A-188", "si(N == 1, 2, 0)", "45-45", 'Dintel y umbral adaptador celosía · postigón de 1 hoja', 15),
    ("Actual", "AC-PPOST", "MT-0272", "OTRO", "(A/2)-171", "si(N == 1, 0, 4)", "45-45", 'Dintel y umbral adaptador celosía · postigón de 2 hojas', 16),
    ("Actual", "AC-PPOST", "MT-2705", "OTRO", "A-248", "si(N == 1, piso((H-360)/67), 0)", "90-90", 'Tablilla · postigón de 1 hoja · MEDIDA DEDUCIDA la cantidad: el catálogo dice «según altura»; paso 67 mm y 360 mm de adaptador y terminales (págs. 028 y 094)', 17),
    ("Actual", "AC-PPOST", "MT-2705", "OTRO", "(A/2)-231", "si(N == 1, 0, 2*piso((H-360)/67))", "90-90", 'Tablilla · postigón de 2 hojas · MEDIDA DEDUCIDA la cantidad: el catálogo dice «según altura»; paso 67 mm y 360 mm de adaptador y terminales (págs. 028 y 094)', 18),
    ("Actual", "AC-PPOST", "MT-2695", "OTRO", "A-234", "si(N == 1, 2, 0)", "90-90", 'Adaptador terminal celosía regulable · postigón de 1 hoja', 19),
    ("Actual", "AC-PPOST", "MT-2708", "OTRO", "A-248", "si(N == 1, 2, 0)", "90-90", 'Tapaluz · postigón de 1 hoja', 20),
    ("Actual", "AC-PPOST", "MT-2708", "OTRO", "(A/2)-231", "si(N == 1, 0, 4)", "90-90", 'Tapaluz · postigón de 2 hojas', 21),
    ("Actual", "AC-PPOST", "MT-0206", "OTRO", "H+27", 2, "45-90", 'Jambas contramarco · el catálogo marca (*): ajustá la medida según el nivel del piso terminado', 22),
    ("Actual", "AC-PPOST", "MT-2695", "OTRO", "(A/2)-217", "si(N == 1, 0, 4)", "90-90", 'Adaptador terminal celosía regulable · postigón de 2 hojas', 23),
    ("Actual", "AC-PPOST", "MT-2706", "OTRO", "A-248", "si(N == 1, 2, 0)", "90-90", 'Terminal corto celosía regulable · postigón de 1 hoja · el catálogo dice «corto o largo»: si al armar sobra altura, usá MT-2707', 24),
    ("Actual", "AC-PPOST", "MT-2706", "OTRO", "(A/2)-231", "si(N == 1, 0, 4)", "90-90", 'Terminal corto celosía regulable · postigón de 2 hojas · el catálogo dice «corto o largo»: si al armar sobra altura, usá MT-2707', 25),
    ("Actual", "AC-PPOST", "MT-2707", "OTRO", "A-248", 0, "90-90", 'Terminal largo celosía regulable · postigón de 1 hoja · alternativa de MT-2706: poné la cantidad si usás este perfil', 26),
    ("Actual", "AC-PPOST", "MT-2707", "OTRO", "(A/2)-231", 0, "90-90", 'Terminal largo celosía regulable · postigón de 2 hojas · alternativa de MT-2706: poné la cantidad si usás este perfil', 27),
    ("Actual", "AC-COR2", "MT-0205", "PREMARCO", "H+36", 2, "45-45", 'Jambas premarco', 1),
    ("Actual", "AC-COR2", "MT-0205", "PREMARCO", "A+36", 2, "45-45", 'Umbral y dintel premarco', 2),
    ("Actual", "AC-COR2", "MT-0206", "OTRO", "H+54", 2, "45-45", 'Jambas contramarco', 3),
    ("Actual", "AC-COR2", "MT-0206", "OTRO", "A+54", 2, "45-45", 'Umbral y dintel contramarco', 4),
    ("Actual", "AC-COR2", "MT-0200", "MARCO_HORIZONTAL", "A-42", 2, "90-90", 'Umbral y dintel marco', 5),
    ("Actual", "AC-COR2", "MT-0201", "MARCO_VERTICAL", "H", 2, "90-90", 'Jambas de marco', 6),
    ("Actual", "AC-COR2", "MT-0203", "HOJA_VERTICAL", "H-79", 2, "90-90", 'Parante lateral de hoja para VS', 7),
    ("Actual", "AC-COR2", "MT-0204", "HOJA_HORIZONTAL", "(A/2)-25", 4, "90-90", 'Zócalo bajo de hoja VS', 8),
    ("Actual", "AC-COR2", "MT-0207", "HOJA_VERTICAL", "H-79", 2, "90-90", 'Parante central VS', 9),
    ("Actual", "AC-COR2", "MT-0208", "HOJA_VERTICAL", "H-79", 0, "90-90", 'Parante central con asa VS · alternativa de MT-0207: poné la cantidad si usás este perfil', 10),
    ("Actual", "AC-COR2", "MT-0248", "HOJA_VERTICAL", "H-79", 4, "90-90", 'Parante lateral de hoja para DVH', 11),
    ("Actual", "AC-COR2", "MT-0249", "HOJA_HORIZONTAL", "(A/2)-25", 0, "90-90", 'Zócalo bajo de hoja para DVH · alternativa de MT-0204: poné la cantidad si usás este perfil', 12),
    ("Actual", "AC-COR2", "MT-0251", "HOJA_VERTICAL", "H-79", 0, "90-90", 'Parante central con asa para DVH · alternativa de MT-0207: poné la cantidad si usás este perfil', 13),
    ("Actual", "AC-COR2", "MT-0255", "HOJA_HORIZONTAL", "(A/2)-7", 2, "45-45", 'Zócalo y cabezal mosquitero', 14),
    ("Actual", "AC-COR2", "MT-0255", "MARCO_VERTICAL", "H-88", 4, "45-45", 'Jambas mosquitero', 15),
    ("Actual", "AC-COR2", "MT-0228", "MARCO_VERTICAL", "H-100", 2, "90-90", 'Tope mosquitero corrediza', 16),
    ("Actual", "AC-COR2", "MT-0243", "MARCO_VERTICAL", "H-100", 2, "90-90", 'Guía de cortina común', 17),
    ("Actual", "AC-COR4", "MT-0205", "PREMARCO", "H+36", 2, "45-45", 'Jambas premarco', 1),
    ("Actual", "AC-COR4", "MT-0205", "PREMARCO", "A+36", 2, "45-45", 'Umbral y dintel premarco', 2),
    ("Actual", "AC-COR4", "MT-0206", "OTRO", "H+54", 2, "45-45", 'Jambas contramarco', 3),
    ("Actual", "AC-COR4", "MT-0206", "OTRO", "A+54", 2, "45-45", 'Umbral y dintel contramarco', 4),
    ("Actual", "AC-COR4", "MT-0200", "MARCO_HORIZONTAL", "A-42", 2, "90-90", 'Umbral y dintel marco', 5),
    ("Actual", "AC-COR4", "MT-0201", "MARCO_VERTICAL", "H", 2, "90-90", 'Jambas de marco', 6),
    ("Actual", "AC-COR4", "MT-0203", "HOJA_VERTICAL", "H-79", 2, "90-90", 'Parante lateral de hoja para VS', 7),
    ("Actual", "AC-COR4", "MT-0204", "HOJA_HORIZONTAL", "(A/4)-13", 8, "90-90", 'Zócalo bajo de hoja VS', 8),
    ("Actual", "AC-COR4", "MT-0207", "HOJA_VERTICAL", "H-79", 2, "90-90", 'Parante central VS', 9),
    ("Actual", "AC-COR4", "MT-0208", "HOJA_VERTICAL", "H-79", 0, "90-90", 'Parante central con asa VS · alternativa de MT-0207: poné la cantidad si usás este perfil', 10),
    ("Actual", "AC-COR4", "MT-0248", "HOJA_VERTICAL", "H-79", 4, "90-90", 'Parante lateral de hoja para DVH', 11),
    ("Actual", "AC-COR4", "MT-0249", "HOJA_HORIZONTAL", "(A/4)-13", 0, "90-90", 'Zócalo bajo de hoja para DVH · alternativa de MT-0204: poné la cantidad si usás este perfil', 12),
    ("Actual", "AC-COR4", "MT-0251", "HOJA_VERTICAL", "H-79", 0, "90-90", 'Parante central con asa para DVH · alternativa de MT-0207: poné la cantidad si usás este perfil', 13),
    ("Actual", "AC-COR4", "MT-0255", "HOJA_HORIZONTAL", "(A/4)+5", 4, "45-45", 'Zócalo y cabezal mosquitero', 14),
    ("Actual", "AC-COR4", "MT-0255", "MARCO_VERTICAL", "H-88", 4, "45-45", 'Jambas mosquitero', 15),
    ("Actual", "AC-COR4", "MT-0228", "MARCO_VERTICAL", "H-100", 2, "90-90", 'Tope mosquitero corrediza', 16),
    ("Actual", "AC-COR4", "MT-0243", "MARCO_VERTICAL", "H-100", 2, "90-90", 'Guía de cortina común', 17),
    ("Actual", "AC-PCOR2", "MT-0205", "PREMARCO", "H+36", 2, "45-45", 'Jambas premarco', 1),
    ("Actual", "AC-PCOR2", "MT-0205", "PREMARCO", "A+36", 2, "45-45", 'Umbral y dintel premarco', 2),
    ("Actual", "AC-PCOR2", "MT-0206", "OTRO", "A+54", 2, "45-45", 'Umbral y dintel contramarco', 3),
    ("Actual", "AC-PCOR2", "MT-0200", "MARCO_HORIZONTAL", "A-42", 2, "90-90", 'Umbral y dintel marco', 4),
    ("Actual", "AC-PCOR2", "MT-0201", "MARCO_VERTICAL", "H", 2, "90-90", 'Jambas de marco', 5),
    ("Actual", "AC-PCOR2", "MT-0203", "HOJA_VERTICAL", "H-79", 4, "90-90", 'Parante lateral de hoja para VS', 6),
    ("Actual", "AC-PCOR2", "MT-0204", "HOJA_HORIZONTAL", "(A/2)-25", 2, "90-90", 'Zócalo bajo de hoja para VS', 7),
    ("Actual", "AC-PCOR2", "MT-0209", "HOJA_HORIZONTAL", "(A/2)-25", 0, "90-90", 'Zócalo alto de hoja para VS · alternativa de MT-0204: poné la cantidad si usás este perfil', 8),
    ("Actual", "AC-PCOR2", "MT-0207", "MARCO_VERTICAL", "H-79", 2, "90-90", '', 9),
    ("Actual", "AC-PCOR2", "MT-0239", "HOJA_HORIZONTAL", "H-79", 4, "90-90", 'Travesaño hoja para VS', 10),
    ("Actual", "AC-PCOR2", "MT-0248", "HOJA_VERTICAL", "H-79", 2, "90-90", 'Parante lateral de hoja para DVH', 11),
    ("Actual", "AC-PCOR2", "MT-0249", "HOJA_HORIZONTAL", "(A/2)-25", 2, "90-90", 'Zócalo bajo de hoja para DVH', 12),
    ("Actual", "AC-PCOR2", "MT-0252", "HOJA_HORIZONTAL", "(A/2)-25", 0, "90-90", 'Zócalo alto de hoja para DVH · alternativa de MT-0249: poné la cantidad si usás este perfil', 13),
    ("Actual", "AC-PCOR2", "MT-0251", "HOJA_VERTICAL", "H-79", 0, "90-90", 'Parante central con asa para DVH · el catálogo no publica su peso por metro: poné el peso y la cantidad para usarlo', 14),
    ("Actual", "AC-PCOR2", "MT-0253", "HOJA_HORIZONTAL", "H-79", 4, "90-90", 'Travesaño hoja para DVH', 15),
    ("Actual", "AC-PCOR2", "MT-0255", "HOJA_HORIZONTAL", "(A/2)-7", 2, "45-45", 'Zócalo y cabezal mosquitero', 16),
    ("Actual", "AC-PCOR2", "MT-0255", "MARCO_VERTICAL", "H-88", 4, "45-45", 'Jambas mosquitero', 17),
    ("Actual", "AC-PCOR2", "MT-0255", "MARCO_VERTICAL", "H-88", 0, "45-45", 'Jambas mosquitero · alternativa de MT-0255: poné la cantidad si usás este perfil', 18),
    ("Actual", "AC-PCOR2", "MT-0256", "MARCO_HORIZONTAL", "(A/2)-74", 1, "90-90", 'Travesaño de mosquitero', 19),
    ("Actual", "AC-PCOR2", "MT-0228", "MARCO_VERTICAL", "H-100", 2, "90-90", 'Tope mosquitero corrediza', 20),
    ("Actual", "AC-PCOR2", "MT-0243", "MARCO_VERTICAL", "H-100", 2, "90-90", 'Guía de cortina común', 21),
    ("Actual", "AC-PCOR4", "MT-0205", "PREMARCO", "H+36", 2, "45-45", 'Jambas premarco', 1),
    ("Actual", "AC-PCOR4", "MT-0205", "PREMARCO", "A+36", 2, "45-45", 'Umbral y dintel premarco', 2),
    ("Actual", "AC-PCOR4", "MT-0206", "OTRO", "A+54", 2, "45-45", 'Umbral y dintel contramarco', 3),
    ("Actual", "AC-PCOR4", "MT-0200", "MARCO_HORIZONTAL", "A-42", 2, "90-90", 'Umbral y dintel marco', 4),
    ("Actual", "AC-PCOR4", "MT-0201", "MARCO_VERTICAL", "H", 2, "90-90", 'Jambas de marco', 5),
    ("Actual", "AC-PCOR4", "MT-0203", "HOJA_VERTICAL", "H-79", 4, "90-90", 'Parante lateral de hoja para VS', 6),
    ("Actual", "AC-PCOR4", "MT-0204", "HOJA_HORIZONTAL", "(A/4)-13", 4, "90-90", 'Cabezal de hoja para VS', 7),
    ("Actual", "AC-PCOR4", "MT-0209", "HOJA_HORIZONTAL", "(A/4)-13", 4, "90-90", 'Zócalo alto de hoja para VS', 8),
    ("Actual", "AC-PCOR4", "MT-0207", "MARCO_VERTICAL", "H-79", 2, "90-90", '', 9),
    ("Actual", "AC-PCOR4", "MT-0239", "HOJA_HORIZONTAL", "H-79", 4, "90-90", 'Travesaño hoja para VS', 10),
    ("Actual", "AC-PCOR4", "MT-0248", "HOJA_VERTICAL", "H-79", 2, "90-90", 'Parante lateral de hoja para DVH', 11),
    ("Actual", "AC-PCOR4", "MT-0249", "HOJA_HORIZONTAL", "(A/4)-13", 4, "90-90", 'Zócalo bajo de hoja para DVH', 12),
    ("Actual", "AC-PCOR4", "MT-0252", "HOJA_HORIZONTAL", "(A/4)-13", 0, "90-90", 'Zócalo alto de hoja para DVH · alternativa de MT-0249: poné la cantidad si usás este perfil', 13),
    ("Actual", "AC-PCOR4", "MT-0251", "HOJA_VERTICAL", "H-79", 0, "90-90", 'Parante central con asa para DVH · el catálogo no publica su peso por metro: poné el peso y la cantidad para usarlo', 14),
    ("Actual", "AC-PCOR4", "MT-0253", "HOJA_HORIZONTAL", "H-79", 4, "90-90", 'Travesaño hoja para DVH', 15),
    ("Actual", "AC-PCOR4", "MT-0255", "HOJA_HORIZONTAL", "(A/4)+5", 4, "45-45", 'Zócalo y cabezal mosquitero', 16),
    ("Actual", "AC-PCOR4", "MT-0255", "MARCO_VERTICAL", "H-88", 4, "45-45", 'Jambas mosquitero', 17),
    ("Actual", "AC-PCOR4", "MT-0255", "MARCO_VERTICAL", "H-88", 0, "45-45", 'Jambas mosquitero · alternativa de MT-0255: poné la cantidad si usás este perfil', 18),
    ("Actual", "AC-PCOR4", "MT-0256", "MARCO_HORIZONTAL", "(A/4)-62", 4, "90-90", 'Travesaño de mosquitero', 19),
    ("Actual", "AC-PCOR4", "MT-0228", "MARCO_VERTICAL", "H-100", 2, "90-90", 'Tope mosquitero corrediza', 20),
    ("Actual", "AC-PCOR4", "MT-0243", "MARCO_VERTICAL", "H-100", 2, "90-90", 'Guía de cortina común', 21),
    ("Actual", "AC-COR3", "MT-2220", "PREMARCO", "H+36", 2, "45-45", 'Jambas premarco', 1),
    ("Actual", "AC-COR3", "MT-2220", "PREMARCO", "A+36", 2, "45-45", 'Umbral y dintel premarco', 2),
    ("Actual", "AC-COR3", "MT-0206", "OTRO", "H+54", 2, "45-45", 'Jambas contramarco', 3),
    ("Actual", "AC-COR3", "MT-0206", "OTRO", "A+54", 2, "45-45", 'Umbral y dintel contramarco', 4),
    ("Actual", "AC-COR3", "MT-0240", "MARCO_HORIZONTAL", "A-42", 2, "90-90", 'Umbral y dintel marco', 5),
    ("Actual", "AC-COR3", "MT-0241", "MARCO_VERTICAL", "H", 2, "90-90", 'Jambas de marco', 6),
    ("Actual", "AC-COR3", "MT-0207", "HOJA_VERTICAL", "H-79", 2, "90-90", 'Parante central vidrio simple', 7),
    ("Actual", "AC-COR3", "MT-0248", "HOJA_VERTICAL", "H-79", 2, "90-90", 'Parante lateral de hoja DVH', 8),
    ("Actual", "AC-COR3", "MT-0250", "HOJA_VERTICAL", "H-79", 4, "90-90", 'Parante central de hoja DVH', 9),
    ("Actual", "AC-COR245", "MT-0205", "PREMARCO", "H+36", 2, "45-45", 'Jambas premarco', 1),
    ("Actual", "AC-COR245", "MT-0205", "PREMARCO", "A+36", 2, "45-45", 'Dintel y umbral premarco', 2),
    ("Actual", "AC-COR245", "MT-0206", "OTRO", "H+54", 2, "45-45", 'Jambas contramarco', 3),
    ("Actual", "AC-COR245", "MT-0206", "OTRO", "A+54", 2, "45-45", 'Dintel y umbral contramarco', 4),
    ("Actual", "AC-COR245", "MT-0280", "MARCO_VERTICAL", "H", 2, "45-45", 'Jambas marco', 5),
    ("Actual", "AC-COR245", "MT-0280", "MARCO_HORIZONTAL", "A", 2, "45-45", 'Dintel y umbral marco', 6),
    ("Actual", "AC-COR245", "MT-0324", "OTRO", "H-78", 2, "45-45", 'Encuentro central corrediza de 4 hoja', 7),
    ("Actual", "AC-COR245", "MT-0325", "HOJA_VERTICAL", "H-78", 4, "45-45", 'Parante lateral y central de hoja', 8),
    ("Actual", "AC-COR245", "MT-0325", "HOJA_HORIZONTAL", "(A/2)-8", 4, "45-45", 'Zócalo y cabezal de hoja', 9),
    ("Actual", "AC-COR245", "MT-0383", "HOJA_VERTICAL", "H-78", 0, "45-45", 'Parante lateral y central de hoja · alternativa de MT-0325: poné la cantidad si usás este perfil', 10),
    ("Actual", "AC-COR245", "MT-0383", "HOJA_HORIZONTAL", "(A/2)-8", 0, "45-45", 'Zócalo y cabezal de hoja · alternativa de MT-0325: poné la cantidad si usás este perfil', 11),
    ("Actual", "AC-COR245", "MT-0316", "REFUERZO", "H-134", 4, "90-90", 'Refuerzo parantes central', 12),
    ("Actual", "AC-COR245", "MT-0315", "OTRO", "H-152", 4, "90-90", 'Solapa central de hoja', 13),
    ("Actual", "AC-COR245", "MT-0255", "MARCO_VERTICAL", "H-88", 2, "45-45", '', 14),
    ("Actual", "AC-COR245", "MT-0255", "HOJA_HORIZONTAL", "(A/2)-21", 2, "45-45", 'Zócalo y cabezal mosquitero', 15),
    ("Actual", "AC-PCOR245", "MT-0205", "PREMARCO", "H+36", 2, "45-45", 'Jambas premarco', 1),
    ("Actual", "AC-PCOR245", "MT-0205", "PREMARCO", "A+36", 2, "45-45", 'Dintel y umbral premarco', 2),
    ("Actual", "AC-PCOR245", "MT-0206", "OTRO", "A+54", 1, "45-45", 'Dintel y umbral contramarco', 3),
    ("Actual", "AC-PCOR245", "MT-0280", "MARCO_VERTICAL", "H", 2, "45-45", 'Jambas marco', 4),
    ("Actual", "AC-PCOR245", "MT-0280", "MARCO_HORIZONTAL", "A", 2, "45-45", 'Dintel y umbral marco', 5),
    ("Actual", "AC-PCOR245", "MT-0324", "HOJA_VERTICAL", "H-78", 2, "45-45", 'Parante lateral y central de hoja', 6),
    ("Actual", "AC-PCOR245", "MT-0325", "HOJA_VERTICAL", "H-78", 0, "45-45", 'Parante lateral y central de hoja · alternativa de MT-0324: poné la cantidad si usás este perfil', 7),
    ("Actual", "AC-PCOR245", "MT-0325", "HOJA_HORIZONTAL", "(A/2)-7", 4, "45-45", 'Zócalo y cabezal de hoja', 8),
    ("Actual", "AC-PCOR245", "MT-0383", "HOJA_VERTICAL", "H-78", 0, "45-45", 'Parante lateral y central de hoja · alternativa de MT-0324: poné la cantidad si usás este perfil', 9),
    ("Actual", "AC-PCOR245", "MT-0383", "HOJA_HORIZONTAL", "(A/2)-7", 0, "45-45", 'Zócalo y cabezal de hoja · alternativa de MT-0325: poné la cantidad si usás este perfil', 10),
    ("Actual", "AC-PCOR245", "MT-0316", "REFUERZO", "H-134", 4, "90-90", 'Refuerzo parantes central', 11),
    ("Actual", "AC-PCOR245", "MT-0315", "OTRO", "H-152", 4, "90-90", 'Solapa central de hoja', 12),
    ("Actual", "AC-PCOR245", "MT-0255", "MARCO_VERTICAL", "H-88", 2, "45-45", '', 13),
    ("Actual", "AC-PCOR245", "MT-0255", "HOJA_HORIZONTAL", "(A/2)-21", 2, "45-45", 'Zócalo y cabezal mosquitero', 14),
]


# ---------------------------------------------------------------------------
# Vidrios
# ---------------------------------------------------------------------------
#: Los tipos de vidrio de uso corriente, con la medida de plancha con la que se
#: compran. **Todos entran en $0**: el precio del vidrio lo pone la vidriería de
#: cada uno y cambia todos los meses, así que ponerle un número de fábrica sería
#: mentirle al presupuesto. Las medidas de plancha sí son reales, y son las que
#: usa el optimizador de corte para decir cuántas planchas hacen falta.
#:
#: (nombre, tipo, espesor, ancho plancha, alto plancha, desperdicio)
VIDRIOS_MDT = [
    ("Float 3 mm",        "Float",     3.0, 3600, 2500, 0.10),
    ("Float 4 mm",        "Float",     4.0, 3600, 2500, 0.10),
    ("Float 5 mm",        "Float",     5.0, 3600, 2500, 0.10),
    ("Float 6 mm",        "Float",     6.0, 3600, 2500, 0.10),
    ("Esmerilado 4 mm",   "Float",     4.0, 3600, 2500, 0.10),
    ("Laminado 3+3",      "Laminado",  6.0, 3600, 2500, 0.12),
    ("Laminado 4+4",      "Laminado",  8.0, 3600, 2500, 0.12),
    ("Templado 6 mm",     "Templado",  6.0, 3600, 2500, 0.15),
    ("DVH 4/9/4",         "DVH",      17.0, 3210, 2250, 0.12),
    ("DVH 4/12/4",        "DVH",      20.0, 3210, 2250, 0.12),
    ("DVH 5/12/5",        "DVH",      22.0, 3210, 2250, 0.12),
]


# ---------------------------------------------------------------------------
# Accesorios
# ---------------------------------------------------------------------------
#: Los códigos de accesorio que los dos catálogos nombran en sus páginas de
#: detalles y mecanizados. La familia sale del prefijo, que es como MDT los
#: numera:
#:
#:     ME…  escuadras de armado        MB…  burletes y felpas
#:     MR…  rodamientos y ruedas       MS…  selladores y accesorios varios
#:     HD…  herrajes
#:
#: Estos dos catálogos son de **perfilería**: publican qué accesorio lleva cada
#: encuentro, no su descripción comercial ni su precio. Por eso cada uno entra
#: con el nombre de su familia y en **$0**, para completarlo con el catálogo de
#: accesorios del proveedor.
#:
#: (código, descripción, unidad)
ACCESORIOS_MDT = [
    ("ME66",  "Escuadra de armado ME66", "u"),
    ("ME67",  "Escuadra de armado ME67", "u"),
    ("ME68",  "Escuadra de armado ME68", "u"),
    ("ME69",  "Escuadra de armado ME69", "u"),
    ("ME70",  "Escuadra de armado ME70", "u"),
    ("ME71",  "Escuadra de armado ME71", "u"),
    ("ME72",  "Escuadra de armado ME72", "u"),
    ("ME73",  "Escuadra de armado ME73", "u"),
    ("ME83",  "Escuadra de armado ME83", "u"),
    ("ME97",  "Escuadra de armado ME97", "u"),
    ("ME98",  "Escuadra de armado ME98", "u"),
    ("ME300", "Escuadra de armado ME300", "u"),
    ("ME308", "Escuadra de armado ME308", "u"),
    ("MB29",  "Burlete MB29", "ml"),
    ("MB30",  "Burlete MB30", "ml"),
    ("MB31",  "Burlete MB31", "ml"),
    ("MB52",  "Burlete MB52", "ml"),
    ("MB57",  "Burlete MB57", "ml"),
    ("MB60",  "Burlete MB60", "ml"),
    ("MB66",  "Burlete MB66", "ml"),
    ("MB67",  "Burlete MB67", "ml"),
    ("MB68",  "Burlete MB68", "ml"),
    ("MB69",  "Burlete MB69", "ml"),
    ("MB70",  "Burlete MB70", "ml"),
    ("MR10",  "Rodamiento MR10", "u"),
    ("MR11",  "Rodamiento MR11", "u"),
    ("MR39",  "Rodamiento MR39", "u"),
    ("MR40",  "Rodamiento MR40", "u"),
    ("MR41",  "Rodamiento MR41", "u"),
    ("MR42",  "Rodamiento MR42", "u"),
    ("MR43",  "Rodamiento MR43", "u"),
    ("MS9",   "Sellador / accesorio MS9", "u"),
    ("HD102", "Herraje HD102", "u"),
    # -- lo que toda abertura lleva y ningún catálogo de perfilería numera ----
    ("MDT-CIERRE",  "Cierre / traba de hoja", "u"),
    ("MDT-MANIJA",  "Manija", "u"),
    ("MDT-BISAGRA", "Bisagra de abrir", "u"),
    ("MDT-FELPA",   "Felpa de hoja", "ml"),
    ("MDT-TORN",    "Kit de tornillería y sellado", "jgo"),
]


# ---------------------------------------------------------------------------
# Kits
# ---------------------------------------------------------------------------
#: Qué accesorios lleva cada familia de abertura y en qué cantidad. La cantidad
#: es una **fórmula**, igual que los cortes: ``2*N`` son dos por hoja y
#: ``2*N*(HH+AH)/1000`` es el perímetro de las hojas en metros.
#:
#: Los kits entran en $0 como todo lo demás, pero entran **completos**: así el
#: presupuesto sale con sus renglones de accesorio desde el primer día y lo
#: único que falta es ponerle el precio a cada uno.
#:
#: (esquema, [(código accesorio, fórmula de cantidad)])
KITS_MDT = {
    "corrediza": [
        ("MR43", "2*N"), ("MDT-CIERRE", "1"), ("MDT-MANIJA", "N"),
        ("MDT-FELPA", "2*N*(HH+AH)/1000"), ("MB57", "2*(A+H)/1000"),
        ("ME69", "4*N"), ("MDT-TORN", "N"),
    ],
    "batiente": [
        ("MDT-BISAGRA", "3*N"), ("MDT-CIERRE", "N"), ("MDT-MANIJA", "N"),
        ("MB68", "2*N*(HH+AH)/1000"), ("ME69", "4*N"), ("MDT-TORN", "N"),
    ],
    "puerta_batiente": [
        ("MDT-BISAGRA", "3*N"), ("MDT-CIERRE", "N"), ("MDT-MANIJA", "N"),
        ("MB68", "2*N*(HH+AH)/1000"), ("ME69", "4*N"), ("MDT-TORN", "N"),
    ],
    "banderola": [
        ("MDT-BISAGRA", "2"), ("MDT-CIERRE", "1"),
        ("MB68", "2*(AH+HH)/1000"), ("ME69", "4"), ("MDT-TORN", "1"),
    ],
    "fijo": [
        ("MB68", "2*(A+H)/1000"), ("ME69", "4"), ("MDT-TORN", "1"),
    ],
}


# ---------------------------------------------------------------------------
# Opciones de cada abertura: premarco, contramarco y mosquitero
# ---------------------------------------------------------------------------
#: Las tablas de corte de Actual listan el premarco y el contramarco junto al
#: marco. Cargadas tal cual, TODA abertura de la línea los cortaba y los
#: cobraba, aunque la obra no los llevara. Desde la versión 2 del catálogo son
#: dos opciones de cada abertura.
#:
#: Qué renglón pertenece a qué opción se decide con reglas, y no con una lista
#: a mano de renglones que habría que mantener en paralelo:
#:
#:     premarco      función PREMARCO (MT-0205, y su alternativa MT-2220)
#:     contramarco   función OTRO con perfil de contramarco (MT-0206, MT-0906)
#:     mosquitero    corrediza con perfil de mosquitero de su línea (versión 4)
#:
#: AC-PPOST quedó afuera de la versión 2: su tabla se había cargado con el
#: premarco como marco. Desde la versión 3, con la tabla corregida, sus
#: renglones de premarco y contramarco entran por las mismas dos reglas.
PERFILES_CONTRAMARCO_ACTUAL = ("MT-0206", "MT-0906")

#: (clave, etiqueta, ayuda, orden) de las dos opciones. Arrancan en 0: nada se
#: corta ni se cobra si no se elige.
OPCIONES_MONTAJE = [
    ("PREMARCO", "Lleva premarco",
     "No se elige acá: lo decide la casilla «Incluye premarco» de la abertura.", 1),
    ("CONTRAMARCO", "Lleva contramarco",
     "Corta el contramarco perimetral que da la tabla del fabricante.", 2),
]

#: Las opciones de montaje, que declaran los pasos a las versiones 2 y 3. Cada
#: paso de actualización toca sólo sus opciones.
CLAVES_V2 = ("PREMARCO", "CONTRAMARCO")

#: Perfiles del mosquitero de las corredizas, por línea (versión 4).
#:
#: Las tablas de las corredizas traen la hoja del mosquitero y se cortaba
#: siempre; encima «Incluye mosquitero» lo sumaba por m²: se cobraba dos veces.
#: Esos renglones no tienen función propia —se cargaron como HOJA_* y MARCO_*—,
#: así que se reconocen por perfil:
#:
#:     Actual    MT-0255 hoja, MT-0256 travesaño y MT-0228 tope en el marco
#:     Clásica   MT-0905, MT-1110 y MT-0005 hoja; MT-1203 parante, en cantidad 0
#:               porque el catálogo lo cita pero no lo lista
#:
#: Sólo en las corredizas: CL-PMOSQ es una puerta mosquitero, ahí el mosquitero
#: ES la abertura (y sus perfiles son otros).
PERFILES_MOSQUITERO = {
    "Actual": ("MT-0255", "MT-0256", "MT-0228"),
    "Clásica": ("MT-0905", "MT-1110", "MT-0005", "MT-1203"),
}

#: Función con la que quedan las piezas del mosquitero. Además de identificarlas
#: para el costo (``calculo.costo_mosquitero``), las saca de AH y HH: el zócalo
#: del mosquitero es más largo que el de la hoja y, cargado como
#: HOJA_HORIZONTAL, agrandaba el vidrio.
FUNCION_MOSQUITERO = "MOSQUITERO"

#: (clave, etiqueta, ayuda, orden) del mosquitero. Arranca en 0 como las otras,
#: pero no se elige en el bloque de opciones: lo decide la casilla «Incluye
#: mosquitero» (``variables.VINCULADAS``), que es lo que imprime el PDF.
OPCIONES_CORREDIZA = [
    ("MOSQUITERO", "Lleva mosquitero",
     "No se elige acá: lo decide la casilla «Incluye mosquitero» de la abertura.", 3),
]

#: Corredizas del catálogo: la regla del mosquitero sólo mira éstas.
_CORREDIZAS = frozenset(codigo for _linea, codigo, _nombre, esquema, _hojas
                        in TIPOLOGIAS_MDT if esquema == "corrediza")

#: Línea de cada tipología del catálogo, con el nombre de la línea ("MDT Actual").
_LINEA_DE_TIPOLOGIA = {codigo: linea for linea, codigo, *_resto in TIPOLOGIAS_MDT}


def opcion_de_renglon(linea: str, tipologia: str, perfil: str, funcion: str) -> str:
    """Clave de la opción que gobierna un renglón de ``FORMULAS_MDT``, o ''.

    Premarco y contramarco sólo miran la línea Actual: en Clásica esos perfiles
    no están activos en ninguna tabla. El mosquitero mira las dos líneas, pero
    sólo en las corredizas.
    """
    if tipologia in _CORREDIZAS and perfil in PERFILES_MOSQUITERO.get(linea, ()):
        return "MOSQUITERO"
    if linea != "Actual":
        return ""
    if funcion == "PREMARCO":
        return "PREMARCO"
    if funcion == "OTRO" and perfil in PERFILES_CONTRAMARCO_ACTUAL:
        return "CONTRAMARCO"
    return ""


def formulas_de_fabrica(linea: str, tipologia: str, perfil: str, funcion: str,
                        formula: str, cantidad) -> tuple[str, str]:
    """Largo y cantidad de un renglón, tal como los siembra la versión vigente.

    El renglón de una opción se envuelve en ``si()``: con la opción apagada el
    largo da 0 y ``despiece_aluminio`` descarta la pieza, sin ningún caso
    especial. Se condicionan las DOS columnas, así la opción sigue mandando
    aunque alguien edite una de ellas. Una alternativa (cantidad 0) queda en 0:
    su nota dice "poné la cantidad si usás este perfil", y cuando el usuario lo
    haga, el largo condicionado la sigue gobernando.
    """
    clave = opcion_de_renglon(linea, tipologia, perfil, funcion)
    if not clave:
        return formula, str(cantidad)
    largo = f"si({clave}, {formula}, 0)"
    piezas = f"si({clave}, {cantidad}, 0)" if cantidad else str(cantidad)
    return largo, piezas


def funcion_de_fabrica(linea: str, tipologia: str, perfil: str, funcion: str) -> str:
    """Función de un renglón, tal como la siembra la versión vigente.

    Las piezas del mosquitero pasan a :data:`FUNCION_MOSQUITERO` (versión 4);
    todo lo demás queda con la función con la que se cargó.
    """
    if opcion_de_renglon(linea, tipologia, perfil, funcion) == "MOSQUITERO":
        return FUNCION_MOSQUITERO
    return funcion


def aclaracion_de_fabrica(nota: str, corte: str) -> str:
    """La aclaración que se guarda en ``tipologia_formulas.nota``: la nota más el corte.

    ``sembrar_mdt`` la armaba en línea; los pasos de actualización necesitan la
    misma cuenta para saber si una nota sigue como la dejó la fábrica.
    """
    if not corte:
        return nota
    return f"{nota} · corte {corte}".strip(" ·")


def _columnas_de_fabrica(renglon) -> dict:
    """Las columnas de un renglón de ``FORMULAS_MDT`` tal como las siembra el código.

    Función, largo, cantidad y nota, con las reglas vigentes: las opciones
    condicionan largo y cantidad, y las piezas del mosquitero cambian de
    función. Es contra lo que se compara la base, columna por columna.
    """
    linea, tip, perfil, funcion, form, cant, corte, nota, _orden = renglon
    largo, cantidad = formulas_de_fabrica(linea, tip, perfil, funcion, form, cant)
    return {"funcion": funcion_de_fabrica(linea, tip, perfil, funcion),
            "formula_largo": largo, "cantidad_piezas": cantidad,
            "nota": aclaracion_de_fabrica(nota, corte)}


def opciones_por_tipologia(solo=None, formulas=None) -> dict[str, list[str]]:
    """``{tipología: [claves]}`` de las tipologías MDT que usan alguna opción.

    Con ``solo`` se limita a esas claves. ``formulas`` es la tabla que se mira:
    por defecto la vigente; el paso a la versión 2 le pasa la de esa versión
    (:func:`_formulas_v2`), así declara exactamente lo que declaraba.
    """
    salida: dict[str, list[str]] = {}
    for linea, tip, perfil, funcion, *_resto in (FORMULAS_MDT if formulas is None
                                                 else formulas):
        clave = opcion_de_renglon(linea, tip, perfil, funcion)
        if not clave or (solo and clave not in solo):
            continue
        if clave not in salida.setdefault(tip, []):
            salida[tip].append(clave)
    return salida


def _insertar(db, tabla: str, datos: dict) -> None:
    """INSERT sin commit. Lo confirma quien llama, junto con la marca de versión."""
    columnas = ", ".join(datos)
    marcas = ", ".join("?" * len(datos))
    db.cx.execute(f"INSERT INTO {tabla} ({columnas}) VALUES ({marcas})",
                  tuple(datos.values()))


def _declarar_opciones(db, solo=None, formulas=None, tipologias=None) -> dict:
    """Declara las opciones en las tipologías MDT que las usan, cada una en su línea.

    Nunca modifica una declaración existente: si la clave ya está —porque el
    usuario la cargó a mano— queda la suya, con su etiqueta y su valor.

    Cada paso de actualización declara sólo lo suyo, y para eso se acota:

    * ``solo``: las claves (las versiones 2 y 3, premarco y contramarco; la 4,
      mosquitero). Sin ``solo`` van todas, que es lo que hace una siembra nueva.
    * ``formulas``: la tabla que se mira (ver :func:`opciones_por_tipologia`).
    * ``tipologias``: sólo esas. La versión 3 deja afuera una tabla que el
      usuario rehízo a mano.
    """
    hecho = {"opciones": 0, "opciones_copiadas": 0}

    datos_opcion = {clave: (etiqueta, ayuda, orden) for clave, etiqueta, ayuda, orden
                    in OPCIONES_MONTAJE + OPCIONES_CORREDIZA}
    ids_linea: dict[str, int] = {}

    for tip, claves in opciones_por_tipologia(solo, formulas).items():
        if tipologias is not None and tip not in tipologias:
            continue
        # Cada tipología se declara en SU línea: el mosquitero entra en las dos.
        nombre_linea = _LINEA_DE_TIPOLOGIA.get(tip, "")
        if nombre_linea not in ids_linea:
            ids_linea[nombre_linea] = _linea_id(db, nombre_linea) if nombre_linea else 0
        linea_id = ids_linea[nombre_linea]
        if not linea_id:
            continue    # el usuario borró la línea: no hay dónde declarar
        if not db.query_one("SELECT 1 FROM tipologias WHERE codigo = ?", (tip,)):
            continue    # el usuario la borró: no se resucita

        de_la_linea = {f["clave"] for f in db.query(
            "SELECT clave FROM tipologia_variables "
            "WHERE tipologia_codigo = ? AND linea_id = ?", (tip, linea_id))}

        if not de_la_linea:
            # variables.declaradas(): lo de la línea pisa a lo genérico y no se
            # mezclan. Si el usuario tenía opciones genéricas en esta tipología,
            # declarar las nuestras para la línea se las escondería a sus
            # fórmulas; por eso antes se copian a la línea.
            for generica in db.query(
                    "SELECT * FROM tipologia_variables "
                    "WHERE tipologia_codigo = ? AND linea_id IS NULL", (tip,)):
                copia = {k: generica[k] for k in generica.keys() if k != "id"}
                copia["linea_id"] = linea_id
                _insertar(db, "tipologia_variables", copia)
                de_la_linea.add(generica["clave"])
                hecho["opciones_copiadas"] += 1

        for clave in claves:
            if clave in de_la_linea:
                continue
            etiqueta, ayuda, orden = datos_opcion[clave]
            _insertar(db, "tipologia_variables", {
                "tipologia_codigo": tip, "linea_id": linea_id, "clave": clave,
                "etiqueta": etiqueta, "tipo": "bool", "opciones": "",
                "valor_default": "0", "minimo": 0, "maximo": 0,
                "ayuda": ayuda, "activo": 1, "orden": orden})
            hecho["opciones"] += 1

    return hecho


# ---------------------------------------------------------------------------
# Siembra
# ---------------------------------------------------------------------------

def _linea_id(db, nombre: str) -> int:
    fila = db.query_one("SELECT id FROM lineas WHERE nombre = ?", (nombre,))
    return fila["id"] if fila else 0


#: Marca que se escribe recién cuando la siembra terminó entera. Mirar si hay
#: perfiles o kits no alcanza: si el programa se corta en el medio —y sembrar
#: los dos catálogos lleva unos segundos— la base queda a medias y parecería
#: completa. Con la marca, una siembra interrumpida simplemente vuelve a
#: correr en el próximo arranque.
PARAM_SEMBRADO = "catalogo_mdt_version"

#: Se sube cuando cambian los datos del catálogo. Una base sembrada con una
#: versión anterior NO se vuelve a sembrar —borraría lo que el usuario corrigió
#: en esas fórmulas—: recibe los pasos de :data:`ACTUALIZACIONES`.
#:
#:     1   los dos catálogos tal cual los publica el fabricante
#:     2   premarco y contramarco de Actual pasan a ser opciones de la abertura
#:     3   las tablas de AC-PF, AC-BAND y AC-PPOST, corregidas contra el catálogo
#:     4   el mosquitero de las corredizas de las dos líneas pasa a ser opción,
#:         vinculada a «Incluye mosquitero», y sus piezas a la función MOSQUITERO
VERSION_CATALOGO = 4


def version_sembrada(db) -> int:
    """Versión del catálogo con la que quedó sembrada la base (0 = sin sembrar)."""
    try:
        return int(db.parametro(PARAM_SEMBRADO, 0) or 0)
    except (TypeError, ValueError):
        return 0


def ya_sembrado(db) -> bool:
    """¿La siembra de los dos catálogos terminó, y con esta versión de datos?"""
    return version_sembrada(db) >= VERSION_CATALOGO


def sembrar_mdt(db) -> dict:
    """Deja los dos catálogos MDT cargados y al día. Se puede correr las veces que sea.

    Hay dos caminos, según la marca de la base:

    * **Sin marca** —base nueva, o una siembra que se cortó a la mitad—: se
      siembra todo. No pisa nada que el usuario haya tocado: usa ``INSERT OR
      IGNORE`` para lo que se identifica solo (perfiles por línea+código,
      accesorios por código) y sólo reemplaza las fórmulas de las tipologías
      MDT, que son datos del fabricante.
    * **Sembrada con una versión anterior**: no se resiembra. Se aplican los
      pasos de :data:`ACTUALIZACIONES`, que cambian sólo lo que sigue como lo
      dejó la fábrica.

    Devuelve un resumen de lo que hizo, para poder mostrarlo.
    """
    anterior = version_sembrada(db)
    if anterior >= 1:
        return actualizar_mdt(db, anterior)

    hecho = {"lineas": 0, "perfiles": 0, "tipologias": 0, "formulas": 0,
             "vidrios": 0, "accesorios": 0, "kits": 0}

    # -- líneas ---------------------------------------------------------------
    ids = {}
    for nombre, extrusora, descripcion in LINEAS_MDT:
        lid = _linea_id(db, nombre)
        if not lid:
            lid = db.insertar("lineas", {
                "nombre": nombre, "descripcion": descripcion,
                "modo_costeo": "kg", "extrusora": extrusora, "activo": 1})
            hecho["lineas"] += 1
            # Un color por defecto, para que la línea sea usable de entrada.
            for color in ("Natural", "Blanco", "Negro", "Símil madera"):
                db.insertar("linea_precios", {
                    "linea_id": lid, "color": color, "precio_kg": 0.0,
                    "precio_m2_perfil": 0.0, "activo": 1})
        ids[nombre] = lid

    # -- perfiles -------------------------------------------------------------
    for nombre, perfiles in (("MDT Clásica", PERFILES_CLASICA),
                             ("MDT Actual", PERFILES_ACTUAL)):
        lid = ids[nombre]
        for codigo, peso, descripcion, nota in perfiles:
            if db.query_one("SELECT 1 FROM perfiles WHERE linea_id = ? AND codigo = ?",
                            (lid, codigo)):
                continue
            db.insertar("perfiles", {
                "linea_id": lid, "codigo": codigo, "descripcion": descripcion,
                "peso_kg_m": peso, "largo_barra_mm": LARGO_BARRA,
                "familia": "", "notas": nota})
            hecho["perfiles"] += 1

    # -- tipologías -----------------------------------------------------------
    for _linea, codigo, nombre, esquema, hojas in TIPOLOGIAS_MDT:
        if db.query_one("SELECT 1 FROM tipologias WHERE codigo = ?", (codigo,)):
            continue
        db.insertar("tipologias", {
            "codigo": codigo, "nombre": nombre, "hojas_default": hojas,
            "admite_mosquitero": 1 if esquema == "corrediza" else 0,
            "admite_premarco": 1, "esquema": esquema, "imagen": "",
            "horas_por_m2": 0.9, "activo": 1})
        hecho["tipologias"] += 1

    # -- fórmulas de despiece -------------------------------------------------
    # Se borran primero las de estas tipologías: son datos del fabricante, no
    # del usuario, y así una corrección del catálogo entra limpia.
    codigos_mdt = tuple(t[1] for t in TIPOLOGIAS_MDT)
    marcas = ",".join("?" * len(codigos_mdt))
    for nombre in ids:
        db.cx.execute(
            f"DELETE FROM tipologia_formulas WHERE linea_id = ? "
            f"AND tipologia_codigo IN ({marcas})", (ids[nombre],) + codigos_mdt)

    pesos = {}
    for nombre, perfiles in (("MDT Clásica", PERFILES_CLASICA),
                             ("MDT Actual", PERFILES_ACTUAL)):
        for codigo, peso, *_ in perfiles:
            pesos[(nombre, codigo)] = peso

    for linea, tip, perfil, funcion, form, cant, corte, nota, orden in FORMULAS_MDT:
        nombre = "MDT Clásica" if linea == "Clásica" else "MDT Actual"
        aclaracion = aclaracion_de_fabrica(nota, corte)
        # Premarco, contramarco y mosquitero entran condicionados a su opción, y
        # las piezas del mosquitero con su propia función; todo lo demás, tal
        # cual lo publica el fabricante.
        largo, cantidad = formulas_de_fabrica(linea, tip, perfil, funcion, form, cant)
        db.insertar("tipologia_formulas", {
            "tipologia_codigo": tip, "linea_id": ids[nombre],
            "perfil_codigo": perfil,
            "funcion": funcion_de_fabrica(linea, tip, perfil, funcion),
            "formula_largo": largo, "cantidad_piezas": cantidad,
            "peso_kg_m": pesos.get((nombre, perfil), 0.0),
            "nota": aclaracion, "orden": orden})
        hecho["formulas"] += 1

    # -- vidrios --------------------------------------------------------------
    for nombre, tipo, espesor, pa, ph, desp in VIDRIOS_MDT:
        if db.query_one("SELECT 1 FROM vidrios WHERE nombre = ?", (nombre,)):
            continue
        db.insertar("vidrios", {
            "nombre": nombre, "tipo": tipo, "espesor_mm": espesor,
            "precio_m2": 0.0, "plancha_ancho_mm": pa, "plancha_alto_mm": ph,
            "precio_plancha": 0.0, "desperdicio_pct": desp, "activo": 1})
        hecho["vidrios"] += 1

    # -- accesorios -----------------------------------------------------------
    id_acc = {}
    for codigo, descripcion, unidad in ACCESORIOS_MDT:
        fila = db.query_one("SELECT id FROM accesorios WHERE codigo = ?", (codigo,))
        if fila:
            id_acc[codigo] = fila["id"]
            continue
        id_acc[codigo] = db.insertar("accesorios", {
            "codigo": codigo, "descripcion": descripcion, "unidad": unidad,
            "precio": 0.0, "activo": 1})
        hecho["accesorios"] += 1

    # -- kits, uno por tipología ----------------------------------------------
    for linea, codigo, nombre, esquema, _hojas in TIPOLOGIAS_MDT:
        lid = ids[linea]
        if db.query_one("SELECT 1 FROM kits WHERE linea_id = ? AND tipologia_codigo = ?",
                        (lid, codigo)):
            continue
        kit_id = db.insertar("kits", {
            "nombre": f"Kit {nombre} — {linea}", "linea_id": lid,
            "tipologia_codigo": codigo,
            "descripcion": "Accesorios de la tipología. Falta cargarles el precio.",
            "activo": 1})
        for acc, formula in KITS_MDT.get(esquema, []):
            if acc in id_acc:
                db.insertar("kit_items", {
                    "kit_id": kit_id, "accesorio_id": id_acc[acc],
                    "cantidad_formula": formula, "variable_clave": ""})
        hecho["kits"] += 1

    # -- opciones: premarco y contramarco (Actual), mosquitero (corredizas) --
    hecho.update(_declarar_opciones(db))

    # La marca va al final y en el mismo commit que todo lo demás: o queda
    # sembrado y marcado, o no queda ninguna de las dos cosas.
    db.set_parametro(PARAM_SEMBRADO, VERSION_CATALOGO,
                     "Versión de los catálogos MDT ya sembrados", "Técnico")
    db.cx.commit()
    return hecho


# ---------------------------------------------------------------------------
# Actualización de una base ya sembrada
# ---------------------------------------------------------------------------

def _mismo_valor(guardado, esperado) -> bool:
    """¿La columna sigue teniendo ese valor? Tolera espacios, mayúsculas y "2" contra "2.0"."""
    a = str("" if guardado is None else guardado).replace(" ", "").upper()
    b = str("" if esperado is None else esperado).replace(" ", "").upper()
    if a == b:
        return True
    try:
        return float(a) == float(b)
    except ValueError:
        return False


#: Las tipologías cuya tabla corrigió la versión 3.
TIPOLOGIAS_CORREGIDAS_V3 = ("AC-PF", "AC-BAND", "AC-PPOST")

#: Esas tres tablas tal como las sembró la versión 2, congeladas. Son la
#: "fábrica" contra la que compara :func:`_actualizar_a_v3`, y lo que sigue
#: mirando el paso a la versión 2. No se tocan: si mañana se vuelve a corregir
#: una de estas tablas, eso es otra versión, con su propia copia.
_FORMULAS_V2_CORREGIDAS = [
    ("Actual", "AC-PF", "MT-0205", "PREMARCO", "H+36", 2, "45-45", 'Jambas premarco', 1),
    ("Actual", "AC-PF", "MT-0205", "PREMARCO", "A+36", 2, "45-45", 'Umbral y dintel premarco', 2),
    ("Actual", "AC-PF", "MT-2220", "PREMARCO", "H+35", 0, "45-45", 'Jambas premarco · alternativa de MT-0205: poné la cantidad si usás este perfil', 3),
    ("Actual", "AC-PF", "MT-2220", "PREMARCO", "A+35", 0, "45-45", 'Umbral y dintel premarco · alternativa de MT-0205: poné la cantidad si usás este perfil', 4),
    ("Actual", "AC-PF", "MT-0206", "OTRO", "H+53", 2, "45-45", 'Jambas contramarco', 5),
    ("Actual", "AC-PF", "MT-0206", "OTRO", "A+53", 2, "45-45", 'Umbal y dintel contramarco', 6),
    ("Actual", "AC-PF", "MT-0906", "OTRO", "H+55", 0, "45-45", 'Jambas contramarco · alternativa de MT-0206: poné la cantidad si usás este perfil', 7),
    ("Actual", "AC-PF", "MT-0906", "OTRO", "A+55", 0, "45-45", 'Umbal y dintel contramarco · alternativa de MT-0206: poné la cantidad si usás este perfil', 8),
    ("Actual", "AC-PF", "MT-0216", "MARCO_VERTICAL", "H", 2, "45-45", 'Jambas marco recto  [medida corregida: el catálogo la trae invertida]', 9),
    ("Actual", "AC-PF", "MT-0216", "MARCO_HORIZONTAL", "A", 2, "45-45", 'Umbral y dintel marco recto  [medida corregida: el catálogo la trae invertida]', 10),
    ("Actual", "AC-PF", "MT-0229", "MARCO_VERTICAL", "H", 0, "45-45", 'Jambas marco curvo  [medida corregida: el catálogo la trae invertida] · alternativa de MT-0216: poné la cantidad si usás este perfil', 11),
    ("Actual", "AC-PF", "MT-0229", "MARCO_HORIZONTAL", "A", 0, "45-45", 'Umbral y dintel marco curvo  [medida corregida: el catálogo la trae invertida] · alternativa de MT-0216: poné la cantidad si usás este perfil', 12),
    ("Actual", "AC-PF", "MT-0202", "MARCO_VERTICAL", "H", 0, "45-45", 'Jambas marco 75 mm  [medida corregida: el catálogo la trae invertida] · alternativa de MT-0216: poné la cantidad si usás este perfil', 13),
    ("Actual", "AC-PF", "MT-0202", "MARCO_HORIZONTAL", "A", 0, "45-45", 'Umbral y dintel marco 75 mm  [medida corregida: el catálogo la trae invertida] · alternativa de MT-0216: poné la cantidad si usás este perfil', 14),
    ("Actual", "AC-PF", "MT-0270", "HOJA_HORIZONTAL", "A-51", 1, "90-90", 'Travesaño horizontal', 15),
    ("Actual", "AC-PF", "MT-0270", "HOJA_VERTICAL", "H-51", 1, "90-90", 'Travesaño vertical', 16),
    ("Actual", "AC-PF", "MT-0221", "HOJA_HORIZONTAL", "A-51", 0, "90-90", 'Travesaño horizontal angosto · alternativa de MT-0270: poné la cantidad si usás este perfil', 17),
    ("Actual", "AC-PF", "MT-0221", "HOJA_VERTICAL", "H-51", 0, "90-90", 'Travesaño vertical angosto · alternativa de MT-0270: poné la cantidad si usás este perfil', 18),
    ("Actual", "AC-PF", "MT-0222", "HOJA_HORIZONTAL", "A-51", 0, "90-90", 'Travesaño horizontal ancho · alternativa de MT-0270: poné la cantidad si usás este perfil', 19),
    ("Actual", "AC-PF", "MT-0222", "HOJA_VERTICAL", "H-51", 0, "90-90", 'Travesaño vertical ancho · alternativa de MT-0270: poné la cantidad si usás este perfil', 20),
    ("Actual", "AC-PF", "MT-0264", "HOJA_HORIZONTAL", "A-51", 1, "90-90", 'Travesaño horizontal PF curvo', 21),
    ("Actual", "AC-PF", "MT-0264", "HOJA_VERTICAL", "H-51", 1, "90-90", 'Travesaño vertical PF curvo', 22),
    ("Actual", "AC-BAND", "MT-0205", "PREMARCO", "H+36", 2, "45-45", 'Jambas premarco', 1),
    ("Actual", "AC-BAND", "MT-0205", "PREMARCO", "A+36", 2, "45-45", 'Umbral y dintel premarco', 2),
    ("Actual", "AC-BAND", "MT-0206", "OTRO", "H+54", 2, "45-45", 'Jambas contramarco', 3),
    ("Actual", "AC-BAND", "MT-0206", "OTRO", "A+54", 2, "45-45", 'Umbal y dintel contramarco', 4),
    ("Actual", "AC-BAND", "MT-0216", "MARCO_VERTICAL", "H", 2, "45-45", 'Jambas de marco', 5),
    ("Actual", "AC-BAND", "MT-0216", "MARCO_HORIZONTAL", "A", 2, "45-45", 'Umbral y dintel marco', 6),
    ("Actual", "AC-BAND", "MT-0227", "MARCO_VERTICAL", "H-39", 2, "45-45", 'Jambas de hoja borde recto', 7),
    ("Actual", "AC-BAND", "MT-0227", "HOJA_HORIZONTAL", "A-39", 2, "45-45", 'Zócalo y cabezal de hoja borde recto', 8),
    ("Actual", "AC-BAND", "MT-0236", "MARCO_VERTICAL", "H-39", 2, "45-45", 'Jambas de hoja borde curvo', 9),
    ("Actual", "AC-BAND", "MT-0236", "HOJA_HORIZONTAL", "A-39", 2, "45-45", 'Zócalo y cabezal de hoja borde curvo', 10),
    ("Actual", "AC-BAND", "MT-0215", "MARCO_VERTICAL", "H-39", 0, "45-45", 'Jambas de hoja borde recto · alternativa de MT-0227: poné la cantidad si usás este perfil', 11),
    ("Actual", "AC-BAND", "MT-0215", "HOJA_HORIZONTAL", "A-39", 0, "45-45", 'Zócalo y cabezal de hoja borde recto · alternativa de MT-0227: poné la cantidad si usás este perfil', 12),
    ("Actual", "AC-BAND", "MT-0235", "MARCO_VERTICAL", "H-39", 0, "45-45", 'Jambas de hoja borde curvo · alternativa de MT-0236: poné la cantidad si usás este perfil', 13),
    ("Actual", "AC-BAND", "MT-0235", "HOJA_HORIZONTAL", "A-39", 0, "45-45", 'Zócalo y cabezal de hoja borde curvo · alternativa de MT-0236: poné la cantidad si usás este perfil', 14),
    ("Actual", "AC-BAND", "MT-2210", "MARCO_VERTICAL", "H-39", 0, "45-45", 'Jambas de hoja borde curvo v/s  [medida corregida: el catálogo la trae invertida] · el catálogo no publica su peso por metro: poné el peso y la cantidad para usarlo', 15),
    ("Actual", "AC-BAND", "MT-1211", "MARCO_VERTICAL", "H-39", 0, "45-45", 'Jambas de hoja borde curvo DVH  [medida corregida: el catálogo la trae invertida] · alternativa de MT-0236: poné la cantidad si usás este perfil', 16),
    ("Actual", "AC-BAND", "MT-0221", "HOJA_HORIZONTAL", "A-34", 1, "90-90", 'Travesaño horizontal angosto', 17),
    ("Actual", "AC-BAND", "MT-0213", "MARCO_VERTICAL", "H", 1, "90-90", '', 18),
    ("Actual", "AC-PPOST", "MT-0205", "MARCO_VERTICAL", "H+18", 2, "45-90", '', 1),
    ("Actual", "AC-PPOST", "MT-0205", "MARCO_HORIZONTAL", "A+36", 1, "45-45", '', 2),
    ("Actual", "AC-PPOST", "MT-0206", "MARCO_HORIZONTAL", "A+54", 0, "45-45", 'alternativa de MT-0205: poné la cantidad si usás este perfil', 3),
    ("Actual", "AC-PPOST", "MT-0216", "MARCO_VERTICAL", "H", 0, "45-90", 'alternativa de MT-0205: poné la cantidad si usás este perfil', 4),
    ("Actual", "AC-PPOST", "MT-0216", "MARCO_HORIZONTAL", "A", 0, "45-45", 'alternativa de MT-0205: poné la cantidad si usás este perfil', 5),
    ("Actual", "AC-PPOST", "MT-0214", "MARCO_VERTICAL", "H-24", 0, "45-90", 'alternativa de MT-0205: poné la cantidad si usás este perfil', 6),
    ("Actual", "AC-PPOST", "MT-0214", "MARCO_HORIZONTAL", "A-39", 0, "45-45", 'alternativa de MT-0205: poné la cantidad si usás este perfil', 7),
    ("Actual", "AC-PPOST", "MT-0214", "MARCO_HORIZONTAL", "(A/2)-23", 0, "45-45", 'alternativa de MT-0205: poné la cantidad si usás este perfil', 8),
    ("Actual", "AC-PPOST", "MT-0218", "MARCO_HORIZONTAL", "A-192", 0, "90-90", 'alternativa de MT-0205: poné la cantidad si usás este perfil', 9),
    ("Actual", "AC-PPOST", "MT-0218", "MARCO_HORIZONTAL", "(A/2)-175", 0, "90-90", 'alternativa de MT-0205: poné la cantidad si usás este perfil', 10),
    ("Actual", "AC-PPOST", "MT-0219", "MARCO_HORIZONTAL", "A-192", 0, "90-90", 'alternativa de MT-0205: poné la cantidad si usás este perfil', 11),
    ("Actual", "AC-PPOST", "MT-0219", "MARCO_HORIZONTAL", "(A/2)-175", 0, "90-90", 'alternativa de MT-0205: poné la cantidad si usás este perfil', 12),
    ("Actual", "AC-PPOST", "MT-0224", "MARCO_VERTICAL", "H-52", 0, "90-90", 'alternativa de MT-0205: poné la cantidad si usás este perfil', 13),
    ("Actual", "AC-PPOST", "MT-0272", "MARCO_VERTICAL", "H-219", 0, "45-45", 'alternativa de MT-0205: poné la cantidad si usás este perfil', 14),
    ("Actual", "AC-PPOST", "MT-0272", "MARCO_HORIZONTAL", "A-188", 0, "45-45", 'alternativa de MT-0205: poné la cantidad si usás este perfil', 15),
    ("Actual", "AC-PPOST", "MT-0272", "MARCO_HORIZONTAL", "(A/2)-171", 0, "45-45", 'alternativa de MT-0205: poné la cantidad si usás este perfil', 16),
    ("Actual", "AC-PPOST", "MT-2705", "MARCO_HORIZONTAL", "A-248", 0, "90-90", 'alternativa de MT-0205: poné la cantidad si usás este perfil', 17),
    ("Actual", "AC-PPOST", "MT-2705", "MARCO_HORIZONTAL", "(A/2)-231", 0, "90-90", 'alternativa de MT-0205: poné la cantidad si usás este perfil', 18),
    ("Actual", "AC-PPOST", "MT-2695", "MARCO_HORIZONTAL", "A-234", 0, "90-90", 'alternativa de MT-0205: poné la cantidad si usás este perfil', 19),
    ("Actual", "AC-PPOST", "MT-2708", "MARCO_HORIZONTAL", "A-248", 0, "90-90", 'alternativa de MT-0205: poné la cantidad si usás este perfil', 20),
    ("Actual", "AC-PPOST", "MT-2708", "MARCO_HORIZONTAL", "(A/2)-231", 0, "90-90", 'alternativa de MT-0205: poné la cantidad si usás este perfil', 21),
]


def _formulas_v2() -> list[tuple]:
    """``FORMULAS_MDT`` como era en la versión 2: la vigente, con las tres tablas viejas."""
    return ([r for r in FORMULAS_MDT if r[1] not in TIPOLOGIAS_CORREGIDAS_V3]
            + _FORMULAS_V2_CORREGIDAS)


def _actualizar_a_v2(db) -> dict:
    """Versión 1 -> 2: premarco y contramarco de Actual pasan a ser opciones.

    No resiembra nada. Recorre los renglones de fábrica de esas dos opciones y,
    en cada uno, reescribe una columna SÓLO si todavía tiene el valor que sembró
    la versión 1. Lo que el usuario cambió queda como lo dejó, y se informa:

    * cambió la cantidad de una alternativa para usarla: se condiciona el
      largo, así la opción la sigue gobernando;
    * corrigió un largo: su largo queda y se condiciona la cantidad;
    * borró el renglón: no se vuelve a crear.

    Un renglón se reconoce por tipología, perfil, función y orden. Correr el
    paso dos veces no cambia nada: lo que ya tiene el valor de la versión 2 se
    saltea. No hace commit; lo hace :func:`actualizar_mdt` junto con la marca.
    """
    hecho = {"formulas_actualizadas": 0, "formulas_editadas": [],
             "formulas_ausentes": 0, "opciones": 0, "opciones_copiadas": 0}
    lid = _linea_id(db, "MDT Actual")
    if not lid:
        return hecho    # el usuario borró la línea: no hay nada que actualizar

    # La tabla de la versión 2, no la vigente: la 3 corrigió tres tipologías, y
    # el paso a la 2 tiene que seguir haciendo exactamente lo que hacía.
    formulas_v2 = _formulas_v2()
    for linea, tip, perfil, funcion, form, cant, _corte, _nota, orden in formulas_v2:
        # Sólo premarco y contramarco: el mosquitero es de la versión 4.
        if opcion_de_renglon(linea, tip, perfil, funcion) not in CLAVES_V2:
            continue
        largo_v2, cantidad_v2 = formulas_de_fabrica(linea, tip, perfil, funcion, form, cant)
        filas = db.query(
            "SELECT id, formula_largo, cantidad_piezas FROM tipologia_formulas "
            "WHERE tipologia_codigo = ? AND linea_id = ? AND perfil_codigo = ? "
            "AND funcion = ? AND orden = ?", (tip, lid, perfil, funcion, orden))
        if not filas:
            hecho["formulas_ausentes"] += 1
            continue

        for fila in filas:
            cambios = {}
            for columna, de_v1, de_v2 in (("formula_largo", form, largo_v2),
                                          ("cantidad_piezas", cant, cantidad_v2)):
                if _mismo_valor(fila[columna], de_v2):
                    continue                        # ya está al día
                if _mismo_valor(fila[columna], de_v1):
                    cambios[columna] = de_v2        # sigue de fábrica: se actualiza
                else:                               # lo tocó el usuario: se respeta
                    hecho["formulas_editadas"].append(
                        f"{tip} · {perfil} · {columna} = {fila[columna]!r}")
            if cambios:
                asignaciones = ", ".join(f"{columna} = ?" for columna in cambios)
                db.cx.execute(f"UPDATE tipologia_formulas SET {asignaciones} WHERE id = ?",
                              (*cambios.values(), fila["id"]))
                hecho["formulas_actualizadas"] += 1

    hecho.update(_declarar_opciones(db, CLAVES_V2, formulas=formulas_v2))
    return hecho


def _actualizar_a_v3(db) -> dict:
    """Versión 2 -> 3: las tablas de AC-PF, AC-BAND y AC-PPOST, corregidas.

    Mismo contrato que :func:`_actualizar_a_v2`, columna por columna —función,
    largo, cantidad y nota—, comparando cada renglón contra cómo lo sembró la
    versión 2 (:data:`_FORMULAS_V2_CORREGIDAS`):

    * sigue de fábrica: pasa a la versión 3;
    * el usuario editó una columna que la corrección cambia: queda la suya y se
      informa; si la corrección no cambia esa columna, queda sin aviso;
    * el usuario borró el renglón: no se vuelve a crear;
    * los renglones que la versión 2 no tenía (AC-BAND 19 y 20, AC-PPOST 22 a
      27) se agregan, una sola vez;
    * si ningún renglón de la tipología conserva su nota de fábrica, la tabla la
      rehizo el usuario a mano: no se toca —ni correcciones, ni renglones
      nuevos, ni opciones— y se informa.

    Un renglón se reconoce por tipología, perfil y orden, sin la función, que
    es una de las columnas que se corrigen: por eso los renglones nuevos van al
    final y los existentes no se renumeran. Ninguna de las tres es corrediza, así
    que las reglas vigentes de :func:`_columnas_de_fabrica` son, para ellas, las
    de la versión 3. No hace commit; lo hace :func:`actualizar_mdt`.
    """
    hecho = {"formulas_actualizadas": 0, "formulas_editadas": [], "formulas_ausentes": 0,
             "formulas_agregadas": 0, "tablas_a_mano": [],
             "opciones": 0, "opciones_copiadas": 0}
    lid = _linea_id(db, "MDT Actual")
    if not lid:
        return hecho    # el usuario borró la línea: no hay nada que actualizar

    pesos = {codigo: peso for codigo, peso, *_resto in PERFILES_ACTUAL}
    corregidas = []

    for tip in TIPOLOGIAS_CORREGIDAS_V3:
        de_v2 = {(r[2], r[8]): _columnas_de_fabrica(r)
                 for r in _FORMULAS_V2_CORREGIDAS if r[1] == tip}
        de_v3 = [(r, _columnas_de_fabrica(r)) for r in FORMULAS_MDT if r[1] == tip]
        filas = db.query("SELECT * FROM tipologia_formulas "
                         "WHERE tipologia_codigo = ? AND linea_id = ?", (tip, lid))

        # ¿La rehizo a mano? Ningún renglón conserva una nota de fábrica, ni de
        # la versión 2 ni —si el paso ya corrió— de la 3.
        notas = {c["nota"] for c in de_v2.values()} | {c["nota"] for _r, c in de_v3}
        if not any(_mismo_valor(f["nota"], nota) for f in filas for nota in notas):
            hecho["tablas_a_mano"].append(tip)
            continue
        corregidas.append(tip)

        for renglon, nuevas in de_v3:
            perfil, orden = renglon[2], renglon[8]
            propias = [f for f in filas
                       if f["perfil_codigo"] == perfil and f["orden"] == orden]
            viejas = de_v2.get((perfil, orden))

            if viejas is None:
                # Un renglón que faltaba en la versión 2: se agrega una sola vez.
                if not propias:
                    _insertar(db, "tipologia_formulas", {
                        "tipologia_codigo": tip, "linea_id": lid,
                        "perfil_codigo": perfil, **nuevas,
                        "peso_kg_m": pesos.get(perfil, 0.0), "orden": orden})
                    hecho["formulas_agregadas"] += 1
                continue
            if not propias:
                hecho["formulas_ausentes"] += 1     # lo borró el usuario
                continue

            for fila in propias:
                cambios = {}
                for columna in ("funcion", "formula_largo", "cantidad_piezas", "nota"):
                    if viejas[columna] == nuevas[columna]:
                        continue                    # la corrección no toca esta columna
                    if _mismo_valor(fila[columna], nuevas[columna]):
                        continue                    # ya está al día
                    if _mismo_valor(fila[columna], viejas[columna]):
                        cambios[columna] = nuevas[columna]   # sigue de fábrica
                    else:                           # lo tocó el usuario: se respeta
                        hecho["formulas_editadas"].append(
                            f"{tip} · {perfil} · {columna} = {fila[columna]!r}")
                if cambios:
                    asignaciones = ", ".join(f"{columna} = ?" for columna in cambios)
                    db.cx.execute(
                        f"UPDATE tipologia_formulas SET {asignaciones} WHERE id = ?",
                        (*cambios.values(), fila["id"]))
                    hecho["formulas_actualizadas"] += 1

    # AC-PPOST tiene ahora premarco y contramarco: se declaran sus opciones,
    # salvo en una tabla que el usuario rehízo a mano.
    hecho.update(_declarar_opciones(db, CLAVES_V2, tipologias=corregidas))
    return hecho


def _actualizar_a_v4(db) -> dict:
    """Versión 3 -> 4: el mosquitero de las corredizas pasa a ser opción.

    Mismo contrato que los pasos anteriores: no resiembra nada, y en cada
    renglón de mosquitero reescribe una columna —largo, cantidad o función—
    SÓLO si todavía tiene el valor de fábrica. Lo que el usuario cambió queda
    como lo dejó:

    * corrigió un largo: su largo queda, y cantidad y función se actualizan;
    * le cambió la función: queda la suya, y largo y cantidad se condicionan;
    * le puso cantidad a una alternativa: su cantidad queda y el largo
      condicionado la sigue gobernando;
    * borró el renglón: no se vuelve a crear.

    Se informa lo editado que choca con el cambio; una columna que la versión 4
    no cambia (la cantidad en 0 de una alternativa) queda sin aviso, como en la
    versión 3. El renglón se reconoce por tipología, línea, perfil y orden, sin
    la función, que es una de las columnas que cambia. Corre sobre las dos
    líneas, y correrlo dos veces no cambia nada. No hace commit; lo hace
    :func:`actualizar_mdt`.
    """
    hecho = {"formulas_actualizadas": 0, "formulas_editadas": [],
             "formulas_ausentes": 0, "opciones": 0, "opciones_copiadas": 0}
    ids: dict[str, int] = {}

    for renglon in FORMULAS_MDT:
        linea, tip, perfil, funcion, form, cant, _corte, _nota, orden = renglon
        if opcion_de_renglon(linea, tip, perfil, funcion) != "MOSQUITERO":
            continue
        nombre = _LINEA_DE_TIPOLOGIA.get(tip, "")
        if nombre not in ids:
            ids[nombre] = _linea_id(db, nombre) if nombre else 0
        if not ids[nombre]:
            continue    # el usuario borró la línea: no hay nada que actualizar

        nuevas = _columnas_de_fabrica(renglon)
        # Hasta la versión 3 estos renglones se sembraban tal cual los publica el
        # fabricante: sin condición y con la función con la que se cargaron.
        viejas = {"funcion": funcion, "formula_largo": form, "cantidad_piezas": str(cant)}
        filas = db.query(
            "SELECT id, funcion, formula_largo, cantidad_piezas FROM tipologia_formulas "
            "WHERE tipologia_codigo = ? AND linea_id = ? AND perfil_codigo = ? "
            "AND orden = ?", (tip, ids[nombre], perfil, orden))
        if not filas:
            hecho["formulas_ausentes"] += 1
            continue

        for fila in filas:
            cambios = {}
            for columna, de_antes in viejas.items():
                if de_antes == nuevas[columna]:
                    continue                        # la versión 4 no cambia esta columna
                if _mismo_valor(fila[columna], nuevas[columna]):
                    continue                        # ya está al día
                if _mismo_valor(fila[columna], de_antes):
                    cambios[columna] = nuevas[columna]   # sigue de fábrica
                else:                               # lo tocó el usuario: se respeta
                    hecho["formulas_editadas"].append(
                        f"{tip} · {perfil} · {columna} = {fila[columna]!r}")
            if cambios:
                asignaciones = ", ".join(f"{columna} = ?" for columna in cambios)
                db.cx.execute(f"UPDATE tipologia_formulas SET {asignaciones} WHERE id = ?",
                              (*cambios.values(), fila["id"]))
                hecho["formulas_actualizadas"] += 1

    hecho.update(_declarar_opciones(db, ("MOSQUITERO",)))
    return hecho


#: Pasos para llevar una base sembrada con una versión anterior a la vigente:
#: ``{versión de destino: función}``. Cada paso cambia sólo lo que sigue de
#: fábrica y no hace commit.
ACTUALIZACIONES = {
    2: _actualizar_a_v2,
    3: _actualizar_a_v3,
    4: _actualizar_a_v4,
}


def _sumar_resumen(total: dict, parcial: dict) -> dict:
    """Suma el resumen de un paso al acumulado: los números se suman y las listas se juntan.

    Los pasos informan con las mismas claves; con ``update`` una base que salta
    de la versión 1 a la última se quedaría sólo con lo que dijo el último paso,
    y perdería, por ejemplo, las ediciones del usuario que informó la 2.
    """
    for clave, valor in parcial.items():
        if isinstance(valor, list):
            total.setdefault(clave, []).extend(valor)
        elif isinstance(valor, (int, float)):
            total[clave] = total.get(clave, 0) + valor
        else:
            total[clave] = valor
    return total


def actualizar_mdt(db, anterior: int) -> dict:
    """Aplica, en orden, los pasos que le faltan a una base ya sembrada.

    Respalda antes, como una migración de esquema, y confirma todo en un solo
    commit junto con la marca de versión: si algo falla no queda nada a medias,
    y el próximo arranque lo vuelve a intentar.
    """
    hecho: dict = {}
    if anterior >= VERSION_CATALOGO:
        return hecho

    db.respaldar(f"previo_catalogo_v{VERSION_CATALOGO}")
    try:
        for destino in range(anterior + 1, VERSION_CATALOGO + 1):
            paso = ACTUALIZACIONES.get(destino)
            if paso:
                _sumar_resumen(hecho, paso(db))
        # set_parametro() confirma: los cambios de los pasos entran con la marca.
        db.set_parametro(PARAM_SEMBRADO, VERSION_CATALOGO,
                         "Versión de los catálogos MDT ya sembrados", "Técnico")
    except Exception:
        db.cx.rollback()
        raise
    return hecho
