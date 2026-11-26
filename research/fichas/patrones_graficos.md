# Ficha: patrones de gráfico con detección algorítmica (hombro-cabeza-hombro y doble techo/suelo)

*Propuesta por Alejandro, redactada el 26 nov 2026. Destino en el repositorio: `research/fichas/patrones_graficos.md`.*

## Fuente
- Lo, Mamaysky y Wang (2000), *Foundations of Technical Analysis: Computational Algorithms, Statistical Inference, and Empirical Implementation*, Journal of Finance 55(4). Define los patrones con reglas exactas sobre extremos locales de un precio suavizado. Encuentran que algunos patrones aportan información sobre el rendimiento siguiente, aunque poca (más en Nasdaq que en NYSE/AMEX).
- Osler y Chang (1995), *Head and Shoulders: Not Just a Flaky Pattern*, Federal Reserve Bank of New York Staff Report 4. Hombro-cabeza-hombro en divisas: beneficio en algunos pares antes de costes, poco fiable después.
- Referencia de practicante para objetivos y stops: Bulkowski, *Encyclopedia of Chart Patterns* (cifras sin costes; solo para las reglas de salida).

## Por qué probarla
- Familia nueva: no se ha probado nada de patrones de gráfico.
- Probablemente **poco correlacionada** con el momentum que opera ahora.
- Los patrones bajistas (hombro-cabeza-hombro, doble techo) pueden operarse con **ETFs inversos** (SH, PSQ) en índices: encaja con la prioridad de estrategias que ganen cuando el mercado baja.
- En forex intradía hacen falta ideas específicas; hay evidencia previa (Osler y Chang).

## Reglas exactas (parámetros de la fuente, sin optimizar)

**1. Extremos locales sin mirar al futuro**
- En cada vela t, ventana de las últimas **38 velas** (l = 35 + d = 3, como Lo, Mamaysky y Wang).
- Suavizado del cierre con regresión kernel gaussiana (Nadaraya-Watson) ajustada **solo con datos de la ventana**; ancho de banda = 0,3 × el de validación cruzada (como en el paper).
- Extremo local = cambio de signo de la pendiente del precio suavizado. Para cada extremo se toma el precio real máximo/mínimo en ±1 vela.
- Un patrón solo cuenta si su último extremo está entre las velas t−d y t (confirmado con d = 3 velas de retraso).

**2. Patrones** (E1…E5 = cinco extremos consecutivos)
- **Hombro-cabeza-hombro (HS, bajista):** E1 máximo; E3 > E1 y E3 > E5; E1 y E5 a menos de un 1,5 % de su media; E2 y E4 a menos de un 1,5 % de su media.
- **Hombro-cabeza-hombro invertido (IHS, alcista):** el mismo patrón en espejo (E1 mínimo; E3 < E1 y E3 < E5; mismas tolerancias).
- **Doble techo (DTOP, bajista):** E1 máximo; Ea = el máximo más alto tras E1 dentro de la ventana; E1 y Ea a menos de un 1,5 % de su media; separación entre E1 y Ea > 22 velas.
- **Doble suelo (DBOT, alcista):** el mismo patrón en espejo.

**3. Entrada (al cierre de la vela, ejecutada en la apertura de la siguiente, como el resto del sistema)**
- Línea clavicular: recta entre E2 y E4 (HS/IHS); el mínimo entre los dos techos (DTOP) o el máximo entre los dos suelos (DBOT).
- **Alcistas (IHS, DBOT):** compra cuando el cierre supera la línea clavicular, como mucho 10 velas después de confirmar el patrón.
- **Bajistas (HS, DTOP):** (a) salida de una posición larga si la hay; (b) en SPY y QQQ, compra del ETF inverso (SH, PSQ) cuando el cierre rompe la línea clavicular. Alpaca no permite cortos con fracciones.

**4. Salidas**
- Stop: por debajo de la cabeza (E3) o del suelo más bajo; si queda a más de 3 ATR, stop a 3 ATR. Tamaño por el riesgo del 1,5 % del sistema.
- Objetivo: movimiento medido = distancia entre la cabeza y la línea clavicular, proyectada desde la ruptura.
- Salida por tiempo: 20 velas.

## Mercados y horizontes a cribar
- Acciones/ETFs, datos diarios (cribado antes de 2018).
- Acciones/ETFs, velas de media sesión (cribado antes de jul-2024; regla PDT del simulador).
- Cripto, velas de 4 h y datos diarios.
- Forex, velas de 4 h (Dukascopy).

## Rejilla para la validación completa (fijada ahora, antes de ver resultados)
- Ventana: 25 / 38 / 60 velas
- Tolerancia: 1,5 % / 3 %
- Patrones: cada uno por separado y los cuatro juntos

## Riesgos a vigilar
- **Mirar al futuro:** el suavizado y la detección de extremos deben usar solo datos hasta t. Es el fallo típico de estos backtests. Añadir un test que lo compruebe (por ejemplo, que la señal en t no cambia al añadir velas posteriores).
- **Pocas operaciones:** los patrones son raros. Hay que juntar todo el universo de cada mercado para llegar a ≥ 50 operaciones en el cribado y a ≥ 100 en la validación.
- Expectativa baja: la evidencia académica habla de poca información y de beneficios que no sobreviven bien a los costes.
- Cada combinación cribada cuenta para el Sharpe deflactado.

---

## Resultado del cribado (investigador, ejecución extra del 26 nov 2026)

Programada como familia táctica `patrones_graficos` (`src/tactico/patrones.py` + `src/tactico/familias.py`), con
los parámetros de la ficha sin tocar (ventana 38, d = 3, tolerancia 1,5 %, los cuatro patrones juntos).
Tests: la señal en t no cambia al añadir velas posteriores (detector y familia completa, incluido el ETF
inverso) y un caso de hombro-cabeza-hombro invertido.

Notas de implementación (sin efecto en el veredicto):
- Mercado de investigación nuevo `acciones_inversos` = universo de acciones del sistema + SH y PSQ. Los
  patrones bajistas de SPY/QQQ compran SH/PSQ; los de los demás activos solo cierran el largo.
- El objetivo (movimiento medido) se ejecuta como salida al cierre que lo alcanza (el simulador no tiene
  órdenes de objetivo). El stop del inverso se traslada en % desde la cabeza del índice (tope 3 ATR del inverso).
- Observación: en velas de 4 h el ancho de banda de validación cruzada sale casi siempre en el mínimo
  (0,5 velas), así que 0,3 × ese ancho apenas suaviza y los extremos son los del cierre real. Los patrones
  salen pequeños y frecuentes (muchas operaciones, objetivos cortos). Es lo que da la regla del paper.

| Mercado (velas) | Periodo | Sharpe | Rentab. anual | Peor caída | Operaciones | Sharpe sin costes | Correlación con lo que opera | Veredicto |
|---|---|---|---|---|---|---|---|---|
| Acciones + SH/PSQ (media sesión) | 2020-10 a 2024-06 | 0,04 | −0,3 % | −25 % | 1.036 | 0,52 | 0,54 | ❌ |
| Cripto (4 h) | 2021-01 a 2024-06 | −0,81 | −24,7 % | −69 % | 1.426 | 0,83 | 0,05 | ❌ |
| Forex (4 h) | 2016-02 a 2024-06 | −0,65 | −2,2 % | −21 % | 3.915 | 0,41 | 0,13 | ❌ |

- Como dice el paper, los patrones tienen algo de información (Sharpe positivo sin costes en los tres
  mercados, 0,83 en cripto), pero no sobrevive a los costes: operaciones muy cortas (0,8 días de media en
  cripto) con un resultado medio por operación menor que el coste de ida y vuelta.
- Los ETFs inversos por patrones bajistas de SPY/QQQ: 59 operaciones, resultado medio −0,31 % (−0,21 % sin
  costes). No aportan.
- **No cribados**: acciones y cripto con datos diarios. El motor diario trabaja con pesos de cartera, sin
  stops ni objetivos por operación, así que haría falta adaptar la familia; y el presupuesto de la semana
  (10 cribados) no da para todo. Se puede proponer otra semana si Alejandro quiere.

**Resultado: rechazada en los tres mercados.** No pasa a validación completa (la rejilla de la ficha no se
ha llegado a usar). No se reajusta nada a la vista de estos resultados.
