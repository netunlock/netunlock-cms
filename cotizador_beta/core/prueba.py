# -*- coding: utf-8 -*-
"""
Período de prueba gratuito.

Quien baja el programa lo usa **tres días completos** sin pedir nada. Cuando se
terminan, la pantalla de activación le dice a dónde escribir. La idea no es
poner una traba: es que pruebe con sus propios presupuestos y, si le sirve,
tenga a mano cómo seguir.

Cómo se cuenta
--------------
El primer arranque anota la fecha en ``datos/prueba.dat``, firmada con HMAC
usando la misma clave derivada del equipo que usa :mod:`core.reloj`. Editar el
archivo a mano invalida la firma, y una prueba sin firma válida se trata como
vencida: si no se puede saber cuándo empezó, no se puede regalar tiempo.

La fecha con la que se compara **no es la del reloj del sistema**, sino la que
devuelve :func:`core.reloj.verificar_integridad_reloj`, que ya cruza la marca
local, la fecha de la base, la de la licencia y la hora de internet. Atrasar el
reloj de Windows no agrega días: el propio módulo de reloj corta antes.

La fecha se anota **dos veces**: en ese archivo y en la tabla ``parametros`` de
la propia base del programa. Vale siempre la más vieja de las dos. Borrar la
carpeta del usuario ya no reinicia nada, porque la base sigue teniendo la fecha;
y borrar también la base se lleva puesto todo lo cargado —presupuestos, precios,
fórmulas, órdenes—, que es justamente lo que nadie quiere perder después de tres
días de trabajo.

Las dos copias están a la vista y en lugares donde el programa ya guarda cosas.
No hay marcas escondidas en el registro ni archivos sueltos por el disco: eso es
lo que hace un programa que uno no quiere tener instalado.

Lo que esto no pretende
-----------------------
Alguien decidido a resetear la prueba puede: borra las dos copias y empieza de
nuevo. La defensa que importa no está acá sino en
:mod:`reports.marca_prueba`, que cruza de rojo todo lo que se imprima mientras
no haya licencia. Reiniciar la cuenta sirve para seguir *usando* el programa,
no para sacar un presupuesto que se le pueda mandar a un cliente, y eso es lo
único por lo que alguien paga.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from . import reloj

#: Días que dura la prueba.
DIAS = 3

#: Dónde se escribe, a quién escribirle.
ARCHIVO = "prueba.dat"
CONTACTO = "cotizadoraberturas@gmail.com"


def ruta() -> Path:
    return reloj.carpeta_datos() / ARCHIVO


@dataclass
class EstadoPrueba:
    """En qué anda la prueba de este equipo."""

    activa: bool = False
    iniciada: date | None = None
    dias_restantes: int = 0
    vencida: bool = False

    @property
    def texto(self) -> str:
        if self.activa:
            if self.dias_restantes == 1:
                return "Te queda 1 día de prueba."
            return f"Te quedan {self.dias_restantes} días de prueba."
        if self.vencida:
            return "Se terminaron los días de prueba."
        return ""


def _firmar(carga: str) -> str:
    """Misma clave que la marca del reloj: atada al equipo, no adivinable."""
    return hmac.new(reloj._clave_marca(), carga.encode("utf-8"),
                    hashlib.sha256).hexdigest()[:32]


#: Dónde queda la segunda copia, dentro de la base del programa.
PARAM = "prueba_inicio"


def _conexion():
    """Abre la base directamente, sin pasar por :class:`core.database.DB`.

    Importar ``DB`` acá dispararía la creación y el sembrado de la base, y esto
    corre mientras se está decidiendo si el programa puede siquiera abrirse.
    """
    import sqlite3
    from . import rutas
    if not rutas.RUTA_DB.exists():
        return None
    cx = sqlite3.connect(rutas.RUTA_DB, timeout=3)
    return cx


def _leer_base() -> datetime | None:
    """La copia que vive en la base. Misma firma que el archivo."""
    cx = _conexion()
    if cx is None:
        return None
    try:
        fila = cx.execute("SELECT valor FROM parametros WHERE clave = ?",
                          (PARAM,)).fetchone()
        if not fila:
            return None
        datos = json.loads(fila[0])
        carga = datos["inicio"]
        if not hmac.compare_digest(datos.get("tag", ""), _firmar(carga)):
            return None
        return datetime.fromisoformat(carga)
    except Exception:
        return None
    finally:
        cx.close()


def _escribir_base(momento: datetime) -> None:
    """Guarda la copia en la base. Si no se puede, no pasa nada: el archivo manda."""
    cx = _conexion()
    if cx is None:
        return
    try:
        carga = momento.astimezone(timezone.utc).isoformat()
        cx.execute(
            "INSERT INTO parametros (clave, valor, descripcion, grupo) "
            "VALUES (?, ?, ?, 'Licencia') "
            "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
            (PARAM, json.dumps({"inicio": carga, "tag": _firmar(carga)}),
             "Fecha en que empezó la prueba gratuita de este equipo"))
        cx.commit()
    except Exception:
        pass
    finally:
        cx.close()


def _leer() -> datetime | None:
    try:
        datos = json.loads(ruta().read_text(encoding="utf-8"))
        carga = datos["inicio"]
        if not hmac.compare_digest(datos.get("tag", ""), _firmar(carga)):
            return None            # tocado a mano
        return datetime.fromisoformat(carga)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _escribir(momento: datetime) -> bool:
    carga = momento.astimezone(timezone.utc).isoformat()
    try:
        ruta().parent.mkdir(parents=True, exist_ok=True)
        ruta().write_text(json.dumps({"inicio": carga, "tag": _firmar(carga)}),
                          encoding="utf-8")
        return True
    except OSError:
        return False


def estado(ahora: datetime | None = None, iniciar: bool = True) -> EstadoPrueba:
    """Cuántos días de prueba quedan. La arranca si es el primer uso.

    ``iniciar=False`` sirve para consultar sin comprometer el primer día, por
    ejemplo desde una pantalla informativa.
    """
    if ahora is None:
        ahora = datetime.now(timezone.utc)

    del_archivo = _leer()
    de_la_base = _leer_base()

    # Vale la más vieja de las dos copias. Así, borrar una sola no devuelve días:
    # la que quedó sigue diciendo cuándo empezó todo esto.
    fechas = [f for f in (del_archivo, de_la_base) if f is not None]
    inicio = min(fechas) if fechas else None

    if inicio is None:
        if not ruta().exists() and iniciar:
            # Primer arranque de este equipo: empieza la prueba.
            if not _escribir(ahora):
                # Sin permiso de escritura no se puede llevar la cuenta. Se
                # concede el día en curso y se avisa en la pantalla.
                return EstadoPrueba(activa=True, iniciada=ahora.date(),
                                    dias_restantes=DIAS)
            _escribir_base(ahora)
            inicio = ahora
        else:
            # El archivo existe pero no valida: se considera agotada.
            return EstadoPrueba(vencida=True)
    else:
        # Si una de las dos copias falta o quedó atrasada, se rehace con la
        # fecha buena. Es lo que repone la marca después de borrar Roaming.
        if del_archivo is None or del_archivo > inicio:
            _escribir(inicio)
        if de_la_base is None or de_la_base > inicio:
            _escribir_base(inicio)

    # Nunca negativo: una fecha anterior al inicio cuenta como el día cero, no
    # como días de más. En condiciones normales core.reloj corta antes de llegar
    # acá, pero la cuenta de la prueba no puede depender de que otro módulo la
    # proteja: sola tiene que dar como mucho DIAS.
    transcurridos = max(0, (ahora.date() - inicio.date()).days)
    restantes = DIAS - transcurridos
    if restantes <= 0:
        return EstadoPrueba(iniciada=inicio.date(), dias_restantes=0, vencida=True)
    return EstadoPrueba(activa=True, iniciada=inicio.date(),
                        dias_restantes=restantes)


def sincronizar() -> None:
    """Repone la copia que falte, con la base ya abierta.

    El control de licencia corre **antes** de que exista ``cotizador.db``: en el
    primerísimo arranque la copia de la base no se puede escribir todavía. Esto
    se llama después, cuando la aplicación ya abrió la base, y deja las dos
    copias en la fecha más vieja de las dos.
    """
    del_archivo = _leer()
    de_la_base = _leer_base()
    fechas = [f for f in (del_archivo, de_la_base) if f is not None]
    if not fechas:
        return
    inicio = min(fechas)
    if del_archivo is None or del_archivo > inicio:
        _escribir(inicio)
    if de_la_base is None or de_la_base > inicio:
        _escribir_base(inicio)


def licencia_de_prueba(est: EstadoPrueba):
    """Arma la ``Licencia`` que representa la prueba, para mostrarla en Ajustes."""
    from .licencia import Licencia
    from datetime import timedelta

    vence = ""
    if est.iniciada:
        vence = (est.iniciada + timedelta(days=DIAS)).isoformat()
    return Licencia(cliente="Prueba gratuita", hwid="", plan="prueba",
                    emitida=est.iniciada.isoformat() if est.iniciada else "",
                    vence=vence,
                    notas=f"Prueba de {DIAS} días. Para seguir usándolo, "
                          f"escribí a {CONTACTO}")
