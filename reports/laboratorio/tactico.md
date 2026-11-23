# Laboratorio táctico (velas de 1 hora) · 2026-11-23

6 experimentos. Pruebas acumuladas en el registro: **160**.

Simulación con stop en cada operación, tamaño por riesgo (1,5 % del capital del motor), entrada en la vela siguiente a la señal, costes por operación (cripto 0,25 %, acciones 0,05 %) y, en acciones, sin cierres el mismo día (norma PDT). Test desde julio de 2024; mínimo 100 operaciones.

| Experimento | Veredicto | Sharpe completo | Sharpe test | CAGR | Peor caída | Operaciones | % aciertos | Qué falla |
|---|---|---|---|---|---|---|---|---|
| Momentum horario con stop dinámico · Acciones y ETFs | ❌ RECHAZADA | 0,34 | 0,25 | 4,1 % | -30 % | 2628 | 39 % | Sharpe en test, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo |
| Ruptura horaria (canal de N velas) · Acciones y ETFs | ❌ RECHAZADA | 0,42 | -0,58 | 5,4 % | -31 % | 1083 | 30 % | Sharpe en test, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo |
| Reversión horaria (RSI-2 con tendencia) · Acciones y ETFs | ❌ RECHAZADA | -0,83 | -1,22 | -11,7 % | -57 % | 5218 | 50 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo |
| Ruptura horaria (canal de N velas) · Cripto | ❌ RECHAZADA | -1,13 | -1,95 | -43,2 % | -98 % | 2241 | 21 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo |
| Momentum horario con stop dinámico · Cripto | ❌ RECHAZADA | -3,43 | -4,58 | -76,8 % | -100 % | 6712 | 22 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo |
| Reversión horaria (RSI-2 con tendencia) · Cripto | ❌ RECHAZADA | -6,04 | -7,81 | -71,5 % | -100 % | 6928 | 40 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo |

## Diagnóstico: ¿hay ventaja antes de costes?

Mismos experimentos (parámetros por defecto) sin costes. Si el Sharpe bruto es bueno y el neto malo, la idea tiene algo pero opera demasiado o con stops demasiado ajustados para sus costes.

| Experimento | Sharpe bruto | Sharpe neto | Operaciones | Duración media | Resultado medio por operación (neto) |
|---|---|---|---|---|---|
| Momentum horario con stop dinámico · Acciones y ETFs | 0,97 | 0,34 | 2628 | 80 h | 0,04 % |
| Ruptura horaria (canal de N velas) · Acciones y ETFs | 0,68 | 0,42 | 1083 | 185 h | 0,21 % |
| Reversión horaria (RSI-2 con tendencia) · Acciones y ETFs | 0,54 | -0,83 | 5218 | 34 h | -0,06 % |
| Ruptura horaria (canal de N velas) · Cripto | -0,06 | -1,13 | 2241 | 37 h | -0,50 % |
| Momentum horario con stop dinámico · Cripto | -0,14 | -3,43 | 6712 | 15 h | -0,54 % |
| Reversión horaria (RSI-2 con tendencia) · Cripto | 0,76 | -6,04 | 6928 | 4 h | -0,43 % |

## Candidatas para el motor táctico

Ninguna: ninguna familia táctica supera las pruebas. El motor táctico sigue sin operar.
