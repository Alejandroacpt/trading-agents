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
    # Para los cortos: varias monedas (incluido BTC) con tendencia bajista
    bajista = {a: agregar_cripto(velas(100 * np.exp(np.cumsum(rng.normal(-0.0002, 0.01, 24 * 400)))))
               for a in ("BTC/USD", "ETH/USD", "SOL/USD", "DOGE/USD")}
    for nombre, fam in familias.FAMILIAS_TACTICAS.items():
        df = largo if fam.get("velas") == "4h" else corto
        ohlc = bajista if nombre.startswith("corto_") else {"A": df}
        res = fam["funcion"](ohlc, **fam["parametros"])
        for out in res.values():
            assert {"entrada", "salida", "stop", "dinamico", "max_velas"} <= set(out.columns), nombre
            assert out["entrada"].dtype == bool
            assert (out["stop"].dropna() > 0).all()
        assert sum(out["entrada"].sum() for out in res.values()) > 0, nombre
        if nombre.startswith("corto_"):
            assert all(out["corto"].all() for out in res.values()), nombre


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


# --- Cortos (solo investigación) ---

def senal_corta(df, **kw):
    s = senal(df, **kw)
    s["corto"] = True
    return s


def test_corto_gana_si_el_precio_baja():
    df = velas([100, 100, 100, 90, 90], amplitud=0.0)
    res = simular({"A": df}, {"A": senal_corta(df, entradas=[1], salidas=[3], stop=5.0)}, P0)
    op = res.operaciones.iloc[0]
    assert op["lado"] == "corto" and op["resultado"] == pytest.approx(0.10)
    # posición del 20 % (riesgo 1 % con stop a 5 $) que gana un 10 % -> +2 %
    assert res.equity.iloc[-1] == pytest.approx(1.02)
    assert res.pesos["A"].iloc[2] == pytest.approx(-0.20)   # peso negativo mientras está abierto


def test_stop_del_corto_salta_por_arriba_y_el_hueco_se_paga():
    df = velas([100, 100, 100, 110, 110], amplitud=0.0)
    res = simular({"A": df}, {"A": senal_corta(df, entradas=[1], stop=5.0)}, P0)
    op = res.operaciones.iloc[0]
    assert op["motivo"] == "stop"
    assert res.equity.iloc[-1] == pytest.approx(0.99)        # salta en 105: pierde el 1 %
    df2 = velas([100, 100, 100, 100], amplitud=0.0)
    df2.loc[df2.index[3], ["open", "high", "low", "close"]] = [120, 120, 120, 120]
    res2 = simular({"A": df2}, {"A": senal_corta(df2, entradas=[1], stop=5.0)}, P0)
    assert res2.equity.iloc[-1] == pytest.approx(1 - 0.20 * 0.20)  # abre en 120: se recompra a 120


def test_stop_dinamico_del_corto_baja_con_el_precio():
    df = velas([100, 100, 100, 80, 60, 75], amplitud=0.0)
    res = simular({"A": df}, {"A": senal_corta(df, entradas=[1], stop=5.0, dinamico=10.0)}, P0)
    op = res.operaciones.iloc[0]
    assert op["motivo"] == "stop" and op["resultado"] == pytest.approx((100 - 70) / 100)


def test_financiacion_del_corto_se_cobra_por_tiempo():
    df = velas([100] * 26, freq="D", amplitud=0.0)
    p = Parametros(riesgo=0.01, max_posiciones=5, max_peso=1.0, coste=0.0, financiacion_corto=0.365)
    res = simular({"A": df}, {"A": senal_corta(df, entradas=[0], stop=5.0)}, p)
    # posición del 20 % abierta 24 días a un 36,5 % anual (0,1 % diario) -> 0,2 × 0,1 % × 24
    assert res.equity.iloc[-1] == pytest.approx(1 - 0.20 * 0.001 * 24)


def test_largos_sin_cambios_con_columna_corto_falsa():
    df = velas([100, 100, 100, 110, 110], amplitud=0.0)
    s = senal(df, entradas=[1], salidas=[3], stop=5.0)
    s["corto"] = False
    res = simular({"A": df}, {"A": s}, P0)
    assert res.operaciones.iloc[0]["lado"] == "largo"
    assert res.equity.iloc[-1] == pytest.approx(1.02)


def test_regimen_bajista_no_mira_el_dia_en_curso():
    from src.tactico.velas import regimen_bajista

    idx = pd.date_range("2024-01-01", periods=24 * 60, freq="h")
    precio = pd.Series(100.0, index=idx)
    precio[idx >= "2024-02-25"] = 50.0                            # caída el día 25
    df = pd.DataFrame({"open": precio, "high": precio, "low": precio, "close": precio})
    r = regimen_bajista(df, dias=5)
    assert not r[idx.normalize() == pd.Timestamp("2024-02-25")].any()
    assert r[idx.normalize() == pd.Timestamp("2024-02-26")].all()
    # Con pendiente: exige además que la media de ayer esté por debajo de la de 3 días antes
    assert regimen_bajista(df, dias=5, pendiente=3)[idx.normalize() == pd.Timestamp("2024-02-26")].all()
    assert not regimen_bajista(df, dias=5, pendiente=3)[idx.normalize() == pd.Timestamp("2024-02-20")].any()


def test_debilidad_relativa_solo_corta_las_mas_debiles_y_nunca_btc():
    idx = pd.date_range("2024-01-01", periods=6 * 120, freq="4h")
    n = len(idx)
    base = np.linspace(100, 60, n)                                # BTC bajando: régimen bajista
    precios = {"BTC/USD": base, "A": base * np.linspace(1, 0.5, n),   # A, la más débil
               "B": base * np.linspace(1, 0.8, n), "C": base * np.linspace(1, 1.2, n),
               "D": base * np.linspace(1, 1.5, n)}
    ohlc = {k: velas(v, freq="4h") for k, v in precios.items()}
    out = familias.corto_debilidad_relativa(ohlc, velas=42)
    assert not out["BTC/USD"]["entrada"].any()
    assert out["A"]["entrada"].iloc[-1] and out["B"]["entrada"].iloc[-1]
    assert not out["C"]["entrada"].any() and not out["D"]["entrada"].any()
    assert not out["C"]["salida"].iloc[-1]                         # 3.ª peor: se mantendría
    assert out["D"]["salida"].iloc[-1]                             # fuera de las 3 peores


def test_patrones_graficos_no_miran_al_futuro():
    """La señal en t no cambia al añadir velas posteriores (suavizado y extremos solo con datos hasta t)."""
    from src.tactico import patrones as pt

    rng = np.random.default_rng(3)
    precios = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 1500)))
    n = 1200
    corta, larga = pt.senales(precios[:n]), pt.senales(precios)
    assert corta["alcista"].sum() + corta["bajista"].sum() > 0
    for k in corta:
        np.testing.assert_array_equal(corta[k], larga[k][:n], err_msg=k)
    # Lo mismo con la familia completa (incluido el ETF inverso que sigue al SPY)
    idx = pd.date_range("2024-01-01", periods=1500, freq="4h")
    ohlc = {a: velas(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 1500))), freq="4h").set_axis(idx)
            for a in ("SPY", "SH", "BTC")}
    larga = familias.patrones_graficos(ohlc)
    corta = familias.patrones_graficos({a: df.iloc[:n] for a, df in ohlc.items()})
    for a in ohlc:
        pd.testing.assert_frame_equal(corta[a], larga[a].iloc[:n], check_freq=False)
    assert larga["SH"]["entrada"].sum() > 0


def test_patron_hombro_cabeza_hombro_invertido():
    from src.tactico import patrones as pt

    # Extremos: mínimo 100, máximo 110, cabeza 90, máximo 110, mínimo 100 -> IHS con clavicular en 110
    ext = [(10, -1, 100.0), (17, 1, 110.0), (24, -1, 90.0), (30, 1, 110.5), (35, -1, 100.5)]
    p = pt.buscar_patrones(ext, ventana=38, d=3, tol=0.015)
    assert [x["tipo"] for x in p] == ["IHS"]
    assert p[0]["cabeza"] == 90.0 and pt.clavicular_en(p[0], 17) == 110.0
    # Si el último extremo es antiguo (no está en las 3 últimas velas), no se confirma nada
    assert pt.buscar_patrones(ext[:-1] + [(32, -1, 100.5)], ventana=38, d=3, tol=0.015) == []
