"""
Gestión de temas: **Modo Claro** y **Modo Silver**.

Cómo funciona el cambio en vivo
-------------------------------
CustomTkinter acepta cada color como una tupla ``(claro, oscuro)`` y
``set_appearance_mode()`` reevalúa esas tuplas en todos los widgets ya creados.
Aprovechando eso, se arma un único archivo de tema donde:

    índice 0 (appearance "light")  ->  paleta **Claro**
    índice 1 (appearance "dark")   ->  paleta **Silver**

Así, cambiar de tema es un solo llamado y no hay que reconstruir la ventana.

Modo Silver
-----------
Grises neutros sobre base slate (#2B2D42 / #3D405B / #8D99AE): baja la
luminancia respecto del modo claro para jornadas largas en taller, pero sin
llegar al negro puro, que produce halos al leer texto claro sobre fondo oscuro.
"""

from __future__ import annotations

import json
import tkinter.font as tkfont
from tkinter import ttk

import customtkinter as ctk

from core import rutas

NOMBRES = {"claro": "Modo Claro", "silver": "Modo Silver"}
NOMBRES_CORTOS = {"claro": "Claro", "silver": "Silver"}
_APARIENCIA = {"claro": "light", "silver": "dark"}

# ---------------------------------------------------------------------------
# Paletas
# ---------------------------------------------------------------------------

PALETAS: dict[str, dict[str, str]] = {
    "claro": {
        "ventana": "#EEF1F5",
        "superficie": "#FFFFFF",
        "superficie_2": "#F6F8FA",
        "superficie_3": "#E8EDF3",
        "borde": "#D3DAE3",
        "borde_suave": "#E4E9EF",
        "texto": "#16202B",
        "texto_suave": "#5B6B7C",
        "texto_tenue": "#8A98A6",
        "primario": "#1B3A57",
        "primario_hover": "#2A5580",
        "sobre_primario": "#FFFFFF",
        "acento": "#0F766E",
        "acento_hover": "#0B5D57",
        "alerta": "#B45309",
        "alerta_fondo": "#FEF6E7",
        "error": "#B91C1C",
        "ok": "#15803D",
        "fila_alterna": "#F5F7FA",
        "seleccion": "#D7E4F1",
        "campo": "#FFFFFF",
        "campo_borde": "#C3CCD8",
        "badge": "#EDF1F6",
        "badge_texto": "#5B6B7C",
    },
    "silver": {
        "ventana": "#2B2D42",
        "superficie": "#3D405B",
        "superficie_2": "#363950",
        "superficie_3": "#464A68",
        "borde": "#525777",
        "borde_suave": "#454965",
        "texto": "#EDF0F6",
        "texto_suave": "#B4BECD",
        "texto_tenue": "#8D99AE",
        "primario": "#8D99AE",
        "primario_hover": "#A6B1C4",
        "sobre_primario": "#23253A",
        "acento": "#6EC1A7",
        "acento_hover": "#58A88E",
        "alerta": "#E0A458",
        "alerta_fondo": "#463F32",
        "error": "#E87A7A",
        "ok": "#7FD1A8",
        "fila_alterna": "#434662",
        "seleccion": "#5B6187",
        "campo": "#343751",
        "campo_borde": "#565B7C",
        "badge": "#4A4E6C",
        "badge_texto": "#B4BECD",
    },
}

RADIO = 8
RADIO_CHICO = 6

#: Fuente base según sistema
FAMILIA = {"Windows": "Segoe UI", "macOS": "SF Pro Text", "Linux": "DejaVu Sans"}


def _par(clave: str) -> list[str]:
    """Devuelve ``[color_en_claro, color_en_silver]`` para una clave semántica."""
    return [PALETAS["claro"][clave], PALETAS["silver"][clave]]


def _construir_json() -> dict:
    """Arma el archivo de tema de CustomTkinter con las dos paletas."""
    return {
        "CTk": {"fg_color": _par("ventana")},
        "CTkToplevel": {"fg_color": _par("ventana")},
        "CTkFrame": {
            "corner_radius": RADIO,
            "border_width": 0,
            "fg_color": _par("superficie"),
            "top_fg_color": _par("superficie_2"),
            "border_color": _par("borde"),
        },
        "CTkButton": {
            "corner_radius": RADIO_CHICO,
            "border_width": 0,
            "fg_color": _par("primario"),
            "hover_color": _par("primario_hover"),
            "border_color": _par("borde"),
            "text_color": _par("sobre_primario"),
            "text_color_disabled": _par("texto_tenue"),
        },
        "CTkLabel": {
            "corner_radius": 0,
            "fg_color": "transparent",
            "text_color": _par("texto"),
        },
        "CTkEntry": {
            "corner_radius": RADIO_CHICO,
            "border_width": 1,
            "fg_color": _par("campo"),
            "border_color": _par("campo_borde"),
            "text_color": _par("texto"),
            "placeholder_text_color": _par("texto_tenue"),
        },
        "CTkCheckBox": {
            "corner_radius": 4,
            "border_width": 2,
            "fg_color": _par("primario"),
            "border_color": _par("campo_borde"),
            "hover_color": _par("primario_hover"),
            "checkmark_color": _par("sobre_primario"),
            "text_color": _par("texto"),
            "text_color_disabled": _par("texto_tenue"),
        },
        "CTkSwitch": {
            "corner_radius": 1000,
            "border_width": 3,
            "button_length": 0,
            "fg_color": _par("superficie_3"),
            "progress_color": _par("acento"),
            "button_color": _par("superficie"),
            "button_hover_color": _par("superficie_2"),
            "text_color": _par("texto"),
            "text_color_disabled": _par("texto_tenue"),
        },
        "CTkRadioButton": {
            "corner_radius": 1000,
            "border_width_checked": 6,
            "border_width_unchecked": 2,
            "fg_color": _par("primario"),
            "border_color": _par("campo_borde"),
            "hover_color": _par("primario_hover"),
            "text_color": _par("texto"),
            "text_color_disabled": _par("texto_tenue"),
        },
        "CTkProgressBar": {
            "corner_radius": 1000,
            "border_width": 0,
            "fg_color": _par("superficie_3"),
            "progress_color": _par("acento"),
            "border_color": _par("borde"),
        },
        "CTkSlider": {
            "corner_radius": 1000, "button_corner_radius": 1000,
            "border_width": 6, "button_length": 0,
            "fg_color": _par("superficie_3"),
            "progress_color": _par("primario"),
            "button_color": _par("primario"),
            "button_hover_color": _par("primario_hover"),
        },
        "CTkOptionMenu": {
            "corner_radius": RADIO_CHICO,
            "fg_color": _par("campo"),
            "button_color": _par("superficie_3"),
            "button_hover_color": _par("borde"),
            "text_color": _par("texto"),
            "text_color_disabled": _par("texto_tenue"),
        },
        "CTkComboBox": {
            "corner_radius": RADIO_CHICO,
            "border_width": 1,
            "fg_color": _par("campo"),
            "border_color": _par("campo_borde"),
            "button_color": _par("campo_borde"),
            "button_hover_color": _par("borde"),
            "text_color": _par("texto"),
            "text_color_disabled": _par("texto_tenue"),
        },
        "CTkScrollbar": {
            "corner_radius": 1000,
            "border_spacing": 4,
            "fg_color": "transparent",
            "button_color": _par("borde"),
            "button_hover_color": _par("texto_tenue"),
        },
        "CTkSegmentedButton": {
            "corner_radius": RADIO_CHICO,
            "border_width": 2,
            "fg_color": _par("superficie_3"),
            "selected_color": _par("primario"),
            "selected_hover_color": _par("primario_hover"),
            "unselected_color": _par("superficie_3"),
            "unselected_hover_color": _par("borde"),
            "text_color": _par("sobre_primario"),
            "text_color_disabled": _par("texto_tenue"),
        },
        "CTkTextbox": {
            "corner_radius": RADIO_CHICO,
            "border_width": 1,
            "fg_color": _par("campo"),
            "border_color": _par("campo_borde"),
            "text_color": _par("texto"),
            "scrollbar_button_color": _par("borde"),
            "scrollbar_button_hover_color": _par("texto_tenue"),
        },
        "CTkScrollableFrame": {"label_fg_color": _par("superficie_2")},
        "DropdownMenu": {
            "fg_color": _par("superficie"),
            "hover_color": _par("seleccion"),
            "text_color": _par("texto"),
        },
        "CTkFont": {
            "macOS": {"family": FAMILIA["macOS"], "size": 13, "weight": "normal"},
            "Windows": {"family": FAMILIA["Windows"], "size": 13, "weight": "normal"},
            "Linux": {"family": FAMILIA["Linux"], "size": 13, "weight": "normal"},
        },
    }


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

_actual = "claro"
_suscriptores: list = []


def inicializar(nombre: str = "claro", escala: float = 1.0) -> None:
    """Escribe el tema y lo activa. Debe llamarse ANTES de crear widgets."""
    global _actual
    rutas.asegurar_carpetas()
    archivo = rutas.DATOS / "tema_ctk.json"
    archivo.write_text(json.dumps(_construir_json(), indent=2), encoding="utf-8")

    ctk.set_default_color_theme(str(archivo))
    _actual = nombre if nombre in PALETAS else "claro"
    ctk.set_appearance_mode(_APARIENCIA[_actual])
    ctk.set_widget_scaling(escala)
    ctk.set_window_scaling(escala)


def aplicar(nombre: str) -> None:
    """Cambia el tema en caliente: los widgets ya creados se actualizan solos."""
    global _actual
    if nombre not in PALETAS:
        return
    _actual = nombre
    ctk.set_appearance_mode(_APARIENCIA[nombre])
    for callback in list(_suscriptores):
        try:
            callback(nombre)
        except Exception:
            pass


def al_cambiar(callback) -> None:
    """Registra algo que hay que repintar a mano (tablas ttk, canvas, etc.)."""
    _suscriptores.append(callback)


def actual() -> str:
    return _actual


def c(clave: str) -> tuple[str, str]:
    """Color semántico como tupla ``(claro, silver)``, listo para un widget CTk."""
    return PALETAS["claro"][clave], PALETAS["silver"][clave]


def color_plano(clave: str) -> str:
    """Color resuelto para el tema activo (para widgets tk clásicos y ttk)."""
    return PALETAS[_actual][clave]


def fuente(tam: int = 13, peso: str = "normal") -> ctk.CTkFont:
    import platform
    familia = FAMILIA.get(
        {"Windows": "Windows", "Darwin": "macOS"}.get(platform.system(), "Linux"),
        "Segoe UI")
    return ctk.CTkFont(family=familia, size=tam, weight=peso)


# ---------------------------------------------------------------------------
# Tablas ttk.Treeview: no son widgets de CustomTkinter, hay que pintarlas aparte
# ---------------------------------------------------------------------------

def estilizar_tablas(root) -> None:
    """Aplica la paleta activa a todos los ttk.Treeview y ttk.Scrollbar."""
    estilo = ttk.Style(root)
    try:
        estilo.theme_use("clam")  # el único tema ttk que respeta los colores
    except Exception:
        pass

    p = PALETAS[_actual]
    escala = ctk.ScalingTracker.get_widget_scaling(root) if hasattr(ctk, "ScalingTracker") else 1.0
    alto_fila = int(30 * max(0.8, escala))

    fuente_tabla = (FAMILIA.get("Windows", "Segoe UI"), int(10 * max(0.85, escala)))
    fuente_encabezado = (fuente_tabla[0], fuente_tabla[1], "bold")

    estilo.configure(
        "Cotizador.Treeview",
        background=p["superficie"],
        fieldbackground=p["superficie"],
        foreground=p["texto"],
        bordercolor=p["borde"],
        borderwidth=0,
        rowheight=alto_fila,
        font=fuente_tabla,
    )
    estilo.configure(
        "Cotizador.Treeview.Heading",
        background=p["superficie_3"],
        foreground=p["texto_suave"],
        relief="flat",
        borderwidth=0,
        padding=(8, 7),
        font=fuente_encabezado,
    )
    estilo.map(
        "Cotizador.Treeview",
        background=[("selected", p["seleccion"])],
        foreground=[("selected", p["texto"])],
    )
    estilo.map(
        "Cotizador.Treeview.Heading",
        background=[("active", p["borde"])],
    )
    estilo.layout("Cotizador.Treeview", [
        ("Cotizador.Treeview.treearea", {"sticky": "nswe"})
    ])  # saca el borde 3D que dibuja clam

    for orientacion in ("Vertical", "Horizontal"):
        estilo.configure(f"Cotizador.{orientacion}.TScrollbar",
                         background=p["borde"], troughcolor=p["superficie_2"],
                         bordercolor=p["superficie_2"], arrowcolor=p["texto_suave"],
                         relief="flat", borderwidth=0)
        estilo.map(f"Cotizador.{orientacion}.TScrollbar",
                   background=[("active", p["texto_tenue"])])


def etiquetas_filas(tree) -> None:
    """Configura el rayado alterno y los colores de aviso de una tabla."""
    p = PALETAS[_actual]
    tree.tag_configure("par", background=p["superficie"], foreground=p["texto"])
    tree.tag_configure("impar", background=p["fila_alterna"], foreground=p["texto"])
    tree.tag_configure("inactivo", foreground=p["texto_tenue"])
    tree.tag_configure("alerta", foreground=p["alerta"])
    tree.tag_configure("total", background=p["superficie_3"], foreground=p["texto"])


def medir_texto(texto: str, tam: int = 10) -> int:
    """Ancho en píxeles de un texto, para dimensionar columnas."""
    try:
        return tkfont.Font(family=FAMILIA["Windows"], size=tam).measure(texto)
    except Exception:
        return len(texto) * 7
