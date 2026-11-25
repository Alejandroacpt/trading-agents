"""
Pruebas del agente de riesgo, las alertas y la cartera virtual.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents import alertas, cartera_virtual, riesgo  # noqa: E402

SISTEMA = {
    "capital_eur": 1000,
    "riesgo": {"tope_cripto": 0.25, "tope_por_activo": 0.20, "ventana_volatilidad": 252,
               "kill_switch": {"reducir_a_la_mitad": 0.15, "pausa": 0.25}},
    "cartera_ejecutable": {"max_posiciones": 5, "minimo_posicion_eur": 50},
    "alertas": {"umbral_ajuste": 0.05},
}


# ---------------------------------------------------------------- riesgo

def test_cartera_ejecutable_reescala_a_la_exposicion_del_modelo():
    modelo = pd.Series({"A": 0.10, "B": 0.08, "C": 0.06, "D": 0.05, "E": 0.04, "F": 0.03, "G": 0.02})
    ej = riesgo.cartera_ejecutable(modelo, SISTEMA)
    assert len(ej) <= 5
    assert ej.sum() == pytest.approx(modelo.sum())        # misma exposición total
    assert (ej * 1000 >= 50 - 1e-9).all()                  # nada por debajo de 50 €
    assert (ej <= 0.20 + 1e-12).all()                      # tope por activo


def test_cartera_ejecutable_respeta_tope_aunque_baje_la_exposicion():
    modelo = pd.Series({"A": 0.5, "B": 0.4})
    ej = riesgo.cartera_ejecutable(modelo, SISTEMA)
    assert (ej <= 0.20 + 1e-12).all()


def test_cartera_ejecutable_vacia_si_todo_es_liquidez():
    assert riesgo.cartera_ejecutable(pd.Series(dtype=float), SISTEMA).empty


def test_kill_switch():
    assert riesgo.factor_kill_switch(-0.05, SISTEMA) == (1.0, "NORMAL")
    assert riesgo.factor_kill_switch(-0.16, SISTEMA) == (0.5, "MITAD")
    assert riesgo.factor_kill_switch(-0.30, SISTEMA) == (0.0, "PAUSA")


def test_tope_de_cripto_en_el_reparto():
    idx = pd.date_range("2024-01-01", periods=400, freq="D")
    precios = pd.DataFrame({"BTC-USD": 100.0, "SPY": 100.0}, index=idx)
    precios.iloc[::2] = 101.0  # algo de movimiento
    senales = {
        "cripto": {"estrategia": {"universo": ["BTC-USD", "BIL"]}, "config": {"peso_riesgo": 1.0},
                   "objetivos": pd.DataFrame({"BTC-USD": 1.0}, index=idx)},
        "bolsa": {"estrategia": {"universo": ["SPY", "BIL"]}, "config": {"peso_riesgo": 0.01},
                  "objetivos": pd.DataFrame({"SPY": 1.0}, index=idx)},
    }
    rep = riesgo.reparto_estrategias(senales, precios, SISTEMA)
    assert rep["cripto"] == pytest.approx(0.25)
    assert rep.sum() == pytest.approx(1.0)


# ---------------------------------------------------------------- alertas

def test_detectar_cambios():
    antes = {"SPY": 0.10, "GLD": 0.08, "TLT": 0.05}
    despues = {"SPY": 0.10, "TLT": 0.12, "BTC-USD": 0.06}
    cambios = {c["activo"]: c["tipo"] for c in alertas.detectar_cambios(antes, despues, 0.05)}
    assert cambios == {"GLD": "VENTA", "BTC-USD": "COMPRA", "TLT": "AJUSTE"}


def test_ajuste_pequeno_no_avisa():
    assert alertas.detectar_cambios({"SPY": 0.10}, {"SPY": 0.12}, 0.05) == []


def test_mensaje_de_compra_lleva_todo_lo_necesario():
    detalle = {"BTC-USD": {"cierre": 62805.5, "estrategias": {"crypto_trend_vol": {
        "estado": "aprobada", "motivo": "BTC cerró por encima de su media.", "salida": "Se vende si cierra por debajo."}}}}
    msg = alertas.mensaje_cambio({"activo": "BTC-USD", "tipo": "COMPRA", "antes": 0.0, "despues": 0.08},
                                 1000, detalle, {"BTC-USD": "crypto"})
    for texto in ("COMPRA BTC-USD", "80 €", "8,0 %", "aprobada", "Por qué", "Salida", "Ejecutar: hoy"):
        assert texto in msg


def test_kill_switch_solo_avisa_si_cambia():
    assert alertas.mensaje_kill_switch("NORMAL", "NORMAL", -0.05) is None
    assert "mitad" in alertas.mensaje_kill_switch("NORMAL", "MITAD", -0.16)


# ---------------------------------------------------------------- cartera virtual

def test_cartera_virtual_revaloriza_y_mide_la_caida():
    previo = {"cartera": {"SPY": 0.5}, "precios_ref": {"SPY": 100.0},
              "virtual": {"valor": 1000.0, "maximo": 1100.0, "inicio": "2026-11-23", "historial": []}}
    v = cartera_virtual.actualizar_valor(previo, {"SPY": 110.0}, 1000)
    assert v["valor"] == pytest.approx(1050.0)             # +10 % sobre la mitad de la cartera
    assert v["drawdown"] == pytest.approx(1050 / 1100 - 1)
    assert v["pesos_derivados"]["SPY"] == pytest.approx(0.55 / 1.05)


def test_cartera_virtual_cobra_costes_al_cambiar():
    virtual = {"valor": 1000.0, "maximo": 1000.0, "pesos_derivados": {}, "inicio": "2026-11-23", "historial": []}
    est = cartera_virtual.nuevo_estado(virtual, {"SPY": 0.5}, {"SPY": 100.0}, {"SPY": "equity"},
                                       "NORMAL", {}, "2026-11-23")
    assert est["virtual"]["valor"] == pytest.approx(1000 * (1 - 0.5 * 0.001))


def test_cambiar_capital_reescala_la_cartera_virtual():
    estado = {"capital_eur": 1000.0, "cartera": {"SPY": 0.1},
              "virtual": {"valor": 1050.0, "maximo": 1100.0, "inicio": "2026-11-23",
                          "historial": [["2026-11-23", 1000.0], ["2026-11-30", 1050.0]]}}
    e = cartera_virtual.ajustar_capital(estado, 2000)
    assert e["virtual"]["valor"] == pytest.approx(2100.0)      # misma rentabilidad (+5 %)
    assert e["virtual"]["maximo"] == pytest.approx(2200.0)
    assert e["virtual"]["historial"][0][1] == pytest.approx(2000.0)
    assert e["cartera"] == {"SPY": 0.1}                          # los pesos no cambian
    assert cartera_virtual.ajustar_capital(e, 2000)["virtual"]["valor"] == pytest.approx(2100.0)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))


def test_coste_frente_a_la_vela_horaria(tmp_path, monkeypatch):
    import pandas as pd
    from src.agents import diario as dmod
    from src.data import horario
    velas = pd.DataFrame({"open": [100.0, 101.0], "high": [101, 102], "low": [99, 100], "close": [100.5, 101.5],
                          "volume": [1, 1]}, index=pd.to_datetime(["2026-11-24 14:00", "2026-11-24 15:00"]))
    monkeypatch.setattr(horario, "cargar", lambda m, s: velas if s == "AAPL" else pd.DataFrame())
    d = pd.DataFrame([{"fecha_utc": "2026-11-24T10:00+00:00", "tipo": "orden", "activo": "AAPL", "accion": "comprar",
                       "importe": 100, "estado": "accepted", "order_id": "o1", "precio_ref": 90.0}])

    class C:
        def orden(self, oid):
            return {"status": "filled", "filled_avg_price": "100.05", "filled_qty": "1",
                    "filled_at": "2026-11-24T14:30:05Z"}

    r = dmod.actualizar_ejecuciones(d, C())
    assert r.loc[0, "precio_ref"] == 100.0                     # apertura de la vela de las 14:00, no el cierre viejo
    assert abs(r.loc[0, "coste_ejecucion"] - 0.0005) < 1e-9
    assert r.loc[0, "fecha_ejecucion"] == "2026-11-24T14:30:05"


def test_reintenta_coste_de_ordenes_ejecutadas_recientes():
    import pandas as pd
    from datetime import datetime, timezone
    from src.agents import diario as dmod
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M+00:00")
    fila = pd.Series({"estado": "filled", "coste_ejecucion": float("nan"), "fecha_ejecucion": float("nan"), "fecha_utc": hoy})
    assert dmod._necesita_revision(fila)
    vieja = fila.copy(); vieja["fecha_utc"] = "2020-01-01T00:00+00:00"
    assert not dmod._necesita_revision(vieja)
