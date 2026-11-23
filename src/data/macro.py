"""
TIPOS DE INTERÉS (FRED) Y FOREX CON CARRY
-----------------------------------------
Descarga los tipos de interés a 3 meses de las 6 divisas de nuestro
universo desde FRED (la base de datos pública de la Reserva Federal de
San Luis; gratis y sin clave) y los guarda en data/macro/tipos_3m.csv.

¿Para qué?
En forex, quien compra una divisa con tipos más altos que la que vende
cobra la diferencia cada día (el "carry"). Medir las divisas solo por su
precio ignora esa parte de la rentabilidad. Con los tipos construimos
series "con carry" (rentabilidad total), que son las que usa el
laboratorio para probar cualquier estrategia de forex.
"""

import io

import numpy as np
import pandas as pd

from src.config import DATA_DIR

RUTA_TIPOS = DATA_DIR / "macro" / "tipos_3m.csv"

# Tipo interbancario a 3 meses (OCDE, mensual), publicado en FRED
SERIES_FRED = {
    "USD": "IR3TIB01USM156N",
    "EUR": "IR3TIB01EZM156N",
    "GBP": "IR3TIB01GBM156N",
    "JPY": "IR3TIB01JPM156N",
    "AUD": "IR3TIB01AUM156N",
    "CHF": "IR3TIB01CHM156N",
}

# Par de Yahoo -> (divisa que se compra al ir "largo", divisa que se vende)
PARES = {
    "EURUSD=X": ("EUR", "USD"),
    "GBPUSD=X": ("GBP", "USD"),
    "AUDUSD=X": ("AUD", "USD"),
    "JPY=X": ("USD", "JPY"),    # USD/JPY: largo = comprar dólares
    "CHF=X": ("USD", "CHF"),    # USD/CHF: largo = comprar dólares
}


def descargar_fred(serie: str, intentos: int = 2) -> pd.Series:
    import time

    import requests

    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={serie}"
    for i in range(intentos):
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (trading-agents research)"})
            r.raise_for_status()
            break
        except Exception:  # noqa: BLE001
            if i == intentos - 1:
                raise
            time.sleep(5)
    df = pd.read_csv(io.StringIO(r.text))
    col_fecha = df.columns[0]           # "observation_date" o "DATE" según la versión
    s = pd.to_numeric(df[df.columns[1]], errors="coerce")
    s.index = pd.to_datetime(df[col_fecha])
    return s.dropna()


def actualizar_tipos() -> dict:
    """Descarga todas las series. Si una falla, conserva la guardada."""
    previos = cargar_tipos()
    columnas, informe = {}, {}
    for divisa, serie in SERIES_FRED.items():
        try:
            s = descargar_fred(serie)
            columnas[divisa] = s
            informe[divisa] = f"OK hasta {s.index.max().date()}"
        except Exception as e:  # noqa: BLE001
            if divisa in previos:
                columnas[divisa] = previos[divisa].dropna()
            informe[divisa] = f"ERROR ({type(e).__name__}); se mantiene lo guardado"
    if columnas:
        tipos = pd.DataFrame(columnas).sort_index()
        RUTA_TIPOS.parent.mkdir(parents=True, exist_ok=True)
        tipos.to_csv(RUTA_TIPOS, index_label="date", float_format="%.4f")
    return informe


def cargar_tipos() -> pd.DataFrame:
    if not RUTA_TIPOS.exists():
        return pd.DataFrame()
    return pd.read_csv(RUTA_TIPOS, index_col="date", parse_dates=["date"])


def diferencial_diario(tipos: pd.DataFrame, indice: pd.DatetimeIndex) -> pd.DataFrame:
    """Diferencial de tipos (en tanto por uno anual) que cobra una posición
    LARGA en cada par, alineado a días.

    Se usa el dato del mes anterior (los tipos mensuales se publican con
    retraso): así no se usa información que aún no se conocía.
    """
    salida = {}
    t = tipos.shift(1)  # mes anterior
    for par, (larga, corta) in PARES.items():
        if larga in t and corta in t:
            dif = (t[larga] - t[corta]) / 100
            salida[par] = dif.reindex(indice.union(dif.index)).ffill().reindex(indice)
    return pd.DataFrame(salida, index=indice)


def forex_con_carry(precios: pd.DataFrame, tipos: pd.DataFrame | None = None) -> pd.DataFrame:
    """Devuelve una copia de 'precios' en la que los pares de forex incluyen
    el carry (precio × crecimiento acumulado por el diferencial de tipos).
    Si no hay tipos descargados, devuelve los precios sin cambios."""
    tipos = cargar_tipos() if tipos is None else tipos
    if tipos.empty:
        return precios
    out = precios.copy()
    for par in PARES:
        if par not in out:
            continue
        s = out[par].dropna()
        dif = diferencial_diario(tipos, s.index)[par].fillna(0.0)
        dias = s.index.to_series().diff().dt.days.fillna(0).to_numpy()
        crecimiento = np.exp(np.cumsum(dif.to_numpy() * dias / 365))
        out.loc[s.index, par] = s.to_numpy() * crecimiento
    return out
