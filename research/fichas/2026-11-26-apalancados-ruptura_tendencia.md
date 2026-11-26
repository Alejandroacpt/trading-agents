# Ruptura con tendencia diaria en ETFs x3 e inversos (media sesión)

- **Idea**: `apalancados-ruptura_tendencia` · familia existente `ruptura_tendencia` (sin programar nada)
- **Fuente**: prioridad 1 de la guía; canal de Donchian (Faith, 2007) con filtro de tendencia de
  Faber (2007). Mercado de investigación `apalancados` (ETFs x3 e inversos, ver ficha anterior).
- **Parámetros**: los del sistema, sin tocar: N = 60 velas, salida mínimo de 30, stop 3 ATR, dinámico 4 ATR.

## Cribado (2020-10-20 a 2024-06-28)

| Sharpe | Rentab. anual | Peor caída | Operaciones | Correlación con lo que opera | Veredicto |
|---|---|---|---|---|---|
| −0,36 | −8,8 % | −45 % | 142 | 0,25 | ❌ NO PASA |

**Resultado: rechazada.**
