"""
Emisor de licencias por suscripción.  **HERRAMIENTA INTERNA — NO SE ENTREGA AL CLIENTE.**

Este archivo nunca se incluye en el ejecutable: ``build_exe.py`` lo excluye y
además verifica el binario resultante para confirmarlo.

Flujo de trabajo
----------------
1. El cliente abre la app, ve su **CÓDIGO DE EQUIPO** y te lo manda por WhatsApp.
2. Vos corrés esta herramienta y le pegás el código.
3. Te devuelve una **clave de una línea**. Se la mandás por WhatsApp.
4. El cliente la pega en la ventana de activación. Listo.

Modo interactivo (el habitual):
    python -m tools.keygen

Modo directo:
    python -m tools.keygen --hwid 00C0-5CF4-A01D-964C --cliente "Aberturas del Sur" --dias 30
    python -m tools.keygen --hwid ... --cliente ... --vence 2027-01-31
    python -m tools.keygen --hwid ... --cliente ... --perpetua

Administración:
    python -m tools.keygen --listar              historial de emisiones
    python -m tools.keygen --vencimientos        a quién hay que cobrarle este mes
    python -m tools.keygen --verificar "COTIZ-…" control de una clave emitida
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.licencia import (  # noqa: E402
    Licencia, PREFIJO_CLAVE, emitir, emitir_clave, hwid_valido, validar_texto)
from tools.generar_claves import cargar_privada  # noqa: E402

CARPETA = Path(__file__).resolve().parent.parent / "licencias"
REGISTRO = CARPETA / "registro.json"

DIAS_POR_DEFECTO = 30


# ---------------------------------------------------------------------------
# Registro de emisiones
# ---------------------------------------------------------------------------

def _historial() -> list[dict]:
    try:
        return json.loads(REGISTRO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _registrar(lic: Licencia, clave: str) -> None:
    CARPETA.mkdir(parents=True, exist_ok=True)
    historial = _historial()
    historial.append({**lic.como_dict(), "clave": clave})
    REGISTRO.write_text(json.dumps(historial, indent=2, ensure_ascii=False),
                        encoding="utf-8")


def _nombre_archivo(cliente: str) -> str:
    limpio = "".join(c if c.isalnum() or c in " -_" else "" for c in cliente).strip()
    return (limpio.replace(" ", "_") or "cliente") + ".lic"


# ---------------------------------------------------------------------------
# Emisión
# ---------------------------------------------------------------------------

def emitir_suscripcion(hwid: str, cliente: str, vence: str, plan: str = "completa",
                       notas: str = "") -> tuple[str, Path]:
    secreto = cargar_privada()
    hwid = hwid.strip().upper()

    lic = Licencia(cliente=cliente.strip(), hwid=hwid, emitida=date.today().isoformat(),
                   vence=vence, plan=plan, notas=notas)
    clave = emitir_clave(hwid, vence, plan, secreto)

    CARPETA.mkdir(parents=True, exist_ok=True)
    destino = CARPETA / _nombre_archivo(cliente)
    destino.write_text(emitir(lic, secreto), encoding="utf-8")
    _registrar(lic, clave)

    # Control: se valida la clave recién emitida contra el HWID de destino
    control = validar_texto(clave, hwid_actual=hwid)
    if not control.valida:
        raise SystemExit(f"La clave emitida no valida: {control.motivo}")

    return clave, destino


def _mostrar(clave: str, lic_cliente: str, hwid: str, vence: str, archivo: Path) -> None:
    ancho = 72
    print()
    print("=" * ancho)
    print("  CLAVE DE ACTIVACIÓN".center(ancho))
    print("=" * ancho)
    print(f"  Cliente : {lic_cliente}")
    print(f"  Equipo  : {hwid}")
    if vence:
        dias = (date.fromisoformat(vence) - date.today()).days
        print(f"  Vence   : {date.fromisoformat(vence):%d/%m/%Y}  ({dias} días)")
    else:
        print("  Vence   : no vence (perpetua)")
    print("-" * ancho)
    print()
    print(clave)
    print()
    print("-" * ancho)
    print("  Copiá la línea de arriba y mandala por WhatsApp.")
    print("  El cliente la pega en: Ajustes → Licencia → Activar")
    print()
    print(f"  Respaldo (.lic): {archivo}")
    print("=" * ancho)


def _interactivo() -> int:
    print("=" * 72)
    print("  EMISOR DE LICENCIAS — Cotizador de Aberturas".center(72))
    print("=" * 72)
    print("\nPedile al cliente el CÓDIGO DE EQUIPO que muestra la aplicación.\n")

    hwid = input("  Código de equipo (XXXX-XXXX-XXXX-XXXX): ").strip().upper()
    if not hwid_valido(hwid):
        print(f"\n  '{hwid}' no tiene el formato correcto.")
        print("  Deben ser 4 grupos de 4 caracteres hexadecimales (0-9, A-F).")
        return 2

    previas = [r for r in _historial() if r["hwid"] == hwid]
    if previas:
        ultima = previas[-1]
        print(f"\n  Este equipo ya tiene {len(previas)} emisión(es).")
        print(f"  Última: {ultima['cliente']} — vence {ultima['vence'] or 'nunca'}")

    cliente = input("\n  Nombre del cliente: ").strip()
    if not cliente:
        cliente = previas[-1]["cliente"] if previas else "Sin nombre"
        print(f"  (se usa: {cliente})")

    texto_dias = input(f"\n  Días de validez [{DIAS_POR_DEFECTO}]: ").strip()
    if texto_dias.lower() in ("p", "perpetua", "0"):
        vence = ""
    else:
        try:
            dias = int(texto_dias) if texto_dias else DIAS_POR_DEFECTO
        except ValueError:
            print(f"  Valor inválido, se usan {DIAS_POR_DEFECTO} días.")
            dias = DIAS_POR_DEFECTO
        # Si renueva antes de vencer, se suma al saldo en lugar de perderlo
        base = date.today()
        if previas and previas[-1]["vence"]:
            try:
                anterior = date.fromisoformat(previas[-1]["vence"])
                if anterior > base:
                    base = anterior
                    print(f"  Renovación: se suma sobre el vencimiento actual ({anterior:%d/%m/%Y}).")
            except ValueError:
                pass
        vence = (base + timedelta(days=dias)).isoformat()

    clave, archivo = emitir_suscripcion(hwid, cliente, vence)
    _mostrar(clave, cliente, hwid, vence, archivo)
    return 0


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

def _listar() -> int:
    historial = _historial()
    if not historial:
        print("Todavía no emitiste ninguna licencia.")
        return 0
    print(f"{'CLIENTE':<30} {'EQUIPO':<21} {'EMITIDA':<12} {'VENCE':<12} ESTADO")
    print("-" * 88)
    for registro in historial:
        vence = registro["vence"]
        if not vence:
            estado = "perpetua"
        else:
            dias = (date.fromisoformat(vence) - date.today()).days
            estado = f"{dias} días" if dias >= 0 else f"vencida hace {-dias}"
        print(f"{registro['cliente'][:29]:<30} {registro['hwid']:<21} "
              f"{registro['emitida']:<12} {vence or '—':<12} {estado}")
    print(f"\n{len(historial)} emisión(es).")
    return 0


def _vencimientos(dias_vista: int = 30) -> int:
    """Qué suscripciones vencen pronto: la lista de cobranza del mes."""
    vigentes: dict[str, dict] = {}
    for registro in _historial():
        if registro["vence"]:
            previo = vigentes.get(registro["hwid"])
            if previo is None or registro["vence"] > previo["vence"]:
                vigentes[registro["hwid"]] = registro

    proximos = []
    for registro in vigentes.values():
        dias = (date.fromisoformat(registro["vence"]) - date.today()).days
        if dias <= dias_vista:
            proximos.append((dias, registro))
    proximos.sort(key=lambda x: x[0])

    if not proximos:
        print(f"Ninguna suscripción vence en los próximos {dias_vista} días.")
        return 0

    print(f"Suscripciones a renovar (próximos {dias_vista} días)\n")
    print(f"{'CLIENTE':<30} {'EQUIPO':<21} {'VENCE':<12} ESTADO")
    print("-" * 78)
    for dias, registro in proximos:
        estado = "VENCIDA" if dias < 0 else ("vence hoy" if dias == 0 else f"en {dias} días")
        print(f"{registro['cliente'][:29]:<30} {registro['hwid']:<21} "
              f"{registro['vence']:<12} {estado}")
    print(f"\n{len(proximos)} cliente(s) para contactar.")
    return 0


def _verificar(clave: str) -> int:
    coincidencias = [r for r in _historial()
                     if r.get("clave", "").replace(PREFIJO_CLAVE, "") ==
                     clave.strip().replace(PREFIJO_CLAVE, "")]
    if not coincidencias:
        print("Esa clave no figura en tu registro de emisiones.")
        return 1
    registro = coincidencias[-1]
    estado = validar_texto(clave, hwid_actual=registro["hwid"])
    print(f"Cliente : {registro['cliente']}")
    print(f"Equipo  : {registro['hwid']}")
    print(f"Vence   : {registro['vence'] or 'perpetua'}")
    print(f"Firma   : {'VÁLIDA' if estado.licencia else 'RECHAZADA'}")
    print(f"Estado  : {estado.motivo}")
    return 0 if estado.valida else 1


# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Emite licencias por suscripción")
    parser.add_argument("--hwid", help="Código de equipo del cliente")
    parser.add_argument("--cliente", help="Nombre o razón social")
    parser.add_argument("--dias", type=int, help=f"Validez en días (default {DIAS_POR_DEFECTO})")
    parser.add_argument("--vence", help="Fecha de vencimiento AAAA-MM-DD")
    parser.add_argument("--perpetua", action="store_true", help="Sin vencimiento")
    parser.add_argument("--notas", default="")
    parser.add_argument("--listar", action="store_true")
    parser.add_argument("--vencimientos", nargs="?", type=int, const=30, default=None)
    parser.add_argument("--verificar", metavar="CLAVE")
    args = parser.parse_args()

    if args.listar:
        return _listar()
    if args.vencimientos is not None:
        return _vencimientos(args.vencimientos)
    if args.verificar:
        return _verificar(args.verificar)
    if not args.hwid:
        return _interactivo()

    if not hwid_valido(args.hwid):
        print(f"El código '{args.hwid}' no tiene el formato XXXX-XXXX-XXXX-XXXX.")
        return 2

    if args.perpetua:
        vence = ""
    elif args.vence:
        try:
            date.fromisoformat(args.vence)
        except ValueError:
            print(f"Fecha inválida: {args.vence}. Usá AAAA-MM-DD.")
            return 2
        vence = args.vence
    else:
        vence = (date.today() + timedelta(days=args.dias or DIAS_POR_DEFECTO)).isoformat()

    cliente = args.cliente or "Sin nombre"
    clave, archivo = emitir_suscripcion(args.hwid, cliente, vence, notas=args.notas)
    _mostrar(clave, cliente, args.hwid.upper(), vence, archivo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
