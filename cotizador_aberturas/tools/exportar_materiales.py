"""
Exporta a Excel el listado completo de materiales de un presupuesto.

Es el equivalente a la salida de materiales de Winmaker: una planilla que se le
manda al proveedor o se usa en el taller, con una hoja por tipo de material más
el detalle de corte abertura por abertura.

    python -m tools.exportar_materiales                # último presupuesto
    python -m tools.exportar_materiales PRES-0007      # uno en particular
    python -m tools.exportar_materiales PRES-0007 -o compras.xlsx

Hojas que genera
----------------
``Resumen``      cabecera del presupuesto y totales por rubro
``Perfiles``     consolidado por perfil y largo, con barras a comprar
``Barras``       cuántas barras de cada perfil, con su recorte
``Vidrios``      m² por tipo, netos y con desperdicio
``Accesorios``   consumo total por artículo
``Cortes``       listado de corte pieza por pieza, agrupado por abertura

openpyxl se importa adentro de las funciones a propósito: el programa tiene que
poder abrirse aunque la librería no esté instalada, y avisar recién cuando el
usuario pide exportar.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from core import formato as F
from core.calculo import (calcular_presupuesto, presupuesto_desde_db,
                          resumen_materiales)
from core.despiece import optimizar_por_perfil

#: Ancho de columna por tipo de contenido, en caracteres de Excel
ANCHOS = {"codigo": 16, "descripcion": 44, "numero": 14, "texto": 22}


def _encabezado(ws, titulos: list[str], anchos: list[int]) -> None:
    from openpyxl.styles import Alignment, Font, PatternFill

    relleno = PatternFill("solid", fgColor="1B3A57")
    for col, (titulo, ancho) in enumerate(zip(titulos, anchos), start=1):
        celda = ws.cell(row=1, column=col, value=titulo)
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = relleno
        celda.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[celda.column_letter].width = ancho
    ws.freeze_panes = "A2"


def _fila(ws, valores: list, numero_fila: int, formatos: dict[int, str] | None = None):
    for col, valor in enumerate(valores, start=1):
        celda = ws.cell(row=numero_fila, column=col, value=valor)
        if formatos and col in formatos:
            celda.number_format = formatos[col]
    return numero_fila + 1


# ---------------------------------------------------------------------------
# Hojas
# ---------------------------------------------------------------------------

def _hoja_resumen(wb, db, pres) -> None:
    from openpyxl.styles import Font

    ws = wb.active
    ws.title = "Resumen"
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 46

    emp = db.empresa()
    datos = [
        ("Presupuesto", pres.numero),
        ("Fecha", str(pres.fecha)),
        ("Cliente", pres.cliente.razon_social),
        ("Obra", pres.cliente.obra),
        ("Emitido por", emp["razon_social"] or "—"),
        ("", ""),
        ("Aberturas", sum(i.cantidad for i in pres.items)),
        ("Superficie total", round(sum(i.m2_total for i in pres.items), 3)),
        ("Peso de aluminio (kg)",
         round(sum(r.despiece.aluminio.peso_total_kg * r.item.cantidad
                   for r in pres.resultados), 3)),
        ("Vidrio (m²)",
         round(sum(r.despiece.vidrio.m2_total * r.item.cantidad
                   for r in pres.resultados), 3)),
    ]

    ws["A1"] = "Listado de materiales"
    ws["A1"].font = Font(bold=True, size=14)
    fila = 3
    for etiqueta, valor in datos:
        ws.cell(row=fila, column=1, value=etiqueta).font = Font(bold=bool(etiqueta))
        ws.cell(row=fila, column=2, value=valor)
        fila += 1

    ws.cell(row=fila + 1, column=1,
            value=f"Generado el {date.today().isoformat()}").font = Font(italic=True,
                                                                          size=9)


def _hoja_perfiles(wb, materiales) -> None:
    ws = wb.create_sheet("Perfiles")
    _encabezado(ws, ["Perfil", "Descripción", "Largo (mm)", "Piezas", "Peso (kg)"],
                [ANCHOS["codigo"], ANCHOS["descripcion"], 14, 12, 14])
    fila = 2
    for reg in materiales["perfiles"]:
        fila = _fila(ws, [reg["perfil"], reg["descripcion"], round(reg["largo_mm"], 1),
                          reg["cantidad"], round(reg["peso_kg"], 3)], fila,
                     {3: "0.0", 5: "0.000"})


def _hoja_barras(wb, pres) -> None:
    """Barras a comprar, consolidando todas las aberturas del presupuesto.

    No alcanza con sumar las barras de cada ítem por separado: si dos aberturas
    usan el mismo perfil, los recortes de una sirven para la otra. Por eso se
    juntan TODAS las piezas del presupuesto y recién ahí se optimiza.
    """
    ws = wb.create_sheet("Barras")
    _encabezado(ws, ["Perfil", "Descripción", "Largo de barra (mm)", "Barras",
                     "Metros útiles", "Recorte (m)", "% recorte", "Peso comprado (kg)"],
                [ANCHOS["codigo"], ANCHOS["descripcion"], 20, 10, 14, 13, 11, 18])

    todas = []
    for res in pres.resultados:
        for _ in range(res.item.cantidad):
            todas.extend(res.despiece.aluminio.piezas)

    fila = 2
    for b in optimizar_por_perfil(todas):
        fila = _fila(ws, [b.perfil_codigo, b.descripcion, b.largo_barra_mm, b.cantidad,
                          round(b.metros_utiles, 2), round(b.recorte_mm / 1000.0, 2),
                          round(b.desperdicio_pct, 4), round(b.peso_comprado_kg, 3)],
                     fila, {5: "0.00", 6: "0.00", 7: "0.0%", 8: "0.000"})


def _hoja_vidrios(wb, pres, materiales) -> None:
    ws = wb.create_sheet("Vidrios")
    _encabezado(ws, ["Tipo de vidrio", "Paño (mm)", "Paños", "m² netos"],
                [30, 20, 10, 14])

    # Detalle por medida: es lo que la vidriería necesita para cortar
    medidas: dict[tuple[str, float, float], int] = defaultdict(int)
    for res in pres.resultados:
        for pano in res.despiece.vidrio.panos:
            clave = (res.despiece.vidrio.tipo, pano.ancho_mm, pano.alto_mm)
            medidas[clave] += pano.cantidad * res.item.cantidad

    fila = 2
    for (tipo, ancho, alto), cantidad in sorted(medidas.items()):
        fila = _fila(ws, [tipo, f"{ancho:.0f} x {alto:.0f}", cantidad,
                          round(ancho * alto / 1_000_000 * cantidad, 3)], fila,
                     {4: "0.000"})

    fila += 1
    ws.cell(row=fila, column=1, value="TOTALES POR TIPO")
    fila += 1
    for reg in materiales["vidrios"]:
        fila = _fila(ws, [reg["tipo"], "", "", reg["m2"]], fila, {4: "0.000"})


def _hoja_accesorios(wb, materiales) -> None:
    ws = wb.create_sheet("Accesorios")
    _encabezado(ws, ["Código", "Descripción", "Unidad", "Cantidad", "Importe"],
                [ANCHOS["codigo"], ANCHOS["descripcion"], 10, 14, 16])
    fila = 2
    for reg in materiales["accesorios"]:
        fila = _fila(ws, [reg["codigo"], reg["descripcion"], reg["unidad"],
                          round(reg["cantidad"], 3), round(reg["total"], 2)], fila,
                     {4: "0.000", 5: '"$"#,##0.00'})


def _hoja_cortes(wb, pres) -> None:
    """Listado de corte, agrupado por abertura. Es la hoja que va al taller."""
    from openpyxl.styles import Font

    ws = wb.create_sheet("Cortes")
    _encabezado(ws, ["Ítem", "Abertura", "Perfil", "Función / aclaración",
                     "Largo (mm)", "Piezas", "Peso (kg)"],
                [8, 34, ANCHOS["codigo"], 32, 13, 10, 13])

    fila = 2
    for res in pres.resultados:
        it = res.item
        celda = ws.cell(row=fila, column=2,
                        value=f"{it.descripcion} · {it.medida_texto} · x{it.cantidad}")
        celda.font = Font(bold=True)
        ws.cell(row=fila, column=1, value=it.orden).font = Font(bold=True)
        fila += 1
        for p in res.despiece.aluminio.piezas:
            fila = _fila(ws, ["", "", p.perfil_codigo, p.funcion_legible,
                              round(p.largo_mm, 1), p.cantidad * it.cantidad,
                              round(p.peso_kg * it.cantidad, 3)], fila,
                         {5: "0.0", 7: "0.000"})
        fila += 1


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def exportar(db, pres, destino: str | Path) -> Path:
    """Escribe la planilla y devuelve la ruta.

    ``pres`` tiene que venir ya calculado (con ``resultados`` cargados). Si no lo
    está, se recalcula acá para que la función sirva también desde la consola.
    """
    try:
        from openpyxl import Workbook
    except ImportError as exc:                       # pragma: no cover
        raise ImportError(
            "Para exportar a Excel hace falta openpyxl.\n\n    pip install openpyxl"
        ) from exc

    if not getattr(pres, "resultados", None):
        calcular_presupuesto(db, pres)

    materiales = resumen_materiales(pres)

    wb = Workbook()
    _hoja_resumen(wb, db, pres)
    _hoja_perfiles(wb, materiales)
    _hoja_barras(wb, pres)
    _hoja_vidrios(wb, pres, materiales)
    _hoja_accesorios(wb, materiales)
    _hoja_cortes(wb, pres)

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    wb.save(destino)
    return destino


def nombre_sugerido(pres) -> str:
    numero = (pres.numero or "presupuesto").replace("/", "-").replace("\\", "-")
    return f"Materiales {numero}.xlsx"


# ---------------------------------------------------------------------------
# Uso desde la consola
# ---------------------------------------------------------------------------

def _main(argv: list[str]) -> int:
    from core.database import DB

    numero = ""
    salida = ""
    resto = list(argv)
    if "-o" in resto:
        i = resto.index("-o")
        salida = resto[i + 1] if len(resto) > i + 1 else ""
        del resto[i:i + 2]
    if resto:
        numero = resto[0]

    db = DB()
    if numero:
        fila = db.query_one("SELECT id FROM presupuestos WHERE numero = ?", (numero,))
    else:
        fila = db.query_one("SELECT id FROM presupuestos ORDER BY id DESC LIMIT 1")
    if fila is None:
        print("No se encontró el presupuesto.")
        return 1

    pres = presupuesto_desde_db(db, fila["id"])
    calcular_presupuesto(db, pres)
    ruta = exportar(db, pres, salida or nombre_sugerido(pres))
    print(f"Listado de materiales: {ruta}")
    print(f"  {len(pres.items)} abertura(s) · "
          f"{F.kilos(sum(r.despiece.aluminio.peso_total_kg * r.item.cantidad for r in pres.resultados))}")
    db.cerrar()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
