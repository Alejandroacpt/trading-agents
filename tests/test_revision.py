"""Kill-switch táctico, stop dentro de la vela en curso y auditoría de la cuenta."""

import importlib.util
from pathlib import Path

import pandas as pd

from src.agents import auditor

_spec = importlib.util.spec_from_file_location("run_tactico", Path(__file__).resolve().parent.parent / "scripts" / "run_tactico.py")
run_tactico = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_tactico)

KS = {"reducir_a_la_mitad": 0.15, "pausa": 0.25}


def test_kill_switch_tactico():
    idx = pd.date_range("2026-11-01", periods=10, freq="D")
    eq = pd.Series([1.0, 1.0, 1.1, 1.2, 1.1, 1.0, 0.98, 0.97, 0.96, 0.95], index=idx)
    # Antes de la puesta en marcha no cuenta: desde el 2026-11-03 el máximo es 1,2 -> caída del 21 %
    f, k, dd = run_tactico.factor_riesgo_tactico(eq, "2026-11-03", KS, 0.0)
    assert k == "MITAD" and f == 0.5 and round(dd, 3) == round(0.95 / 1.2 - 1, 3)
    # La caída de la cartera total también cuenta
    f, k, _ = run_tactico.factor_riesgo_tactico(eq, "2026-11-09", KS, -0.30)
    assert k == "PAUSA" and f == 0.0
    f, k, _ = run_tactico.factor_riesgo_tactico(eq, "2026-11-09", KS, -0.01)
    assert k == "NORMAL" and f == 1.0


def test_tramo_acciones_y_cripto():
    # 14:00 UTC = 9:00 NY (mañana); 18:00 UTC = 13:00 NY (tarde), en invierno
    assert run_tactico._tramo(pd.Timestamp("2026-11-24 14:00"), "acciones").endswith("-0")
    assert run_tactico._tramo(pd.Timestamp("2026-11-24 18:00"), "acciones").endswith("-1")
    assert run_tactico._tramo(pd.Timestamp("2026-11-24 05:00"), "cripto") == str(pd.Timestamp("2026-11-24 04:00"))


def test_desviacion_cuenta():
    alp = {"capital_gestionado_usd": 1000.0, "objetivo": {"SPY": 0.20, "BTC-USD": 0.10},
           "posiciones": {"SPY": 200.0, "AAPL": 80.0}}
    d = auditor.desviacion_cuenta(alp)
    assert abs(d["total"] - 0.18) < 1e-9
    assert set(d["grandes"]) == {"BTC-USD", "AAPL"}     # falta BTC (-10 %) y sobra AAPL (+8 %)
    assert auditor.desviacion_cuenta({}) is None


def test_vivo_tactico_diario():
    idx = pd.to_datetime(["2026-11-24 14:00", "2026-11-24 18:00", "2026-11-25 14:00", "2026-11-25 18:00"])
    eq = pd.Series([1.0, 1.01, 1.02, 0.99], index=idx)
    r = auditor.vivo_tactico(eq, "2026-11-24")
    assert len(r) == 1 and abs(r.iloc[0] - (0.99 / 1.01 - 1)) < 1e-12
