"""
Descarga/actualiza las velas de 1 hora de forex (Dukascopy) para el laboratorio.

Uso:
    python3 scripts/update_forex.py [PAR ...]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data import forex  # noqa: E402


def main() -> int:
    pares = [a.upper() for a in sys.argv[1:]] or None
    informe = forex.actualizar(pares)
    print("\n".join(informe) if informe else "Sin pares configurados (config/investigacion.yaml -> forex)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
