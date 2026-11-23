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

@pytest.mark.parametrize("nombre", list(familias.FAMILIAS))
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
    assert len(exps) == len(familias.FAMILIAS) * len(laboratorio.MERCADOS)
    assert len({e["id"] for e in exps}) == len(exps)
    for e in exps:
        assert e["parametros"] in e["rejilla"]   # el parámetro por defecto está en la rejilla


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
