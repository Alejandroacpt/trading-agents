"""
Laboratorio táctico: prueba las familias de corto plazo (velas de 1 hora)
en cripto y en acciones/ETFs, con stops, costes y el validador estricto.

Guarda reports/laboratorio/tactico.md, apunta las pruebas en el registro
y avisa por Telegram.

Uso:
    python scripts/run_lab_tactico.py [--sin-telegram]
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.alerts import telegram  # noqa: E402
from src.backtest import validator  # noqa: E402
from src.config import REPORTS_DIR  # noqa: E402
from src.research import registro  # noqa: E402
from src.tactico import laboratorio  # noqa: E402

ICONO = {"APROBADA": "✅", "OBSERVACIÓN": "🟡", "RECHAZADA": "❌"}


def _n(x, dec=2):
    return "-" if x is None or x != x else f"{x:.{dec}f}".replace(".", ",")


def _p(x, dec=0):
    return "-" if x is None or x != x else f"{x * 100:.{dec}f} %".replace(".", ",")


def _spy(v):
    s = v.get("spy") or {}
    return f"{_p(s['cagr'])} / {_p(s['cagr_spy'])}" if s else "—"


def main() -> int:
    experimentos = laboratorio.todos_los_experimentos()
    if not experimentos:
        print("No hay datos horarios descargados: ejecuta antes la descarga del histórico.")
        return 0

    validaciones = []
    for e in experimentos:
        print(f"Probando {e['nombre']}...")
        try:
            validaciones.append(validator.validar(e, None, {}))
        except Exception as ex:  # noqa: BLE001
            print(f"  ERROR: {type(ex).__name__}: {ex}")

    total = registro.registrar(validaciones, origen="laboratorio_tactico")
    validator.anadir_dsr(validaciones, n_minimo=total)
    for v in validaciones:
        v["veredicto"] = validator.veredicto(v)

    fecha = datetime.now(timezone.utc).date().isoformat()
    L = [f"# Laboratorio táctico (velas de 1 hora) · {fecha}", "",
         f"{len(validaciones)} experimentos. Pruebas acumuladas en el registro: **{total}**.", "",
         "Simulación con stop en cada operación, tamaño por riesgo (1,5 % del capital del motor), "
         "entrada en la vela siguiente a la señal, costes por operación (cripto 0,25 %, acciones 0,05 %) "
         "y, en acciones, sin cierres el mismo día (norma PDT). Test desde julio de 2024; mínimo 100 operaciones.", "",
         "| Experimento | Veredicto | Sharpe completo | Sharpe test | CAGR | Peor caída | Operaciones | % aciertos | Test: rent. / SPY | Qué falla |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    orden = sorted(validaciones, key=lambda v: (["APROBADA", "OBSERVACIÓN", "RECHAZADA"].index(v["veredicto"]["decision"]),
                                                -v["periodos"]["test"].get("sharpe", -9)))
    for v in orden:
        p, vd = v["periodos"], v["veredicto"]
        c = p["completo"]
        L.append(f"| {v['estrategia']['nombre']} | {ICONO[vd['decision']]} {vd['decision']} | {_n(c.get('sharpe'))} | "
                 f"{_n(p['test'].get('sharpe'))} | {_p(c.get('cagr'), 1)} | {_p(c.get('max_drawdown'))} | "
                 f"{c.get('operaciones', 0)} | {_p(c.get('aciertos'))} | {_spy(v)} | {', '.join(vd['fallos']) or '—'} |")
    # Diagnóstico de costes: ¿hay ventaja antes de costes? (pista para el investigador)
    L += ["", "## Diagnóstico: ¿hay ventaja antes de costes?", "",
          "Mismos experimentos (parámetros por defecto) sin costes. Si el Sharpe bruto es bueno y el neto malo, "
          "la idea tiene algo pero opera demasiado o con stops demasiado ajustados para sus costes.", "",
          "| Experimento | Sharpe bruto | Sharpe neto | Operaciones | Duración media | Resultado medio por operación (neto) |",
          "|---|---|---|---|---|---|"]
    from src.backtest import metrics as M  # noqa: E402
    for v in orden:
        e = v["estrategia"]
        bruto = e["simular"](e["parametros"], 0.0)
        ops = v["resultado"].operaciones
        L.append(f"| {e['nombre']} | {_n(M.sharpe(bruto.rentabilidad))} | {_n(v['periodos']['completo'].get('sharpe'))} | "
                 f"{len(ops)} | {_n(ops['dias'].mean() * 24 if len(ops) else float('nan'), 0)} h | "
                 f"{_p(ops['resultado'].mean() if len(ops) else float('nan'), 2)} |")

    candidatas = [v for v in orden if v["veredicto"]["decision"] in ("APROBADA", "OBSERVACIÓN")]
    L += ["", "## Candidatas para el motor táctico", ""]
    L += ([f"- {ICONO[v['veredicto']['decision']]} **{v['estrategia']['nombre']}** (`{v['estrategia']['id']}`)"
           for v in candidatas] or ["Ninguna: ninguna familia táctica supera las pruebas. El motor táctico sigue sin operar."])

    carpeta = REPORTS_DIR / "laboratorio"
    carpeta.mkdir(parents=True, exist_ok=True)
    texto = "\n".join(L) + "\n"
    (carpeta / "tactico.md").write_text(texto, encoding="utf-8")
    print(texto)

    msg = [f"⚡ Laboratorio táctico · {len(validaciones)} experimentos"]
    for v in orden[:6]:
        msg.append(f"{ICONO[v['veredicto']['decision']]} {v['estrategia']['nombre']}: Sharpe test "
                   f"{_n(v['periodos']['test'].get('sharpe'))}, {v['periodos']['completo'].get('operaciones', 0)} operaciones")
    if "--sin-telegram" not in sys.argv:
        telegram.send_message("\n".join(msg), silencioso=not any(v["veredicto"]["decision"] == "APROBADA" for v in orden))
    return 0


if __name__ == "__main__":
    sys.exit(main())
