# Propuesta (sin cribar): ETF x3 con filtro de la media de 200 días del índice

- **Fuentes**:
  - Gayed y Bilello (2016), *Leverage for the Long Run*, premio NAAIM Wagner — resumen en CXO Advisory:
    https://www.cxoadvisory.com/volatility-effects/leveraging-the-u-s-stock-market-based-on-sma-rules/
  - Script de TradingView "SPY 200SMA +4% Entry -3% Exit Strategy (QQQ/TQQQ)": https://de.tradingview.com/scripts/longterm/
  - QuantConnect, *Leveraged ETFs with systematic risk management*:
    https://www.quantconnect.com/learning/articles/investment-strategy-library/leveraged-etfs-with-systematic-risk-management
- **Reglas (variante de TradingView)**: con el cierre DIARIO del SPY, comprar TQQQ cuando el SPY cierra un
  4 % por encima de su media de 200 días; vender (a liquidez) cuando cierra un 3 % por debajo. Sin stop.
  Gayed y Bilello: mantener el S&P x2/x3 con el índice por encima de su media de 200 días, letras del Tesoro si no.

## Por qué no se ha cribado

Es una estrategia de **asignación diaria** (100 % invertido o 100 % en liquidez, sin stop), y el simulador
táctico dimensiona por riesgo con stop (1,5 % del capital por operación, tope del 25 % por posición): con
un stop de "catástrofe" amplio la exposición quedaría en un 5-10 % y la comparación no sería justa. El
motor diario sí sirve, pero su universo (yahoo) no incluye TQQQ/UPRO.

## Propuesta para Alejandro

Si te interesa, añadir TQQQ y UPRO (o QLD/SSO, x2) al universo diario de investigación y probar esta
regla con el validador diario (test desde 2018, que incluye 2020 y 2022). Ojo: su correlación con el
momentum en acciones que ya opera será alta (los dos ganan con el Nasdaq al alza), así que aportaría
rentabilidad pero poca diversificación. No se ha tocado ninguna configuración.
