"""
Cribado rápido de una idea (embudo del investigador).

Prueba una familia ya programada SOLO con los datos anteriores al periodo de
test, con los parámetros de la fuente, y la apunta en research/cribado.csv.
Si pasa, se valida después con el laboratorio completo.

Uso:
    python3 scripts/cribar.py tactico <familia> <mercado> --idea "..." [--fuente "..."] [--url "..."] [--param clave=valor ...]
    python3 scripts/cribar.py diario  <familia> <mercado> --idea "..." [...]

    mercados tácticos: cripto, acciones, apalancados
    mercados diarios : los de src/research/laboratorio.py (MERCADOS)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.research import cribado  # noqa: E402


def _valor(x: str):
    for tipo in (int, float):
        try:
            return tipo(x)
        except ValueError:
            pass
    return {"true": True, "false": False}.get(x.lower(), x)


def main() -> int:
    ap = argparse.ArgumentParser(description="Cribado rápido de una idea")
    ap.add_argument("tipo", choices=["tactico", "diario"])
    ap.add_argument("familia")
    ap.add_argument("mercado")
    ap.add_argument("--idea", required=True, help="nombre corto de la idea")
    ap.add_argument("--fuente", default="", help="de dónde sale (paper, canal de YouTube, script de TradingView...)")
    ap.add_argument("--url", default="")
    ap.add_argument("--param", action="append", default=[], help="parámetro clave=valor (puede repetirse)")
    a = ap.parse_args()
    params = {k: _valor(v) for k, v in (p.split("=", 1) for p in a.param)}

    f = cribado.cribar_tactico if a.tipo == "tactico" else cribado.cribar_diario
    r = f(a.familia, a.mercado, params)
    total = cribado.registrar(r, a.idea, a.fuente, a.url)
    ops = f" · {r['operaciones']} operaciones" if r["operaciones"] is not None else ""
    c = r.get("correlacion")
    ops += f" · correlación con lo que opera {c:.2f}" if c == c else ""
    print(f"{'✅ PASA' if r['pasa'] else '❌ NO PASA'} · {a.idea} · {a.familia} en {a.mercado} "
          f"({r['desde']} a {r['hasta']}): Sharpe {r['sharpe']:.2f} · rentabilidad anual {r['cagr']:.1%} · "
          f"caída máx. {r['max_dd']:.0%}{ops}\n  {r['motivo']}\n  Ideas cribadas en total: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
