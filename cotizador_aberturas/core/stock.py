"""
Control de inventario de perfiles, vidrios y accesorios.

Es **opcional**: mientras el parámetro ``usar_stock`` esté en 0 el módulo no
interviene en ningún cálculo y la aplicación se comporta exactamente como antes.
Ninguna función de acá se llama desde el motor de cotización — el stock no puede
cambiar un precio ni frenar un presupuesto.

Modelo
------
Dos tablas, como en cualquier inventario serio:

``stock``
    El saldo actual por (tipo, referencia, depósito). Es un caché: se puede
    reconstruir entero desde los movimientos con :func:`recalcular`.

``stock_movimientos``
    El libro mayor. **Nunca se borra un movimiento.** Deshacer un consumo es
    registrar otro movimiento de signo contrario con motivo ``anulacion``, así
    el historial siempre explica cómo se llegó al saldo actual.

Unidades
--------
Cada tipo se lleva en la unidad en la que se compra, no en la que se consume:

    perfil     -> barras enteras     (el despiece dice cuántas hay que cortar)
    vidrio     -> m²
    accesorio  -> la unidad del accesorio (u, jgo, ml, m2, kg)

Por eso el consumo de perfiles pasa por el optimizador de corte: gastar 9,5 m
de un perfil no son 9,5 unidades de stock, son 2 barras.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .despiece import optimizar_por_perfil

#: Motivos válidos de un movimiento. 'inicial' y 'ajuste' los genera el usuario;
#: 'consumo' y 'anulacion' los genera el programa al emitir o anular una OT.
MOTIVOS = ("inicial", "compra", "consumo", "ajuste", "anulacion")

TIPOS = ("perfil", "vidrio", "accesorio")

#: Unidad en la que se inventaría cada tipo
UNIDAD_POR_TIPO = {"perfil": "barras", "vidrio": "m2", "accesorio": "u"}


# ---------------------------------------------------------------------------
# Activación
# ---------------------------------------------------------------------------

def activo(db) -> bool:
    """``True`` si el usuario habilitó el control de stock en Costos operativos."""
    return bool(db.parametro_int("usar_stock", 0))


def deposito_default(db) -> str:
    return db.parametro("stock_deposito_default", "Principal") or "Principal"


# ---------------------------------------------------------------------------
# Consulta de saldos
# ---------------------------------------------------------------------------

def saldo(db, tipo: str, referencia_id: int, deposito: str | None = None) -> float:
    fila = db.query_one(
        "SELECT cantidad FROM stock WHERE tipo = ? AND referencia_id = ? AND deposito = ?",
        (tipo, referencia_id, deposito or deposito_default(db)))
    return float(fila["cantidad"]) if fila else 0.0


def listar(db, tipo: str = "", solo_bajo_minimo: bool = False) -> list[dict]:
    """Saldos con el nombre del artículo resuelto, listo para mostrar en tabla.

    Se arma con tres consultas y un LEFT JOIN por tipo porque las referencias
    apuntan a tablas distintas: SQLite no tiene claves foráneas polimórficas.
    """
    filas: list[dict] = []

    consultas = {
        "perfil": ("SELECT s.*, p.codigo, p.descripcion, l.nombre AS linea "
                   "FROM stock s LEFT JOIN perfiles p ON p.id = s.referencia_id "
                   "LEFT JOIN lineas l ON l.id = p.linea_id WHERE s.tipo = 'perfil'"),
        "vidrio": ("SELECT s.*, v.nombre AS codigo, v.tipo AS descripcion, "
                   "'' AS linea FROM stock s "
                   "LEFT JOIN vidrios v ON v.id = s.referencia_id WHERE s.tipo = 'vidrio'"),
        "accesorio": ("SELECT s.*, a.codigo, a.descripcion, '' AS linea FROM stock s "
                      "LEFT JOIN accesorios a ON a.id = s.referencia_id "
                      "WHERE s.tipo = 'accesorio'"),
    }

    for clave, sql in consultas.items():
        if tipo and tipo != clave:
            continue
        for fila in db.query(sql + " ORDER BY codigo"):
            registro = dict(fila)
            registro["tipo"] = clave
            registro["bajo_minimo"] = (
                registro["minimo"] or 0) > 0 and registro["cantidad"] < registro["minimo"]
            if solo_bajo_minimo and not registro["bajo_minimo"]:
                continue
            filas.append(registro)

    return filas


def movimientos(db, tipo: str = "", referencia_id: int = 0,
                documento: str = "", limite: int = 300) -> list:
    sql = "SELECT * FROM stock_movimientos WHERE 1 = 1"
    params: list = []
    if tipo:
        sql += " AND tipo = ?"
        params.append(tipo)
    if referencia_id:
        sql += " AND referencia_id = ?"
        params.append(referencia_id)
    if documento:
        sql += " AND documento = ?"
        params.append(documento)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limite)
    return db.query(sql, tuple(params))


# ---------------------------------------------------------------------------
# Registro de movimientos
# ---------------------------------------------------------------------------

def registrar(db, tipo: str, referencia_id: int, cantidad: float,
              motivo: str = "ajuste", documento: str = "", nota: str = "",
              deposito: str | None = None, unidad: str = "") -> float:
    """Asienta un movimiento y actualiza el saldo. Devuelve el saldo nuevo.

    ``cantidad`` positiva ingresa y negativa egresa. Un movimiento de cantidad
    cero no se registra: ensucia el historial sin aportar nada.
    """
    if tipo not in TIPOS:
        raise ValueError(f"Tipo de stock desconocido: {tipo}")
    if not cantidad:
        return saldo(db, tipo, referencia_id, deposito)

    deposito = deposito or deposito_default(db)
    ahora = datetime.now().isoformat(timespec="seconds")

    db.insertar("stock_movimientos", {
        "fecha": ahora, "tipo": tipo, "referencia_id": referencia_id,
        "deposito": deposito, "cantidad": float(cantidad),
        "motivo": motivo if motivo in MOTIVOS else "ajuste",
        "documento": documento, "nota": nota})

    fila = db.query_one(
        "SELECT * FROM stock WHERE tipo = ? AND referencia_id = ? AND deposito = ?",
        (tipo, referencia_id, deposito))

    if fila is None:
        db.insertar("stock", {
            "tipo": tipo, "referencia_id": referencia_id, "deposito": deposito,
            "cantidad": float(cantidad), "unidad": unidad or UNIDAD_POR_TIPO[tipo],
            "minimo": 0, "actualizado": ahora})
        return float(cantidad)

    nuevo = float(fila["cantidad"]) + float(cantidad)
    db.execute("UPDATE stock SET cantidad = ?, actualizado = ? WHERE id = ?",
               (nuevo, ahora, fila["id"]))
    return nuevo


def fijar_saldo(db, tipo: str, referencia_id: int, cantidad: float,
                deposito: str | None = None, nota: str = "") -> float:
    """Deja el saldo en un valor exacto (recuento físico).

    No escribe el número a mano en ``stock``: calcula la diferencia y la asienta
    como movimiento de ajuste, para que el libro mayor siga cerrando.
    """
    actual = saldo(db, tipo, referencia_id, deposito)
    return registrar(db, tipo, referencia_id, cantidad - actual,
                     motivo="ajuste", nota=nota or "Recuento físico",
                     deposito=deposito)


def fijar_minimo(db, tipo: str, referencia_id: int, minimo: float,
                 deposito: str | None = None) -> None:
    deposito = deposito or deposito_default(db)
    fila = db.query_one(
        "SELECT id FROM stock WHERE tipo = ? AND referencia_id = ? AND deposito = ?",
        (tipo, referencia_id, deposito))
    if fila:
        db.execute("UPDATE stock SET minimo = ? WHERE id = ?", (float(minimo), fila["id"]))
    else:
        db.insertar("stock", {
            "tipo": tipo, "referencia_id": referencia_id, "deposito": deposito,
            "cantidad": 0, "unidad": UNIDAD_POR_TIPO[tipo], "minimo": float(minimo),
            "actualizado": datetime.now().isoformat(timespec="seconds")})


def recalcular(db) -> int:
    """Reconstruye todos los saldos sumando los movimientos.

    Es la red de seguridad del módulo: si un saldo quedó mal por un corte de luz
    en medio de una operación, esto lo devuelve a la verdad del libro mayor.
    Devuelve la cantidad de saldos corregidos.
    """
    ahora = datetime.now().isoformat(timespec="seconds")
    corregidos = 0
    for fila in db.query(
            "SELECT tipo, referencia_id, deposito, SUM(cantidad) AS total "
            "FROM stock_movimientos GROUP BY tipo, referencia_id, deposito"):
        actual = db.query_one(
            "SELECT id, cantidad FROM stock WHERE tipo = ? AND referencia_id = ? "
            "AND deposito = ?",
            (fila["tipo"], fila["referencia_id"], fila["deposito"]))
        total = float(fila["total"] or 0)
        if actual is None:
            db.insertar("stock", {
                "tipo": fila["tipo"], "referencia_id": fila["referencia_id"],
                "deposito": fila["deposito"], "cantidad": total,
                "unidad": UNIDAD_POR_TIPO.get(fila["tipo"], "u"),
                "minimo": 0, "actualizado": ahora})
            corregidos += 1
        elif abs(float(actual["cantidad"]) - total) > 1e-6:
            db.execute("UPDATE stock SET cantidad = ?, actualizado = ? WHERE id = ?",
                       (total, ahora, actual["id"]))
            corregidos += 1
    return corregidos


# ---------------------------------------------------------------------------
# Necesidad de materiales de un despiece
# ---------------------------------------------------------------------------

@dataclass
class Necesidad:
    """Lo que hace falta de un artículo, y lo que hay."""

    tipo: str
    referencia_id: int
    codigo: str
    descripcion: str
    unidad: str
    requerido: float
    disponible: float = 0.0

    @property
    def faltante(self) -> float:
        return max(0.0, self.requerido - self.disponible)

    @property
    def alcanza(self) -> bool:
        return self.disponible >= self.requerido


@dataclass
class Requerimiento:
    """Necesidad completa de un presupuesto o de una orden de trabajo."""

    lineas: list[Necesidad] = field(default_factory=list)

    @property
    def faltantes(self) -> list[Necesidad]:
        return [n for n in self.lineas if not n.alcanza]

    @property
    def completo(self) -> bool:
        return not self.faltantes


def necesidad_de_despiece(db, despiece, cantidad: int = 1) -> Requerimiento:
    """Traduce un despiece a consumo de inventario, en unidades de compra.

    * **Perfiles**: se pasa por el optimizador de corte. Lo que se descuenta son
      BARRAS enteras, que es lo que sale del depósito, no los metros útiles.
    * **Vidrio**: m² con desperdicio, que es lo que factura la vidriería.
    * **Accesorios**: la cantidad ya resuelta por el kit, en su propia unidad.
    """
    req = Requerimiento()

    for barras in optimizar_por_perfil(despiece.aluminio.piezas):
        perfil_id = next((p.perfil_id for p in despiece.aluminio.piezas
                          if p.perfil_codigo == barras.perfil_codigo and p.perfil_id), 0)
        if not perfil_id:
            continue          # perfil de una fórmula genérica, no está en el catálogo
        req.lineas.append(Necesidad(
            tipo="perfil", referencia_id=perfil_id,
            codigo=barras.perfil_codigo, descripcion=barras.descripcion,
            unidad="barras", requerido=barras.cantidad * cantidad,
            disponible=saldo(db, "perfil", perfil_id)))

    vidrio = despiece.vidrio
    if vidrio.vidrio_id and vidrio.m2_con_desperdicio:
        req.lineas.append(Necesidad(
            tipo="vidrio", referencia_id=vidrio.vidrio_id,
            codigo=vidrio.tipo, descripcion="Vidrio", unidad="m2",
            requerido=round(vidrio.m2_con_desperdicio * cantidad, 3),
            disponible=saldo(db, "vidrio", vidrio.vidrio_id)))

    for linea in despiece.accesorios.lineas:
        if not linea.accesorio_id:
            continue          # estimación por hoja: no hay artículo que descontar
        req.lineas.append(Necesidad(
            tipo="accesorio", referencia_id=linea.accesorio_id,
            codigo=linea.codigo, descripcion=linea.descripcion,
            unidad=linea.unidad, requerido=round(linea.cantidad * cantidad, 3),
            disponible=saldo(db, "accesorio", linea.accesorio_id)))

    return req


def consumir(db, requerimiento: Requerimiento, documento: str,
             nota: str = "") -> int:
    """Descuenta del inventario todo lo de un requerimiento.

    Devuelve cuántos movimientos se asentaron. Si ``stock_permite_negativo``
    está en 0 y algo no alcanza, no descuenta nada y levanta ``ValueError``:
    media orden descontada es peor que ninguna.
    """
    if not db.parametro_int("stock_permite_negativo", 1):
        faltan = requerimiento.faltantes
        if faltan:
            detalle = ", ".join(
                f"{n.codigo} (faltan {n.faltante:g} {n.unidad})" for n in faltan[:5])
            raise ValueError(f"No hay stock suficiente: {detalle}")

    for necesidad in requerimiento.lineas:
        registrar(db, necesidad.tipo, necesidad.referencia_id,
                  -abs(necesidad.requerido), motivo="consumo",
                  documento=documento, nota=nota, unidad=necesidad.unidad)
    return len(requerimiento.lineas)


def devolver(db, documento: str, nota: str = "") -> int:
    """Revierte los consumos de un documento (anular una OT).

    Busca los movimientos de consumo de ese documento y asienta el opuesto. No
    toca los originales: el historial tiene que seguir contando lo que pasó.
    """
    consumos = db.query(
        "SELECT * FROM stock_movimientos WHERE documento = ? AND motivo = 'consumo'",
        (documento,))
    for mov in consumos:
        registrar(db, mov["tipo"], mov["referencia_id"], -float(mov["cantidad"]),
                  motivo="anulacion", documento=documento,
                  nota=nota or f"Anulación de {documento}",
                  deposito=mov["deposito"])
    return len(consumos)
