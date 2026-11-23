"""
DATOS INSTITUCIONALES
---------------------
Qué hace el "dinero grande", con fuentes públicas y gratuitas:

1. POSICIONAMIENTO EN FUTUROS (informe COT de la CFTC, semanal).
   Cada martes la CFTC publica cuántos contratos tienen comprados y
   vendidos los grandes especuladores (fondos), las coberturas
   comerciales (productores y consumidores) y los pequeños operadores, en
   cada mercado de futuros. Se publica el viernes.
   -> data/institucional/cot.csv

2. COMPRAS DE DIRECTIVOS (SEC, formulario 4).
   Los directivos de una empresa deben declarar cuándo compran o venden
   acciones de su propia empresa. Las COMPRAS con su propio dinero son una
   de las pocas señales con evidencia académica sólida (Lakonishok y Lee,
   2001; Cohen, Malloy y Pomorski, 2012). Usamos los conjuntos de datos
   trimestrales de la SEC (sirven para backtest; llegan con retraso).
   -> data/institucional/compras_directivos.csv

Todo con tolerancia a fallos: si una fuente no responde, se conserva lo
guardado y se informa.
"""

import io
import zipfile
from datetime import date

import pandas as pd

from src.config import DATA_DIR

CARPETA = DATA_DIR / "institucional"
RUTA_COT = CARPETA / "cot.csv"
RUTA_DIRECTIVOS = CARPETA / "compras_directivos.csv"

# Código de mercado de la CFTC -> activo de nuestro universo al que se refiere
MERCADOS_COT = {
    "13874A": "SPY",       # E-mini S&P 500
    "209742": "QQQ",       # Nasdaq-100 mini
    "043602": "IEF",       # Bono del Tesoro a 10 años
    "020601": "TLT",       # Bono del Tesoro a largo plazo
    "088691": "GLD",       # Oro
    "084691": "SLV",       # Plata
    "067651": "USO",       # Petróleo WTI
    "099741": "EURUSD=X",  # Euro
    "096742": "GBPUSD=X",  # Libra
    "097741": "JPY=X",     # Yen (ojo: largo en futuros de yen = corto en USD/JPY)
    "232741": "AUDUSD=X",  # Dólar australiano
    "092741": "CHF=X",     # Franco suizo (largo en futuros de franco = corto en USD/CHF)
    "133741": "BTC-USD",   # Bitcoin (CME)
    "146021": "ETH-USD",   # Ether (CME)
}

URL_COT = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"  # informe "legacy", solo futuros
CABECERA_SEC = {"User-Agent": "trading-agents research (github.com/Alejandroacpt/trading-agents)"}


# ----------------------------------------------------------------------
# COT
# ----------------------------------------------------------------------

def procesar_cot(filas: list[dict]) -> pd.DataFrame:
    """Convierte la respuesta de la CFTC en una tabla limpia."""
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    num = lambda c: pd.to_numeric(df.get(c), errors="coerce")  # noqa: E731
    out = pd.DataFrame({
        "fecha": pd.to_datetime(df["report_date_as_yyyy_mm_dd"]).dt.date,
        "codigo": df["cftc_contract_market_code"].astype(str).str.strip(),
        "interes_abierto": num("open_interest_all"),
        "especuladores_largo": num("noncomm_positions_long_all"),
        "especuladores_corto": num("noncomm_positions_short_all"),
        "comerciales_largo": num("comm_positions_long_all"),
        "comerciales_corto": num("comm_positions_short_all"),
    })
    out["activo"] = out["codigo"].map(MERCADOS_COT)
    out["especuladores_neto"] = out["especuladores_largo"] - out["especuladores_corto"]
    out["comerciales_neto"] = out["comerciales_largo"] - out["comerciales_corto"]
    # En % del interés abierto: comparable entre mercados y a lo largo del tiempo
    out["especuladores_neto_pct"] = out["especuladores_neto"] / out["interes_abierto"]
    return out.dropna(subset=["activo"]).sort_values(["activo", "fecha"])


def actualizar_cot(desde: str = "2006-01-01") -> str:
    import requests

    codigos = ",".join(f"'{c}'" for c in MERCADOS_COT)
    params = {
        "$where": f"cftc_contract_market_code in ({codigos}) AND report_date_as_yyyy_mm_dd >= '{desde}'",
        "$limit": 50000,
        "$order": "report_date_as_yyyy_mm_dd",
    }
    try:
        r = requests.get(URL_COT, params=params, timeout=60)
        r.raise_for_status()
        df = procesar_cot(r.json())
    except Exception as e:  # noqa: BLE001
        return f"COT: ERROR ({type(e).__name__}: {str(e)[:120]}); se mantiene lo guardado"
    if df.empty:
        return "COT: la respuesta llegó vacía; se mantiene lo guardado"
    CARPETA.mkdir(parents=True, exist_ok=True)
    df.to_csv(RUTA_COT, index=False, float_format="%.6g")
    faltan = sorted(set(MERCADOS_COT.values()) - set(df["activo"]))
    return (f"COT: {len(df)} filas, {df['activo'].nunique()} mercados, hasta {df['fecha'].max()}"
            + (f". Sin datos: {', '.join(faltan)}" if faltan else ""))


def cargar_cot() -> pd.DataFrame:
    if not RUTA_COT.exists():
        return pd.DataFrame()
    return pd.read_csv(RUTA_COT, parse_dates=["fecha"])


# ----------------------------------------------------------------------
# Compras de directivos (SEC, conjuntos de datos trimestrales del formulario 4)
# ----------------------------------------------------------------------

def _col(df: pd.DataFrame, nombre: str) -> str:
    """Busca una columna sin distinguir mayúsculas (la SEC no es constante)."""
    for c in df.columns:
        if c.upper() == nombre.upper():
            return c
    raise KeyError(nombre)


def procesar_form345(submission: pd.DataFrame, transacciones: pd.DataFrame, propietarios: pd.DataFrame) -> pd.DataFrame:
    """Compras en mercado abierto (código P) agregadas por empresa y día de declaración."""
    t = transacciones
    compras = t[(t[_col(t, "TRANS_CODE")].astype(str).str.upper() == "P")
                & (t[_col(t, "TRANS_ACQUIRED_DISP_CD")].astype(str).str.upper() == "A")].copy()
    compras["importe"] = (pd.to_numeric(compras[_col(t, "TRANS_SHARES")], errors="coerce")
                          * pd.to_numeric(compras[_col(t, "TRANS_PRICEPERSHARE")], errors="coerce"))
    acc = _col(t, "ACCESSION_NUMBER")
    s = submission.rename(columns={_col(submission, "ACCESSION_NUMBER"): acc})
    s = s[[acc, _col(submission, "FILING_DATE"), _col(submission, "ISSUERTRADINGSYMBOL")]]
    s.columns = [acc, "fecha_declaracion", "ticker"]
    p = propietarios.rename(columns={_col(propietarios, "ACCESSION_NUMBER"): acc})
    p = p[[acc, _col(propietarios, "RPTOWNERCIK")]].drop_duplicates(acc)
    p.columns = [acc, "directivo"]
    df = compras.merge(s, on=acc).merge(p, on=acc, how="left")
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["fecha_declaracion"] = pd.to_datetime(df["fecha_declaracion"], errors="coerce", format="mixed").dt.date
    agg = (df.dropna(subset=["fecha_declaracion"])
             .groupby(["ticker", "fecha_declaracion"])
             .agg(directivos=("directivo", "nunique"), operaciones=(acc, "nunique"), importe_usd=("importe", "sum"))
             .reset_index())
    return agg[agg["ticker"].str.len().between(1, 6)]


def _trimestres(n: int) -> list[str]:
    hoy = date.today()
    y, q = hoy.year, (hoy.month - 1) // 3 + 1
    salida = []
    for _ in range(n + 1):
        q -= 1
        if q == 0:
            y, q = y - 1, 4
        salida.append(f"{y}q{q}")
    return salida  # del más reciente (puede no estar publicado aún) al más antiguo


def actualizar_directivos(trimestres: int = 12) -> str:
    import requests

    previos = cargar_directivos()
    hechos = set(previos["trimestre"].unique()) if not previos.empty else set()
    nuevos, informe = [], []
    for tq in _trimestres(trimestres):
        if tq in hechos:
            continue
        url = f"https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{tq}_form345.zip"
        try:
            r = requests.get(url, headers=CABECERA_SEC, timeout=120)
            if r.status_code == 404:
                informe.append(f"{tq}: aún no publicado")
                continue
            r.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                leer = lambda nombre: pd.read_csv(  # noqa: E731
                    z.open(next(n for n in z.namelist() if n.upper().endswith(nombre))),
                    sep="\t", dtype=str, low_memory=False)
                agg = procesar_form345(leer("SUBMISSION.TSV"), leer("NONDERIV_TRANS.TSV"), leer("REPORTINGOWNER.TSV"))
            agg["trimestre"] = tq
            nuevos.append(agg)
            informe.append(f"{tq}: {len(agg)} días-empresa con compras")
        except Exception as e:  # noqa: BLE001
            informe.append(f"{tq}: ERROR ({type(e).__name__}: {str(e)[:80]})")
    if nuevos:
        todo = pd.concat([previos] + nuevos, ignore_index=True) if not previos.empty else pd.concat(nuevos)
        todo = todo.drop_duplicates(["ticker", "fecha_declaracion", "trimestre"]).sort_values(["fecha_declaracion", "ticker"])
        CARPETA.mkdir(parents=True, exist_ok=True)
        todo.to_csv(RUTA_DIRECTIVOS, index=False, float_format="%.0f")
    return "Directivos: " + ("; ".join(informe) if informe else "nada nuevo")


def cargar_directivos() -> pd.DataFrame:
    if not RUTA_DIRECTIVOS.exists():
        return pd.DataFrame()
    return pd.read_csv(RUTA_DIRECTIVOS, parse_dates=["fecha_declaracion"])
