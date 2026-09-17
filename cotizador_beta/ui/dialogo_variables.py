"""
Bloque de opciones de la tipología dentro del diálogo de abertura.

Se dibuja solo a partir de lo que la tipología declara en ``tipologia_variables``:
cada variable elige su control según el tipo, y el conjunto devuelve un
diccionario ``{CLAVE: número}`` que va derecho al contexto del motor de fórmulas.

    bool      -> casilla                -> 1 / 0
    numero    -> campo numérico         -> el número, recortado a mín. y máx.
    opcion    -> lista desplegable      -> el número asociado a la elegida
    accesorio -> lista del catálogo     -> el id del accesorio elegido

Si la tipología no declara nada, el bloque no se muestra: una línea sin opciones
no tiene por qué ocupar lugar ni sugerir que falta completar algo.
"""

from __future__ import annotations

import customtkinter as ctk

from core import variables as V
from . import tema
from .componentes import CampoCheck, CampoCombo, CampoUnidad, Tarjeta


class BloqueVariables(Tarjeta):
    """Tarjeta con los controles de las variables de una tipología.

    Se reconstruye entera cada vez que cambia la tipología o la línea, porque el
    juego de variables es otro. Los valores que el usuario ya había elegido se
    conservan si la variable sigue existiendo con el mismo nombre.
    """

    def __init__(self, master, db, al_cambiar=None):
        super().__init__(master, "Opciones de la tipología")
        self.db = db
        self._al_cambiar = al_cambiar
        self._controles: dict[str, tuple] = {}
        self.cuerpo.columnconfigure((0, 1), weight=1)
        self._vacio = None

    # -- construcción --------------------------------------------------------

    def construir(self, tipologia_codigo: str, linea_id: int,
                  valores: dict | None = None) -> bool:
        """Redibuja el bloque. Devuelve si hay algo que mostrar."""
        elegidos = dict(valores or {})
        # Lo que el usuario ya había puesto manda sobre lo que se está borrando
        for clave, control, _tipo, _opciones in self._controles.values():
            elegidos.setdefault(clave, self._leer(control, _tipo, _opciones))

        for hijo in self.cuerpo.winfo_children():
            hijo.destroy()
        self._controles = {}

        # Las vinculadas (PREMARCO) no se dibujan: las decide una casilla que el
        # diálogo ya tiene, «Incluye premarco», y dos controles para lo mismo
        # terminarían diciendo cosas distintas.
        declaradas = [v for v in V.declaradas(self.db, tipologia_codigo, linea_id)
                      if v["clave"] not in V.VINCULADAS]
        if not declaradas:
            return False

        fila = 0
        for i, var in enumerate(declaradas):
            clave = var["clave"]
            valor = elegidos.get(clave, V._a_numero(var["valor_default"]))
            control, tipo, opciones = self._crear(var, valor)
            columna = i % 2
            control.grid(row=fila, column=columna, sticky="ew",
                         padx=(0, 12) if columna == 0 else 0, pady=4)
            self._controles[clave] = (clave, control, tipo, opciones)
            if columna == 1:
                fila += 1
        return True

    def _crear(self, var, valor):
        tipo = var["tipo"]
        ayuda = var["ayuda"] or ""

        if tipo == "bool":
            control = CampoCheck(self.cuerpo, var["etiqueta"], bool(valor),
                                 al_cambiar=self._al_cambiar)
            return control, tipo, ()

        if tipo in ("opcion", "accesorio"):
            # Las dos ramas terminan en el mismo control: una lista de pares
            # (etiqueta, número). Lo único que cambia es de dónde salen los pares
            # —del JSON de la declaración o del catálogo de accesorios— así que
            # leer el valor elegido es idéntico en los dos casos.
            opciones = (V.opciones_de_accesorio(self.db, var["opciones"])
                        if tipo == "accesorio"
                        else V.parsear_opciones(var["opciones"]))
            etiquetas = [e for e, _v in opciones]
            # Se busca por valor y no por posición: si mañana se reordenan las
            # opciones, una abertura vieja tiene que seguir mostrando la suya.
            actual = next((e for e, v in opciones if v == valor),
                          etiquetas[0] if etiquetas else "")
            control = CampoCombo(self.cuerpo, var["etiqueta"], etiquetas, actual,
                                 ancho=200, ayuda=ayuda, al_cambiar=self._al_cambiar)
            return control, tipo, opciones

        unidad = "milimetros" if (var["maximo"] or 0) > 20 else ""
        control = CampoUnidad(self.cuerpo, var["etiqueta"], unidad, valor,
                              ancho=120, decimales=1, quitar_ceros=True,
                              ayuda=ayuda or self._ayuda_rango(var),
                              al_cambiar=self._al_cambiar)
        return control, tipo, ()

    @staticmethod
    def _ayuda_rango(var) -> str:
        minimo, maximo = var["minimo"] or 0, var["maximo"] or 0
        if maximo:
            return f"Entre {minimo:g} y {maximo:g}"
        return ""

    # -- lectura -------------------------------------------------------------

    @staticmethod
    def _leer(control, tipo, opciones):
        if tipo == "bool":
            return 1.0 if control.get() else 0.0
        if tipo in ("opcion", "accesorio"):
            etiqueta = control.get()
            return next((v for e, v in opciones if e == etiqueta), 0.0)
        return float(control.get() or 0.0)

    def valores(self) -> dict[str, float]:
        """Lo elegido, listo para guardar en el ítem."""
        return {clave: self._leer(control, tipo, opciones)
                for clave, control, tipo, opciones in self._controles.values()}

    @property
    def hay_variables(self) -> bool:
        return bool(self._controles)


def resumen_opciones(db, item) -> str:
    """Texto corto con las opciones activas, para la columna Opcionales.

    Sólo se nombran las que están puestas: listar "Sin premarco · Sin mosquitero"
    en cada renglón ocupa lugar y no dice nada.
    """
    declaradas = V.declaradas(db, item.tipologia_codigo, item.linea_id)
    if not declaradas:
        return ""

    elegidos = getattr(item, "variables", None) or {}
    partes = []
    for var in declaradas:
        if var["clave"] in V.VINCULADAS:
            continue    # ya la nombra su casilla: la columna dice "Premarco"
        valor = elegidos.get(var["clave"], V._a_numero(var["valor_default"]))
        if var["tipo"] == "bool":
            if valor:
                partes.append(var["etiqueta"])
        elif var["tipo"] == "opcion":
            opciones = V.parsear_opciones(var["opciones"])
            etiqueta = next((e for e, v in opciones if v == valor), "")
            # La primera opción es el caso corriente: no aporta nombrarla
            if etiqueta and opciones and valor != opciones[0][1]:
                partes.append(etiqueta)
        elif var["tipo"] == "accesorio":
            # El valor es un id: mostrarlo no le dice nada a nadie. Se busca el
            # código, que es lo que el taller y el proveedor reconocen.
            fila = db.query_one("SELECT codigo FROM accesorios WHERE id = ?",
                                (int(valor),)) if valor else None
            if fila:
                partes.append(f"{var['etiqueta']}: {fila['codigo']}")
        elif valor:
            partes.append(f"{var['etiqueta']}: {valor:g}")
    return " + ".join(partes)
