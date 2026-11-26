# Momentum con tendencia diaria en ETFs x3 e inversos (media sesión)

- **Idea**: `apalancados-momentum_tendencia` · familia existente `momentum_tendencia` (sin programar nada)
- **Fuente**: prioridad 1 de la guía (momentum de baja rotación en ETFs apalancados con filtro de
  tendencia); Moskowitz, Ooi y Pedersen (2012), *Time Series Momentum*, JFE. Es la misma familia que opera
  en acciones, aplicada al mercado de investigación `apalancados`: TQQQ, UPRO, SOXL, TECL, TNA y los
  inversos SH, PSQ, SQQQ, SPXU (el filtro de tendencia diaria sobre el propio inverso hace que solo se
  compren en mercados bajistas: es la forma de "ganar cuando el mercado baja" sin cortos).
- **Parámetros**: los del sistema, sin tocar: N = 90 velas, stop 3 ATR(14), stop dinámico 4 ATR.

## Cribado (2020-10-20 a 2024-06-28)

| Sharpe | Rentab. anual | Peor caída | Operaciones | Correlación con lo que opera | Veredicto |
|---|---|---|---|---|---|
| −0,04 | −3,0 % | −37 % | 239 | 0,25 | ❌ NO PASA |

**Resultado: rechazada.** No pasa a validación completa.
