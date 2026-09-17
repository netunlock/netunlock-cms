"""
Motor de cotización.

Encadena despiece -> costos -> precio de venta -> descuentos -> IVA -> total.

Orden del desglose final (el mismo que sale impreso en el PDF):

    Subtotal ítems (bruto)
  - Descuentos por ítem
  = Subtotal ítems
  + Mano de obra
  + Logística
  = Subtotal general
  - Descuento global (% o $)
  = Neto
  + IVA
  = TOTAL
"""

from __future__ import annotations

from dataclasses import asdict

from datetime import date

from . import variables as variables_tipologia
from .despiece import calcular_despiece
from .models import (Cliente, CostosItem, Item, Logistica, ManoObra, Presupuesto,
                     Resumen, ResultadoItem)


#: Función de despiece de las piezas de premarco (ver despiece.FUNCIONES_CONOCIDAS).
FUNCION_PREMARCO = "PREMARCO"


def costo_premarco(db, item, despiece=None) -> float:
    """Premarco cobrado por parámetro: por m² de abertura o por metro de perímetro.

    Es para las líneas que no cortan el premarco con sus propios perfiles. Si el
    despiece ya trae piezas de premarco —MDT Actual con la casilla tildada—, el
    premarco ya se cobra con el aluminio, por peso, y sumar además el parámetro
    lo cobraría dos veces. Con ``despiece=None`` se comporta como siempre.
    """
    if not item.incluye_premarco:
        return 0.0
    if despiece is not None and any(p.funcion == FUNCION_PREMARCO
                                    for p in despiece.aluminio.piezas):
        return 0.0
    modo = (db.parametro("premarco_modo", "m2") or "m2").lower()
    if modo == "ml":
        perimetro_m = 2.0 * (item.ancho_mm + item.alto_mm) / 1000.0
        return perimetro_m * db.parametro_float("premarco_ml", 4500)
    return item.m2_unitario * db.parametro_float("premarco_m2", 6000)


#: Función de despiece de las piezas de mosquitero (ver despiece.FUNCIONES_CONOCIDAS).
FUNCION_MOSQUITERO = "MOSQUITERO"


def costo_mosquitero(db, item, despiece=None) -> float:
    """Mosquitero cobrado por parámetro, por m² de abertura.

    ``mosquitero_m2`` es el mosquitero entero, para las líneas que no lo cortan
    con sus propios perfiles. Si el despiece ya trae piezas de mosquitero —una
    corrediza MDT con la casilla tildada—, el aluminio ya se cobra por peso y
    sumar ``mosquitero_m2`` lo cobraría dos veces. Lo que el despiece no trae es
    la tela: se cobra con ``mosquitero_tela_m2``, que arranca en $ 0.

    Con ``despiece=None`` se comporta como siempre.
    """
    if not item.incluye_mosquitero:
        return 0.0
    if despiece is not None and any(p.funcion == FUNCION_MOSQUITERO
                                    for p in despiece.aluminio.piezas):
        return item.m2_unitario * db.parametro_float("mosquitero_tela_m2", 0.0)
    return item.m2_unitario * db.parametro_float("mosquitero_m2", 9000)


def calcular_item(db, item, margen_pct: float, mano_obra_en_item: bool = False) -> ResultadoItem:
    """Calcula el despiece y los costos de UNA unidad, y arma el resultado del renglón."""
    despiece = calcular_despiece(
        db,
        item.tipologia_codigo,
        item.linea_id,
        item.color,
        item.ancho_mm,
        item.alto_mm,
        item.hojas,
        item.vidrio_id,
        # Las opciones de la tipología (premarco, alto del paño fijo, tipo de
        # cierre) entran al contexto de las fórmulas. Si la tipología no declara
        # ninguna, esto es {} y el despiece se comporta igual que siempre.
        variables=variables_tipologia.resolver(db, item),
    )

    mo = 0.0
    if mano_obra_en_item:
        mo = item.m2_unitario * db.parametro_float("mo_por_m2_directo", 0.0)

    costos = CostosItem(
        aluminio=despiece.aluminio.costo,
        vidrio=despiece.vidrio.costo,
        accesorios=despiece.accesorios.costo,
        # Con el despiece a la vista: si ya corta el premarco o el mosquitero, no
        # se cobran otra vez por m² (del mosquitero queda la tela).
        premarco=costo_premarco(db, item, despiece),
        mosquitero=costo_mosquitero(db, item, despiece),
        mano_obra=mo,
    )

    return ResultadoItem(item=item, despiece=despiece, costos=costos, margen_pct=margen_pct)


def horas_sugeridas(db, items) -> float:
    """Horas de fabricación estimadas a partir de los m² y la tipología."""
    total = 0.0
    for item in items:
        tip = db.tipologia(item.tipologia_codigo)
        horas_m2 = (
            tip["horas_por_m2"] if tip and tip["horas_por_m2"] else db.parametro_float("mo_horas_por_m2", 0.85)
        )
        total += item.m2_total * horas_m2
    return round(total, 2)


def calcular_presupuesto(db, pres: Presupuesto, mano_obra_en_item: bool = False) -> Presupuesto:
    """Recalcula todo el presupuesto in-place y devuelve el mismo objeto."""

    pres.resultados = [
        calcular_item(db, it, pres.margen_pct, mano_obra_en_item) for it in pres.items
    ]

    r = Resumen()
    r.subtotal_items_bruto = sum(x.bruto for x in pres.resultados)
    r.descuentos_items = sum(x.descuento for x in pres.resultados)
    r.subtotal_items = r.subtotal_items_bruto - r.descuentos_items

    if pres.mano_obra.automatica:
        pres.mano_obra.horas = horas_sugeridas(db, pres.items)
    r.mano_obra = 0.0 if mano_obra_en_item else pres.mano_obra.costo
    r.logistica = pres.logistica.costo

    r.subtotal_general = r.subtotal_items + r.mano_obra + r.logistica

    if pres.descuento_global_tipo == "monto":
        r.descuento_global = min(pres.descuento_global_valor, r.subtotal_general)
    else:
        r.descuento_global = r.subtotal_general * pres.descuento_global_valor

    r.neto = r.subtotal_general - r.descuento_global
    r.iva_pct = pres.iva_pct if pres.aplica_iva else 0.0
    r.iva = r.neto * r.iva_pct
    r.total = r.neto + r.iva

    pres.resumen = r
    pres.snapshot = snapshot(pres)
    return pres


def snapshot(pres: Presupuesto) -> dict:
    """Congela el cálculo completo para poder reimprimir el PDF sin recalcular."""
    return {
        "numero": pres.numero,
        "fecha": str(pres.fecha),
        "margen_pct": pres.margen_pct,
        "resumen": asdict(pres.resumen),
        "items": [
            {
                "orden": res.item.orden,
                "descripcion": res.item.descripcion,
                "medida": res.item.medida_texto,
                "cantidad": res.item.cantidad,
                "hojas": res.item.hojas,
                "costos": res.costos.como_dict(),
                "precio_unitario": res.precio_unitario,
                "descuento_pct": res.item.descuento_pct,
                "neto": res.neto,
                "peso_aluminio_kg": round(res.despiece.aluminio.peso_total_kg, 3),
                "m2_vidrio": round(res.despiece.vidrio.m2_total, 3),
                "piezas": [
                    {
                        "perfil": p.perfil_codigo,
                        "funcion": p.funcion,
                        "largo_mm": p.largo_mm,
                        "cantidad": p.cantidad,
                        "peso_kg": round(p.peso_kg, 3),
                    }
                    for p in res.despiece.aluminio.piezas
                ],
            }
            for res in pres.resultados
        ],
    }


def _columna(fila, nombre: str, por_defecto=None):
    """Lee una columna que puede no existir todavía en la base del usuario."""
    try:
        return fila[nombre]
    except (IndexError, KeyError):
        return por_defecto


def presupuesto_desde_db(db, pid: int) -> Presupuesto:
    """Reconstruye un :class:`Presupuesto` guardado, listo para recalcular.

    La interfaz arma el presupuesto campo por campo mientras el usuario lo edita;
    esto es el camino inverso, y lo necesitan todos los consumidores que trabajan
    sobre un presupuesto ya cerrado: exportación a Excel, órdenes de trabajo y
    reimpresión desde la consola.
    """
    cab, filas = db.cargar_presupuesto(pid)
    if cab is None:
        raise ValueError(f"No existe el presupuesto con id {pid}.")

    try:
        fecha = date.fromisoformat(cab["fecha"])
    except (TypeError, ValueError):
        fecha = date.today()

    pres = Presupuesto(
        id=cab["id"],
        numero=cab["numero"],
        fecha=fecha,
        validez_dias=cab["validez_dias"] or 15,
        cliente=Cliente(
            razon_social=cab["cliente_razon_social"], documento=cab["cliente_documento"],
            contacto=cab["cliente_contacto"], localidad=cab["cliente_localidad"],
            obra=cab["cliente_obra"], forma_pago=cab["cliente_forma_pago"]),
        mano_obra=ManoObra(
            valor_hora=cab["mo_valor_hora"], operarios=cab["mo_operarios"],
            horas=cab["mo_horas"], automatica=bool(cab["mo_automatica"])),
        logistica=Logistica(
            flete_recepcion=cab["log_flete_recepcion"],
            envio_colocacion=cab["log_envio_colocacion"]),
        descuento_global_tipo=cab["descuento_global_tipo"],
        descuento_global_valor=cab["descuento_global_valor"],
        aplica_iva=bool(cab["aplica_iva"]),
        iva_pct=cab["iva_pct"],
        margen_pct=cab["margen_pct"],
        observaciones_generales=cab["observaciones_generales"],
    )

    for fila in filas:
        pres.items.append(Item(
            id=fila["id"], orden=fila["orden"],
            tipologia_codigo=fila["tipologia_codigo"],
            tipologia_nombre=fila["tipologia_nombre"],
            linea_id=fila["linea_id"], linea_nombre=fila["linea_nombre"],
            color=fila["color"], ancho_mm=fila["ancho_mm"], alto_mm=fila["alto_mm"],
            hojas=fila["hojas"], cantidad=fila["cantidad"],
            vidrio_id=fila["vidrio_id"], vidrio_nombre=fila["vidrio_nombre"],
            incluye_premarco=bool(fila["incluye_premarco"]),
            incluye_mosquitero=bool(fila["incluye_mosquitero"]),
            descuento_pct=fila["descuento_pct"],
            observaciones=fila["observaciones"],
            variables=variables_tipologia.leer_json(
                _columna(fila, "variables_json", ""))))

    return pres


def resumen_materiales(pres: Presupuesto) -> dict:
    """Consolidado de materiales de todo el presupuesto (para compras)."""
    perfiles: dict[tuple[str, float], dict] = {}
    vidrios: dict[str, float] = {}
    accesorios: dict[str, dict] = {}

    for res in pres.resultados:
        cant_item = res.item.cantidad
        for p in res.despiece.aluminio.piezas:
            clave = (p.perfil_codigo, p.largo_mm)
            reg = perfiles.setdefault(
                clave,
                {"perfil": p.perfil_codigo, "descripcion": p.descripcion,
                 "largo_mm": p.largo_mm, "cantidad": 0, "peso_kg": 0.0},
            )
            reg["cantidad"] += p.cantidad * cant_item
            reg["peso_kg"] += p.peso_kg * cant_item

        for pano in res.despiece.vidrio.panos:
            vidrios[res.despiece.vidrio.tipo] = (
                vidrios.get(res.despiece.vidrio.tipo, 0.0) + pano.m2_total * cant_item
            )

        for acc in res.despiece.accesorios.lineas:
            reg = accesorios.setdefault(
                acc.codigo,
                {"codigo": acc.codigo, "descripcion": acc.descripcion,
                 "unidad": acc.unidad, "cantidad": 0.0, "total": 0.0},
            )
            reg["cantidad"] += acc.cantidad * cant_item
            reg["total"] += acc.total * cant_item

    return {
        "perfiles": sorted(perfiles.values(), key=lambda r: (r["perfil"], -r["largo_mm"])),
        "vidrios": [{"tipo": k, "m2": round(v, 3)} for k, v in sorted(vidrios.items())],
        "accesorios": sorted(accesorios.values(), key=lambda r: r["codigo"]),
    }
