"""
Pruebas del motor de backtest, las métricas y las estrategias, con
casos sencillos cuyo resultado se puede calcular a mano.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest import metrics  # noqa: E402
from src.backtest.engine import run_backtest  # noqa: E402
from src.strategies import dual_momentum, faber, tsmom  # noqa: E402

FECHAS = pd.bdate_range("2024-01-01", periods=6)
CLASES = {"A": "equity", "B": "equity"}


def precios(*series):
    return pd.DataFrame({n: s for n, s in zip("AB", series)}, index=FECHAS[: len(series[0])])


def objetivos_constantes(p, pesos: dict, desde=0):
    obj = pd.DataFrame(np.nan, index=p.index, columns=p.columns)
    obj.iloc[desde] = [pesos.get(c, 0.0) for c in p.columns]
    return obj


# ---------------------------------------------------------------- motor

def test_comprar_y_mantener_sin_costes_replica_el_activo():
    p = precios([100, 110, 99, 108.9, 120])
    res = run_backtest(p, objetivos_constantes(p, {"A": 1.0}), CLASES, retraso=0, multiplicador_costes=0)
    # comprado al cierre del día 0 -> gana todo lo que sube después
    assert res.curva.iloc[-1] == pytest.approx(120 / 100)


def test_retraso_de_un_dia():
    p = precios([100, 110, 121, 133.1])
    res = run_backtest(p, objetivos_constantes(p, {"A": 1.0}), CLASES, retraso=1, multiplicador_costes=0)
    # señal al cierre del día 0, compra al cierre del día 1 (110): gana 110 -> 133,1
    assert res.curva.iloc[-1] == pytest.approx(133.1 / 110)
    assert res.rentabilidad.iloc[1] == 0  # el día 1 aún no estaba dentro


def test_coste_de_entrada():
    p = precios([100, 100, 100])
    res = run_backtest(p, objetivos_constantes(p, {"A": 1.0}), CLASES, retraso=0)
    # comprar el 100 % de la cartera en un ETF cuesta 0,10 %
    assert res.costes.iloc[0] == pytest.approx(0.001)
    assert res.curva.iloc[-1] == pytest.approx(0.999)


def test_liquidez_cobra_su_rentabilidad():
    p = precios([100, 100, 100])
    liq = pd.Series(0.0001, index=p.index)
    res = run_backtest(p, objetivos_constantes(p, {}), CLASES, liq, retraso=0)
    assert res.curva.iloc[-1] == pytest.approx(1.0001 ** 3)


def test_posicion_corta_gana_si_baja():
    p = precios([100, 90])
    res = run_backtest(p, objetivos_constantes(p, {"A": -1.0}), CLASES, retraso=0, multiplicador_costes=0)
    assert res.rentabilidad.iloc[1] == pytest.approx(0.10)


def test_deriva_sin_rebalanceo():
    p = precios([100, 200], [100, 100])
    res = run_backtest(p, objetivos_constantes(p, {"A": 0.5, "B": 0.5}), CLASES, retraso=0, multiplicador_costes=0)
    # A se duplica: pasa a pesar 2/3 sin que se opere
    assert res.pesos.iloc[-1]["A"] == pytest.approx(2 / 3)
    assert res.rotacion.iloc[1] == 0


def test_registro_de_operaciones():
    p = precios([100, 110, 121, 121, 121])
    obj = pd.DataFrame(np.nan, index=p.index, columns=p.columns)
    obj.iloc[0] = 1.0   # compra al cierre del día 0 (100)
    obj.iloc[2] = 0.0   # vende al cierre del día 2 (121)
    res = run_backtest(p, obj, CLASES, retraso=0, multiplicador_costes=0)
    ops = res.operaciones
    assert len(ops) == 1
    assert ops.iloc[0]["resultado"] == pytest.approx(0.21)


# ---------------------------------------------------------------- métricas

def test_drawdown_y_cagr():
    idx = pd.date_range("2020-01-01", periods=3, freq="365D")
    r = pd.Series([0.0, -0.5, 1.0], index=idx)
    assert metrics.drawdown(r).min() == pytest.approx(-0.5)
    m = metrics.resumen(pd.concat([r] * 10).set_axis(pd.date_range("2000-01-01", periods=30, freq="365D")))
    assert m["max_drawdown"] == pytest.approx(-0.5)


def test_sharpe_por_suerte_crece_con_las_pruebas_y_baja_con_los_datos():
    assert metrics.sharpe_maximo_por_suerte(30, 5000) > metrics.sharpe_maximo_por_suerte(5, 5000)
    assert metrics.sharpe_maximo_por_suerte(30, 5000) < metrics.sharpe_maximo_por_suerte(30, 500)


def test_sharpe_probabilistico_de_una_estrategia_buena():
    rng = np.random.default_rng(1)
    idx = pd.bdate_range("2000-01-01", periods=5000)
    r = pd.Series(rng.normal(0.0008, 0.01, len(idx)), index=idx)  # Sharpe ~1,3
    assert metrics.sharpe_probabilistico(r) > 0.99


# ---------------------------------------------------------------- estrategias

def mercado_simulado(tendencias: dict, anios=4):
    idx = pd.bdate_range("2015-01-01", periods=252 * anios)
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {a: 100 * np.exp(np.cumsum(mu / 252 + rng.normal(0, 0.005, len(idx)))) for a, mu in tendencias.items()},
        index=idx,
    )


def test_faber_invierte_en_lo_que_sube_y_sale_de_lo_que_baja():
    tend = {a: 0.3 for a in faber.CESTA}
    tend["DBC"] = -0.3
    obj = faber.senales(mercado_simulado(tend)).dropna(how="all")
    ultimo = obj.iloc[-1]
    assert ultimo["SPY"] == pytest.approx(1 / 7)
    assert ultimo["DBC"] == 0


def test_tsmom_solo_largos_nunca_corto_y_sin_apalancamiento():
    tend = {a: (0.2 if i % 2 else -0.2) for i, a in enumerate(tsmom.UNIVERSO)}
    obj = tsmom.senales(mercado_simulado(tend)).dropna(how="all")
    assert (obj.fillna(0) >= 0).all().all()
    assert (obj.abs().sum(axis=1) <= 1 + 1e-9).all()


def test_dual_momentum_elige_la_mejor_bolsa_o_refugio():
    tend = {"SPY": 0.1, "VGK": 0.4, "EWJ": 0.0, "EEM": 0.05, "IEF": 0.02, "BIL": 0.01}
    obj = dual_momentum.senales(mercado_simulado(tend)).dropna(how="all")
    assert obj.iloc[-1]["VGK"] == 1.0
    tend = {"SPY": -0.3, "VGK": -0.3, "EWJ": -0.3, "EEM": -0.3, "IEF": 0.02, "BIL": 0.01}
    obj = dual_momentum.senales(mercado_simulado(tend)).dropna(how="all")
    assert obj.iloc[-1]["IEF"] == 1.0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
