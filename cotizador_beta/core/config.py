"""
Preferencias de la aplicación (tema, escala, últimas rutas).

Se guardan en ``datos/ajustes.json``, es decir dentro de la carpeta de datos de
usuario: una actualización de código nunca las pisa.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields

from . import rutas

TEMAS_DISPONIBLES = ("claro", "silver")


@dataclass
class Ajustes:
    tema: str = "claro"
    escala: float = 1.0            # 0.9 / 1.0 / 1.1 / 1.25 para pantallas grandes
    maximizar_al_iniciar: bool = False
    carpeta_pdf: str = ""          # última carpeta usada al exportar
    ultimo_uso: str = ""           # control de reloj del módulo de licencia
    aviso_licencia_visto: str = ""  # fecha del último aviso de vencimiento mostrado

    # -- persistencia --------------------------------------------------------

    @classmethod
    def cargar(cls) -> "Ajustes":
        try:
            datos = json.loads(rutas.RUTA_AJUSTES.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        validos = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in datos.items() if k in validos})

    def guardar(self) -> None:
        rutas.asegurar_carpetas()
        try:
            rutas.RUTA_AJUSTES.write_text(
                json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass  # no vale la pena romper la app por no poder guardar una preferencia

    # -- normalización -------------------------------------------------------

    def tema_valido(self) -> str:
        return self.tema if self.tema in TEMAS_DISPONIBLES else "claro"

    def escala_valida(self) -> float:
        return min(1.5, max(0.8, float(self.escala or 1.0)))
