"""
Configuración general del proyecto.

Aquí se definen las rutas de carpetas y la función que lee el
universo de activos (config/universe.yaml).
"""

from pathlib import Path

import yaml

# Carpeta raíz del repositorio (la que contiene src/, config/, data/...)
ROOT = Path(__file__).resolve().parent.parent

CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"          # aquí se guardan los CSV de precios
REPORTS_DIR = ROOT / "reports"    # aquí se guardan los informes

# Clases de activo que cotizan TODOS los días (también fines de semana).
# El resto solo cotiza de lunes a viernes.
CLASES_7_DIAS = {"crypto"}


def load_universe(path: Path | None = None) -> list[dict]:
    """Lee config/universe.yaml y devuelve la lista de activos.

    Cada activo es un diccionario, por ejemplo:
        {"ticker": "SPY", "nombre": "S&P 500", "clase": "equity"}
    """
    path = path or CONFIG_DIR / "universe.yaml"
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assets = data["assets"]

    # Comprobaciones básicas para detectar errores al editar el YAML
    tickers = [a["ticker"] for a in assets]
    if len(tickers) != len(set(tickers)):
        raise ValueError("Hay tickers repetidos en universe.yaml")
    for a in assets:
        if "clase" not in a:
            raise ValueError(f"Al activo {a['ticker']} le falta la 'clase'")
        a.setdefault("source", "yahoo")

    return assets
