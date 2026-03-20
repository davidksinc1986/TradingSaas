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

## Ciclo incremental 2026-03-20 — persistencia real y eliminación de contradicciones

### Hallazgos de causa raíz
- `update_connector(...)` fusionaba `config_json` sin limpiar claves incompatibles, por lo que un conector podía pasar de futures a spot conservando `futures_margin_mode`, `futures_position_mode` y `futures_leverage`. Ese residuo dejaba contradicciones silenciosas entre UI, runtime y execution guardrails.
- El frontend de conectores no enviaba valores nulos al limpiar campos opcionales durante edición, así que “borrar” parámetros era cosmético: el backend nunca recibía la intención de eliminación.
- `update_bot_session(...)` permitía cambiar `trade_amount_mode` sin normalizar los overrides excluyentes (`amount_per_trade` vs `amount_percentage`), dejando sesiones con sizing ambiguo o inválido.
- La UI de edición de sesiones automáticas no exponía los inputs de override de sizing, dificultando corregir la configuración persistida desde el dashboard.

### Correcciones aterrizadas
- Se añadió una normalización backend explícita para `config_json` de conectores: los `null` borran claves y los campos exclusivos de futures se purgan automáticamente cuando el mercado resuelto ya no es `futures`.
- Se incorporó validación determinística para overrides de sizing de `BotSession`; si el usuario elige `fixed_usd` o `balance_percent` sin el valor requerido, el backend responde con `PRECHECK_CONFIG_NOT_PERSISTED`.
- La edición de conectores ahora puede limpiar parámetros opcionales desde el frontend enviando `null` en campos vacíos durante modo edición.
- La edición de sesiones automáticas muestra y persiste `amount_per_trade` y `amount_percentage`, limpiando el campo opuesto al cambiar de modo.

### Riesgo mitigado
- Menos probabilidad de regressions donde “guardar” no guarda realmente o deja residuos invisibles.
- Menos contradicciones entre market type configurado y parámetros runtime aplicados en execution/pretrade.
- Menos sesiones automáticas con sizing ambiguo que luego bloquean ejecución o provocan rechazos difíciles de diagnosticar.
