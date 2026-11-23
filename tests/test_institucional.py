"""
Pruebas del procesado de datos institucionales (con datos de ejemplo, sin internet).
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data import institucional  # noqa: E402


def test_procesar_cot_calcula_posicion_neta():
    filas = [
        {"report_date_as_yyyy_mm_dd": "2026-11-17T00:00:00.000", "cftc_contract_market_code": "088691",
         "open_interest_all": "500000", "noncomm_positions_long_all": "300000", "noncomm_positions_short_all": "100000",
         "comm_positions_long_all": "50000", "comm_positions_short_all": "250000"},
        {"report_date_as_yyyy_mm_dd": "2026-11-17T00:00:00.000", "cftc_contract_market_code": "999999",
         "open_interest_all": "1"},
    ]
    df = institucional.procesar_cot(filas)
    assert len(df) == 1                                   # el código desconocido se descarta
    fila = df.iloc[0]
    assert fila["activo"] == "GLD"
    assert fila["especuladores_neto"] == 200000
    assert fila["comerciales_neto"] == -200000
    assert fila["especuladores_neto_pct"] == pytest.approx(0.4)


def test_procesar_form345_agrega_solo_compras():
    sub = pd.DataFrame({"ACCESSION_NUMBER": ["a1", "a2", "a3"], "FILING_DATE": ["03-NOV-2025", "03-NOV-2025", "04-NOV-2025"],
                        "ISSUERTRADINGSYMBOL": ["aapl", "AAPL", "MSFT"]})
    trans = pd.DataFrame({"ACCESSION_NUMBER": ["a1", "a2", "a3"], "TRANS_CODE": ["P", "P", "S"],
                          "TRANS_ACQUIRED_DISP_CD": ["A", "A", "D"], "TRANS_SHARES": ["100", "50", "10"],
                          "TRANS_PRICEPERSHARE": ["200", "210", "400"]})
    owners = pd.DataFrame({"ACCESSION_NUMBER": ["a1", "a2", "a3"], "RPTOWNERCIK": ["111", "222", "333"]})
    agg = institucional.procesar_form345(sub, trans, owners)
    assert list(agg["ticker"]) == ["AAPL"]                # la venta de MSFT no cuenta
    assert agg.iloc[0]["directivos"] == 2                 # dos directivos comprando el mismo día
    assert agg.iloc[0]["importe_usd"] == pytest.approx(100 * 200 + 50 * 210)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
