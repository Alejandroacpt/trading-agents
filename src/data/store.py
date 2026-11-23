"""
ALMACÉN DE DATOS
----------------
Guarda y lee los precios en archivos CSV, uno por activo:

    data/<clase>/<ticker>.csv      por ejemplo  data/equity/SPY.csv

¿Por qué CSV y no una base de datos?
- Se puede abrir y revisar directamente en GitHub o en Excel.
- Git guarda muy bien los cambios en texto: añadir un día nuevo
  ocupa muy poco en el historial del repositorio.
- Con ~20 activos y datos diarios, el volumen es pequeño (pocos MB).
"""

import re
from pathlib import Path

import pandas as pd

from src.config import DATA_DIR

DECIMALES = 6  # suficientes para forex (5 decimales) y para precios grandes


def ticker_a_archivo(ticker: str) -> str:
    """Convierte un ticker en un nombre de archivo seguro.

    'EURUSD=X' -> 'EURUSD_X'   ·   'BTC-USD' -> 'BTC-USD'
    """
    return re.sub(r"[^A-Za-z0-9\-]", "_", ticker)


def ruta_csv(asset: dict, data_dir: Path = DATA_DIR) -> Path:
    return data_dir / asset["clase"] / f"{ticker_a_archivo(asset['ticker'])}.csv"


def save_prices(df: pd.DataFrame, path: Path) -> None:
    """Guarda una tabla de precios en CSV (redondeada para que git
    no registre cambios por ruido en los últimos decimales)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    out[["open", "high", "low", "close"]] = out[["open", "high", "low", "close"]].round(DECIMALES)
    out["volume"] = out["volume"].fillna(0).round(0).astype("int64")
    out.to_csv(path, date_format="%Y-%m-%d")


def load_prices(path: Path) -> pd.DataFrame:
    """Lee un CSV de precios. Devuelve una tabla vacía si no existe."""
    if not Path(path).exists():
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    return pd.read_csv(path, index_col="date", parse_dates=["date"])


def quitar_vela_incompleta(df: pd.DataFrame, clase: str, ahora_utc: pd.Timestamp | None = None) -> pd.DataFrame:
    """Elimina la vela del día en curso si el mercado aún no ha cerrado.

    Si el pipeline se ejecuta a mitad de sesión, Yahoo devuelve una vela
    "a medias" para hoy. Una estrategia nunca debe usarla: el precio y el
    volumen todavía van a cambiar. Reglas:
      - cripto: el día de Yahoo va de 00:00 a 24:00 UTC, así que la vela
        de hoy (UTC) siempre está incompleta.
      - forex: se da por cerrada a partir de las 22:00 UTC.
      - bolsa de EEUU (ETFs): cierra a las 16:00 hora de Nueva York;
        damos margen hasta las 16:30 para que Yahoo publique el cierre.
    """
    if df.empty:
        return df
    ahora_utc = ahora_utc if ahora_utc is not None else pd.Timestamp.now(tz="UTC")
    if ahora_utc.tzinfo is None:
        ahora_utc = ahora_utc.tz_localize("UTC")

    if clase == "crypto":
        hoy = ahora_utc.tz_localize(None).normalize()
        return df[df.index < hoy]

    if clase == "forex":
        hoy = ahora_utc.tz_localize(None).normalize()
        if ahora_utc.hour < 22:
            return df[df.index < hoy]
        return df

    # ETFs de EEUU (renta variable, bonos, materias primas, liquidez)
    ahora_ny = ahora_utc.tz_convert("America/New_York")
    hoy_ny = ahora_ny.tz_localize(None).normalize()
    if (ahora_ny.hour, ahora_ny.minute) < (16, 30):
        return df[df.index < hoy_ny]
    return df


def decide_replace(old: pd.DataFrame, new: pd.DataFrame) -> tuple[bool, str]:
    """Decide si la descarga nueva sustituye al archivo guardado.

    Cada día se vuelve a descargar TODO el histórico, porque cuando un
    ETF paga dividendo, Yahoo reajusta todos los precios pasados. Pero
    por seguridad NO sustituimos los datos guardados si la descarga
    nueva parece incompleta (una caída de la fuente no debe borrar
    años de histórico).
    """
    if new.empty:
        return False, "la descarga llegó vacía"
    if old.empty:
        return True, "archivo nuevo"
    if new.index.max() < old.index.max():
        return False, (
            f"la descarga termina antes ({new.index.max().date()}) "
            f"que lo guardado ({old.index.max().date()})"
        )
    if len(new) < 0.98 * len(old):
        return False, f"la descarga tiene muchas menos filas ({len(new)} vs {len(old)})"
    return True, "actualizado"


def load_all(assets: list[dict], data_dir: Path = DATA_DIR) -> dict[str, pd.DataFrame]:
    """Carga los precios de todos los activos: {ticker: tabla}."""
    return {a["ticker"]: load_prices(ruta_csv(a, data_dir)) for a in assets}


def close_matrix(assets: list[dict], data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Tabla con una columna de precio de cierre por activo.
    Útil para el motor de backtest (semana 2)."""
    precios = load_all(assets, data_dir)
    return pd.DataFrame({t: df["close"] for t, df in precios.items() if not df.empty}).sort_index()
