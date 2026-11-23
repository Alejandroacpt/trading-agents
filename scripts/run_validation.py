"""
Valida todas las estrategias de la biblioteca con los datos guardados
y genera el informe en reports/validacion/informe.md.

Uso:
    python scripts/run_validation.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest import validator  # noqa: E402
from src.backtest.report import ICONO, informe  # noqa: E402
from src.config import REPORTS_DIR, load_universe  # noqa: E402
from src.data.store import close_matrix  # noqa: E402
from src.research import registro  # noqa: E402
from src.strategies import TODAS  # noqa: E402


def main() -> int:
    assets = load_universe()
    clases = {a["ticker"]: a["clase"] for a in assets}
    precios = close_matrix(assets)
    print(f"Datos: {precios.index.min().date()} → {precios.index.max().date()}, {precios.shape[1]} activos")

    validaciones = []
    for e in TODAS:
        print(f"Validando {e['nombre']}...")
        validaciones.append(validator.validar(e, precios, clases))
    total = registro.registrar(validaciones, origen="biblioteca")
    validator.anadir_dsr(validaciones, n_minimo=total)
    print(f"Pruebas acumuladas en el registro: {total}")
    for v in validaciones:
        v["veredicto"] = validator.veredicto(v)

    ruta = informe(validaciones, REPORTS_DIR / "validacion", precios.index.max().date())
    print(f"\nInforme: {ruta}\n")
    for v in validaciones:
        vd = v["veredicto"]
        print(f"{ICONO[vd['decision']]} {v['estrategia']['nombre']}: {vd['decision']}"
              + (f"  (falla: {', '.join(vd['fallos'])})" if vd["fallos"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
