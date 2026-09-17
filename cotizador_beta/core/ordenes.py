"""
Órdenes de trabajo: una por cada abertura presupuestada.

La OT es el papel que baja al taller. Por eso **congela el despiece** en el
momento de emitirla: si mañana se corrige una fórmula o cambia el precio del
aluminio, la orden que el operario tiene en la mano sigue diciendo lo mismo que
cuando se emitió. El presupuesto se recalcula; la OT no.

Ciclo de vida
-------------
    Pendiente -> En fabricación -> Terminada -> Entregada
                                            \\-> Anulada

Sólo al **emitir** se descuenta stock (si el control está activo) y sólo al
**anular** se devuelve. Cambiar de Pendiente a En fabricación no mueve nada:
el material ya salió del depósito cuando se emitió la orden.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime

from . import stock
from .calculo import calcular_item
from .database import ESTADOS_OT
from .despiece import optimizar_conjunto


@dataclass
class ResultadoEmision:
    """Qué pasó al emitir un lote de órdenes."""

    numeros: list[str]
    stock_movido: int = 0
    aviso: str = ""


# ---------------------------------------------------------------------------
# Congelado del despiece
# ---------------------------------------------------------------------------

def snapshot_de_item(db, item, margen_pct: float = 0.0) -> dict:
    """Serializa todo lo que el taller necesita para fabricar la abertura.

    Guarda medidas de corte, paños de vidrio, accesorios y barras a comprar. No
    guarda precios: una OT no es un documento comercial y no tiene por qué
    andar circulando por el taller con los costos encima.
    """
    resultado = calcular_item(db, item, margen_pct)
    d = resultado.despiece

    return {
        "version": 1,
        "generado": datetime.now().isoformat(timespec="seconds"),
        "abertura": {
            "tipologia_codigo": item.tipologia_codigo,
            "tipologia_nombre": item.tipologia_nombre,
            "linea": item.linea_nombre,
            "color": item.color,
            "ancho_mm": item.ancho_mm,
            "alto_mm": item.alto_mm,
            "hojas": item.hojas,
            "cantidad": item.cantidad,
            "vidrio": item.vidrio_nombre,
            "premarco": bool(item.incluye_premarco),
            "mosquitero": bool(item.incluye_mosquitero),
            "observaciones": item.observaciones,
            "ancho_hoja_mm": d.ancho_hoja_mm,
            "alto_hoja_mm": d.alto_hoja_mm,
        },
        "cortes": [
            {"perfil": p.perfil_codigo, "descripcion": p.descripcion,
             "funcion": p.funcion, "detalle": p.funcion_legible,
             "largo_mm": p.largo_mm, "cantidad": p.cantidad,
             "peso_kg_m": p.peso_kg_m, "largo_barra_mm": p.largo_barra_mm}
            for p in d.aluminio.piezas
        ],
        # Las barras se optimizan para TODAS las unidades de la orden juntas y
        # se guardan ya totalizadas: el taller corta las tres ventanas de la
        # misma barra, no una barra por ventana.
        "barras": [
            {"perfil": b.perfil_codigo, "descripcion": b.descripcion,
             "largo_barra_mm": b.largo_barra_mm, "barras": b.cantidad,
             "recorte_mm": round(b.recorte_mm, 1)}
            for b in optimizar_conjunto([(d.aluminio.piezas, item.cantidad)])
        ],
        #: Las barras ya están totalizadas; los cortes y accesorios son por unidad
        "barras_totalizadas": True,
        "vidrios": [
            {"tipo": p.descripcion, "ancho_mm": p.ancho_mm, "alto_mm": p.alto_mm,
             "cantidad": p.cantidad}
            for p in d.vidrio.panos
        ],
        "accesorios": [
            {"codigo": a.codigo, "descripcion": a.descripcion,
             "unidad": a.unidad, "cantidad": a.cantidad}
            for a in d.accesorios.lineas
        ],
        "kit": d.accesorios.kit_nombre,
        "peso_kg": round(d.aluminio.peso_total_kg, 3),
        "m2_vidrio": round(d.vidrio.m2_total, 3),
        "advertencias": d.advertencias,
    }


# ---------------------------------------------------------------------------
# Alta
# ---------------------------------------------------------------------------

def emitir(db, pres, ordenes_de: list[int] | None = None,
           entrega: str = "", responsable: str = "") -> ResultadoEmision:
    """Crea una OT por cada abertura del presupuesto.

    ``ordenes_de`` limita a ciertos ``item.orden``; si es None se emiten todas.
    Un mismo ítem con cantidad 3 genera **una** orden de cantidad 3, no tres
    órdenes: es el mismo trabajo repetido y el taller lo corta junto.
    """
    if not pres.items:
        raise ValueError("El presupuesto no tiene aberturas.")

    hoy = date.today().isoformat()
    ahora = datetime.now().isoformat(timespec="seconds")
    numeros: list[str] = []
    movimientos = 0
    avisos: list[str] = []

    for item in pres.items:
        if ordenes_de is not None and item.orden not in ordenes_de:
            continue

        numero = db.numero_ot_sugerido()
        instantanea = snapshot_de_item(db, item, pres.margen_pct)

        db.insertar("ordenes_trabajo", {
            "numero": numero,
            "presupuesto_id": pres.id or None,
            "presupuesto_numero": pres.numero,
            "item_orden": item.orden,
            "descripcion": f"{item.descripcion} · {item.medida_texto}",
            "cliente": pres.cliente.razon_social,
            "obra": pres.cliente.obra,
            "cantidad": item.cantidad,
            "fecha": hoy,
            "entrega": entrega,
            "estado": "Pendiente",
            "responsable": responsable,
            "notas": item.observaciones,
            "snapshot_json": json.dumps(instantanea, ensure_ascii=False),
            "stock_descontado": 0,
            "creado": ahora,
        })
        db.avanzar_numeracion_ot(numero)
        numeros.append(numero)

        if stock.activo(db):
            resultado = calcular_item(db, item, pres.margen_pct)
            requerimiento = stock.necesidad_de_despiece(db, resultado.despiece,
                                                        item.cantidad)
            try:
                movimientos += stock.consumir(
                    db, requerimiento, documento=numero,
                    nota=f"Consumo de {numero}")
                db.execute("UPDATE ordenes_trabajo SET stock_descontado = 1 "
                           "WHERE numero = ?", (numero,))
            except ValueError as exc:
                # La orden queda emitida igual: frenar la producción por el
                # inventario sería peor que emitirla con un aviso.
                avisos.append(f"{numero}: {exc}")

    return ResultadoEmision(numeros=numeros, stock_movido=movimientos,
                            aviso="\n".join(avisos))


# ---------------------------------------------------------------------------
# Consulta y estados
# ---------------------------------------------------------------------------

def listar(db, estado: str = "", filtro: str = "") -> list:
    sql = "SELECT * FROM ordenes_trabajo WHERE 1 = 1"
    params: list = []
    if estado:
        sql += " AND estado = ?"
        params.append(estado)
    if filtro:
        sql += (" AND (numero LIKE ? OR cliente LIKE ? OR obra LIKE ? "
                "OR presupuesto_numero LIKE ?)")
        params += [f"%{filtro}%"] * 4
    return db.query(sql + " ORDER BY id DESC", tuple(params))


def obtener(db, numero: str):
    return db.query_one("SELECT * FROM ordenes_trabajo WHERE numero = ?", (numero,))


def snapshot(orden) -> dict:
    try:
        return json.loads(orden["snapshot_json"] or "{}")
    except (TypeError, ValueError):
        return {}


def cambiar_estado(db, numero: str, estado: str) -> None:
    """Mueve la OT de estado. Anular devuelve el material al depósito."""
    if estado not in ESTADOS_OT:
        raise ValueError(f"Estado desconocido: {estado}")

    orden = obtener(db, numero)
    if orden is None:
        raise ValueError(f"No existe la orden {numero}.")
    if orden["estado"] == estado:
        return

    if estado == "Anulada" and orden["stock_descontado"]:
        stock.devolver(db, numero, nota=f"Anulación de {numero}")
        db.execute("UPDATE ordenes_trabajo SET stock_descontado = 0 WHERE numero = ?",
                   (numero,))

    db.execute("UPDATE ordenes_trabajo SET estado = ? WHERE numero = ?", (estado, numero))
