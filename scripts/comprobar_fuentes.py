"""
Comprueba qué fuentes de datos responden desde el servidor donde se ejecuta
(GitHub Actions). Útil cuando una descarga falla: dice si la fuente está
caída o bloqueada, sin esperar minutos.

Uso:
    python scripts/comprobar_fuentes.py
"""

import time

import requests

FUENTES = {
    "FRED (gráficos CSV)": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=IR3TIB01USM156N",
    "FRED (API)": "https://api.stlouisfed.org/fred/series?series_id=DGS3MO",
    "BIS (tipos oficiales, API)": "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0/M.US?format=csv",
    "BIS (web)": "https://www.bis.org/statistics/cbpol.htm",
    "OECD (SDMX)": "https://sdmx.oecd.org/public/rest/dataflow/all",
    "DBnomics": "https://api.db.nomics.world/v22/providers",
    "BCE (API de datos)": "https://data-api.ecb.europa.eu/service/data/FM/M.U2.EUR.RT.MM.EURIBOR3MD_.HSTA?format=csvdata&lastNObservations=3",
    "CFTC (COT)": "https://publicreporting.cftc.gov/resource/6dca-aqww.json?$limit=1",
    "SEC": "https://www.sec.gov/files/company_tickers.json",
    "Yahoo Finance": "https://query1.finance.yahoo.com/v8/finance/chart/%5EIRX?range=5d&interval=1d",
}

CABECERA = {"User-Agent": "Mozilla/5.0 (trading-agents research)"}

for nombre, url in FUENTES.items():
    t = time.time()
    try:
        r = requests.get(url, headers=CABECERA, timeout=15)
        print(f"{nombre:28s} HTTP {r.status_code}  {time.time() - t:4.1f}s  {r.text[:60]!r}")
    except Exception as e:  # noqa: BLE001
        print(f"{nombre:28s} FALLA {type(e).__name__}  {time.time() - t:4.1f}s")
