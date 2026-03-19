# Rediseño integral de producto, UX y arquitectura funcional

## 1. North Star del producto

**Posicionamiento:** plataforma multi-exchange para operar bots y estrategias con máxima claridad operativa, control de riesgo visible y administración centralizada.

**Resultado esperado en 3 segundos:**
- cuánto capital tiene el usuario
- cuánto gana o pierde hoy
- cuántos bots están activos
- si existe algún riesgo crítico
- qué acción debe tomar ahora

**Principios operativos obligatorios:**
1. **Una decisión principal por pantalla.**
2. **Toda acción crítica debe mostrar impacto y riesgo antes de confirmar.**
3. **Toda configuración compleja debe explicarse en lenguaje simple.**
4. **Todo comportamiento configurable debe venir del backend/admin.**
5. **Toda integración nueva debe conectarse como adapter, no como excepción.**

---

## 2. Identidad visual lista para implementar

### Paleta base
- `bg-primary`: `#050505` → fondo general
- `bg-surface`: `#111111` → cards base
- `bg-elevated`: `#1A1A1A` → contenedores destacados
- `border-subtle`: `#2A2A2A`
- `text-primary`: `#F5F5F5`
- `text-secondary`: `#B8B8B8`
- `accent-action`: `#F0B90B`
- `accent-action-pressed`: `#DDA800`
- `success`: `#22C55E`
- `danger`: `#EF4444`
- `warning`: `#F59E0B`
- `info`: `#38BDF8`

### Reglas de uso visual
- Fondo casi negro siempre, evitando gradientes fuertes fuera de hero/admin summary.
- Amarillo reservado para CTA, estados de foco, tabs activas y alertas accionables.
- Verde y rojo solo para PnL, riesgo, drawdown, estados de orden y salud de bots.
- Nada de más de **1 CTA primario amarillo por viewport móvil**.
- Cards con radio 16-20px, sombra suave y borde visible para separación sin ruido.

### Tipografía y espaciado
- Headings: `Space Grotesk` o equivalente geométrica.
- UI / labels / tablas: `Inter`.
- Escala móvil:
  - H1: 28
  - H2: 22
  - H3: 18
  - body: 14/16
  - caption: 12
- Grid base: múltiplos de 4.
- Espaciado entre bloques principales: 16-20px móvil.

### Componentes visuales obligatorios
- `Primary CTA` amarillo.
- `Secondary CTA` ghost con borde gris.
- `Danger CTA` rojo solo para kill switch, cierre forzado y bloqueo.
- `Risk badge`: low / medium / high / critical.
- `PnL pill`: positivo verde, negativo rojo, neutro gris.
- `Status chip`: active, paused, syncing, error, blocked.

---

## 3. Estructura final de la app principal (mobile first)

## Navegación inferior
1. **Dashboard**
2. **Bots**
3. **Estrategias**
4. **Actividad**
5. **Perfil**

### Reglas de navegación
- Bottom nav fija, área táctil mínima 48px.
- FAB opcional en Dashboard/Bots: `+ Crear bot`.
- Acciones críticas accesibles en máximo 2 taps:
  - crear bot
  - pausar bot
  - ver error
  - activar/desactivar kill switch personal

### Soporte multilenguaje (obligatorio)
- Idiomas soportados desde lanzamiento: **español, inglés, francés y portugués**.
- El idioma inicial debe detectarse automáticamente según el idioma del dispositivo/navegador.
- El usuario puede cambiar manualmente el idioma desde Perfil, pero el modo por defecto es `Automático`.
- Orden de resolución de idioma:
  1. preferencia manual del usuario
  2. preferencia guardada en cookie/sesión
  3. idioma del dispositivo (`Accept-Language` / `navigator.languages`)
  4. fallback a español
- Todo texto visible, ayudas, validaciones, tooltips, errores y reportes exportables debe venir de catálogos de traducción y no quedar hardcodeado en componentes.

### Arquitectura de información por tab

#### Dashboard
**Objetivo:** resumen instantáneo y acciones de control.

**Orden móvil:**
1. Hero de balance total + PnL hoy
2. Alertas críticas
3. Posiciones abiertas
4. Bots activos
5. Rendimiento rápido
6. Acciones rápidas

#### Bots
**Objetivo:** operar bots sin entrar a pantallas profundas.

**Orden móvil:**
1. Filtros sticky
2. Lista de bots por cards
3. CTA crear bot
4. Drawer de acciones rápidas

#### Estrategias
**Objetivo:** elegir, comparar y editar lógica operativa.

**Orden móvil:**
1. Buscador + filtros
2. Estrategias favoritas/recomendadas
3. Cards con rendimiento y riesgo
4. Editor por bloques

#### Actividad
**Objetivo:** ver solo eventos relevantes.

**Orden móvil:**
1. Filtros rápidos
2. Timeline de eventos
3. Eventos críticos fijados arriba
4. CTA a detalle si hace falta

#### Perfil
**Objetivo:** seguridad, conexiones y preferencias globales.

**Orden móvil:**
1. Estado de cuenta
2. Exchanges conectados
3. API keys / credenciales
4. Config global de riesgo
5. Seguridad y sesiones

---

## 4. Diseño de cada sección del usuario

## A. Dashboard

### Layout móvil
1. **Resumen financiero principal**
   - Balance total
   - PnL hoy
   - PnL total
   - Exposure actual
2. **Alert strip**
   - error de exchange
   - bot detenido
   - riesgo alto
3. **Open positions snapshot**
4. **Bots activos**
5. **Acciones rápidas**
6. **Actividad reciente relevante**

### Componentes
- `PortfolioHeroCard`
- `AlertCarousel`
- `OpenPositionsMiniTable`
- `BotHealthCard`
- `KillSwitchCard`
- `QuickActionsSheet`

### Jerarquía visual
- Arriba del fold: balance, pnl, alertas, kill switch.
- Abajo del fold: rendimiento por bot y actividad.

### Acciones rápidas
- `STOP TODO`
- `Crear bot`
- `Ver posiciones`
- `Pausar bots en error`

### Diseño concreto
- Hero card de 2 niveles:
  - nivel 1: balance + pnl
  - nivel 2: exposición, posiciones, bots activos
- El botón `STOP TODO` debe ser rojo, ancho completo y siempre visible en dashboard.
- Si hay alertas críticas, el kill switch sube encima del resto.

---

## B. Bots (Apps)

### Layout móvil
1. Header con total de bots + filtros
2. Segment control:
   - todos
   - activos
   - pausados
   - error
3. Lista vertical de bot cards
4. CTA fijo `+ Crear bot`

### Card de bot
- Nombre del bot
- Exchange + mercado
- Símbolos (máx. 3 visibles + `+N`)
- Estado
- PnL hoy
- Riesgo configurado
- Última ejecución
- Próxima ejecución

### Acciones por card
- Toggle activar/pausar
- `Editar`
- `Detalle`
- `Duplicar`
- `Cerrar posiciones`

### Jerarquía visual
- Nombre + estado arriba
- PnL y riesgo al centro
- Acciones abajo en sticky action row

### Quick detail drawer
Al tocar la card:
- resumen del bot
- razones de error si existen
- riesgo actual
- posiciones ligadas
- logs recientes

---

## C. Estrategias

### Layout móvil
1. Buscador
2. Filtros por tipo, exchange compatible, riesgo, estado
3. Cards de estrategia
4. Editor por acordeones

### Card de estrategia
- nombre
- tipo: tendencia / reversión / breakout / grid / scalping / discretionary-assist
- exchanges compatibles
- win rate
- drawdown
- retorno estimado histórico
- nivel de riesgo

### Editor estructurado en 4 bloques
1. **Entrada**
   - señales de entrada
   - confirmaciones
   - timeframe
2. **Salida**
   - take profit
   - stop loss
   - trailing
   - cierre por señal
3. **Riesgo**
   - riesgo por trade
   - posiciones máximas
   - exposición total
4. **Mercado**
   - spot / futures / forex / cfd
   - apalancamiento permitido
   - símbolos válidos

### Reglas UX
- Cada bloque muestra resumen comprimido cuando está colapsado.
- Cada parámetro debe tener:
  - nombre
  - descripción simple
  - ejemplo
  - sugerencia recomendada
- Debe haber `Preview del perfil de riesgo` en tiempo real.

---

## D. Actividad

### Layout móvil
1. Filtros sticky de 1 línea
2. Timeline agrupada por fecha
3. Eventos destacados arriba

### Tipos de eventos visibles
- trade ejecutado
- orden rechazada
- bot pausado
- stop loss activado
- cierre manual
- error de conexión
- sync completado

### Filtros simples
- Bot
- Símbolo
- Resultado
- Exchange
- Tipo de evento

### Regla de diseño
- Nunca mostrar logs crudos primero.
- Priorizar lenguaje humano:
  - “Bot Alpha pausado por error de autenticación en Binance.”
  - “Take profit ejecutado en BTCUSDT con +2.1%.”

---

## E. Perfil

### Layout móvil
1. Estado general de cuenta
2. Exchanges conectados
3. Seguridad
4. Configuraciones globales
5. Notificaciones

### Bloques
- `ConnectedExchangesList`
- `CredentialVaultStatus`
- `GlobalRiskPreferences`
- `NotificationChannels`
- `SecurityCenter`

### Acciones críticas
- conectar exchange
- regenerar API credenciales internas
- cambiar 2FA
- cerrar sesiones
- desactivar trading live

### Preferencias de idioma en Perfil
- selector `Idioma de la app` con opciones: `Automático`, `Español`, `English`, `Français`, `Português`
- subtítulo visible: `Automático usa el idioma configurado en tu dispositivo`
- vista previa del idioma efectivo detectado
- canal de alertas y emails transaccionales deben heredar el mismo idioma, salvo override explícito

---

## 5. Flujos completos listos para implementar

## A. Flujo Crear Bot

### Paso 1: Elegir exchange
- Lista de exchanges compatibles con badge de salud.
- Mostrar mercado permitido: spot, futures, forex/cfd.
- Si exchange está degradado, mostrar warning y permitir continuar solo si admin lo habilita.

**Microcopy:**
- Título: `Elige dónde operará tu bot`
- Ayuda: `Puedes conectar más exchanges después. Aquí defines el entorno principal de ejecución.`

### Paso 2: Elegir estrategia
- Lista de estrategias filtradas por exchange/mercado.
- Cada estrategia muestra riesgo, retorno histórico, drawdown y complejidad.
- CTA: `Usar recomendada`.

### Paso 3: Configurar riesgo
- Riesgo por trade
- máximo de posiciones
- stop loss
- take profit
- trailing stop
- exposición máxima por exchange

**Panel lateral/resumen sticky móvil:**
- bot name
- exchange
- estrategia
- riesgo total estimado

### Paso 4: Selección de símbolos
Opciones excluyentes:
- `Usar símbolos automáticos`
- `Seleccionar manualmente`

Si automático:
- mostrar origen del scanner
- cantidad máxima de símbolos
- reglas: volumen, volatilidad, spread

Si manual:
- multi-select
- favoritos
- recientes
- búsqueda

### Paso 5: Confirmación
Resumen completo:
- exchange
- estrategia
- riesgo
- símbolos
- modo paper/live
- validaciones finales

**Confirmación obligatoria:**
`Entiendo que este bot operará bajo los límites de riesgo configurados.`

### Paso 6: Resultado
- Estado: creado / creado y pausado / error de validación
- CTA siguientes:
  - activar ahora
  - revisar configuración
  - crear otro bot

---

## B. Flujo Editar Estrategia

1. Abrir estrategia
2. Editar por bloques (`Entrada`, `Salida`, `Riesgo`, `Mercado`)
3. Validación inline inmediata
4. Preview de impacto
5. Guardar como:
   - actualizar actual
   - duplicar como nueva
   - guardar como borrador

### Validaciones UX
- Error debajo del campo, no arriba del formulario.
- Si el cambio rompe reglas globales, mostrar:
  - qué regla falla
  - cuál es el límite admin
  - cómo corregirlo

### Preview simple
- riesgo estimado
- frecuencia esperada
- mercados compatibles
- capital mínimo sugerido

---

## C. Flujo Activar Bot

1. CTA `Activar`
2. Modal de resumen final
3. Mostrar:
   - exchange
   - modo paper/live
   - estrategia
   - símbolos
   - riesgo por trade
   - stop loss
   - exposición máxima
4. Confirmación explícita
5. Estado final:
   - activo
   - activo con warnings
   - bloqueado por política

---

## 6. Admin panel completo

## Mapa principal del admin
1. **Dashboard**
2. **Usuarios**
3. **Exchanges**
4. **Configuración dinámica**
5. **Estrategias**
6. **Bots & posiciones**
7. **Logs & errores**
8. **Reportes**
9. **Control crítico**

### A. Dashboard admin

#### KPIs arriba del fold
- usuarios activos hoy
- bots activos
- volumen operado 24h
- errores críticos abiertos
- posiciones abiertas globales
- exchanges degradados

#### Widgets
- `SystemHealthCard`
- `ExchangeStatusBoard`
- `ActiveRiskHeatmap`
- `UsersAtRiskList`
- `CriticalErrorsQueue`

#### Acciones rápidas
- bloquear exchange
- desactivar estrategia global
- cerrar posiciones huérfanas
- abrir kill switch global

---

### B. Gestión de usuarios

#### Vista lista
- nombre
- email
- rol
- estado
- bots activos
- exchanges conectados
- PnL 30d
- riesgo actual

#### Vista detalle usuario
- perfil
- seguridad
- límites
- bots
- estrategias permitidas
- eventos críticos
- auditoría

#### Acciones admin
- activar/bloquear usuario
- reset credenciales
- reset 2FA
- cambiar plan/rol
- imponer límite de riesgo
- deshabilitar trading live

---

### C. Gestión de exchanges

#### Lista por exchange/adaptador
- Binance
- Bybit
- MetaTrader / FXCM bridge
- futuros exchanges

#### Para cada uno mostrar
- estado API
- latencia
- error rate
- rate limit usage
- instrumentos disponibles
- mercados soportados
- últimas incidencias

#### Acciones
- habilitar/deshabilitar exchange
- modo maintenance
- restringir live
- actualizar límites
- definir compatibilidades

---

### D. Configuraciones dinámicas

#### Qué puede hacer el admin
- crear campos configurables
- agruparlos por módulo
- definir tipo de input
- definir default
- definir validaciones
- definir ayuda contextual
- activar/desactivar features
- decidir visibilidad por exchange/mercado/rol/estrategia

#### Control multilenguaje desde admin
- mantener catálogo de traducciones por clave (`es`, `en`, `fr`, `pt`)
- detectar claves faltantes antes de publicar cambios
- permitir preview por idioma en user app y admin
- versionar copy, ayudas, ejemplos y mensajes críticos
- bloquear publicación de configuraciones nuevas si falta traducción obligatoria

#### Módulos sugeridos
- bot creation
- strategy editor
- global risk
- exchange specific
- reporting
- notifications

#### UI admin recomendada
- tabla de definiciones
- panel lateral de edición
- preview live de cómo se verá en la app del usuario
- historial de cambios y rollback

---

### E. Estrategias admin

#### Funciones
- crear estrategia base
- editar definición de parámetros
- activar/desactivar
- versionar
- asignar compatibilidad por exchange/mercado
- etiquetar riesgo y complejidad

#### Vista de estrategia admin
- metadata
- parámetros dinámicos
- reglas de validación
- defaults
- copy UX para usuarios
- métricas históricas si existen

---

### F. Monitoreo de posiciones

#### Tabla global
- usuario
- bot
- exchange
- símbolo
- lado
- tamaño
- PnL
- stop actual
- estado sync
- orphan flag

#### Acciones
- cerrar posición
- reintentar sync
- reasignar al bot origen
- marcar como revisada

#### Detección de huérfanas
Una posición es huérfana si:
- existe en exchange pero no en DB
- existe en DB pero no en exchange
- bot origen ya no existe
- ejecución falló y quedó sin lifecycle completo

---

### G. Logs y errores

#### Vistas
- sistema
- exchange
- órdenes
- riesgo
- autenticación
- webhooks

#### Reglas UX
- separar `warning`, `error`, `critical`
- permitir abrir el contexto del error
- mostrar impacto:
  - cuántos usuarios
  - cuántos bots
  - cuántas posiciones

#### Acciones rápidas
- reintentar
- silenciar temporalmente
- escalar
- abrir incidente

---

### H. Kill switch global

#### Requisitos
- botón rojo fijo en `Control crítico`
- confirmación en 2 pasos
- texto obligatorio: `CERRAR TODO`
- registra auditoría completa
- ejecuta por exchange adapter y devuelve progreso

#### Estados
- pending
- running
- partial
- completed
- failed

---

## 7. Sistema de configuraciones dinámicas

## Objetivo
Eliminar formularios hardcodeados y permitir que admin controle:
- qué campos existen
- cuándo aparecen
- qué valores aceptan
- qué defaults tienen
- cómo se explican

## Modelo funcional recomendado

### Entidades
1. `config_definitions`
2. `config_option_sets`
3. `config_defaults`
4. `feature_flags`
5. `exchange_capabilities`
6. `strategy_blueprints`
7. `risk_policies`
8. `audit_events`

### Estructura mínima de `config_definitions`
- `key`
- `label`
- `description`
- `help_example`
- `recommended_value`
- `i18n_key`
- `translations` (`es`, `en`, `fr`, `pt`)
- `input_type`
- `scope` (`global`, `exchange`, `market`, `strategy`, `role`)
- `default_value`
- `validation_rules`
- `visibility_rules`
- `dependency_rules`
- `is_required`
- `is_active`
- `sort_order`

### Tipos de input soportados
- text
- number
- percent
- boolean
- single_select
- multi_select
- radio_group
- risk_slider
- symbol_selector
- schedule_window
- json_advanced

### Ejemplo concreto: selector de símbolos

```json
{
  "key": "symbol_selection_mode",
  "label": "Selección de símbolos",
  "input_type": "radio_group",
  "default_value": "auto",
  "options": [
    {"value": "auto", "label": "Usar símbolos automáticos"},
    {"value": "manual", "label": "Seleccionar manualmente"}
  ],
  "dependency_rules": [
    {
      "when": {"equals": "manual"},
      "show": ["manual_symbols"]
    }
  ],
  "visibility_rules": {
    "markets": ["spot", "futures", "forex"]
  }
}
```

### Renderizado UX esperado
- radio inicial
- si elige `manual`, aparece multi-select con búsqueda
- si elige `auto`, aparece explicación del scanner y número de símbolos permitidos

### Validaciones backend obligatorias
- schema validation
- reglas por exchange
- reglas por mercado
- reglas por estrategia
- límites globales admin
- límites del plan del usuario

### Orden de evaluación
1. feature flags globales
2. capacidad del exchange
3. restricciones del plan
4. límites de riesgo
5. dependencia entre campos
6. validación final del payload

---

## 8. UX guiado: formato estándar por campo

Todo campo configurable debe tener 4 piezas:
1. nombre
2. explicación simple
3. ejemplo real
4. sugerencia recomendada

### Ejemplo 1: Stop Loss (%)
- **Descripción:** `Porcentaje máximo de pérdida antes de cerrar la posición.`
- **Ejemplo:** `Si entras en 100 USD y configuras 2%, la posición se cerrará cerca de 98 USD.`
- **Sugerencia:** `Recomendado entre 1% y 3% para perfiles conservadores/moderados.`

### Ejemplo 2: Máximo de posiciones abiertas
- **Descripción:** `Límite de posiciones simultáneas que puede mantener este bot.`
- **Ejemplo:** `Si defines 3, el bot no abrirá una cuarta posición aunque detecte otra señal.`
- **Sugerencia:** `Recomendado entre 1 y 5 para mantener control de exposición.`

### Ejemplo 3: Selección automática de símbolos
- **Descripción:** `El sistema elegirá símbolos usando reglas de volumen, volatilidad y liquidez.`
- **Ejemplo:** `Puede seleccionar BTCUSDT, ETHUSDT y SOLUSDT si cumplen tus filtros.`
- **Sugerencia:** `Úsalo si prefieres velocidad y no quieres revisar manualmente cada mercado.`

### Patrón de ayuda visual
- ícono info en línea
- tooltip corto
- drawer de ejemplo al tocar `Ver ejemplo`
- nunca usar texto técnico sin traducción humana

---

## 9. Arquitectura funcional escalable

## Capas

### 1. Experience layer
- app usuario mobile-first
- admin panel desktop-first pero responsive
- sistema de diseño compartido
- locale manager central con modo `auto` basado en idioma del dispositivo

### 2. API / BFF layer
- endpoints separados por dominio:
  - auth
  - portfolio
  - bots
  - strategies
  - activity
  - admin
  - reports
  - config

### 3. Domain services
- `BotOrchestrator`
- `StrategyEngine`
- `RiskEngine`
- `ExecutionRouter`
- `PositionLifecycleService`
- `ActivityFeedService`
- `DynamicConfigService`
- `ReportingService`
- `AdminCommandService`

### 4. Exchange adapter layer
Contrato estándar para Binance, Bybit, MetaTrader/FXCM y futuros exchanges:
- `health_check()`
- `fetch_balance()`
- `fetch_positions()`
- `fetch_orders()`
- `place_order()`
- `cancel_order()`
- `close_position()`
- `sync_symbols()`
- `capabilities()`

### 5. Eventing / observabilidad
- auditoría de acciones
- event bus para errores, fills, sync, alerts
- métricas por exchange, bot y usuario

### 6. Data layer
- OLTP principal para operación
- tablas de eventos/auditoría
- snapshots de pnl/portfolio
- vistas agregadas para reportes

## Dominios funcionales recomendados
- `Identity & Access`
- `Exchange Connectivity`
- `Portfolio & Positions`
- `Bots & Automation`
- `Strategies & Templates`
- `Risk & Guardrails`
- `Dynamic Configuration`
- `Reporting & Analytics`
- `Notifications & Incidents`
- `Admin Governance`

---

## 10. Reportes reales y accionables

### Reportes usuario/admin
1. PnL por usuario
2. PnL por bot
3. PnL por estrategia
4. Drawdown por periodo
5. Win rate
6. Profit factor
7. Volumen operado
8. Exposición por exchange
9. Errores por exchange
10. Bots con más incidencias

### Diseño de reportes
- filtros por rango de fecha
- export CSV
- comparación vs periodo anterior
- segmentación por exchange, mercado, estrategia, usuario

### KPIs prioritarios
- `PnL neto`
- `Max drawdown`
- `Sharpe-like simplified score` opcional
- `Win rate`
- `Average loss`
- `Average win`
- `Open risk`

### Reglas multilenguaje para reportes
- exportaciones CSV/PDF usan el idioma efectivo del usuario o el idioma seleccionado manualmente
- admin puede forzar idioma al generar reportes compartidos
- etiquetas, leyendas y estados deben salir del mismo catálogo i18n

---

## 11. Reglas de diseño para todo el producto

1. **Cada pantalla debe responder una sola pregunta principal.**
2. **No mostrar más de 5 bloques principales en el primer viewport móvil.**
3. **Toda métrica financiera debe indicar periodo.**
4. **Toda acción destructiva debe requerir confirmación.**
5. **Toda alerta debe tener severidad y siguiente acción.**
6. **Todo error debe explicarse en lenguaje claro.**
7. **Toda pantalla crítica debe soportar vacío, carga, error y éxito.**
8. **Toda entidad importante debe tener estado visible.**
9. **Los filtros deben ser pocos, claros y persistentes.**
10. **El usuario nunca debe adivinar si está en paper o live.**

---

## 12. Mejoras concretas sobre la base actual

## Problemas actuales detectados
1. La app actual mezcla dashboard, conectores, wizard y perfil dentro de una estructura más cercana a desktop que a mobile-first.
2. La administración actual cubre usuarios, pricing y políticas, pero no separa claramente monitoreo, incidentes, posiciones globales y configuración dinámica avanzada.
3. Las configuraciones de bots y estrategias siguen muy acopladas a formularios fijos y validaciones embebidas.
4. La noción de exchange policy existe, pero aún no evoluciona a un motor de capacidades + configuración dinámica por contexto.

## Mejora propuesta
1. Separar la experiencia del usuario final en 5 tabs claras y orientadas a decisión rápida.
2. Reorganizar bots y estrategias como dominios separados, con cards y acciones de 1 toque.
3. Convertir la configuración en un motor dinámico gobernado por admin.
4. Incorporar capa formal de `RiskEngine` + `DynamicConfigService` + `ExecutionRouter`.
5. Crear un admin panel con módulos explícitos de exchanges, posiciones, logs, reportes y control crítico.
6. Hacer visible el estado `paper/live` y la severidad del riesgo en toda la UX.
7. Crear reportes reales y tablas operables para auditoría y escalabilidad.

---

## 13. Fases de implementación recomendadas

### Fase 1 — UX foundation
- design tokens
- bottom navigation
- dashboard nuevo
- listado de bots
- activity simplificada

### Fase 2 — Bot creation & strategy UX
- nuevo flujo crear bot
- editor de estrategias por bloques
- previews y validaciones inline

### Fase 3 — Dynamic config engine
- tablas/config service
- renderer de formularios dinámicos
- visibilidad por exchange/mercado/rol

### Fase 4 — Admin control tower
- dashboard admin nuevo
- exchanges monitor
- logs/incidents
- posiciones huérfanas
- kill switch global

### Fase 5 — Reporting & governance
- reportes agregados
- auditoría avanzada
- versionado de estrategia
- rollback de configuración

---

## 14. Backlog funcional mínimo por módulo

### Usuario final
- dashboard v2
- bot list v2
- bot detail drawer
- strategy catalog v2
- strategy editor v2
- activity feed v2
- profile/security center

### Admin
- health dashboard
- users control
- exchange monitor
- dynamic config manager
- strategy governance
- positions monitor
- logs and incidents
- global kill switch
- reports center

### Backend
- config definitions API
- strategy blueprint API
- exchange capability registry
- report aggregation jobs
- audit trail
- incident model

---

## 15. Decisiones funcionales cerradas

- **La app principal se diseña mobile-first.**
- **El panel admin se diseña desktop-first con responsive funcional.**
- **El kill switch existe en usuario y admin.**
- **Toda estrategia usa bloques Entrada / Salida / Riesgo / Mercado.**
- **Toda configuración es backend-driven.**
- **Todo exchange nuevo entra por adapter estándar.**
- **Toda operación crítica deja rastro de auditoría.**
- **Todo flujo live muestra resumen de riesgo antes de activarse.**

