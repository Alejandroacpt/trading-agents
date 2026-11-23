"""
Pruebas del simulador táctico y las familias de corto plazo.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data import horario  # noqa: E402
from src.tactico import familias  # noqa: E402
from src.tactico.simulador import Parametros, simular  # noqa: E402


def velas(precios, inicio="2024-01-01 00:00", freq="h", amplitud=0.002):
    idx = pd.date_range(inicio, periods=len(precios), freq=freq)
    c = pd.Series(precios, index=idx, dtype=float)
    o = c.shift(1).fillna(c.iloc[0])
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) * (1 + amplitud),
                         "low": np.minimum(o, c) * (1 - amplitud), "close": c})


def senal(df, entradas=(), salidas=(), stop=5.0, dinamico=np.nan, max_velas=np.nan):
    s = pd.DataFrame({"entrada": False, "salida": False, "stop": stop, "dinamico": dinamico,
                      "max_velas": max_velas}, index=df.index)
    s.iloc[list(entradas), 0] = True
    s.iloc[list(salidas), 1] = True
    return s


P0 = Parametros(riesgo=0.01, max_posiciones=5, max_peso=1.0, coste=0.0, sin_intradia=False)


def test_entra_en_la_vela_siguiente_y_dimensiona_por_riesgo():
    df = velas([100, 100, 100, 110, 110], amplitud=0.0)
    res = simular({"A": df}, {"A": senal(df, entradas=[1], salidas=[3], stop=5.0)}, P0)
    op = res.operaciones.iloc[0]
    assert op["entrada"] == df.index[2]          # señal en la vela 1 -> compra en la apertura de la 2
    assert op["salida"] == df.index[4]           # salida señalada en la 3 -> se ejecuta en la 4
    # riesgo 1 % con stop a 5 $ sobre 100 $ -> posición del 20 % del capital; gana 10 % -> +2 %
    assert res.equity.iloc[-1] == pytest.approx(1.02)


def test_el_stop_limita_la_perdida_al_riesgo():
    df = velas([100, 100, 100, 90, 90], amplitud=0.0)
    res = simular({"A": df}, {"A": senal(df, entradas=[1], stop=5.0)}, P0)
    op = res.operaciones.iloc[0]
    assert op["motivo"] == "stop"
    # la vela 3 abre en 100 y baja a 90: el stop salta en 95 -> pérdida = 1 % del capital
    assert res.equity.iloc[-1] == pytest.approx(0.99)


def test_hueco_por_debajo_del_stop_se_paga_entero():
    df = velas([100, 100, 100, 100], amplitud=0.0)
    df.loc[df.index[3], ["open", "high", "low", "close"]] = [80, 80, 80, 80]
    res = simular({"A": df}, {"A": senal(df, entradas=[1], stop=5.0)}, P0)
    # abre directamente en 80 (por debajo del stop de 95): se vende a 80
    assert res.equity.iloc[-1] == pytest.approx(1 - 0.20 * 0.20)


def test_stop_dinamico_protege_ganancias():
    df = velas([100, 100, 100, 120, 140, 125], amplitud=0.0)
    res = simular({"A": df}, {"A": senal(df, entradas=[1], stop=5.0, dinamico=10.0)}, P0)
    op = res.operaciones.iloc[0]
    assert op["motivo"] == "stop" and op["resultado"] == pytest.approx(130 / 100 - 1)


def test_regla_pdt_no_cierra_el_mismo_dia():
    idx = pd.date_range("2024-01-02 14:00", periods=4, freq="h").append(
        pd.date_range("2024-01-03 14:00", periods=2, freq="h"))
    df = pd.DataFrame({"open": [100, 100, 100, 100, 100, 100], "high": [100] * 6,
                       "low": [100, 100, 90, 90, 100, 100], "close": [100] * 6}, index=idx, dtype=float)
    s = senal(df, entradas=[0], stop=5.0)
    p = Parametros(riesgo=0.01, max_peso=1.0, coste=0.0, sin_intradia=True)
    res = simular({"A": df}, {"A": s}, p)
    assert res.operaciones.empty or res.operaciones.iloc[0]["salida"].date() > idx[0].date()


def test_costes_y_maximo_de_posiciones():
    dfs = {a: velas([100] * 6, amplitud=0.0) for a in "ABC"}
    sen = {a: senal(dfs[a], entradas=[1]) for a in dfs}
    p = Parametros(riesgo=0.01, max_posiciones=2, max_peso=1.0, coste=0.001)
    res = simular(dfs, sen, p)
    assert (res.pesos.iloc[-1] > 0).sum() == 2
    assert res.equity.iloc[-1] < 1.0          # se han pagado costes


def test_familias_devuelven_las_columnas_esperadas():
    from src.tactico.velas import agregar_cripto

    rng = np.random.default_rng(0)
    corto = velas(100 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, 800))))
    largo = agregar_cripto(velas(100 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, 24 * 400)))))
    for nombre, fam in familias.FAMILIAS_TACTICAS.items():
        df = largo if fam.get("velas") == "4h" else corto
        out = fam["funcion"]({"A": df}, **fam["parametros"])["A"]
        assert {"entrada", "salida", "stop", "dinamico", "max_velas"} <= set(out.columns), nombre
        assert out["entrada"].dtype == bool
        assert (out["stop"].dropna() > 0).all()
        assert out["entrada"].sum() > 0, nombre


def test_datos_horarios_sesion_regular_y_vela_en_curso():
    idx = pd.date_range("2024-07-01 12:00", periods=12, freq="h")   # 8:00-19:00 en Nueva York (verano)
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}, index=idx)
    sesion = horario.solo_sesion_regular(df)
    assert sesion.index.min() == pd.Timestamp("2024-07-01 13:00")  # 9:00 NY
    assert sesion.index.max() == pd.Timestamp("2024-07-01 19:00")  # 15:00 NY
    recortado = horario.sin_vela_en_curso(df, ahora=pd.Timestamp("2024-07-01 20:30"))
    assert recortado.index.max() == pd.Timestamp("2024-07-01 19:00")


def test_agregar_velas_y_descartar_incompletas():
    from src.tactico.velas import agregar_acciones, agregar_cripto

    df = velas(np.arange(1, 11, dtype=float))                     # 10 velas de 1 h desde las 00:00
    a = agregar_cripto(df)
    assert len(a) == 2                                            # 00-04 y 04-08; 08-10 está incompleta
    assert a["open"].iloc[0] == df["open"].iloc[0] and a["close"].iloc[0] == df["close"].iloc[3]
    assert a["high"].iloc[0] == df["high"].iloc[:4].max()
    # Acciones: mañana (4 velas) y tarde (3 velas), en horario de Nueva York (verano: UTC-4)
    idx = pd.date_range("2024-07-01 13:00", periods=7, freq="h")
    acc = pd.DataFrame({"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 1.0}, index=idx)
    g = agregar_acciones(acc)
    assert len(g) == 2 and g.index[1] == pd.Timestamp("2024-07-01 17:00")
    assert len(agregar_acciones(acc.iloc[:6])) == 1               # la tarde incompleta se descarta


def test_tendencia_diaria_no_mira_el_dia_en_curso():
    from src.tactico.velas import tendencia_diaria

    idx = pd.date_range("2024-01-01", periods=24 * 60, freq="h")
    precio = pd.Series(100.0, index=idx)
    precio[idx >= "2024-02-25"] = 200.0                           # salto el día 25
    df = pd.DataFrame({"open": precio, "high": precio, "low": precio, "close": precio})
    t = tendencia_diaria(df, dias=5)
    assert not t[idx.normalize() == pd.Timestamp("2024-02-25")].any()   # ese día aún no se sabe
    assert t[idx.normalize() == pd.Timestamp("2024-02-26")].all()       # al día siguiente, sí


def test_orden_limitada_solo_si_el_precio_llega():
    df = velas([100, 100, 101, 101, 101], amplitud=0.0)
    s = senal(df, entradas=[1], stop=5.0)
    s["limite"] = np.nan
    s.iloc[1, s.columns.get_loc("limite")] = 99.0                 # límite por debajo: el precio no baja a 99
    res = simular({"A": df}, {"A": s}, Parametros(riesgo=0.01, max_peso=1.0, coste=0.0025, coste_limitada=0.0015))
    assert res.operaciones.empty and res.equity.iloc[-1] == pytest.approx(1.0)
    df2 = df.copy()
    df2.loc[df2.index[2], "low"] = 98.0                           # ahora sí toca 99 durante la vela
    res2 = simular({"A": df2}, {"A": s}, Parametros(riesgo=0.01, max_peso=1.0, coste=0.0025, coste_limitada=0.0015))
    assert (res2.pesos.iloc[-1] > 0).any()
    # compra a 99 (el límite): posición = 1 % / 5 $ × 99 $ = 19,8 % del capital, con comisión de limitada
    assert res2.costes.sum() == pytest.approx(0.01 / 5 * 99 * 0.0015, rel=1e-3)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
