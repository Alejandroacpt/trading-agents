"""
Pruebas de la capa de datos con datos SIMULADOS (no necesitan internet).

Se ejecutan con:  pytest -q
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.alerts import telegram  # noqa: E402
from src.config import load_universe  # noqa: E402
from src.data import quality, store  # noqa: E402
from src.data.sources import _normalizar  # noqa: E402
from src.data.update import informe_markdown, resumen_telegram, update_all  # noqa: E402

HOY = pd.Timestamp("2026-11-20")  # un viernes


def precios_simulados(clase: str, inicio="2015-01-01", fin=HOY, semilla=0) -> pd.DataFrame:
    """Genera un paseo aleatorio con velas coherentes."""
    freq = "D" if clase == "crypto" else "B"
    fechas = pd.date_range(inicio, fin, freq=freq)
    rng = np.random.default_rng(semilla)
    vol = 0.0005 if clase == "cash" else 0.01  # la liquidez apenas se mueve
    close = 100 * np.exp(np.cumsum(rng.normal(0, vol, len(fechas))))
    open_ = close * (1 + rng.normal(0, 0.002, len(fechas)))
    high = np.maximum(open_, close) * 1.005
    low = np.minimum(open_, close) * 0.995
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": 1000},
        index=pd.Index(fechas, name="date"),
    )


def descargador_falso(asset):
    semilla = abs(hash(asset["ticker"])) % 1000
    return precios_simulados(asset["clase"], semilla=semilla), "simulado"


# ---------------------------------------------------------------- universo

def test_universo_carga_y_tiene_las_5_clases():
    assets = load_universe()
    clases = {a["clase"] for a in assets}
    assert {"equity", "bonds", "commodities", "crypto", "forex"} <= clases
    assert len(assets) == 20


# ---------------------------------------------------------------- formato

def test_normalizar_formato_yfinance_multiindex_y_zona_horaria():
    fechas = pd.date_range("2024-01-01", periods=3, freq="D", tz="America/New_York")
    cols = pd.MultiIndex.from_product([["Open", "High", "Low", "Close", "Volume"], ["SPY"]])
    raw = pd.DataFrame(np.ones((3, 5)), index=fechas, columns=cols)
    df = _normalizar(raw)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.tz is None
    assert df.index.name == "date"


def test_normalizar_forex_sin_volumen():
    raw = pd.DataFrame({"Open": [1.1], "High": [1.2], "Low": [1.0], "Close": [1.15]},
                       index=pd.to_datetime(["2024-01-02"]))
    assert _normalizar(raw)["volume"].iloc[0] == 0


# ---------------------------------------------------------------- almacén

def test_guardar_y_leer_csv(tmp_path):
    df = precios_simulados("equity", "2024-01-01", "2024-03-01")
    asset = {"ticker": "EURUSD=X", "clase": "forex"}
    path = store.ruta_csv(asset, tmp_path)
    assert path.name == "EURUSD_X.csv"
    store.save_prices(df, path)
    leido = store.load_prices(path)
    assert len(leido) == len(df)
    assert np.allclose(leido["close"], df["close"], atol=1e-6)


def test_no_se_sustituye_si_la_descarga_es_incompleta():
    old = precios_simulados("equity")
    assert store.decide_replace(old, pd.DataFrame())[0] is False          # vacía
    assert store.decide_replace(old, old.tail(100))[0] is False           # recortada
    assert store.decide_replace(old, old.iloc[:-5])[0] is False           # más antigua
    assert store.decide_replace(old, old)[0] is True                      # completa


# ---------------------------------------------------------------- calidad

def test_datos_limpios_sin_problemas():
    df = precios_simulados("equity")
    assert quality.check_prices(df, "equity", HOY) == []


def test_detecta_precio_negativo_salto_hueco_y_serie_parada():
    df = precios_simulados("equity")
    df.iloc[100, df.columns.get_loc("close")] = -1                       # precio imposible
    df.iloc[200:, :4] *= 1.5                                             # salto del 50 %
    df = df.drop(df.index[300:320])                                      # hueco de ~4 semanas
    problemas = quality.check_prices(df, "equity", HOY + pd.Timedelta(days=10))
    texto = " ".join(p["mensaje"] for p in problemas)
    assert quality.resumen_estado(problemas) == "ERROR"
    assert "<= 0" in texto and "saltos" in texto and "huecos" in texto and "último dato" in texto


def test_ventana_reciente_ignora_problemas_antiguos():
    df = precios_simulados("equity")
    df = df.drop(df.index[300:320])  # hueco en 2016
    assert quality.check_prices(df, "equity", HOY, ventana_dias=30) == []
    assert quality.check_prices(df, "equity", HOY) != []


def test_cripto_fin_de_semana_si_es_hueco():
    df = precios_simulados("crypto")
    df = df[df.index.dayofweek < 5]  # quitamos los fines de semana
    problemas = quality.check_prices(df, "crypto", HOY)
    assert any("huecos" in p["mensaje"] for p in problemas)


# ---------------------------------------------------------------- pipeline completo

def test_pipeline_completo_con_datos_simulados(tmp_path):
    assets = load_universe()
    res = update_all(assets, data_dir=tmp_path, downloader=descargador_falso, hoy=HOY, pausa_segundos=0)
    assert len(res) == 20
    assert all(r["guardado"] for r in res)
    assert all(r["estado"] == "OK" for r in res)
    assert (tmp_path / "crypto" / "BTC-USD.csv").exists()

    # Segunda ejecución con una fuente caída: se conservan los datos anteriores
    def descargador_roto(asset):
        raise ConnectionError("Yahoo no responde")

    res2 = update_all(assets, data_dir=tmp_path, downloader=descargador_roto, hoy=HOY, pausa_segundos=0)
    assert not any(r["guardado"] for r in res2)
    assert all(r["filas"] > 1000 for r in res2)          # los datos siguen ahí
    assert all(r["estado"] == "AVISO" for r in res2)     # y se avisa del fallo

    md = informe_markdown(res, HOY)
    assert "SPY" in md and "Estado de los datos" in md
    msg = resumen_telegram(res2, HOY)
    assert "0/20 activos OK" in msg and "fallo de descarga" in msg

    matriz = store.close_matrix(assets, tmp_path)
    assert matriz.shape[1] == 20


# ---------------------------------------------------------------- telegram

def test_telegram_sin_configurar_no_falla(monkeypatch, capsys):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert telegram.send_message("hola") is False
    assert "hola" in capsys.readouterr().out


def test_telegram_trocea_mensajes_largos():
    texto = "\n".join("línea %d" % i for i in range(2000))
    trozos = telegram._trocear(texto)
    assert len(trozos) > 1
    assert all(len(t) <= telegram.LIMITE_CARACTERES for t in trozos)
    assert "".join(trozos) == texto


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
