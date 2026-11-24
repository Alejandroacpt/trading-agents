"""
CRIBADO RÁPIDO DE IDEAS (embudo del investigador)
-------------------------------------------------
Para poder probar muchas ideas a la semana (también de fuentes no
académicas: YouTube, TradingView, blogs, foros...) sin gastar tiempo ni
"mirar" los datos de test, cada idea pasa primero por un cribado:

  - Solo con los datos ANTERIORES al periodo de test (el test queda
    intacto para la validación final). Las señales también se calculan
    con los datos recortados: no se ve nada del futuro.
  - Una sola variante (los parámetros de la fuente), con costes.
  - Criterios mínimos (ver CRITERIOS). Las que pasan van a la validación
    completa del laboratorio (rejilla, walk-forward, costes x2, test,
    listón del SPY y Sharpe deflactado).

Cada idea cribada queda en research/cribado.csv y CUENTA como una prueba
más para el Sharpe deflactado (también se ha mirado, aunque sea el
pasado). El listón crece despacio (logarítmicamente), así que cribar
muchas ideas sale barato.
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.backtest import metrics
from src.config import ROOT

RUTA = ROOT / "research" / "cribado.csv"
COLUMNAS = ["fecha", "idea", "tipo", "familia", "mercado", "parametros", "fuente", "url",
            "desde", "hasta", "sharpe", "cagr", "max_dd", "operaciones", "pasa", "motivo"]

CRITERIOS = {
    "sharpe_min": 0.5,          # Sharpe del periodo de desarrollo
    "cagr_min": 0.0,            # que gane dinero
    "max_dd": 0.35,             # caída máxima tolerable en el cribado
    "operaciones_min": 50,      # táctico: con menos no significa nada
}


def cargar(ruta: Path = RUTA) -> pd.DataFrame:
    if not ruta.exists():
        return pd.DataFrame(columns=COLUMNAS).astype(object)
    return pd.read_csv(ruta).reindex(columns=COLUMNAS).astype(object)


def numero(ruta: Path = RUTA) -> int:
    return len(cargar(ruta))


def _veredicto(sharpe: float, cagr: float, dd: float, ops: int | None) -> tuple[bool, str]:
    fallos = []
    if not sharpe >= CRITERIOS["sharpe_min"]:
        fallos.append(f"Sharpe {sharpe:.2f} < {CRITERIOS['sharpe_min']}")
    if not cagr > CRITERIOS["cagr_min"]:
        fallos.append(f"rentabilidad {cagr:.1%} ≤ 0")
    if not dd >= -CRITERIOS["max_dd"]:
        fallos.append(f"caída {dd:.0%} peor que -{CRITERIOS['max_dd']:.0%}")
    if ops is not None and ops < CRITERIOS["operaciones_min"]:
        fallos.append(f"{ops} operaciones < {CRITERIOS['operaciones_min']}")
    return (not fallos), "; ".join(fallos) or "pasa al laboratorio"


def cribar_tactico(familia_id: str, mercado: str, params: dict | None = None) -> dict:
    """Simula una familia táctica SOLO con las velas anteriores al periodo de test."""
    from src.tactico import laboratorio
    from src.tactico.familias import FAMILIAS_TACTICAS
    from src.tactico.simulador import simular

    fam = FAMILIAS_TACTICAS[familia_id]
    params = {**fam["parametros"], **(params or {})}
    corte = pd.Timestamp(laboratorio.INICIO_TEST_TACTICO)
    ohlc = {a: df[df.index < corte] for a, df in laboratorio.velas_de(fam, mercado).items()}
    ohlc = {a: df for a, df in ohlc.items() if len(df) > 50}
    calentamiento = 120 if fam.get("velas") == "4h" else laboratorio.CALENTAMIENTO
    res = simular(ohlc, fam["funcion"](ohlc, **params), laboratorio.parametros_simulacion(mercado),
                  calentamiento=calentamiento)
    r = res.rentabilidad
    m = metrics.resumen(r, res.liquidez)
    ops = int(len(res.operaciones))
    pasa, motivo = _veredicto(m["sharpe"], m["cagr"], m["max_drawdown"], ops)
    return {"tipo": "tactico", "familia": familia_id, "mercado": mercado, "parametros": params,
            "desde": str(r.index[0].date()), "hasta": str(r.index[-1].date()),
            "sharpe": m["sharpe"], "cagr": m["cagr"], "max_dd": m["max_drawdown"], "operaciones": ops,
            "pasa": pasa, "motivo": motivo}


def cribar_diario(familia_id: str, mercado_id: str, params: dict | None = None) -> dict:
    """Backtest diario de una familia SOLO con los precios anteriores al periodo de test (2018)."""
    from src.backtest.engine import run_backtest
    from src.backtest.validator import INICIO_TEST, rent_liquidez
    from src.config import load_universe
    from src.data.macro import forex_con_carry
    from src.data.store import close_matrix
    from src.research import laboratorio

    e = laboratorio.experimento(familia_id, mercado_id)
    params = {**e["parametros"], **(params or {})}
    universo = load_universe()
    clases = {a["ticker"]: a["clase"] for a in universo}
    precios = forex_con_carry(close_matrix(universo))
    precios = precios[precios.index < INICIO_TEST]
    cols = [c for c in e["universo"] if c in precios.columns]
    p = precios[cols].dropna(how="all")
    obj = e["senales"](p, **params)
    res = run_backtest(p, obj, clases, rent_liquidez(precios, p.index))
    r = res.rentabilidad.dropna()
    r = r[r.index >= obj.dropna(how="all").index.min()] if obj.notna().any().any() else r
    m = metrics.resumen(r, res.liquidez.reindex(r.index).fillna(0.0))
    pasa, motivo = _veredicto(m["sharpe"], m["cagr"], m["max_drawdown"], None)
    return {"tipo": "diario", "familia": familia_id, "mercado": mercado_id, "parametros": params,
            "desde": str(r.index[0].date()), "hasta": str(r.index[-1].date()),
            "sharpe": m["sharpe"], "cagr": m["cagr"], "max_dd": m["max_drawdown"], "operaciones": None,
            "pasa": pasa, "motivo": motivo}


def registrar(resultado: dict, idea: str, fuente: str = "", url: str = "", ruta: Path = RUTA) -> int:
    """Apunta la idea cribada (una fila por idea+familia+mercado+parámetros). Devuelve el total."""
    df = cargar(ruta)
    fila = {"fecha": datetime.now(timezone.utc).date().isoformat(), "idea": idea, "fuente": fuente, "url": url,
            **{k: resultado[k] for k in ("tipo", "familia", "mercado", "desde", "hasta", "pasa", "motivo")},
            "parametros": ",".join(f"{k}={v}" for k, v in sorted(resultado["parametros"].items())),
            "sharpe": round(resultado["sharpe"], 3), "cagr": round(resultado["cagr"], 4),
            "max_dd": round(resultado["max_dd"], 4), "operaciones": resultado["operaciones"]}
    clave = (fila["familia"], fila["mercado"], fila["parametros"])
    if len(df):
        df = df[[(f, m, str(p)) != clave for f, m, p in zip(df["familia"], df["mercado"], df["parametros"])]]
    df = pd.concat([df, pd.DataFrame([fila], columns=COLUMNAS)], ignore_index=True)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False)
    return len(df)
