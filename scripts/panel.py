"""
Panel del sistema: reports/panel.md (+ gráficos en reports/panel/).

Una sola página con todo lo importante: cartera total frente a lo aportado,
cada motor, posiciones, señales pendientes, cuenta paper frente al
objetivo, estado de las estrategias, últimas operaciones e investigación.
Se regenera en cada pipeline diario. En GitHub (web o app) se ve con los
gráficos: github.com/Alejandroacpt/trading-agents/blob/main/reports/panel.md

Uso:
    python scripts/panel.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents import capital as gestor_capital  # noqa: E402
from src.agents.escaner import POR_ID, cargar_sistema  # noqa: E402
from src.config import REPORTS_DIR, ROOT  # noqa: E402
from src.data import horario  # noqa: E402

ESTADO = ROOT / "state"
CARPETA = REPORTS_DIR / "panel"
URL_PANEL = "https://github.com/Alejandroacpt/trading-agents/blob/main/reports/panel.md"


def _leer(nombre):
    p = ESTADO / nombre
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _eur(x, dec=0):
    return f"{x:,.{dec}f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(x, dec=1):
    return "-" if x is None or x != x else f"{x * 100:+.{dec}f} %".replace(".", ",")


def _serie(historial):
    if not historial:
        return pd.Series(dtype=float)
    s = pd.Series({pd.Timestamp(f): v for f, v in historial}).sort_index()
    return s[~s.index.duplicated(keep="last")]


def aportado_por_dia(conf: dict, indice: pd.DatetimeIndex) -> pd.Series:
    inicio = pd.Timestamp(conf.get("inicio", indice.min() if len(indice) else "2026-11-23"))
    aport = [(pd.Timestamp(f), x) for f, x in gestor_capital.aportaciones(conf)]
    return pd.Series([float(conf["inicial_eur"]) + sum(x for f, x in aport if f <= d) if d >= inicio else float("nan")
                      for d in indice], index=indice)


def grafico_total(total: pd.Series, aportado: pd.Series, tactico: pd.Series, estructural: pd.Series) -> str:
    CARPETA.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 3.6), dpi=110)
    if len(total):
        ax.plot(total.index, total.values, color="#1f4e79", lw=2.2, label="Cartera total", marker="o" if len(total) < 15 else None)
        ax.plot(aportado.index, aportado.values, color="#9aa5b1", lw=1.4, ls="--", label="Dinero aportado",
                drawstyle="steps-post", marker="_" if len(aportado) < 15 else None, ms=14)
    if len(tactico):
        ax.plot(tactico.index, tactico.values, color="#d9822b", lw=1.2, label="Motor táctico")
    if len(estructural):
        ax.plot(estructural.index, estructural.values, color="#2e8b57", lw=1.2, label="Motor estructural")
    ax.set_ylabel("€")
    ax.grid(alpha=0.25)
    ax.legend(loc="upper left", fontsize=8, frameon=False)
    loc = mdates.AutoDateLocator(minticks=2, maxticks=8)
    ax.xaxis.set_major_locator(loc)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    fig.tight_layout()
    ruta = CARPETA / "cartera.png"
    fig.savefig(ruta)
    plt.close(fig)
    return "panel/cartera.png"


def main() -> int:
    sistema = cargar_sistema()
    conf_cap = sistema["capital"]
    est, tac, alp, cap = _leer("estado.json"), _leer("tactico.json"), _leer("alpaca.json"), _leer("capital.json")
    vig = _leer("vigilante.json")
    conf_tac = horario.cargar_config()
    ahora = datetime.now(timezone.utc)

    total = _serie((cap.get("total") or {}).get("historial"))
    s_tac = _serie(tac.get("historial"))
    s_est = _serie((est.get("virtual") or {}).get("historial"))
    aportado = aportado_por_dia(conf_cap, total.index) if len(total) else pd.Series(dtype=float)
    img = grafico_total(total, aportado, s_tac, s_est)

    t = cap.get("total") or {}
    aportado_hoy = gestor_capital.capital_aportado(conf_cap)
    fase = cap.get("fase", 0)
    tramo = sistema["fases"]["tramos"][fase]
    reparto = cap.get("reparto") or {"tactico": tramo["tactico"], "estructural": tramo["estructural"]}
    L = [f"# Panel del sistema · {ahora:%d/%m/%Y %H:%M} UTC", ""]
    if vig.get("activos"):
        L += ["> 🚨 **Vigilante:** " + " · ".join(v["texto"] for v in vig["activos"].values()), ""]
    L += [
        "## Cartera", "",
        "| Cartera total | Aportado | Resultado | Caída desde máximo | Fase |",
        "|---|---|---|---|---|",
        f"| **{_eur(t.get('valor', 0))}** | {_eur(aportado_hoy)} | {_eur(t.get('valor', 0) - aportado_hoy)} "
        f"({_pct((t.get('valor', 0) - aportado_hoy) / aportado_hoy if aportado_hoy else 0)}) | {_pct(t.get('drawdown', 0))} "
        f"| {tramo.get('nombre', fase)}: {reparto['tactico']:.0%} táctico / {reparto['estructural']:.0%} estructural |",
        "", f"![Cartera]({img})", "",
        f"Próximas aportaciones: {_eur(conf_cap.get('aportacion_mensual_eur', 0))} el día {conf_cap.get('dia_aportacion', 1)} de cada mes. "
        f"Siguiente fase al superar {_eur(tramo['hasta_eur'])} durante {sistema['fases']['histeresis_dias']} días."
        if tramo.get("hasta_eur") else "", "",
    ]

    # Motores
    L += ["## Motores", "", "| Motor | Valor | Kill-switch | Estrategias |", "|---|---|---|---|"]
    est_tac = ", ".join(f"{POR_ID_T(e)} ({(i.get('estado') if isinstance(i, dict) else 'aprobada')})"
                        for e, i in ((i["id"] if isinstance(i, dict) else i, i) for i in conf_tac.get("estrategias") or []))
    ks_tac = ", ".join(sorted({e.get("kill_switch", "NORMAL") for e in tac.get("estrategias", {}).values()})) or "-"
    L.append(f"| ⚡ Táctico ({conf_tac.get('modo')}) | {_eur(tac.get('valor_total_eur', 0))} | {ks_tac} | {est_tac or 'ninguna'} |")
    est_est = ", ".join(f"{POR_ID[c['id']]['nombre']} ({c['estado']})" for c in sistema["estrategias"])
    L.append(f"| 🧱 Estructural | {_eur((est.get('virtual') or {}).get('valor', 0))} | {est.get('kill_switch', '-')} | {est_est} |")
    L.append("")

    # Posiciones
    L += ["## Posiciones", ""]
    filas = []
    for p in (tac.get("posiciones") or {}).values():
        filas.append(f"| ⚡ {p['activo']} | {_eur(p['importe_eur'])} | {p['precio_entrada']:.2f} | {p['stop']:.2f} | "
                     f"{_pct(p.get('cierre', p['precio_entrada']) / p['precio_entrada'] - 1)} | {str(p['entrada'])[:10]} |")
    v_est = (est.get("virtual") or {}).get("valor", 0)
    for a, w in (est.get("cartera") or {}).items():
        ref = (est.get("precios_ref") or {}).get(a)
        filas.append(f"| 🧱 {a} | {_eur(w * v_est)} | {ref:.2f} | - | - | - |" if ref else f"| 🧱 {a} | {_eur(w * v_est)} | - | - | - | - |")
    L += (["| Activo | Importe | Entrada | Stop | Resultado | Desde |", "|---|---|---|---|---|---|"] + filas
          if filas else ["Sin posiciones abiertas: todo en liquidez a la espera de señales."])
    if alp.get("stops"):
        L += ["", "**Stops reales en Alpaca:** " + ", ".join(f"{a} {v:.2f}" for a, v in alp["stops"].items())]
    pend = list((tac.get("pendientes") or {}).values())
    if pend:
        L += ["", "**Señales pendientes** (se ejecutan en la próxima apertura): "
              + ", ".join(f"{'compra' if p['accion'] == 'comprar' else 'venta'} {p['activo']}" for p in pend)]
    L.append("")

    # Cuenta paper
    pos, obj, capu = alp.get("posiciones") or {}, alp.get("objetivo") or {}, alp.get("capital_gestionado_usd") or 0
    L += ["## Cuenta paper (Alpaca)", "",
          f"Capital gestionado {capu:,.0f} $ · posiciones {alp.get('valor_posiciones_usd', 0):,.0f} $ · "
          f"actualizado {str(alp.get('actualizado', '-'))[:16].replace('T', ' ')} UTC", ""]
    activos = sorted(set(pos) | set(obj))
    if activos and capu:
        L += ["| Activo | Real | Objetivo | Diferencia |", "|---|---|---|---|"]
        for a in activos:
            real, ob = pos.get(a, 0.0) / capu, obj.get(a, 0.0)
            marca = " ⚠️" if abs(real - ob) > 0.05 else ""
            L.append(f"| {a} | {_pct(real)} | {_pct(ob)} | {_pct(real - ob)}{marca} |")
    L.append("")

    # Estrategias (auditor)
    aud = REPORTS_DIR / "auditor" / "ultimo.md"
    if aud.exists():
        filas_aud = [x for x in aud.read_text(encoding="utf-8").splitlines() if x.startswith("| ") and "Estrategia" not in x]
        if filas_aud:
            L += ["## Estrategias en vivo (último auditor)", "",
                  "| Motor | Estrategia | Estado | Días | Resultado en vivo | Caída en vivo | Backtest: CAGR / Sharpe / peor caída | Semáforo |",
                  "|---|---|---|---|---|---|---|---|"] + filas_aud + [""]

    # Últimas operaciones
    ruta_diario = ROOT / "diario" / "operaciones.csv"
    if ruta_diario.exists():
        d = pd.read_csv(ruta_diario)
        d = d[(d["tipo"] == "orden") & (d["estado"].astype(str) != "simulada")].tail(8)
        if len(d):
            L += ["## Últimas órdenes", "", "| Fecha (UTC) | Activo | Acción | Importe | Estado |", "|---|---|---|---|---|"]
            L += [f"| {str(r.fecha_utc)[:16].replace('T', ' ')} | {r.activo} | {r.accion} | {float(r.importe):,.0f} $ | {r.estado} |"
                  for r in d.itertuples()] + [""]

    # Investigación
    from src.research import cribado, registro
    cr = cribado.cargar()
    L += ["## Investigación", "",
          f"- Pruebas acumuladas (listón del Sharpe deflactado): **{registro.numero_pruebas()}**",
          f"- Ideas cribadas: {len(cr)} · pasaron el cribado: {int((cr['pasa'].astype(str) == 'True').sum()) if len(cr) else 0}"]
    fichas = sorted((ROOT / "research" / "fichas").glob("*.md"))[-5:] if (ROOT / "research" / "fichas").exists() else []
    if fichas:
        L.append("- Últimas fichas: " + ", ".join(f"[{f.stem}](../research/fichas/{f.name})" for f in reversed(fichas)))
    L += ["- Informes: [laboratorio](laboratorio/ultimo.md) · [laboratorio táctico](laboratorio/tactico.md) · "
          "[auditor](auditor/ultimo.md) · [señales](senales.md)", ""]

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "panel.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


def POR_ID_T(eid: str) -> str:
    """Nombre legible de una estrategia táctica."""
    from src.tactico.familias import FAMILIAS_TACTICAS
    familia, mercado = eid.removeprefix("tac_").split("__")
    nombre = FAMILIAS_TACTICAS.get(familia, {}).get("nombre", familia)
    return nombre.replace("(4 h)", "(media sesión)") if mercado == "acciones" else nombre


if __name__ == "__main__":
    sys.exit(main())
