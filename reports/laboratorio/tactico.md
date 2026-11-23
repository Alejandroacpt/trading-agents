# Laboratorio táctico (velas de 1 hora) · 2026-11-23

12 experimentos. Pruebas acumuladas en el registro: **178**.

Simulación con stop en cada operación, tamaño por riesgo (1,5 % del capital del motor), entrada en la vela siguiente a la señal, costes por operación (cripto 0,25 %, acciones 0,05 %) y, en acciones, sin cierres el mismo día (norma PDT). Test desde julio de 2024; mínimo 100 operaciones.

| Experimento | Veredicto | Sharpe completo | Sharpe test | CAGR | Peor caída | Operaciones | % aciertos | Qué falla |
|---|---|---|---|---|---|---|---|---|
| Momentum con tendencia diaria (media sesión) · Acciones y ETFs | 🟡 OBSERVACIÓN | 0,95 | 0,96 | 13,0 % | -20 % | 520 | 38 % | Sharpe deflactado (DSR) |
| Momentum con tendencia diaria (4 h) · Cripto | ❌ RECHAZADA | 0,13 | 0,38 | -1,3 % | -58 % | 945 | 29 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo |
| Ruptura con tendencia diaria (4 h) · Cripto | ❌ RECHAZADA | 0,26 | 0,33 | 3,5 % | -45 % | 387 | 30 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo |
| Ruptura con tendencia diaria (media sesión) · Acciones y ETFs | ❌ RECHAZADA | 0,95 | 0,29 | 14,2 % | -14 % | 315 | 43 % | Sharpe en test, Sharpe deflactado (DSR) |
| Momentum horario con stop dinámico · Acciones y ETFs | ❌ RECHAZADA | 0,34 | 0,25 | 4,1 % | -30 % | 2628 | 39 % | Sharpe en test, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo |
| Ruptura horaria (canal de N velas) · Acciones y ETFs | ❌ RECHAZADA | 0,42 | -0,58 | 5,4 % | -31 % | 1083 | 30 % | Sharpe en test, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo |
| Retroceso en tendencia con orden limitada (media sesión) · Acciones y ETFs | ❌ RECHAZADA | -0,26 | -0,76 | -3,2 % | -26 % | 1637 | 60 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo |
| Reversión horaria (RSI-2 con tendencia) · Acciones y ETFs | ❌ RECHAZADA | -0,83 | -1,22 | -11,7 % | -57 % | 5218 | 50 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo |
| Retroceso en tendencia con orden limitada (4 h) · Cripto | ❌ RECHAZADA | -0,81 | -1,42 | -10,8 % | -59 % | 1247 | 57 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo |
| Ruptura horaria (canal de N velas) · Cripto | ❌ RECHAZADA | -1,13 | -1,95 | -43,2 % | -98 % | 2241 | 21 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo |
| Momentum horario con stop dinámico · Cripto | ❌ RECHAZADA | -3,43 | -4,58 | -76,8 % | -100 % | 6712 | 22 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo |
| Reversión horaria (RSI-2 con tendencia) · Cripto | ❌ RECHAZADA | -6,04 | -7,81 | -71,5 % | -100 % | 6928 | 40 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo |

## Diagnóstico: ¿hay ventaja antes de costes?

Mismos experimentos (parámetros por defecto) sin costes. Si el Sharpe bruto es bueno y el neto malo, la idea tiene algo pero opera demasiado o con stops demasiado ajustados para sus costes.

| Experimento | Sharpe bruto | Sharpe neto | Operaciones | Duración media | Resultado medio por operación (neto) |
|---|---|---|---|---|---|
| Momentum con tendencia diaria (media sesión) · Acciones y ETFs | 1,08 | 0,95 | 520 | 421 h | 0,60 % |
| Momentum con tendencia diaria (4 h) · Cripto | 0,60 | 0,13 | 945 | 101 h | -0,00 % |
| Ruptura con tendencia diaria (4 h) · Cripto | 0,48 | 0,26 | 387 | 153 h | 0,49 % |
| Ruptura con tendencia diaria (media sesión) · Acciones y ETFs | 1,02 | 0,95 | 315 | 664 h | 1,59 % |
| Momentum horario con stop dinámico · Acciones y ETFs | 0,97 | 0,34 | 2628 | 80 h | 0,04 % |
| Ruptura horaria (canal de N velas) · Acciones y ETFs | 0,68 | 0,42 | 1083 | 185 h | 0,21 % |
| Retroceso en tendencia con orden limitada (media sesión) · Acciones y ETFs | 0,16 | -0,26 | 1637 | 63 h | -0,07 % |
| Reversión horaria (RSI-2 con tendencia) · Acciones y ETFs | 0,54 | -0,83 | 5218 | 34 h | -0,06 % |
| Retroceso en tendencia con orden limitada (4 h) · Cripto | 0,53 | -0,81 | 1247 | 15 h | -0,20 % |
| Ruptura horaria (canal de N velas) · Cripto | -0,06 | -1,13 | 2241 | 37 h | -0,50 % |
| Momentum horario con stop dinámico · Cripto | -0,14 | -3,43 | 6712 | 15 h | -0,54 % |
| Reversión horaria (RSI-2 con tendencia) · Cripto | 0,76 | -6,04 | 6928 | 4 h | -0,43 % |

## Candidatas para el motor táctico

- 🟡 **Momentum con tendencia diaria (media sesión) · Acciones y ETFs** (`tac_momentum_tendencia__acciones`)
