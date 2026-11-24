# Guía del agente investigador

Sesión semanal (sábados) de Claude que busca, implementa y prueba estrategias nuevas.
Esta guía es la fuente de verdad de cómo trabaja; la tarea programada solo apunta aquí.

## Objetivo

Encontrar cada semana ideas nuevas (de cualquier fuente, académica o no) que puedan mejorar lo que ya opera:
hasta 10 se criban rápido y como mucho 3 pasan a la validación completa.
Alejandro quiere **crecer el capital de forma agresiva** mientras la cartera total sea < 5.000 € (fase
agresiva: 70 % táctico / 30 % estructural, con 100 €/mes de aportación). Por eso:

- **El listón es el SPY.** El validador exige batir a comprar y mantener SPY en el periodo de test (más
  rentabilidad, o un Sharpe al menos 0,2 mejor). En la fase agresiva lo que interesa es la **rentabilidad**:
  una idea con mucho Sharpe pero poca rentabilidad (tipo 5-6 % anual) no sirve ahora.
- Caída máxima aceptable en torno al 25-30 %; más que eso no es agresivo, es temerario.

Prioridad actual:

1. **Táctico agresivo que bata al SPY**: momentum / ruptura de baja rotación aplicados a activos más
   volátiles (ETFs apalancados como TQQQ/SOXL/UPRO con filtro de tendencia, acciones pequeñas, sectores
   fuertes), rotación de momentum entre sectores o acciones, y cripto en velas de 4 h o diarias. Pocas
   operaciones, mucho recorrido por operación y entradas a favor de la tendencia diaria (con velas de 1 hora
   los costes se comen la ventaja: ver `reports/laboratorio/tactico.md`).
   Los activos que no opera el sistema pero quieras investigar van en `config/investigacion.yaml` (SÍ puedes
   editarlo): el escáner horario descarga sus velas y en el laboratorio se cargan con
   `laboratorio.ohlc_mercado("acciones", extra=True)`. Ya incluye ETFs x3 (TQQQ, UPRO, SOXL, TECL, TNA).
   Para probar una familia táctica SOLO en esos activos hay un mercado de investigación:
   `laboratorio.experimento("<familia>", "apalancados")` (velas, costes y norma PDT de acciones). Valídalo con
   `validator.validar(exp, None, {})`, regístralo con `registro.registrar([v], origen="investigador")` y
   anota el resultado en la ficha. El laboratorio semanal no lo prueba solo: cada prueba sube el listón
   del Sharpe deflactado, así que pruébalo cuando tenga una justificación.
   Ojo: un símbolo recién añadido tarda una ejecución del escáner en tener datos; si aún no los tiene,
   lanza el workflow `tactico.yml` y prueba la idea la semana siguiente.
2. **Mejorar la parte cripto del estructural** (tendencia con control de volatilidad, la única estrategia
   aprobada): variantes publicadas, más monedas, señales on-chain o de financiación si hay datos gratuitos.
3. **Datos institucionales** ya descargados: COT (`data/institucional/cot.csv`), tipos de interés
   (`data/macro/tipos_3m.csv`) y, si existe, compras de directivos.
4. **Forex intradía** (mercado táctico `forex`, datos horarios de Dukascopy desde 2016): hay muchísimas
   estrategias públicas (sesiones de Londres/Nueva York, rupturas del rango asiático, cruces de medias,
   reversión en niveles...). Solo investigación y simulación: Alpaca no opera divisas, así que una
   estrategia de forex aprobada solo daría alertas. Ojo: sin apalancamiento el forex rinde poco (los pares
   se mueven ~0,5 % al día); una buena estrategia de forex se reconoce por el **Sharpe**, no por la
   rentabilidad sin apalancar. Para añadir pares: `config/investigacion.yaml` -> `forex`, y lanzar el
   workflow `forex.yml`.
5. Bonos, solo si aparece algo con rentabilidad suficiente.

## Fuentes

Cualquier fuente vale **si la idea se puede convertir en reglas exactas** (entrada, salida, stop, tamaño,
marco temporal). Lo que no se pueda programar sin interpretación ("price action", "zonas de liquidez",
patrones dibujados a ojo) se descarta. Lo que decide es el validador, no la fuente.

- **Académicas**: SSRN, arXiv (q-fin), revistas (JFE, RFS, JF, JPM, FAJ), Quantpedia, Alpha Architect.
- **YouTube**: no puedes ver vídeos, pero sí buscar transcripciones y resúmenes en la web (WebSearch:
  `"<título del vídeo>" transcript`, sitios de resúmenes) y recopilaciones de la comunidad (p. ej. hojas
  de cálculo públicas con estrategias de YouTube "probadas en 100 operaciones"). Ojo: casi siempre son
  muestras cortas y elegidas a dedo; espera muy pocos aprobados.
- **TradingView**: listas de scripts y estrategias (`tradingview.com/scripts/...`) y sus descripciones;
  los de código abierto suelen describir la fórmula.
- **Blogs y webs de estrategias probadas**: Quantified Strategies, Robot Wealth, QuantConnect (foro y
  estrategias de la comunidad), Medium/dev.to/Substack de trading cuantitativo, repositorios de GitHub.
- **Foros públicos** (Forex Factory, BabyPips, Elite Trader) si se pueden leer sin iniciar sesión.
- **No accesibles** desde tu entorno: X/Twitter y Reddit bloquean el acceso automático. No insistas.

En la ficha apunta siempre la fuente y el enlace.

## Procedimiento (embudo)

1. **Leer el estado** (sin gastar de más):
   - `reports/laboratorio/ultimo.md` y `reports/laboratorio/tactico.md`
   - `reports/auditor/ultimo.md`
   - `research/registro_pruebas.csv` y `research/cribado.csv` (qué se ha probado ya; no repetir ideas)
   - `research/fichas/` (fichas de semanas anteriores)
2. **Buscar ideas** en las fuentes de arriba, con prioridad en lo que pide el objetivo.
3. **Cribado rápido (hasta 10 ideas por semana)**. Para cada idea:
   - Escribe una ficha corta en `research/fichas/AAAA-MM-DD-<id>.md`: reglas exactas, mercado, marco
     temporal, fuente y enlace, y los parámetros TAL CUAL los da la fuente (no los optimices).
   - Si una familia existente ya la cubre con otros parámetros, no programes nada: usa `--param`.
     Si no, prográmala como familia nueva (ver paso 5) con un test mínimo.
   - Cribado: `python3 scripts/cribar.py tactico|diario <familia> <mercado> --idea "<id>" --fuente "..." --url "..." [--param clave=valor]`
     Usa solo datos ANTERIORES al periodo de test (táctico: antes de jul-2024; diario: antes de 2018),
     así el test queda intacto para la validación final. Criterios: Sharpe ≥ 0,5, rentabilidad > 0, caída
     ≤ 35 % y, en táctico, ≥ 50 operaciones. Cada idea cribada cuenta como una prueba para el Sharpe
     deflactado (crece despacio; es lo honesto).
   - Mercados tácticos: `cripto`, `acciones`, `apalancados` (ETFs x3 de `config/investigacion.yaml`) y
     `forex` (10 pares de Dukascopy, velas de 1 hora desde 2016, agregadas a 4 h en las familias de 4 h).
4. **Validación completa (máximo 3 por semana)** solo de las que pasen el cribado:
   - Fija en la ficha la rejilla de parámetros ANTES de ejecutar (3 variantes como máximo, con el
     parámetro de la fuente en el centro).
   - Si la familia es nueva, añádela a la rejilla de su familia y ejecuta el laboratorio:
     `python3 scripts/run_lab.py --sin-telegram` y/o `python3 scripts/run_lab_tactico.py --sin-telegram`.
     Para el mercado `apalancados`: `laboratorio.experimento("<familia>", "apalancados")`,
     `validator.validar(exp, None, {})` y `registro.registrar([v], origen="investigador")`.
5. **Programar una familia**:
   - Diaria: en `src/research/familias.py` (función + entrada en `FAMILIAS`). Campo `"mercados"` si solo
     tiene sentido en algunos.
   - Táctica: en `src/tactico/familias.py` (función + entrada en `FAMILIAS_TACTICAS`, con `"velas": "4h"`
     si usa velas de 4 h / media sesión). Puede usar `limite` (orden limitada), `dinamico` (stop dinámico)
     y `max_velas`. Si una familia nueva solo tiene sentido en un mercado, que el laboratorio no la pruebe
     en los demás.
   - Mejor familias **genéricas** con parámetros (p. ej. "cruce de medias + filtro RSI") que una por vídeo:
     así muchas ideas futuras se criban solo cambiando parámetros.
   - Código comentado en español y sencillo. Añade un test en `tests/` y ejecuta `python3 -m pytest -q`.
6. **Anotar el resultado en la ficha** (cribado y, si llegó, validación: veredicto, Sharpe, rentabilidad
   frente al SPY, peor caída, qué falla) sin reajustar parámetros a la vista de los resultados.
7. **Subir** los cambios a `main` con un commit descriptivo (incluye `research/cribado.csv`).
8. **Avisar a Alejandro** lanzando el workflow de notificación:
    `gh api -X POST repos/Alejandroacpt/trading-agents/actions/workflows/notificar.yml/dispatches -f ref=main -f "inputs[mensaje]=<resumen>"`
    Resumen breve: cuántas ideas cribadas (y de qué fuentes), cuáles pasaron, veredicto de las validadas
    y si hay algo que proponer.

## Reglas que no se rompen

- **Nunca** modificar `config/sistema.yaml` ni `config/tactico.yaml` (lo que opera): solo proponer.
- **Nunca** cambiar los umbrales del validador o del cribado ni borrar filas de `research/registro_pruebas.csv` o `research/cribado.csv`.
- **Nunca** ajustar parámetros después de ver resultados para que una estrategia apruebe. Si una idea falla,
  se anota y se pasa a otra.
- Si algo del sistema está roto (tests que fallan, datos sin actualizar), arreglarlo tiene prioridad sobre
  investigar, y se menciona en el aviso.
- Sesión acotada: como máximo 10 ideas cribadas y 3 validaciones completas por semana (el presupuesto de IA es limitado).
