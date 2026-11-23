"""
CLIENTE DE ALPACA (SOLO PAPER TRADING)
--------------------------------------
Habla con la API de Alpaca para consultar la cuenta de simulación y
enviar órdenes. Por seguridad, la dirección está fijada a la de PAPER:
este código no puede operar con dinero real aunque se le den claves de
una cuenta real (las claves de una cuenta real no funcionan en la
dirección de paper).

Claves (secretos de GitHub, nunca en el código):
  ALPACA_API_KEY, ALPACA_SECRET_KEY

Formatos de símbolo:
  - ETFs: igual que en Yahoo (SPY, GLD...).
  - Cripto: en las órdenes "BTC/USD"; en las posiciones aparece "BTCUSD".
"""

import os
import time

import requests

URL_PAPER = "https://paper-api.alpaca.markets"


def a_simbolo_alpaca(ticker: str) -> str:
    """'BTC-USD' (Yahoo) -> 'BTC/USD' (Alpaca). Los ETFs no cambian."""
    return ticker.replace("-", "/") if ticker.endswith("-USD") else ticker


def normalizar(simbolo: str) -> str:
    """Forma común para comparar: 'BTC/USD' y 'BTCUSD' -> 'BTCUSD'."""
    return simbolo.replace("/", "").replace("-", "")


def es_cripto(ticker: str) -> bool:
    return ticker.endswith("-USD")


class ClienteAlpaca:
    def __init__(self, key: str | None = None, secret: str | None = None):
        self.key = key or os.getenv("ALPACA_API_KEY")
        self.secret = secret or os.getenv("ALPACA_SECRET_KEY")
        if not (self.key and self.secret):
            raise RuntimeError("Faltan los secretos ALPACA_API_KEY / ALPACA_SECRET_KEY")
        self.base = URL_PAPER  # fijo: nunca dinero real

    def _pedir(self, metodo: str, ruta: str, intentos: int = 3, **kwargs):
        cabeceras = {"APCA-API-KEY-ID": self.key, "APCA-API-SECRET-KEY": self.secret}
        for i in range(intentos):
            try:
                r = requests.request(metodo, self.base + ruta, headers=cabeceras, timeout=20, **kwargs)
            except requests.exceptions.RequestException as e:
                if i == intentos - 1:
                    raise ConnectionError(f"Alpaca no responde: {type(e).__name__}") from None
                time.sleep(2 ** (i + 1))
                continue
            if r.status_code == 429 and i < intentos - 1:  # demasiadas peticiones: esperar
                time.sleep(3)
                continue
            return r
        return r

    def _json(self, metodo, ruta, **kwargs):
        r = self._pedir(metodo, ruta, **kwargs)
        if r.status_code >= 400:
            raise RuntimeError(f"Alpaca {metodo} {ruta} -> {r.status_code}: {r.text[:300]}")
        return r.json() if r.text else {}

    # --- consultas ---
    def cuenta(self) -> dict:
        return self._json("GET", "/v2/account")

    def posiciones(self) -> list[dict]:
        return self._json("GET", "/v2/positions")

    def ordenes_abiertas(self) -> list[dict]:
        return self._json("GET", "/v2/orders", params={"status": "open", "limit": 500})

    def orden(self, order_id: str) -> dict:
        return self._json("GET", f"/v2/orders/{order_id}")

    # --- acciones ---
    def cancelar(self, order_id: str) -> None:
        r = self._pedir("DELETE", f"/v2/orders/{order_id}")
        if r.status_code not in (200, 204, 404, 422):
            raise RuntimeError(f"No se pudo cancelar {order_id}: {r.status_code} {r.text[:200]}")

    def comprar_importe(self, ticker: str, importe_usd: float, ref: str = "") -> dict:
        """Compra por importe en dólares (permite fracciones)."""
        datos = {
            "symbol": a_simbolo_alpaca(ticker),
            "notional": f"{importe_usd:.2f}",
            "side": "buy",
            "type": "market",
            "time_in_force": "gtc" if es_cripto(ticker) else "day",
        }
        if ref:
            datos["client_order_id"] = ref
        return self._json("POST", "/v2/orders", json=datos)

    def vender_cantidad(self, ticker: str, cantidad: float, ref: str = "") -> dict:
        """Vende una cantidad (permite fracciones)."""
        datos = {
            "symbol": a_simbolo_alpaca(ticker),
            "qty": f"{cantidad:.9f}".rstrip("0").rstrip("."),
            "side": "sell",
            "type": "market",
            "time_in_force": "gtc" if es_cripto(ticker) else "day",
        }
        if ref:
            datos["client_order_id"] = ref
        return self._json("POST", "/v2/orders", json=datos)

    def cerrar_posicion(self, ticker: str) -> dict:
        """Vende toda la posición de un activo."""
        return self._json("DELETE", f"/v2/positions/{normalizar(a_simbolo_alpaca(ticker))}")
