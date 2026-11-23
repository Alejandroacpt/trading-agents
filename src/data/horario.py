"""
DATOS HORARIOS (MOTOR TÁCTICO)
------------------------------
Velas de 1 hora para cripto y acciones/ETFs de EEUU.

Fuente principal: API de datos de Alpaca (gratis con la cuenta paper;
acciones con el feed IEX y cripto), con histórico desde 2018 en acciones
y desde 2021 en cripto. Respaldo: Yahoo Finance (solo los últimos ~2 años).

  - Acciones: solo la sesión regular (9:00-16:00 hora de Nueva York).
  - Nunca se guarda la vela en curso (aún no ha cerrado).
  - Actualización incremental: solo se piden los últimos días.

Archivos: data/horario/<mercado>/<SIMBOLO>.csv con hora en UTC.
"""

import os
import time
from pathlib import Path

import pandas as pd
import yaml

from src.config import CONFIG_DIR, DATA_DIR

CARPETA = DATA_DIR / "horario"
URL_ACCIONES = "https://data.alpaca.markets/v2/stocks/bars"
URL_CRIPTO = "https://data.alpaca.markets/v1beta3/crypto/us/bars"


def cargar_config() -> dict:
    with open(CONFIG_DIR / "tactico.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def nombre_archivo(simbolo: str) -> str:
    return simbolo.replace("/", "-")


def ruta(mercado: str, simbolo: str) -> Path:
    return CARPETA / mercado / f"{nombre_archivo(simbolo)}.csv"


def _cabeceras() -> dict:
    key, secret = os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    if not (key and secret):
        raise RuntimeError("Faltan las claves de Alpaca para descargar datos horarios")
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}


def _a_tabla(barras: list[dict]) -> pd.DataFrame:
    if not barras:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    df = pd.DataFrame(barras)
    df.index = pd.to_datetime(df["t"], utc=True).dt.tz_localize(None)
    df.index.name = "date"
    df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def solo_sesion_regular(df: pd.DataFrame) -> pd.DataFrame:
    """Acciones: velas que empiezan entre las 9:00 y las 15:00 de Nueva York."""
    if df.empty:
        return df
    ny = df.index.tz_localize("UTC").tz_convert("America/New_York")
    mascara = (ny.hour >= 9) & (ny.hour <= 15) & (ny.dayofweek < 5)
    return df[mascara]


def sin_vela_en_curso(df: pd.DataFrame, ahora: pd.Timestamp | None = None) -> pd.DataFrame:
    ahora = ahora or pd.Timestamp.now(tz="UTC").tz_localize(None)
    return df[df.index + pd.Timedelta(hours=1) <= ahora]


def descargar_alpaca(mercado: str, simbolos: list[str], desde: str) -> dict[str, pd.DataFrame]:
    """Descarga velas de 1 hora de varios símbolos a la vez (con paginación)."""
    import requests

    url = URL_CRIPTO if mercado == "cripto" else URL_ACCIONES
    params = {"symbols": ",".join(simbolos), "timeframe": "1Hour", "start": f"{desde}T00:00:00Z",
              "limit": 10000, "sort": "asc"}
    if mercado != "cripto":
        params.update({"adjustment": "all", "feed": "iex"})
    acumulado: dict[str, list] = {s: [] for s in simbolos}
    while True:
        for intento in range(3):
            r = requests.get(url, params=params, headers=_cabeceras(), timeout=60)
            if r.status_code == 429:
                time.sleep(5)
                continue
            break
        r.raise_for_status()
        datos = r.json()
        for s, barras in (datos.get("bars") or {}).items():
            acumulado.setdefault(s, []).extend(barras)
        token = datos.get("next_page_token")
        if not token:
            break
        params["page_token"] = token
        time.sleep(0.3)
    return {s: _a_tabla(b) for s, b in acumulado.items()}


def descargar_yahoo(simbolo: str) -> pd.DataFrame:
    import yfinance as yf

    ticker = simbolo.replace("/", "-")
    df = yf.download(ticker, interval="60m", period="730d", auto_adjust=True, progress=False, threads=False)
    if df is None or df.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]
    idx = pd.to_datetime(df.index)
    df.index = (idx.tz_convert("UTC").tz_localize(None) if idx.tz is not None else idx)
    df.index.name = "date"
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def cargar(mercado: str, simbolo: str) -> pd.DataFrame:
    p = ruta(mercado, simbolo)
    if not p.exists():
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    return pd.read_csv(p, index_col="date", parse_dates=["date"])


def guardar(df: pd.DataFrame, mercado: str, simbolo: str) -> None:
    p = ruta(mercado, simbolo)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.round(6).to_csv(p, date_format="%Y-%m-%d %H:%M")


def _al_dia(df: pd.DataFrame, desde: str) -> bool:
    """¿El archivo ya cubre desde la fecha de inicio hasta hace pocos días?"""
    if df.empty:
        return False
    empieza_bien = df.index.min() <= pd.Timestamp(desde) + pd.Timedelta(days=10)
    reciente = df.index.max() >= pd.Timestamp.now() - pd.Timedelta(days=7)
    return bool(empieza_bien and reciente)


def actualizar(mercado: str | None = None, historico: bool = False, dias_solape: int = 5) -> list[str]:
    """Actualiza los datos horarios, símbolo a símbolo (guardando cada uno al
    terminar). historico=True descarga todo desde el inicio, saltando los
    símbolos que ya estén completos: si se corta, se retoma donde se quedó."""
    conf = cargar_config()
    informe = []
    for m, datos in conf["mercados"].items():
        if mercado and m != mercado:
            continue
        actualizados, fuentes = 0, set()
        for s in datos["activos"]:
            previo = cargar(m, s)
            if historico and _al_dia(previo, datos["desde"]):
                actualizados += 1
                continue
            if historico or previo.empty:
                desde = datos["desde"]
            else:
                desde = (previo.index.max() - pd.Timedelta(days=dias_solape)).strftime("%Y-%m-%d")
            try:
                nuevo = descargar_alpaca(m, [s], desde).get(s, pd.DataFrame())
                fuente = "alpaca"
            except Exception as e:  # noqa: BLE001
                print(f"  {s}: Alpaca falló ({type(e).__name__}); pruebo Yahoo", flush=True)
                try:
                    nuevo, fuente = descargar_yahoo(s), "yahoo"
                except Exception:  # noqa: BLE001
                    nuevo, fuente = pd.DataFrame(), "-"
            if nuevo is None or nuevo.empty:
                print(f"  {s}: sin datos", flush=True)
                continue
            if m == "acciones":
                nuevo = solo_sesion_regular(nuevo)
            nuevo = sin_vela_en_curso(nuevo)
            df = pd.concat([previo, nuevo]) if not previo.empty else nuevo
            df = df[~df.index.duplicated(keep="last")].sort_index()
            guardar(df, m, s)
            actualizados += 1
            fuentes.add(fuente)
            if historico:
                print(f"  {m} {s}: {len(df)} velas desde {df.index.min():%Y-%m-%d} ({fuente})", flush=True)
        informe.append(f"{m}: {actualizados}/{len(datos['activos'])} símbolos al día ({', '.join(sorted(fuentes)) or 'sin cambios'})")
    return informe


def matriz(mercado: str, campo: str = "close") -> pd.DataFrame:
    """Tabla con un campo (close, high, low, open) de todos los activos de un mercado."""
    conf = cargar_config()
    cols = {}
    for s in conf["mercados"][mercado]["activos"]:
        df = cargar(mercado, s)
        if not df.empty:
            cols[s] = df[campo]
    return pd.DataFrame(cols).sort_index()
