"""
Pruebas del registro de pruebas, las familias del laboratorio y el carry.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.research import familias, laboratorio, registro  # noqa: E402


def mercado(tendencias: dict, anios=3, ruido=0.004):
    idx = pd.bdate_range("2018-01-01", periods=252 * anios)
    rng = np.random.default_rng(1)
    return pd.DataFrame({a: 100 * np.exp(np.cumsum(mu / 252 + rng.normal(0, ruido, len(idx))))
                         for a, mu in tendencias.items()}, index=idx)


# ---------------------------------------------------------------- registro

def test_registro_no_duplica_y_cuenta_el_total(tmp_path):
    ruta = tmp_path / "reg.csv"
    v = {"estrategia": {"id": "x", "familia": "f", "mercado": "m"},
         "sharpes_rejilla": {"a=1": 0.5, "a=2": 0.6}, "sharpes_test_rejilla": {"a=1": 0.4, "a=2": 0.3}}
    assert registro.registrar([v], "test", ruta) == 2
    assert registro.registrar([v], "test", ruta) == 2          # repetir no suma pruebas
    v2 = {**v, "estrategia": {"id": "y"}, "sharpes_rejilla": {"b=1": 0.1}, "sharpes_test_rejilla": {"b=1": 0.0}}
    assert registro.registrar([v2], "test", ruta) == 3
    assert registro.numero_pruebas(ruta) == 3


# ---------------------------------------------------------------- familias

@pytest.mark.parametrize("nombre", [f for f, d in familias.FAMILIAS.items() if "mercados" not in d])
def test_familias_sin_apalancamiento_y_sin_cortos_si_no_se_permiten(nombre):
    activos = ["A", "B", "C"]
    p = mercado({"A": 0.3, "B": -0.3, "C": 0.05})
    fam = familias.FAMILIAS[nombre]
    obj = fam["funcion"](p, activos, largo_corto=False, **fam["parametros"]).ffill().dropna(how="all")
    assert (obj.fillna(0) >= -1e-12).all().all()
    assert (obj.abs().sum(axis=1) <= 1 + 1e-9).all()


def test_tendencia_largo_corto_vende_lo_que_baja():
    p = mercado({"A": 0.4, "B": -0.4})
    obj = familias.tendencia_media(p, ["A", "B"], largo_corto=True, dias=50).ffill().dropna(how="all")
    assert obj["A"].iloc[-1] > 0 and obj["B"].iloc[-1] < 0


def test_ruptura_entra_en_maximos():
    p = mercado({"A": 0.8}, ruido=0.002)
    obj = familias.ruptura_canal(p, ["A"], dias=20).ffill().dropna(how="all")
    assert obj["A"].iloc[-1] > 0


def test_todos_los_experimentos_estan_bien_formados():
    exps = laboratorio.todos_los_experimentos()
    # los mercados solo de investigación (MERCADOS_INVESTIGACION) no entran en el laboratorio semanal
    esperados = sum(len([m for m in d.get("mercados", laboratorio.MERCADOS) if m in laboratorio.MERCADOS])
                    for d in familias.FAMILIAS.values())
    assert len(exps) == esperados
    assert len({e["id"] for e in exps}) == len(exps)
    for e in exps:
        assert e["parametros"] in e["rejilla"]   # el parámetro por defecto está en la rejilla


# ---------------------------------------------------------------- carry

def test_forex_con_carry_acumula_el_diferencial():
    from src.data import macro

    idx = pd.date_range("2020-01-01", "2021-12-31", freq="D")
    precios = pd.DataFrame({"EURUSD=X": 1.10, "JPY=X": 110.0}, index=idx)
    meses = pd.date_range("2019-11-01", "2021-12-01", freq="MS")
    tipos = pd.DataFrame({"USD": 2.0, "EUR": 4.0, "JPY": 0.0}, index=meses)
    out = macro.forex_con_carry(precios, tipos)
    # EUR rinde 2 puntos más que USD: un año largo en EUR/USD gana ~2 %
    r_eur = out["EURUSD=X"].iloc[-1] / out["EURUSD=X"].iloc[0] - 1
    assert r_eur == pytest.approx(np.exp(0.02 * 730 / 365) - 1, rel=0.02)
    # USD/JPY: largo en USD (2 %) frente a JPY (0 %)
    assert out["JPY=X"].iloc[-1] > out["JPY=X"].iloc[0]


def test_procesar_bis():
    from src.data import macro

    csv = ("FREQ,REF_AREA,UNIT_MEASURE,TIME_PERIOD,OBS_VALUE,OBS_STATUS\n"
           "M,US,368,2024-01,5.5,A\nM,US,368,2024-02,5.25,A\nM,US,368,2024-03,,A\n")
    s = macro.procesar_bis(csv)
    assert list(s.values) == [5.5, 5.25]
    assert s.index[0] == pd.Timestamp("2024-01-01")


def test_sin_tipos_no_cambia_nada():
    from src.data import macro

    p = pd.DataFrame({"EURUSD=X": [1.1, 1.2]}, index=pd.date_range("2020-01-01", periods=2))
    assert macro.forex_con_carry(p, pd.DataFrame()).equals(p)


def test_carry_solo_en_forex():
    exps = laboratorio.todos_los_experimentos()
    assert {e["mercado"] for e in exps if e["familia"] == "carry_divisas"} == {"forex"}


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))


# ---------------------------------------------------------------- VAA

def test_vaa_va_al_refugio_si_un_ofensivo_cae():
    idx = pd.bdate_range("2010-01-01", "2012-12-31")
    n = len(idx)
    p = pd.DataFrame({"A": np.linspace(100, 200, n), "B": np.linspace(100, 150, n),
                      "C": np.linspace(100, 300, n), "R": np.linspace(100, 105, n),
                      "BIL": np.linspace(100, 101, n)}, index=idx)
    obj = familias.asignacion_vigilante(p, ["A", "B", "C"], defensivos=("R", "BIL")).dropna(how="all")
    assert obj.iloc[-1]["C"] == 1.0                     # todos suben: el de más momentum
    p.loc[p.index >= "2012-11-01", "B"] = np.linspace(150, 120, (p.index >= "2012-11-01").sum())
    obj = familias.asignacion_vigilante(p, ["A", "B", "C"], defensivos=("R", "BIL")).dropna(how="all")
    assert obj.iloc[-1]["R"] == 1.0                     # uno cae: 100 % al mejor refugio
    assert obj.iloc[-1][["A", "B", "C"]].sum() == 0.0
