"""Datos de forex de Dukascopy: decodificación del formato .bi5 y coherencia."""

import lzma
import struct

import pandas as pd
import pytest

from src.data import forex


def _bi5(velas):
    crudo = b"".join(struct.pack(">5if", *v) for v in velas)
    return lzma.compress(crudo, format=lzma.FORMAT_ALONE)


def test_decodificar_velas_horarias():
    # tiempo (s), apertura, cierre, mínimo, máximo (x100.000), volumen
    datos = _bi5([(0, 108000, 108050, 107950, 108100, 12.5),
                  (3600, 108050, 108020, 108000, 108080, 9.0),
                  (7200, 108020, 108020, 108020, 108020, 0.0)])       # hora sin mercado: se descarta
    df = forex.decodificar(datos, pd.Timestamp("2026-01-05"), "EURUSD")
    assert list(df.index) == [pd.Timestamp("2026-01-05 00:00"), pd.Timestamp("2026-01-05 01:00")]
    assert df.iloc[0].to_dict() == {"open": 1.08, "high": 1.081, "low": 1.0795, "close": 1.0805, "volume": 12.5}
    forex.comprobar(df)


def test_pares_con_yen_usan_otra_escala():
    df = forex.decodificar(_bi5([(0, 150123, 150200, 150000, 150300, 1.0)]), pd.Timestamp("2026-01-05"), "USDJPY")
    assert df["open"].iloc[0] == pytest.approx(150.123)


def test_comprobar_detecta_formato_roto():
    df = pd.DataFrame({"open": [1.0] * 10, "high": [0.9] * 10, "low": [1.1] * 10, "close": [1.0] * 10, "volume": [1.0] * 10})
    with pytest.raises(ValueError):
        forex.comprobar(df)


def test_archivo_vacio():
    assert forex.decodificar(b"", pd.Timestamp("2026-01-05"), "EURUSD").empty
