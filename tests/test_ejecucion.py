"""
Pruebas de la ejecución en Alpaca (con un Alpaca falso), el diario y el auditor.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents import auditor, diario, ejecucion  # noqa: E402
from src.broker import alpaca  # noqa: E402

UNIVERSO = ["SPY", "GLD", "TLT", "BTC-USD", "ETH-USD"]


# ---------------------------------------------------------------- cliente

class RespuestaFalsa:
    def __init__(self, status=200, datos=None):
        self.status_code = status
        self._datos = datos if datos is not None else {"id": "abc", "status": "accepted"}
        self.text = "x"

    def json(self):
        return self._datos


def test_cliente_solo_habla_con_paper_y_formatea_bien(monkeypatch):
    llamadas = []

    def falso(metodo, url, **kw):
        llamadas.append((metodo, url, kw.get("json")))
        return RespuestaFalsa()

    monkeypatch.setattr(alpaca.requests, "request", falso)
    c = alpaca.ClienteAlpaca("k", "s")
    c.comprar_importe("SPY", 123.456)
    c.comprar_importe("BTC-USD", 50)
    c.vender_cantidad("GLD", 0.123456789)
    c.cerrar_posicion("ETH-USD")

    assert all(url.startswith("https://paper-api.alpaca.markets/") for _, url, _ in llamadas)
    assert llamadas[0][2] == {"symbol": "SPY", "notional": "123.46", "side": "buy", "type": "market", "time_in_force": "day"}
    assert llamadas[1][2]["symbol"] == "BTC/USD" and llamadas[1][2]["time_in_force"] == "gtc"
    assert llamadas[2][2]["qty"] == "0.123456789" and llamadas[2][2]["side"] == "sell"
    assert llamadas[3][0] == "DELETE" and llamadas[3][1].endswith("/v2/positions/ETHUSD")


def test_cliente_sin_claves_no_arranca(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError):
        alpaca.ClienteAlpaca()


# ---------------------------------------------------------------- cálculo de órdenes

def test_capital_de_referencia():
    assert ejecucion.capital_referencia({"equity": "1150"}, 1000, 1.10) == (1150.0, "cuenta")
    assert ejecucion.capital_referencia({"equity": "100000"}, 1000, 1.10) == (pytest.approx(1100.0), "presupuesto")


def test_posiciones_gestionadas_reconoce_cripto_e_ignora_lo_ajeno():
    pos = [{"symbol": "BTCUSD", "market_value": "80", "qty": "0.001", "current_price": "80000"},
           {"symbol": "SPY", "market_value": "100", "qty": "0.15", "current_price": "690"},
           {"symbol": "AAPL", "market_value": "500", "qty": "2", "current_price": "250"}]
    g = ejecucion.posiciones_gestionadas(pos, UNIVERSO)
    assert set(g) == {"BTC-USD", "SPY"}


def test_calcular_ordenes():
    cartera = {"SPY": 0.10, "GLD": 0.05, "BTC-USD": 0.08}
    actuales = {"SPY": {"valor": 100.0, "cantidad": 0.15, "precio": 690.0},
                "TLT": {"valor": 50.0, "cantidad": 0.6, "precio": 81.0},
                "BTC-USD": {"valor": 120.0, "cantidad": 0.0015, "precio": 80000.0}}
    ordenes = {o["activo"]: o for o in ejecucion.calcular_ordenes(cartera, 1000, actuales, 10)}
    assert ordenes["TLT"]["accion"] == "cerrar"                       # ya no está en la cartera
    assert ordenes["GLD"]["accion"] == "comprar" and ordenes["GLD"]["importe"] == pytest.approx(50)
    assert ordenes["BTC-USD"]["accion"] == "vender"                   # de 120 $ a 80 $
    assert ordenes["BTC-USD"]["cantidad"] == pytest.approx(40 / 80000)
    assert "SPY" not in ordenes                                       # ya está en su objetivo
    lista = ejecucion.calcular_ordenes(cartera, 1000, actuales, 10)
    assert [o["accion"] for o in lista][-1] == "comprar"              # ventas antes que compras


def test_modo_simulacion_no_envia_nada():
    class ClienteQueNoDebeUsarse:
        def __getattr__(self, nombre):
            raise AssertionError(f"en simulación no se debe llamar a {nombre}")

    res = ejecucion.ejecutar([{"activo": "SPY", "accion": "comprar", "importe": 50}],
                             ClienteQueNoDebeUsarse(), "simulacion", UNIVERSO)
    assert res[0]["estado"] == "simulada"


def test_modo_paper_cancela_pendientes_y_sigue_si_una_orden_falla():
    class ClienteFalso:
        def __init__(self):
            self.canceladas, self.enviadas = [], []

        def ordenes_abiertas(self):
            return [{"id": "o1", "symbol": "SPY"}, {"id": "o2", "symbol": "AAPL"}]

        def cancelar(self, oid):
            self.canceladas.append(oid)

        def comprar_importe(self, t, imp, ref):
            if t == "GLD":
                raise RuntimeError("rechazada")
            self.enviadas.append(t)
            return {"id": "n1", "status": "accepted"}

    c = ClienteFalso()
    res = ejecucion.ejecutar([{"activo": "GLD", "accion": "comprar", "importe": 50},
                              {"activo": "SPY", "accion": "comprar", "importe": 50}], c, "paper", UNIVERSO)
    assert c.canceladas == ["o1"]                 # solo las de activos del sistema
    assert res[0]["estado"] == "error" and res[1]["estado"] == "accepted"


# ---------------------------------------------------------------- diario

def test_diario_apunta_la_ejecucion_y_su_coste(tmp_path):
    d = diario.anadir(diario.cargar(tmp_path / "x.csv"), [
        {"tipo": "orden", "activo": "SPY", "accion": "comprar", "importe": 100, "precio_ref": 100.0,
         "estado": "accepted", "order_id": "o1"}])

    class ClienteFalso:
        def orden(self, oid):
            return {"status": "filled", "filled_avg_price": "100.5", "filled_qty": "0.995"}

    d = diario.actualizar_ejecuciones(d, ClienteFalso())
    assert d.loc[0, "estado"] == "filled"
    assert d.loc[0, "coste_ejecucion"] == pytest.approx(0.005)   # comprado un 0,5 % más caro
    diario.guardar(d, tmp_path / "x.csv")
    assert len(diario.cargar(tmp_path / "x.csv")) == 1


# ---------------------------------------------------------------- auditor

REF = {"cagr": 0.10, "volatilidad": 0.15, "sharpe": 0.7, "max_drawdown": -0.20}


def serie(rent_diaria, dias):
    idx = pd.date_range("2027-01-01", periods=dias, freq="D")
    return pd.Series(rent_diaria, index=idx)


def test_semaforo():
    assert auditor.semaforo(serie(0.0003, 30), REF)[0].endswith("POCOS DATOS")
    caida = np.r_[np.zeros(20), np.full(20, -0.012)]                       # cae ~21 %
    assert "DEGRADADA" in auditor.semaforo(serie(caida, 40), REF)[0]
    caida_media = np.r_[np.zeros(20), np.full(20, -0.009)]                  # cae ~17 %
    assert "VIGILAR" in auditor.semaforo(serie(caida_media, 40), REF)[0]
    rng = np.random.default_rng(0)
    normal = rng.normal(0.10 / 365, 0.15 / np.sqrt(365), 200)
    assert auditor.semaforo(serie(normal, 200), REF)[0].endswith("OK")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
