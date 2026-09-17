"""
Prueba de humo sin interfaz gráfica.

Crea una base temporal, arma un presupuesto de ejemplo con varias tipologías,
verifica el despiece contra las fórmulas del enunciado y genera un PDF.

Uso:
    python -m tools.prueba_rapida
"""

from __future__ import annotations

import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.calculo import calcular_presupuesto, resumen_materiales  # noqa: E402
from core.database import DB, RUTA_SALIDAS  # noqa: E402
from core.despiece import calcular_despiece, optimizar_por_perfil  # noqa: E402
from core.models import Cliente, Item, Logistica, ManoObra, Presupuesto  # noqa: E402
from core.utils import fmt_money, fmt_num  # noqa: E402
from reports.pdf_generator import generar_pdf  # noqa: E402

FALLOS: list[str] = []


def verificar(descripcion: str, obtenido, esperado, tolerancia: float = 0.51):
    ok = abs(float(obtenido) - float(esperado)) <= tolerancia
    print(f"  {'OK ' if ok else 'MAL'}  {descripcion}: {obtenido} (esperado {esperado})")
    if not ok:
        FALLOS.append(descripcion)


def _largo(despiece, perfil_codigo: str) -> float:
    """Largo de corte de un perfil dentro del despiece (0 si no aparece)."""
    for p in despiece.aluminio.piezas:
        if p.perfil_codigo == perfil_codigo:
            return p.largo_mm
    return 0.0


def main() -> int:
    ruta = Path(tempfile.gettempdir()) / "cotizador_prueba.db"
    ruta.unlink(missing_ok=True)
    db = DB(ruta)
    # La regresión compara contra totales fijos, así que necesita el juego de
    # datos de ejemplo con sus precios de ejemplo. El programa instalado NO los
    # trae: viene con los catálogos MDT, que están en $0 a propósito y contra
    # los que no habría número que verificar.
    from core.seed_data import sembrar_muestra
    sembrar_muestra(db)
    print(f"Base de prueba: {ruta}\n")

    ids = {l["nombre"]: l["id"] for l in db.lineas()}
    vidrios = {v["nombre"]: v["id"] for v in db.vidrios()}

    # ---------------------------------------------------------------- despiece
    print("1) Fórmulas de despiece del enunciado (A=1500, H=1100, N=2)")

    d_he = calcular_despiece(db, "COR2", ids["Herrero"], "Blanco", 1500, 1100, 2,
                             vidrios["Float 4mm"])
    verificar("Herrero — alto de hoja = H - 35", d_he.alto_hoja_mm, 1065)
    verificar("Herrero — ancho de hoja = (A + 12) / 2", d_he.ancho_hoja_mm, 756)

    d_mo = calcular_despiece(db, "COR2", ids["Módena"], "Blanco", 1500, 1100, 2,
                             vidrios["DVH 4/9/4"])
    # Módena: descuentos oficiales del catálogo Aluar, sección 06-01.
    verificar("Módena — alto de hoja = H - 79", d_mo.alto_hoja_mm, 1021)
    verificar("Módena — ancho de hoja = A / 2 - 24", d_mo.ancho_hoja_mm, 726)
    verificar("Módena — umbral 6200 = A - 42", _largo(d_mo, "6200"), 1458)
    verificar("Módena — jamba 6201 = H", _largo(d_mo, "6201"), 1100)

    print("\n   Despiece Módena corrediza 2 hojas 1500 x 1100:")
    for p in d_mo.aluminio.piezas:
        print(f"     {p.perfil_codigo:<8} {p.funcion:<18} {p.largo_mm:>8.1f} mm x {p.cantidad:>2} "
              f"= {p.peso_kg:>7.3f} kg")
    print(f"     {'TOTAL':<8} {'':<18} {d_mo.aluminio.metros_totales:>8.2f} m    "
          f"  {d_mo.aluminio.peso_total_kg:>7.3f} kg -> {fmt_money(d_mo.aluminio.costo)}")

    pano = d_mo.vidrio.panos[0]
    print(f"     Vidrio: {pano.ancho_mm:.0f} x {pano.alto_mm:.0f} mm x {pano.cantidad} = "
          f"{d_mo.vidrio.m2_total:.3f} m² -> {fmt_money(d_mo.vidrio.costo)}")
    verificar("Vidrio Módena — ancho = AH + 15", pano.ancho_mm, 741)
    verificar("Vidrio Módena — alto = HH - 32", pano.alto_mm, 989)

    print("\n   Barras a comprar (cada perfil sale de su propia barra):")
    por_perfil = optimizar_por_perfil(d_mo.aluminio.piezas)
    for b in por_perfil:
        print(f"     {b.perfil_codigo:<8} {b.cantidad:>2} barra(s) de {b.largo_barra_mm} mm"
              f"   útil {b.metros_utiles:>6.2f} m   recorte {b.desperdicio_pct*100:>5.1f} %")
    # Seis perfiles distintos no pueden compartir barra: mínimo una barra cada uno.
    verificar("Barras — una por perfil como mínimo",
              sum(b.cantidad for b in por_perfil) >= len(por_perfil), True, 0)
    verificar("Barras — ningún perfil mezclado",
              len(por_perfil), len({p.perfil_codigo for p in d_mo.aluminio.piezas}), 0)

    # ------------------------------------------------------- modo de costeo m2
    print("\n2) Modo de costeo por m² (compatibilidad con la planilla Excel)")
    db.execute("UPDATE lineas SET modo_costeo = 'm2' WHERE nombre = 'Módena'")
    d_m2 = calcular_despiece(db, "COR2", ids["Módena"], "Blanco", 1500, 1100, 2,
                             vidrios["DVH 4/9/4"])
    esperado_m2 = 1.65 * 68000  # m² x precio $/m² de la planilla
    verificar("Aluminio por m² = 1,65 m² x $68.000", d_m2.aluminio.costo, esperado_m2, 1.0)
    db.execute("UPDATE lineas SET modo_costeo = 'kg' WHERE nombre = 'Módena'")

    # ------------------------------------------------------------ presupuesto
    print("\n3) Presupuesto completo")
    items = [
        Item(orden=1, tipologia_codigo="COR2", tipologia_nombre="Ventana Corrediza 2 hojas",
             linea_id=ids["Módena"], linea_nombre="Módena", color="Blanco",
             ancho_mm=1500, alto_mm=1100, hojas=2, cantidad=3,
             vidrio_id=vidrios["DVH 4/9/4"], vidrio_nombre="DVH 4/9/4",
             incluye_premarco=True, incluye_mosquitero=True, descuento_pct=0.05,
             observaciones="Color blanco semimate. Mosquitero con tela reforzada."),
        Item(orden=2, tipologia_codigo="PBAL2", tipologia_nombre="Puerta Balcón corrediza 2 hojas",
             linea_id=ids["Módena"], linea_nombre="Módena", color="Negro",
             ancho_mm=1800, alto_mm=2050, hojas=2, cantidad=1,
             vidrio_id=vidrios["Laminado 3+3"], vidrio_nombre="Laminado 3+3",
             incluye_premarco=True, observaciones="Manijón especial de 400 mm. Colocación en altura."),
        Item(orden=3, tipologia_codigo="FIJO", tipologia_nombre="Paño Fijo",
             linea_id=ids["Herrero"], linea_nombre="Herrero", color="Natural",
             ancho_mm=900, alto_mm=600, hojas=1, cantidad=2,
             vidrio_id=vidrios["Esmerilado 4mm"], vidrio_nombre="Esmerilado 4mm",
             observaciones="Vidrio esmerilado — baño."),
        Item(orden=4, tipologia_codigo="BAT1", tipologia_nombre="Ventana Batiente 1 hoja",
             linea_id=ids["A30 New"], linea_nombre="A30 New", color="Negro",
             ancho_mm=600, alto_mm=1100, hojas=1, cantidad=2,
             vidrio_id=vidrios["Float 4mm"], vidrio_nombre="Float 4mm",
             incluye_mosquitero=True),
    ]

    pres = Presupuesto(
        numero=db.numero_sugerido(),
        fecha=date.today(),
        validez_dias=15,
        cliente=Cliente(razon_social="Constructora del Litoral S.R.L.", documento="30-71234567-9",
                        contacto="Ing. Paula Giménez — 341 555-4433", localidad="Rosario, Santa Fe",
                        obra="Edificio Sarmiento 1240 — Piso 3", forma_pago="50% anticipo / 50% contra entrega"),
        items=items,
        mano_obra=ManoObra(valor_hora=9000, operarios=2, horas=0, automatica=True),
        logistica=Logistica(flete_recepcion=45000, envio_colocacion=180000),
        descuento_global_tipo="porcentaje", descuento_global_valor=0.03,
        aplica_iva=True, iva_pct=0.21, margen_pct=0.30,
        observaciones_generales=db.parametro("observaciones_defecto", ""),
    )
    calcular_presupuesto(db, pres)

    r = pres.resumen
    print(f"     Subtotal ítems      {fmt_money(r.subtotal_items_bruto):>18}")
    print(f"     Dto. por ítem       {fmt_money(-r.descuentos_items):>18}")
    print(f"     Mano de obra        {fmt_money(r.mano_obra):>18}  "
          f"({fmt_num(pres.mano_obra.horas, 2)} h x {pres.mano_obra.operarios} op.)")
    print(f"     Logística           {fmt_money(r.logistica):>18}")
    print(f"     Subtotal general    {fmt_money(r.subtotal_general):>18}")
    print(f"     Dto. global 3%      {fmt_money(-r.descuento_global):>18}")
    print(f"     IVA 21%             {fmt_money(r.iva):>18}")
    print(f"     TOTAL               {fmt_money(r.total):>18}")

    # Coherencia aritmética del desglose
    verificar("Subtotal = bruto - dtos.", r.subtotal_items,
              r.subtotal_items_bruto - r.descuentos_items, 0.01)
    verificar("Subtotal general", r.subtotal_general,
              r.subtotal_items + r.mano_obra + r.logistica, 0.01)
    verificar("Neto = subtotal - dto. global", r.neto, r.subtotal_general - r.descuento_global, 0.01)
    verificar("Total = neto + IVA", r.total, r.neto * 1.21, 0.01)

    # Descuento global como monto fijo
    pres.descuento_global_tipo = "monto"
    pres.descuento_global_valor = 250000
    calcular_presupuesto(db, pres)
    verificar("Descuento global por monto fijo", pres.resumen.descuento_global, 250000, 0.01)

    # Sin IVA
    pres.aplica_iva = False
    calcular_presupuesto(db, pres)
    verificar("Sin IVA: total = neto", pres.resumen.total, pres.resumen.neto, 0.01)

    pres.aplica_iva = True
    pres.descuento_global_tipo = "porcentaje"
    pres.descuento_global_valor = 0.03
    calcular_presupuesto(db, pres)

    # ------------------------------------------------------------------- PDF
    print("\n4) Generación del PDF")
    salida = RUTA_SALIDAS / f"{pres.numero}_PRUEBA.pdf"
    generar_pdf(db, pres, salida, incluir_despiece=True)
    tam = salida.stat().st_size
    print(f"     {salida}  ({tam / 1024:.1f} KB)")
    if tam < 3000:
        FALLOS.append("El PDF generado es sospechosamente chico")

    cons = resumen_materiales(pres)
    print(f"\n5) Consolidado de compras: {len(cons['perfiles'])} cortes de perfil, "
          f"{len(cons['vidrios'])} tipos de vidrio, {len(cons['accesorios'])} accesorios")

    db.cerrar()
    print("\n" + ("TODO OK" if not FALLOS else f"FALLARON {len(FALLOS)}: " + " | ".join(FALLOS)))
    return 1 if FALLOS else 0


if __name__ == "__main__":
    raise SystemExit(main())
