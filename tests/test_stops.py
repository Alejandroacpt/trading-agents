"""Órdenes stop reales de las posiciones tácticas en Alpaca paper."""

from src.agents import ejecucion

TACTICO = {
    "posiciones": {
        "e|AAPL|t1": {"activo": "AAPL", "entrada": "2026-11-20 14:00:00", "stop": 180.0, "importe_eur": 100.0},
        "e|MSFT|t2": {"activo": "MSFT", "entrada": "2026-11-25 14:00:00", "stop": 400.0, "importe_eur": 100.0},  # comprada hoy
        "e|NVDA|t3": {"activo": "NVDA", "entrada": "2026-11-18 14:00:00", "stop": 150.0, "importe_eur": 100.0},
        "e|XLE|t4": {"activo": "XLE", "entrada": "2026-11-18 14:00:00", "stop": 90.0, "importe_eur": 100.0},
    },
    "pendientes": {"e|NVDA|vender": {"activo": "NVDA", "accion": "vender"}},
}
POSICIONES = [
    {"symbol": "AAPL", "qty": "0.8", "current_price": "200"},
    {"symbol": "MSFT", "qty": "0.25", "current_price": "420"},
    {"symbol": "NVDA", "qty": "0.7", "current_price": "160"},
    {"symbol": "XLE", "qty": "1.2", "current_price": "88"},       # ya por debajo de su stop
]


def test_stops_deseados():
    d = ejecucion.stops_deseados(TACTICO, POSICIONES, 1.10, "2026-11-25")
    assert set(d) == {"AAPL"}                       # MSFT: comprada hoy; NVDA: venta pendiente; XLE: bajo el stop
    assert abs(d["AAPL"]["cantidad"] - 0.55) < 1e-9  # 100 € x 1,10 / 200 $ (menos que las 0,8 de la cuenta)
    assert d["AAPL"]["stop"] == 180.0


class Cliente:
    def __init__(self):
        self.canceladas, self.puestos = [], []

    def cancelar(self, oid):
        self.canceladas.append(oid)

    def stop_venta(self, activo, cantidad, stop, ref):
        self.puestos.append((activo, round(cantidad, 4), stop))
        return {"id": "n", "status": "accepted"}


def test_sincronizar_mantiene_cambia_y_quita():
    deseados = {"AAPL": {"activo": "AAPL", "cantidad": 0.55, "stop": 180.0},
                "GOOGL": {"activo": "GOOGL", "cantidad": 0.3, "stop": 150.0}}
    abiertas = [
        {"id": "s1", "symbol": "AAPL", "client_order_id": "ta-stop-1", "stop_price": "180.00", "qty": "0.55", "side": "sell"},
        {"id": "s2", "symbol": "GOOGL", "client_order_id": "ta-stop-2", "stop_price": "140.00", "qty": "0.3", "side": "sell"},
        {"id": "s3", "symbol": "TSLA", "client_order_id": "ta-stop-3", "stop_price": "200.00", "qty": "1", "side": "sell"},
        {"id": "o4", "symbol": "SPY", "client_order_id": "ta-2026-1", "side": "buy"},     # no es un stop: no se toca
    ]
    c = Cliente()
    cambios = ejecucion.sincronizar_stops(c, deseados, abiertas)
    assert sorted(c.canceladas) == ["s2", "s3"]      # GOOGL con otro precio, TSLA sin posición
    assert c.puestos == [("GOOGL", 0.3, 150.0)]      # AAPL ya estaba bien
    assert any("GOOGL" in x for x in cambios)


def test_ejecutar_quita_el_stop_antes_de_vender_y_no_lo_cancela_si_no():
    class C(Cliente):
        def ordenes_abiertas(self):
            return [{"id": "s1", "symbol": "AAPL", "client_order_id": "ta-stop-1", "side": "sell"},
                    {"id": "s2", "symbol": "MSFT", "client_order_id": "ta-stop-2", "side": "sell"}]

        def cerrar_posicion(self, t):
            return {"id": "x", "status": "accepted"}

    c = C()
    res = ejecucion.ejecutar([{"activo": "AAPL", "accion": "cerrar", "importe": 100}], c, "paper", ["AAPL", "MSFT"])
    assert c.canceladas == ["s1"]                    # el de MSFT se queda
    assert res[0]["estado"] == "accepted"            # no se confunde con "ya pendiente"
