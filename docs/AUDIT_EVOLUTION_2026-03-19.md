# Auditoría total + evolución ejecutada

## Diagnóstico clave

### Arquitectura
- El repo concentra responsabilidades críticas en `app/services/trading.py`: selección de símbolos, mercado, sizing, ejecución, persistencia, alertas y lifecycle viven en el mismo flujo. Eso elevaba acoplamiento y dificultaba pruebas o cambios de exchange.
- Existía duplicidad parcial entre `app/services/trading.py` y `app/services/connectors.py`, señal de evolución orgánica sin consolidación total del execution layer.
- El data layer dependía de fallback sintético, pero sin un radar explícito de degradación ni caché central para proteger latencia y sobreconsumo.

### Riesgo cuantitativo
- El sizing previo dependía casi solo de `position_size(...)` y del presupuesto fijo del usuario. Faltaban límites explícitos de heat de portafolio, concentración por símbolo, drawdown operativo y visibilidad de kill switch.
- El dashboard mostraba PnL y actividad, pero no priorizaba exposición abierta, drawdown rodante ni calidad de datos.

### Mercado y ejecución
- Se usaban datos sintéticos como fallback útil para resiliencia, pero sin clasificar anomalías de OHLCV ni bloquear live trading cuando la calidad de datos se degradaba.
- Faltaba una capa que convirtiera salud de mercado + riesgo de portafolio en una decisión previa de ejecución.

## Problemas críticos priorizados
1. **Riesgo financiero**: posibilidad de operar live con mercado degradado o con exposición agregada poco visible.
2. **Escalabilidad lógica**: el flujo de trading central mezclaba demasiadas responsabilidades.
3. **UX operacional**: el usuario no veía el riesgo en menos de 3 segundos.
4. **Observabilidad táctica**: no existía un resumen de salud cuantitativa del portafolio a nivel dashboard.

## Refactor evolutivo implementado

### 1) Nuevo risk engine táctico
Se añadió `app/services/risk_engine.py` con:
- `RiskGuardrails` para límites configurables.
- `build_trade_risk_plan(...)` para validar tamaño, heat, concentración y calidad de mercado antes de ejecutar.
- `summarize_portfolio_risk(...)` para producir un radar operacional del portafolio.

### 2) Data engine endurecido
Se evolucionó `app/services/market.py` con:
- caché TTL en memoria para OHLCV;
- detección de anomalías (`detect_market_anomalies`);
- enriquecimiento de `meta` con `health`, `anomalies` y `cache`;
- bloqueo semántico posterior en trading cuando live usa fallback sintético o anomalías severas.

### 3) Trading engine con predecisión cuantitativa
`run_strategy(...)` ahora:
- evalúa exposición abierta y riesgo abierto actual por conector;
- crea un `risk_plan` antes del `pretrade_validate` del exchange;
- rechaza o recorta cantidad cuando hay exceso de heat, concentración o mercado degradado;
- persiste el plan de riesgo en notas/logs para auditoría posterior.

### 4) UX operativa mejorada
El dashboard incorpora un **Risk Radar** con:
- health score;
- open risk estimado;
- drawdown rodante;
- estado de kill switch;
- alertas y sugerencias accionables.

## Próximas fases recomendadas
1. Extraer execution orchestration de `trading.py` a un `execution_engine.py` dedicado.
2. Unificar definitivamente los clients legacy de `trading.py` con `connectors.py`.
3. Persistir métricas/telemetría estructurada por run en tablas dedicadas.
4. Añadir backtesting/forward testing formal con datasets persistidos.
5. Crear control global de riesgo para admin multiusuario (límites por tenant, exchange y market type).
