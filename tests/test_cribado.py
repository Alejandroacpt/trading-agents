"""Cribado rápido: veredicto y registro (las ideas cribadas cuentan como pruebas)."""

from src.research import cribado


def test_veredicto():
    assert cribado._veredicto(0.8, 0.10, -0.20, 120) == (True, "pasa al laboratorio")
    ok, motivo = cribado._veredicto(0.3, -0.02, -0.50, 20)
    assert not ok and "Sharpe" in motivo and "caída" in motivo and "operaciones" in motivo
    assert cribado._veredicto(0.8, 0.10, -0.20, None)[0]          # diario: sin mínimo de operaciones


def test_registrar_no_duplica(tmp_path):
    ruta = tmp_path / "c.csv"
    r = {"tipo": "tactico", "familia": "f", "mercado": "acciones", "parametros": {"a": 1}, "desde": "2020-01-01",
         "hasta": "2024-06-28", "sharpe": 0.7, "cagr": 0.1, "max_dd": -0.2, "operaciones": 80, "pasa": True,
         "motivo": "pasa al laboratorio"}
    assert cribado.registrar(r, "idea1", "YouTube", "https://x", ruta) == 1
    assert cribado.registrar(r, "idea1", "YouTube", "https://x", ruta) == 1      # misma idea: no cuenta dos veces
    assert cribado.registrar({**r, "parametros": {"a": 2}}, "idea2", ruta=ruta) == 2
