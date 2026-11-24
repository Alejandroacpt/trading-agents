"""Fases de capital, aportaciones y cartera combinada de los dos motores."""

from src.agents import capital, cartera_virtual, ejecucion

CONF = {"inicial_eur": 1000, "aportacion_mensual_eur": 100, "primera_aportacion": "2026-12-01", "dia_aportacion": 1}
FASES = [{"hasta_eur": 5000, "tactico": 0.7, "estructural": 0.3},
         {"hasta_eur": 20000, "tactico": 0.5, "estructural": 0.5},
         {"hasta_eur": None, "tactico": 0.2, "estructural": 0.8}]


def test_aportaciones_vencidas():
    assert capital.aportaciones(CONF, "2026-11-30") == []
    assert capital.aportaciones(CONF, "2026-12-01") == [("2026-12-01", 100.0)]
    assert len(capital.aportaciones(CONF, "2027-03-15")) == 4
    assert capital.capital_aportado(CONF, "2027-03-15") == 1400
    assert capital.pendientes(CONF, ["2026-12-01"], "2027-01-02") == [("2027-01-01", 100.0)]


def test_fase_por_valor():
    assert capital.fase_por_valor(FASES, 1000) == 0
    assert capital.fase_por_valor(FASES, 5000) == 1
    assert capital.fase_por_valor(FASES, 25000) == 2


def test_histeresis_cambia_tras_n_dias():
    estado = {"fase": 0}
    for i in range(19):
        f, cambio = capital.actualizar_fase(estado, FASES, 5200, 20, f"2029-01-{i + 1:02d}")
        assert f == 0 and not cambio
    # Un mismo día repetido no suma
    f, cambio = capital.actualizar_fase(estado, FASES, 5200, 20, "2029-01-19")
    assert not cambio
    f, cambio = capital.actualizar_fase(estado, FASES, 5200, 20, "2029-01-20")
    assert f == 1 and cambio


def test_histeresis_se_reinicia_si_vuelve():
    estado = {"fase": 0}
    for i in range(10):
        capital.actualizar_fase(estado, FASES, 5200, 20, f"2029-01-{i + 1:02d}")
    capital.actualizar_fase(estado, FASES, 4800, 20, "2029-01-11")
    assert estado["candidata"] is None
    for i in range(19):
        f, cambio = capital.actualizar_fase(estado, FASES, 5200, 20, f"2029-02-{i + 1:02d}")
    assert f == 0 and not cambio


def test_total_aportacion_no_es_ganancia():
    e = capital.actualizar_total({}, 1000, 0, "2026-11-30")
    e = capital.actualizar_total(e, 950, 0, "2026-12-01")      # cae un 5 %
    e = capital.actualizar_total(e, 1050, 100, "2026-12-02")   # aporta 100: sigue un 5 % abajo
    assert abs(e["total"]["drawdown"] - (1050 / 1100 - 1)) < 1e-4


def test_aportar_estructural():
    estado = {"capital_eur": 300.0, "cartera": {"BTC-USD": 0.5},
              "virtual": {"valor": 300.0, "maximo": 320.0, "inicio": "2026-11-23", "historial": []}}
    cartera_virtual.aportar(estado, 30.0, "2026-12-01")
    assert estado["virtual"]["valor"] == 330.0
    assert estado["virtual"]["maximo"] == 350.0
    assert estado["capital_eur"] == 330.0
    assert abs(estado["cartera"]["BTC-USD"] * 330 - 150) < 1e-9   # mismo importe en BTC
    assert estado["aportaciones"] == ["2026-12-01"]


def test_objetivo_combinado():
    est = {"cartera": {"BTC-USD": 0.5, "SPY": 0.2}, "virtual": {"valor": 300.0}}
    tac = {"valor_total_eur": 700.0,
           "posiciones": {"e|SPY|t": {"activo": "SPY", "importe_eur": 140.0, "estrategia": "e"},
                          "e|AAPL|t": {"activo": "AAPL", "importe_eur": 100.0, "estrategia": "e"}},
           "pendientes": {"e|NVDA|comprar": {"activo": "NVDA", "accion": "comprar", "importe_eur": 70.0, "estrategia": "e"},
                          "e|AAPL|vender": {"activo": "AAPL", "accion": "vender", "estrategia": "e"}}}
    pesos, total = ejecucion.objetivo_combinado(est, tac, True)
    assert total == 1000.0
    assert abs(pesos["BTC-USD"] - 0.15) < 1e-9
    assert abs(pesos["SPY"] - 0.20) < 1e-9          # 60 € estructural + 140 € táctico
    assert abs(pesos["NVDA"] - 0.07) < 1e-9
    assert "AAPL" not in pesos                       # venta pendiente: se cierra
    solo_est, total2 = ejecucion.objetivo_combinado(est, tac, False)
    assert total2 == 300.0 and set(solo_est) == {"BTC-USD", "SPY"}


def test_banda_evita_operar_por_deriva():
    actuales = {"BTC-USD": {"valor": 160.0, "cantidad": 0.002, "precio": 80000.0}}
    # objetivo 150 $, tiene 160 $: desviación 6,7 % < 15 % -> no se opera
    assert ejecucion.calcular_ordenes({"BTC-USD": 0.15}, 1000, actuales, 10, banda=0.15) == []
    # sin banda sí se reajusta (diferencia 10 $)
    assert len(ejecucion.calcular_ordenes({"BTC-USD": 0.15}, 1000, actuales, 10, banda=0.0)) == 1
    # entradas nuevas siempre
    assert ejecucion.calcular_ordenes({"ETH-USD": 0.05}, 1000, {}, 10, banda=0.15)[0]["accion"] == "comprar"


def test_frente_a_spy():
    import numpy as np
    import pandas as pd
    from src.backtest.validator import frente_a_spy
    idx = pd.bdate_range("2020-01-01", "2024-12-31")
    rng = np.random.default_rng(0)
    spy = pd.Series(100 * np.cumprod(1 + 0.0004 + 0.01 * rng.standard_normal(len(idx))), index=idx)
    precios = pd.DataFrame({"SPY": spy})
    r_spy = spy.pct_change().fillna(0)
    mejor = r_spy + 0.0005          # misma volatilidad, más rentabilidad
    peor = r_spy - 0.0005           # misma volatilidad, menos rentabilidad
    assert frente_a_spy(mejor, "2022-01-01", precios)["margen"] > 0
    assert frente_a_spy(peor, "2022-01-01", precios)["margen"] < 0
