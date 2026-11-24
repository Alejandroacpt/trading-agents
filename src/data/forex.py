"""
DATOS HORARIOS DE FOREX (DUKASCOPY)
-----------------------------------
Velas de 1 hora de los pares de divisas, del servicio público y gratuito
de datos históricos de Dukascopy Bank (Suiza). No hace falta cuenta, clave
ni ningún dato personal: solo se descargan precios.

Formato de Dukascopy (datafeed.dukascopy.com):
  - Un archivo por par y MES con las velas de 1 hora:
      <PAR>/<AAAA>/<MM-1>/BID_candles_hour_1.bi5   (el mes empieza en 00)
  - El mes en curso aún no tiene archivo mensual: se usan los archivos
    DIARIOS de velas de 1 minuto y se agregan a horas:
      <PAR>/<AAAA>/<MM-1>/<DD>/BID_candles_min_1.bi5
  - Cada archivo está comprimido con LZMA; cada vela son 24 bytes:
    segundos desde el inicio del periodo, apertura, cierre, mínimo,
    máximo (enteros: precio x 100.000, o x 1.000 en pares con JPY) y volumen.
Las horas son UTC. Precios BID (sin horquilla: los costes del simulador
la incluyen).

Pares y fecha de inicio: config/investigacion.yaml -> forex.
Se guarda en data/horario/forex/<PAR>.csv (mismo formato que el resto).
"""

import lzma
import struct
import time
from datetime import datetime, timezone

import pandas as pd
import yaml

from src.config import CONFIG_DIR
from src.data import horario

URL = "https://datafeed.dukascopy.com/datafeed/{par}/{anio}/{mes:02d}/{resto}"
VELA = struct.Struct(">5if")       # tiempo, apertura, cierre, mínimo, máximo, volumen
MERCADO = "forex"


def cargar_config() -> dict:
    ruta = CONFIG_DIR / "investigacion.yaml"
    with open(ruta, encoding="utf-8") as f:
        conf = (yaml.safe_load(f) or {}).get("forex") or {}
    return {"desde": conf.get("desde", "2016-01-01"), "pares": list(conf.get("pares") or [])}


def escala(par: str) -> float:
    return 1e3 if "JPY" in par else 1e5


def decodificar(datos: bytes, inicio: pd.Timestamp, par: str) -> pd.DataFrame:
    """Convierte un archivo .bi5 de velas en un DataFrame (índice UTC sin zona)."""
    if not datos:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    crudo = lzma.decompress(datos)
    filas = [VELA.unpack_from(crudo, i) for i in range(0, len(crudo) - VELA.size + 1, VELA.size)]
    df = pd.DataFrame(filas, columns=["t", "open", "close", "low", "high", "volume"])
    for c in ("open", "close", "low", "high"):
        df[c] = df[c] / escala(par)
    df.index = inicio + pd.to_timedelta(df.pop("t"), unit="s")
    df.index.name = "date"
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    # Dukascopy rellena las horas sin mercado (fines de semana) con velas planas y volumen 0
    return df[df["volume"] > 0]


PAUSA = 0.4          # segundos entre peticiones (Dukascopy limita a quien pide muy rápido)


def _bajar(url: str, sesion, reintentos: int = 6) -> bytes | None:
    """Descarga un archivo; 404 = no existe (None). Con 503/429 espera cada vez más."""
    for intento in range(reintentos):
        time.sleep(PAUSA)
        try:
            r = sesion.get(url, timeout=30)
            if r.status_code == 404:
                return None
            if r.status_code in (429, 500, 502, 503, 504):
                raise RuntimeError(f"HTTP {r.status_code}")
            r.raise_for_status()
            return r.content
        except Exception:  # noqa: BLE001
            if intento == reintentos - 1:
                raise
            time.sleep(min(60, 3 * 2 ** intento))
    return None


def mes(par: str, anio: int, mes_1: int, sesion) -> pd.DataFrame | None:
    """Velas de 1 hora de un mes completo (None si el archivo mensual aún no existe)."""
    datos = _bajar(URL.format(par=par, anio=anio, mes=mes_1 - 1, resto="BID_candles_hour_1.bi5"), sesion)
    if datos is None:
        return None
    return decodificar(datos, pd.Timestamp(anio, mes_1, 1), par)


def dias_a_horas(par: str, anio: int, mes_1: int, sesion, hasta: pd.Timestamp) -> pd.DataFrame:
    """Para el mes en curso: velas de 1 minuto de cada día, agregadas a 1 hora."""
    partes = []
    for dia in pd.date_range(pd.Timestamp(anio, mes_1, 1), hasta.normalize(), freq="D"):
        url = URL.format(par=par, anio=anio, mes=mes_1 - 1, resto=f"{dia.day:02d}/BID_candles_min_1.bi5")
        datos = _bajar(url, sesion)
        if datos:
            partes.append(decodificar(datos, dia, par))
    if not partes:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    minutos = pd.concat(partes)
    horas = minutos.groupby(minutos.index.floor("h")).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    return horas


def comprobar(df: pd.DataFrame) -> None:
    """Las velas tienen que ser coherentes (mínimo <= apertura/cierre <= máximo)."""
    if df.empty:
        return
    malas = (df["low"] > df[["open", "close"]].min(axis=1) + 1e-9) | (df["high"] < df[["open", "close"]].max(axis=1) - 1e-9)
    if malas.mean() > 0.001:
        raise ValueError(f"Velas incoherentes ({malas.mean():.1%}): el formato de Dukascopy ha cambiado")


def actualizar(pares: list[str] | None = None, desde: str | None = None) -> list[str]:
    """Descarga o actualiza los pares (reanudable: guarda par a par)."""
    import requests

    conf = cargar_config()
    pares = pares or conf["pares"]
    desde = pd.Timestamp(desde or conf["desde"])
    ahora = pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None))
    hora_en_curso = ahora.floor("h")
    sesion = requests.Session()
    sesion.headers["User-Agent"] = "trading-agents (investigación personal)"
    informe = []
    for par in pares:
        try:
            informe.append(_actualizar_par(par, desde, ahora, hora_en_curso, sesion))
        except Exception as e:  # noqa: BLE001 - un par que falla no para los demás
            informe.append(f"{par}: ERROR {type(e).__name__}: {str(e)[:120]}")
        print("  " + informe[-1], flush=True)
    return informe


def _actualizar_par(par, desde, ahora, hora_en_curso, sesion) -> str:
    """Descarga mes a mes; si algo falla a mitad, guarda lo descargado (la próxima vez sigue desde ahí)."""
    previo = horario.cargar(MERCADO, par)
    inicio = desde if previo.empty else (previo.index.max() - pd.Timedelta(days=35)).replace(day=1)
    inicio = max(inicio, desde).normalize().replace(day=1)
    trozos, aviso = [], ""
    for m in pd.date_range(inicio, ahora, freq="MS"):
        try:
            datos = None
            if (m.year, m.month) != (ahora.year, ahora.month):
                datos = mes(par, m.year, m.month, sesion)
            if datos is None:          # mes en curso (o mensual aún no publicado): días sueltos
                datos = dias_a_horas(par, m.year, m.month, sesion, ahora)
        except Exception as e:  # noqa: BLE001
            aviso = f" · cortado en {m:%Y-%m} ({type(e).__name__}: {str(e)[:60]})"
            break
        trozos.append(datos)
    nuevo = pd.concat([t for t in trozos if t is not None and not t.empty]) if trozos else pd.DataFrame()
    if nuevo.empty:
        return f"{par}: sin datos nuevos{aviso}"
    nuevo = nuevo[nuevo.index < hora_en_curso]          # nunca la vela en curso
    comprobar(nuevo)
    df = pd.concat([previo, nuevo]) if not previo.empty else nuevo
    df = df[~df.index.duplicated(keep="last")].sort_index()
    horario.guardar(df, MERCADO, par)
    return f"{par}: {len(df)} velas, de {df.index.min():%Y-%m-%d} a {df.index.max():%Y-%m-%d %H:%M}{aviso}"
