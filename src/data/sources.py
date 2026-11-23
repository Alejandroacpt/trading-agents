"""
FUENTES DE DATOS
----------------
Funciones que descargan precios diarios de internet y los devuelven
SIEMPRE en el mismo formato (una tabla de pandas):

    date (índice) | open | high | low | close | volume

- Los precios vienen AJUSTADOS por dividendos y splits. Así una
  estrategia de tendencia mide el rendimiento total real, no solo
  el movimiento del precio.
- Las fechas no llevan zona horaria (solo el día).

Fuente principal: Yahoo Finance (librería yfinance) para todo.
Fuente de respaldo: Kraken (librería ccxt) solo para cripto.
"""

import pandas as pd

COLUMNAS = ["open", "high", "low", "close", "volume"]


def _normalizar(df: pd.DataFrame) -> pd.DataFrame:
    """Deja cualquier tabla de precios en el formato estándar."""
    if df is None or df.empty:
        return pd.DataFrame(columns=COLUMNAS)

    df = df.copy()

    # yfinance a veces devuelve columnas en dos niveles (campo, ticker).
    # Nos quedamos solo con el nombre del campo.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Nombres de columna en minúsculas: "Close" -> "close"
    df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]

    # Quitamos la zona horaria y la hora: solo nos interesa el día
    idx = pd.to_datetime(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    df.index = idx.normalize()
    df.index.name = "date"

    # Si falta el volumen (pasa en forex), lo ponemos a 0
    if "volume" not in df.columns:
        df["volume"] = 0

    df = df[COLUMNAS]
    df = df[~df.index.duplicated(keep="last")]   # sin días repetidos
    df = df.dropna(subset=["close"])             # sin días vacíos
    return df.sort_index()


def download_yahoo(ticker: str, start: str | None = None) -> pd.DataFrame:
    """Descarga todo el histórico diario de un ticker desde Yahoo Finance.

    start: fecha "AAAA-MM-DD" desde la que descargar. Si es None,
           descarga todo el histórico disponible.
    """
    import yfinance as yf  # se importa aquí para que los tests no lo necesiten

    kwargs = dict(
        interval="1d",
        auto_adjust=True,      # precios ajustados por dividendos y splits
        progress=False,        # sin barra de progreso
        threads=False,
    )
    if start:
        kwargs["start"] = start
    else:
        kwargs["period"] = "max"

    df = yf.download(ticker, **kwargs)
    return _normalizar(df)


def download_ccxt(symbol: str, exchange: str = "kraken", since: str = "2015-01-01") -> pd.DataFrame:
    """Descarga velas diarias de un exchange de cripto (respaldo de Yahoo).

    Kraken devuelve como máximo ~720 velas por petición, así que esta
    función sirve sobre todo para los últimos ~2 años.
    """
    import ccxt

    ex = getattr(ccxt, exchange)()
    since_ms = int(pd.Timestamp(since).timestamp() * 1000)
    velas = ex.fetch_ohlcv(symbol, timeframe="1d", since=since_ms)

    df = pd.DataFrame(velas, columns=["ts", "open", "high", "low", "close", "volume"])
    df.index = pd.to_datetime(df["ts"], unit="ms")
    return _normalizar(df.drop(columns="ts"))


def download_asset(asset: dict) -> tuple[pd.DataFrame, str]:
    """Descarga un activo del universo usando la mejor fuente disponible.

    Devuelve (tabla_de_precios, nombre_de_la_fuente_usada).
    """
    errores = []

    # 1) Intento principal: Yahoo Finance
    try:
        df = download_yahoo(asset["ticker"])
        if not df.empty:
            return df, "yahoo"
        errores.append("yahoo: sin datos")
    except Exception as e:  # noqa: BLE001 - queremos capturar cualquier fallo de red
        errores.append(f"yahoo: {e}")

    # 2) Respaldo para cripto: Kraken vía ccxt
    if asset.get("ccxt"):
        try:
            df = download_ccxt(asset["ccxt"])
            if not df.empty:
                return df, "kraken"
            errores.append("kraken: sin datos")
        except Exception as e:  # noqa: BLE001
            errores.append(f"kraken: {e}")

    raise RuntimeError(f"No se pudo descargar {asset['ticker']}: " + " | ".join(errores))
