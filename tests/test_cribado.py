"""Cribado rápido: veredicto y registro (las ideas cribadas cuentan como pruebas)."""

from src.research import cribado


def test_veredicto():
    assert cribado._veredicto(0.8, 0.10, -0.20, 120) == (True, "pasa al laboratorio")
    ok, motivo = cribado._veredicto(0.3, -0.02, -0.50, 20)
    assert not ok and "Sharpe" in motivo and "caída" in motivo and "operaciones" in motivo
    assert cribado._veredicto(0.8, 0.10, -0.20, None)[0]          # diario: sin mínimo de operaciones


def test_registrar_no_duplica(tmp_path):
    ruta = tmp_path / "c.csv"
    r = {"tipo": "tactico", "familia": "f", "mercado": "acciones", "parametros": {"a": 1}, "desde": "2020-01-01",
         "hasta": "2024-06-28", "sharpe": 0.7, "cagr": 0.1, "max_dd": -0.2, "operaciones": 80, "pasa": True,
         "motivo": "pasa al laboratorio"}
    assert cribado.registrar(r, "idea1", "YouTube", "https://x", ruta) == 1
    assert cribado.registrar(r, "idea1", "YouTube", "https://x", ruta) == 1      # misma idea: no cuenta dos veces
    assert cribado.registrar({**r, "parametros": {"a": 2}}, "idea2", ruta=ruta) == 2


def test_correlacion_con_lo_que_opera():
    import numpy as np
    import pandas as pd
    idx = pd.date_range("2021-01-01", periods=300, freq="D")
    rng = np.random.default_rng(1)
    ref = pd.Series(rng.normal(0, 0.01, 300), index=idx)
    igual = ref * 2
    otra = pd.Series(rng.normal(0, 0.01, 300), index=idx)
    assert cribado.correlacion(igual, {"vivo": ref}) > 0.99
    assert abs(cribado.correlacion(otra, {"vivo": ref})) < 0.2
    assert cribado.correlacion(otra, {}) != cribado.correlacion(otra, {})      # sin referencia: NaN
