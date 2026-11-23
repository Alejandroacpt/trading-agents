"""
Descarga semanal de datos para la investigación (no para las señales diarias):
  - Tipos de interés a 3 meses (FRED) -> data/macro/tipos_3m.csv
  - Posicionamiento en futuros (COT, CFTC) -> data/institucional/cot.csv
  - Compras de directivos (SEC, formulario 4) -> data/institucional/compras_directivos.csv

Uso:
    python scripts/update_research_data.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data import institucional, macro  # noqa: E402


def main() -> int:
    print("Tipos de interés (FRED):")
    for divisa, estado in macro.actualizar_tipos().items():
        print(f"  {divisa}: {estado}")
    print(institucional.actualizar_cot())
    print(institucional.actualizar_directivos())
    return 0


if __name__ == "__main__":
    sys.exit(main())
