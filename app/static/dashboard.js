const PLATFORM_MARKET_TYPES={mt5:['forex','cfd'],ctrader:['forex','cfd','spot','futures'],tradingview:['signals'],binance:['spot','futures'],bybit:['spot','futures'],okx:['spot','futures']};
const CATEGORY_TITLES={broker:'Mercado de valores / Brokers',crypto:'Cryptos',signals:'Señales'};
const STRATEGY_LIBRARY={
  ema_rsi:{name:'EMA + RSI',summary:'Combina tendencia y momentum para filtrar entradas.',useCase:'Mercados con tendencia definida y retrocesos moderados.',timeframes:'15m, 1h, 4h',marketTypes:['spot'],tips:['Evita usarla en rangos muy laterales.','Combínala con niveles de soporte/resistencia.']},
  mean_reversion_zscore:{name:'Mean Reversion Z-Score',summary:'Busca retorno al promedio cuando el precio se aleja demasiado.',useCase:'Mercados en rango o sobre-extensiones puntuales.',timeframes:'5m, 15m, 1h',marketTypes:['spot'],tips:['Reduce riesgo en tendencias muy fuertes.','Úsala mejor con activos líquidos.']},
  momentum_breakout:{name:'Momentum Breakout',summary:'Opera rupturas de máximos y mínimos recientes.',useCase:'Fases de expansión de volatilidad y rompimientos.',timeframes:'15m, 1h, 4h',marketTypes:['futures'],tips:['Confirma volumen o fuerza antes de entrar.','Evita operar justo antes de noticias de alto impacto.']},
  macd_trend_pullback:{name:'MACD Trend Pullback',summary:'Sigue la tendencia con confirmación MACD y pullback.',useCase:'Tendencias limpias con correcciones controladas.',timeframes:'15m, 1h, 4h',marketTypes:['futures'],tips:['Mejor cuando el mercado no está en rango.','Gestiona stop por debajo/encima del último swing.']},
  bollinger_rsi_reversal:{name:'Bollinger + RSI Reversal',summary:'Detecta posible rebote en extremos de bandas.',useCase:'Sobrecompra/sobreventa en mercados con reversión.',timeframes:'5m, 15m, 1h',marketTypes:['spot'],tips:['No sobreapalancar: puede haber continuaciones.','Confirma con vela de rechazo.']},
  adx_trend_follow:{name:'ADX Trend Follow',summary:'Filtra entradas cuando la fuerza de tendencia es real.',useCase:'Mercados con direccionalidad clara.',timeframes:'1h, 4h, 1D',marketTypes:['futures'],tips:['Evita periodos de ADX bajo.','Funciona mejor con stops dinámicos.']},
  stochastic_rebound:{name:'Stochastic Rebound',summary:'Busca rebotes desde extremos del oscilador estocástico.',useCase:'Pullbacks cortos en tendencia o rangos definidos.',timeframes:'5m, 15m, 1h',marketTypes:['spot'],tips:['Esperar confirmación evita señales falsas.','No usar aislada en rupturas violentas.']},
  supertrend_volatility:{name:'Supertrend Volatility',summary:'Captura impulsos fuertes con filtro de volatilidad.',useCase:'Escenarios de continuación con expansión de rango.',timeframes:'5m, 15m, 1h',marketTypes:['futures'],tips:['Evitar anuncios macro de alto impacto.','Ideal en activos con buen volumen.']},
  kalman_trend_filter:{name:'Kalman Trend Filter',summary:'Suaviza ruido para seguir tendencia dominante.',useCase:'Mercados direccionales con retrocesos pequeños.',timeframes:'15m, 1h, 4h',marketTypes:['futures'],tips:['Mejor en marcos de tiempo medios.','Combinar con gestión de riesgo estricta.']},
  atr_channel_breakout:{name:'ATR Channel Breakout',summary:'Rupturas de canal ajustadas a volatilidad ATR.',useCase:'Sesiones con breakout y alta energía.',timeframes:'15m, 1h, 4h',marketTypes:['futures'],tips:['Usar trailing stop para proteger ganancia.','Reducir exposición en baja volatilidad.']},
  volatility_breakout:{name:'Volatility Breakout',summary:'Rompe el rango previo con filtro ATR para evitar ruido.',useCase:'Futures intradía cuando el precio acelera tras compresión.',timeframes:'5m, 15m, 1h',marketTypes:['futures'],tips:['Mejor con volumen creciente.','Evita operar una vela aislada sin confirmación.']},
  ema_rsi_adx_stack:{name:'EMA20/50 + RSI14 + ADX',summary:'Combina tendencia, momentum y fuerza direccional para filtrar entradas.',useCase:'Spot y futures con sesgo claro y continuidad.',timeframes:'3m, 5m, 15m, 1h',marketTypes:['spot','futures'],tips:['Si ADX está plano, reduce tamaño o espera.','Funciona mejor cuando el activo ya salió de rango.']},
  volatility_compression_breakout:{name:'Volatility Compression Breakout',summary:'Detecta squeeze (BB/Keltner + ATR contraction) y opera la expansión posterior.',useCase:'Spot y futures con compresión previa y liberación de volatilidad.',timeframes:'15m, 1h',marketTypes:['spot','futures'],tips:['Busca confirmación de expansión real y no solo un wick.','Muy útil cuando el mercado viene de varias velas estrechas.']},
  volatility_parity_rebalance:{name:'Volatility Parity Rebalance',summary:'Ajusta entradas según régimen de volatilidad.',useCase:'Spot con variaciones de riesgo entre ciclos.',timeframes:'1h, 4h, 1D',marketTypes:['spot'],tips:['Buena para carteras diversificadas.','No perseguir velas extendidas.']},
  pairs_spread_proxy:{name:'Pairs Spread Proxy',summary:'Aproxima spread estadístico para reversión.',useCase:'Spot lateral con desviaciones extremas.',timeframes:'15m, 1h, 4h',marketTypes:['spot'],tips:['Priorizar activos altamente correlacionados.','Usar TP conservador.']},
};
const STRATEGY_NUMERIC_GUIDES={
  default:{risk:['Bajo 0.5%','Medio 1.0%','Alto 1.5%'],ml:['Regular 55%','Bueno 62%','Excelente 70%'],tp:['Conservador 0.8%','Balanceado 1.5%','Agresivo 2.5%'],sl:['Bajo riesgo 0.4%','Medio 0.8%','Amplio 1.2%'],trailing:['Ceñido 0.3%','Normal 0.6%','Amplio 1.0%'],positions:['1 muy conservador','2 balanceado','3 agresivo']},
  momentum_breakout:{risk:['Bajo 0.4%','Medio 0.8%','Alto 1.2%'],ml:['Regular 60%','Bueno 68%','Excelente 75%'],tp:['TPL bajo 0.6%','TPL medio 1.0%','TPL agresivo 1.8%'],sl:['Ajustado 0.3%','Medio 0.5%','Amplio 0.8%'],trailing:['Defensivo 0.25%','Normal 0.45%','Amplio 0.7%'],positions:['1 ideal','2 razonable','3 solo con cartera diversificada']},
  ema_rsi_adx_stack:{risk:['Bajo 0.5%','Medio 0.9%','Alto 1.3%'],ml:['Regular 58%','Bueno 64%','Excelente 72%'],tp:['Conservador 1.0%','Medio 1.8%','Alto 2.8%'],sl:['Ceñido 0.5%','Medio 0.8%','Amplio 1.1%'],trailing:['Ceñido 0.35%','Normal 0.55%','Amplio 0.9%'],positions:['1 bajo riesgo','2 medio riesgo','3 alto riesgo']},
  volatility_breakout:{risk:['Bajo 0.3%','Medio 0.6%','Alto 1.0%'],ml:['Regular 62%','Bueno 70%','Excelente 78%'],tp:['Conservador 0.7%','Medio 1.2%','Agresivo 2.0%'],sl:['Ceñido 0.35%','Medio 0.55%','Amplio 0.8%'],trailing:['Ceñido 0.2%','Normal 0.4%','Amplio 0.65%'],positions:['1 ideal','2 aceptable','3 solo con alta liquidez']},
};
const PLATFORM_FIELD_MAP={
  mt5:[{key:'login',label:'Usuario / Login MT5',target:'secrets',required:true},{key:'password',label:'Contraseña MT5',target:'secrets',required:true},{key:'server',label:'Servidor del broker',target:'secrets',required:true},{key:'default_quantity',label:'Tamaño por operación',target:'config',type:'number',step:'0.01'}],
  ctrader:[{key:'client_id',label:'Client ID',target:'secrets',required:true},{key:'client_secret',label:'Client Secret',target:'secrets',required:true},{key:'access_token',label:'Access Token',target:'secrets',required:true},{key:'account_id',label:'Account ID',target:'secrets',required:true},{key:'default_quantity',label:'Tamaño por operación',target:'config',type:'number',step:'1'}],
  tradingview:[{key:'passphrase',label:'Clave secreta del webhook',target:'config',required:true}],
  binance:[{key:'api_key',label:'API Key',target:'secrets',required:true},{key:'secret_key',label:'Secret Key',target:'secrets',required:true},{key:'default_quantity',label:'Cantidad fija por operación',target:'config',type:'number',step:'0.0001'}],
  bybit:[{key:'api_key',label:'API Key',target:'secrets',required:true},{key:'secret_key',label:'Secret Key',target:'secrets',required:true},{key:'default_quantity',label:'Cantidad fija por operación',target:'config',type:'number',step:'0.0001'}],
  okx:[{key:'api_key',label:'API Key',target:'secrets',required:true},{key:'secret_key',label:'Secret Key',target:'secrets',required:true},{key:'passphrase',label:'Passphrase',target:'secrets',required:true},{key:'default_quantity',label:'Cantidad fija por operación',target:'config',type:'number',step:'0.0001'}],
};
let METADATA={platforms:[]}; let STRATEGY_CONTROL={managed_by_admin:false,allowed_strategies:[],all_strategies:[]}; let DASHBOARD_CACHE={trades:[],summary:{},executionLogs:[],botSessions:[],connectors:[]};
const EXECUTION_LOG_LIMIT=50; const EXECUTION_LOG_REFRESH_MS=5*60*1000;
const TELEMETRY_FILTER_DEFAULTS={limit:50,symbol:''};
let SYMBOL_CATALOG_CACHE={};
let TELEMETRY_FILTER={...TELEMETRY_FILTER_DEFAULTS};
const parseCsv=(v)=>String(v||'').split(',').map(x=>x.trim()).filter(Boolean);
const timeframeToMinutes=(timeframe)=>{const clean=String(timeframe||'').trim().toLowerCase();const map={"1m":1,"3m":3,"5m":5,"15m":15,"30m":30,"1h":60,"2h":120,"4h":240,"6h":360,"8h":480,"12h":720,"1d":1440};return map[clean]||5;};
const setNodeText=(id,value)=>{const node=document.getElementById(id);if(node)node.textContent=value;};
const safeNumber=(value)=>Number(value||0);
const DASHBOARD_LOCALE=(document.documentElement.lang||'es').slice(0,2).toLowerCase();
const isEnglishDashboard=()=>DASHBOARD_LOCALE==='en';
const DASHBOARD_TEXT={
  en:{
    unexpected_error:'Unexpected error',
    resource_not_found:'The requested resource was not found. Check the connector, the route, or reload the dashboard.',
    gateway_timeout:'The exchange or gateway took too long to respond. Try again in a few seconds.',
    bad_gateway:'The external service returned an invalid gateway response. Check connectivity, credentials, or try again.',
    network_error:'No connection to the server or the exchange. Check your network and try again.',
    leave_empty_keep_value:'Leave empty to keep the current value',
    admin_account:'Admin account',
    user_profile:'User profile',
    execution_profile:'Execution profile',
    sizing_by_balance:'Sizing by balance percentage',
    fixed_sizing:'Fixed sizing per operation',
    base_language:'Base language',
    alert_channel:'Alerts channel',
    admin_telegram_active:'Central admin Telegram is active for errors, actions, and monitoring.',
    admin_telegram_missing:'Admin Telegram is not configured yet.',
    operating_universe:'Operating universe',
    platforms_enabled_by_admin:'platforms enabled by admin',
    strategies_available:'strategies available',
    profile_loaded:'Profile loaded',
    profile_prefix:'Profile',
    profile_updated:'Profile updated successfully.',
    connector_for_market_missing:'No connectors for that market',
    no_bots_yet:'There are no active bots yet. Activate one from "Run strategy".',
    capital_per_trade:'Capital per trade',
    every_minutes:'Every {minutes} min',
    paused:'Paused',
    active:'Active',
    pending_first_run:'Pending first run',
    operational_error:'Operational error: {error}',
    bot_resumed:'Bot resumed successfully.',
    bot_paused:'Bot paused successfully.',
    bot_deleted:'Bot deleted successfully.',
    no_live_strategies:'There are no strategies running right now.',
    active_count:'{count} active',
    no_active_strategies:'No active strategies.',
    symbols_count:'symbols: {count}',
    manual:'Manual',
    dynamic_top:'Dynamic top {count}',
    pause:'Pause',
    resume:'Resume',
    edit:'Edit',
    delete:'Delete',
    bots_load_failed:'Could not load bots: {error}',
    select_connector_for_catalog:'Select a connector to view its catalog.',
    loading_symbol_catalog:'Loading symbol catalog...',
    symbol_catalog_source:'{count} symbols · source {source}',
    local_catalog:'Local catalog: {count} suggested symbols for {market}.',
    remote_catalog_failed:'Could not load the remote catalog. Use manual selection and validate the connector.',
    dynamic_universe_placeholder:'The dynamic universe will be taken from the selected connector catalog',
    dynamic_help:'Dynamic: the first {count} symbols from the connector market-filtered catalog will be prioritized.',
    dynamic_help_empty:'Dynamic: no catalog is available yet; test the connector or switch to manual selection.',
    manual_help:'Manual: type comma-separated pairs or build the list from the selector below.',
    select_connector_before_continue:'Explicitly select at least one connector before continuing.',
    activate_one_connector:'To activate a 24/7 bot you must leave exactly one connector selected. This prevents execution in the wrong app or market.',
    no_symbols_available:'No symbols available. Configure them manually or use a connector with a dynamic universe.',
    no_compatible_strategies:'There are no compatible strategies for {markets}. Adjust the connectors or the market.',
    bot_activated:'24/7 bot activated. Session #{session_id} queued for its first run.',
    no_logs_yet:'No logs yet. Run a strategy to get started.',
    execution_logs_meta_empty:'Auto-refresh every 5 minutes · Showing last {limit} logs · No data yet.',
    execution_logs_meta:'Auto-refresh every 5 minutes · Showing {count} of {limit} logs · Last update: {time}',
    execution_logs_refresh_error:'Auto-refresh every 5 minutes · Refresh failed: {error}',
    logs_load_failed:'Could not load logs: {error}',
    top_moves_day:'Top daily movers in USDT pairs.',
    top_moves_range:'Top movers ({range}) in USDT pairs.',
    week:'week',
    month:'month',
    market_load_failed:'Could not load market board: {error}',
    validating_connectors:'Validating connectors...',
    no_active_connectors_validate:'There are no active connectors to validate.',
    connector_validated:'Connector validated: {message}',
    connector_test_completed:'Test completed: {message}',
    connector_updated:'Connector updated successfully.',
    connector_deleted:'Connector deleted successfully.',
    strategy_executed:'Strategy executed successfully with symbol and risk validation.',
    dashboard_load_error:'Error loading dashboard: {error}',
    prompt_bot_session_id:'Bot session ID to copy:',
    prompt_target_connector:'Target connector ID (optional):',
    bot_copied:'Bot copied successfully.',
  },
};
function t(key,fallback,vars={}){
  const template=(DASHBOARD_TEXT[DASHBOARD_LOCALE]||{})[key]||fallback;
  return Object.entries(vars||{}).reduce((acc,[k,v])=>acc.replaceAll(`{${k}}`,String(v)),template);
}
function translateStaticDashboard(){
  if(!isEnglishDashboard())return;
  const phraseMap={
    'Hola,':'Hello,',
    'Tu centro de operación inteligente':'Your smart operations hub',
    'Gestiona conectores, estrategias y resultados desde una vista simple y rápida.':'Manage connectors, strategies, and results from a simple, fast view.',
    'Panel de apps y estrategias':'Apps and strategies panel',
    'Estado actual':'Current status',
    'Apps activas':'Active apps',
    'Símbolos por app (prom.)':'Symbols per app (avg.)',
    'Estrategias activas':'Active strategies',
    'Perfil':'Profile',
    'Apps':'Apps',
    'Estrategias':'Strategies',
    'Actividad':'Activity',
    'Resumen operativo del perfil':'Profile operations summary',
    'Mission control, configuración, decisiones y riesgo ahora viven dentro de Perfil.':'Mission control, configuration, decisions, and risk now live inside Profile.',
    'Estado táctico del sistema':'System tactical status',
    'Refresh':'Refresh',
    'Inicializando':'Initializing',
    'Pendiente':'Pending',
    'Último heartbeat':'Last heartbeat',
    'Configuración operativa':'Operational configuration',
    'Flujo de decisiones':'Decision flow',
    'La telemetría de decisión resume qué evaluó el motor, qué decidió y por qué terminó ejecutando, esperando o descartando una señal. Úsala para detectar sesgos, revisar calidad de datos y ajustar estrategia + timeframe antes de operar live.':'Decision telemetry summarizes what the engine evaluated, what it decided, and why it executed, waited, or discarded a signal. Use it to detect bias, review data quality, and adjust strategy + timeframe before trading live.',
    'Ventana':'Window',
    'Filtrar símbolo':'Filter symbol',
    'Ej. BTC/USDT':'Ex. BTC/USDT',
    'Ajusta tu cuenta por bloques para mantener un flujo claro: identidad, contacto y alertas automatizadas.':'Adjust your account in blocks to keep a clear flow: identity, contact, and automated alerts.',
    'Identidad':'Identity',
    'Nombre':'Name',
    'Contacto':'Contact',
    'Número de teléfono (WhatsApp futuro)':'Phone number (future WhatsApp)',
    'Alertas y notificaciones':'Alerts and notifications',
    'Las alertas de Telegram ahora se centralizan solo en el canal administrativo para monitoreo operativo. Desde aquí ya no se configuran bots, tokens ni chats por usuario.':'Telegram alerts are now centralized only in the admin channel for operational monitoring. Bots, tokens, and per-user chats are no longer configured here.',
    'Idioma base de mensajes internos':'Base language for internal messages',
    'Español':'Spanish',
    'English':'English',
    'Português':'Portuguese',
    'Français':'French',
    'El email solo puede editarlo el super user. Las alertas operativas ya se envían al Telegram central del admin.':'Email can only be edited by the super user. Operational alerts are already sent to the central admin Telegram.',
    'Guardar perfil':'Save profile',
    'Riesgo visible en 3 segundos':'Visible risk in 3 seconds',
    'Estable':'Stable',
    'Resumen concentrado del riesgo real para evitar configuraciones duplicadas y validar rápido si el setup quedó sano.':'A compact summary of real risk to avoid duplicated configurations and quickly validate that the setup is healthy.',
    'Estrategias creadas y funcionando':'Created and running strategies',
    'Resumen agrupado por app y tipo de mercado (spot/futures) para revisar rápidamente tu estado productivo.':'Summary grouped by app and market type (spot/futures) to quickly review your production status.',
    'Ejecutar estrategia':'Run strategy',
    'Validar conectores':'Validate connectors',
    'Tipo de plataforma / mercado':'Platform / market type',
    'Detectar desde el conector seleccionado':'Detect from selected connector',
    'Este campo volvió al tab Base para dejar explícito si la estrategia/bot correrá en spot, futures u otro mercado. También filtra conectores compatibles.':'This field is back on the Base tab to make it explicit whether the strategy/bot will run on spot, futures, or another market. It also filters compatible connectors.',
    'Conectores disponibles para ejecutar':'Available connectors to run',
    'Selecciona uno o más conectores (Ctrl/Cmd + click para selección múltiple). Para activar un bot 24/7 debes dejar exactamente un conector seleccionado para evitar ejecuciones en la app/mercado equivocados.':'Select one or more connectors (Ctrl/Cmd + click for multi-select). To activate a 24/7 bot you must leave exactly one connector selected to avoid execution in the wrong app/market.',
    'Símbolos':'Symbols',
    'Lista de símbolos':'Symbol list',
    'Buscar símbolo':'Search symbol',
    'Ej. BTC, ETH, SOL':'Ex. BTC, ETH, SOL',
    'Agregar →':'Add →',
    '← Quitar':'← Remove',
    'Limpiar':'Clear',
    'Usa el buscador y el selector para construir tu cesta manual. La lista se filtra por conector y mercado.':'Use the search box and selector to build your manual basket. The list is filtered by connector and market.',
    'Modo de selección de símbolos':'Symbol selection mode',
    'Dinámico desde la app seleccionada':'Dynamic from the selected app',
    'Cantidad de símbolos para selección dinámica':'Number of symbols for dynamic selection',
    'Timeframe':'Timeframe',
    'Wizard de configuración':'Setup wizard',
    'Ver guía de campos':'View field guide',
    'Riesgo por trade (%)':'Risk per trade (%)',
    'Prob. mínima ML (%)':'Min ML prob. (%)',
    'Máx. posiciones abiertas simultáneas':'Max simultaneous open positions',
    'Solo contará posiciones realmente abiertas del conector seleccionado.':'Only truly open positions from the selected connector will be counted.',
    'Take Win / Take Profit':'Take Win / Take Profit',
    'Consulta el ejemplo en el botón ? .':'See the example in the ? button.',
    'Stop Loss':'Stop Loss',
    'Trailing Stop':'Trailing Stop',
    'Consulta explicación en el botón ? .':'See the explanation in the ? button.',
    'Cierre por indicador':'Indicator exit',
    'Activado':'Enabled',
    'Cruce MACD':'MACD cross',
    'Reversión RSI':'RSI reversal',
    'Cruce EMA':'EMA cross',
    'Intentar live si el conector está en live':'Try live if the connector is live',
    'Atrás':'Back',
    'Siguiente':'Next',
    'Ejecutar':'Run',
    'Activar bot 24/7':'Activate 24/7 bot',
    'Guía dinámica':'Dynamic guide',
    'Selecciona conector, estrategia y timeframe para recibir una configuración sugerida.':'Select connector, strategy, and timeframe to receive a suggested configuration.',
    'Estrategias disponibles':'Available strategies',
    'Click para ver explicación rápida':'Click to see a quick explanation',
    'Publicar estrategia actual':'Publish current strategy',
    'Ver pool público':'View public pool',
    'Monedas con mayor movimiento / ganancia':'Top moving / gaining coins',
    'Actualizar ahora':'Refresh now',
    'Histórico':'History',
    'Día':'Day',
    'Semana':'Week',
    'Mes':'Month',
    'Moneda':'Coin',
    'Precio':'Price',
    'Variación':'Change',
    'Volumen':'Volume',
    'Bots activos (24/7)':'Active bots (24/7)',
    'Actualizar bots':'Refresh bots',
    'Copiar bot seleccionado':'Copy selected bot',
    'Muestra estrategias realmente en ejecución continua por conector, símbolo y capital asignado por operación en USDT/USD.':'Shows strategies truly running continuously by connector, symbol, and assigned capital per operation in USDT/USD.',
    'Conector':'Connector',
    'Plataforma':'Platform',
    'Capital/op':'Capital/op',
    'Frecuencia':'Frequency',
    'Estado':'Status',
    'Última corrida':'Last run',
    'Acciones':'Actions',
    'Health de conectores':'Connector health',
    'Refrescar':'Refresh',
    'Resumen ejecutivo':'Executive summary',
    'Conectores':'Connectors',
    'Activos':'Active',
    'Trades':'Trades',
    'PNL realizado':'Realized PNL',
    'Logs de ejecución (5m / 1h)':'Execution logs (5m / 1h)',
    'Actualizar logs':'Refresh logs',
    'Descargar CSV':'Download CSV',
    'Muestra la última vela capturada, decisión (sin acción / compra / venta) y estado de ejecución para validar conexión con Binance u otros conectores.':'Shows the latest captured candle, decision (no action / buy / sell), and execution status to validate the connection with Binance or other connectors.',
    'Fecha':'Date',
    'Señal':'Signal',
    'Decisión':'Decision',
    'Vela':'Candle',
    'Transacciones':'Transactions',
    'Filtro':'Filter',
    'Diario':'Daily',
    'Semanal':'Weekly',
    'Mensual':'Monthly',
    'Inversión':'Investment',
    'Resultado':'Result',
    'Actividad y performance avanzada':'Advanced activity and performance',
    'Basado en tus operaciones históricas':'Based on your historical operations',
    'PNL por plataforma':'PNL by platform',
    'Distribución por resultado':'Distribution by result',
    'Evolución acumulada del PNL':'Cumulative PNL evolution',
    'Webhook de TradingView explicado fácil':'TradingView webhook made easy',
    'Consejos':'Tips',
    'Guía rápida del flujo de estrategia':'Quick guide to the strategy flow',
    'Wizard · Configuración profesional':'Wizard · Professional setup',
    'Explicación':'Explanation',
    'Cerrar':'Close',
  };
  const root=document.querySelector('.dashboard-redesign');
  if(!root)return;
  const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
  const nodes=[];
  while(walker.nextNode())nodes.push(walker.currentNode);
  nodes.forEach((node)=>{
    const text=node.textContent;
    const trimmed=String(text||'').trim();
    if(!trimmed)return;
    const translated=phraseMap[trimmed];
    if(!translated)return;
    node.textContent=text.replace(trimmed,translated);
  });
}
function ensureToastHost(){let host=document.getElementById('global-toast-host');if(host)return host;host=document.createElement('div');host.id='global-toast-host';document.body.appendChild(host);return host;}
function showToast(message,type='ok'){const host=ensureToastHost();const toast=document.createElement('div');toast.className=`global-toast ${type==='error'?'status-error':'status-ok'}`;toast.textContent=message;host.appendChild(toast);setTimeout(()=>toast.classList.add('is-visible'),10);setTimeout(()=>{toast.classList.remove('is-visible');setTimeout(()=>toast.remove(),260);},4200);}
function setStatusNode(id,message,type='ok'){const node=document.getElementById(id);if(!node)return;node.textContent=message;node.className=`status-msg ${type==='error'?'status-error':'status-ok'}`;}
function reportMarkup(items=[]){return items.filter(Boolean).map((item)=>`<article class="quantum-report-item"><strong>${item.title||'-'}</strong><small>${item.body||'-'}</small></article>`).join('');}
function parseApiError(error){const raw=String(error?.message||t('unexpected_error','Error inesperado')).trim();if(!raw)return t('unexpected_error','Error inesperado');try{const payload=JSON.parse(raw);if(payload?.detail)return Array.isArray(payload.detail)?payload.detail.map(d=>d.msg||JSON.stringify(d)).join(' | '):String(payload.detail);}catch(_e){}const compact=raw.replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim();if(/404 Not Found/i.test(raw)||compact==='Not Found')return t('resource_not_found','No se encontró el recurso solicitado. Revisa el conector, la ruta o vuelve a cargar el panel.');if(/504 Gateway Time-out/i.test(raw)||/gateway time-out/i.test(compact))return t('gateway_timeout','El exchange o gateway tardó demasiado en responder. Intenta de nuevo en unos segundos.');if(/502 Bad Gateway/i.test(raw)||/bad gateway/i.test(compact))return t('bad_gateway','El servicio externo respondió con un gateway inválido. Revisa conexión, credenciales o inténtalo de nuevo.');if(/failed to fetch|networkerror|network request failed/i.test(compact))return t('network_error','Sin conexión con el servidor o con el exchange. Verifica red y vuelve a intentar.');if(compact&&compact!==raw)return compact;return raw;}
async function api(url,options={}){const res=await fetch(url,{headers:{'Content-Type':'application/json'},credentials:'same-origin',...options});if(!res.ok) throw new Error(await res.text());return res.json();}
const allowedPlatforms=()=>METADATA.platforms.filter((p)=>p.is_enabled_global&&p.grant?.is_enabled).map((p)=>p.platform);
const connectorFieldsFor=(platform)=>PLATFORM_FIELD_MAP[platform]||[];
const connectorMarketTypesFor=(platform)=>PLATFORM_MARKET_TYPES[platform]||['spot'];
const platformMetaFor=(platform)=>METADATA.platforms.find((item)=>item.platform===platform)||{};
function connectorFieldMarkup(field,{value='',editing=false}={}){const safeValue=value===undefined||value===null?'':String(value);const placeholder=editing&&field.target==='secrets'?t('leave_empty_keep_value','Deja vacío para conservar el valor actual'):'';return `<label>${field.label}<input data-field="${field.key}" data-target="${field.target}" ${field.type?`type="${field.type}"`:''} ${field.step?`step="${field.step}"`:''} ${field.required&&!editing?'required':''} value="${safeValue.replace(/"/g,'&quot;')}" ${placeholder?`placeholder="${placeholder}"`:''}></label>`;}
function buildConnectorPayload(form,{includeSecrets=false}={}){const fd=new FormData(form);const config={market_type:String(fd.get('market_type')||'spot')};const secrets={};form.querySelectorAll('[data-field]').forEach((input)=>{const raw=String(input.value||'').trim();if(!raw)return;if(input.dataset.target==='secrets'){if(includeSecrets||raw)secrets[input.dataset.field]=raw;return;}config[input.dataset.field]=input.type==='number'?Number(raw):raw;});return {platform:form.dataset.platform,label:String(fd.get('label')||'').trim(),mode:String(fd.get('mode')||'paper'),market_type:String(fd.get('market_type')||'spot'),symbols:[],config,secrets};}

function initTabs(rootSel,panelPrefix){const buttons=document.querySelectorAll(`${rootSel} .tab-btn`);buttons.forEach((btn)=>btn.addEventListener('click',()=>{buttons.forEach((b)=>b.classList.toggle('active',b===btn));document.querySelectorAll(`[id^="${panelPrefix}"]`).forEach((panel)=>panel.classList.toggle('active',panel.id===`${panelPrefix}${btn.dataset.tab}`));}));}

function renderProfile(user){const name=document.getElementById('profile-name');if(name)name.value=user.name||'';const email=document.getElementById('profile-email');if(email)email.value=user.email||'';const phone=document.getElementById('profile-phone');if(phone)phone.value=user.phone||'';const mode=document.getElementById('trade-amount-mode');if(mode)mode.value=user.trade_amount_mode||'fixed_usd';const fixed=document.getElementById('fixed-trade-amount-usd');if(fixed)fixed.value=Number(user.fixed_trade_amount_usd||10);const pct=document.getElementById('trade-balance-percent');if(pct)pct.value=Number(user.trade_balance_percent||10);const lang=document.getElementById('profile-alert-language');if(lang)lang.value=user.alert_language||'es';const profileTitle=document.getElementById('profile-title');if(profileTitle)profileTitle.textContent=user.is_admin?t('admin_account','Cuenta administrativa'):t('user_profile','Perfil de usuario');}
function updateRunTradeAmountUI(){const mode=String(document.getElementById('run-trade-amount-mode')?.value||'inherit');const amountWrap=document.getElementById('run-amount-per-trade-wrap');const percentWrap=document.getElementById('run-amount-percentage-wrap');const amountInput=document.getElementById('run-amount-per-trade');const percentInput=document.getElementById('run-amount-percentage');if(amountWrap)amountWrap.hidden=mode!=='fixed_usd';if(percentWrap)percentWrap.hidden=mode!=='balance_percent';if(amountInput){amountInput.required=mode==='fixed_usd';if(mode!=='fixed_usd')amountInput.value='';}if(percentInput){percentInput.required=mode==='balance_percent';if(mode!=='balance_percent')percentInput.value='';}}
function renderUserConfigReport(user){const node=document.getElementById('user-config-report');if(!node)return;const strategyCount=(STRATEGY_CONTROL.allowed_strategies||[]).length;node.innerHTML=reportMarkup([{title:t('execution_profile','Perfil de ejecución'),body:`${user.trade_amount_mode==='balance_percent'?t('sizing_by_balance','Sizing por porcentaje de balance'):t('fixed_sizing','Sizing fijo por operación')} · ${t('base_language','Idioma base')}: ${String(user.alert_language||'es').toUpperCase()}`},{title:t('alert_channel','Canal de alertas'),body:user.admin_alerts_enabled?t('admin_telegram_active','Telegram administrativo central activo para errores, acciones y monitoreo.'):t('admin_telegram_missing','Telegram administrativo no configurado todavía.')},{title:t('operating_universe','Universo operativo'),body:`${allowedPlatforms().length} ${t('platforms_enabled_by_admin','plataformas habilitadas por admin')} · ${strategyCount||Object.keys(STRATEGY_LIBRARY).length} ${t('strategies_available','estrategias disponibles')}`}]);setNodeText('user-config-state',user.name?`${t('profile_prefix','Profile')} · ${user.name}`:t('profile_loaded','Profile loaded'));}
function selectedRunConnectorIds(){return Array.from(document.getElementById('run-connector-select')?.selectedOptions||[]).map(o=>Number(o.value));}
function selectedMarketTypes(){const selected=Array.from(document.getElementById('run-connector-select')?.selectedOptions||[]).map(option=>String(option?.dataset?.marketType||'spot').toLowerCase()).filter(Boolean);return selected.length?[...new Set(selected)]:['spot'];}
function selectedMarketType(){return selectedMarketTypes()[0]||'spot';}function selectedRunMarketTypePreference(){return String(document.getElementById('run-market-type-filter')?.value||'').trim().toLowerCase();}function resolveEffectiveRunMarketType(){return selectedRunMarketTypePreference()||selectedMarketType()||'spot';}function syncRunMarketTypeUI(){const select=document.getElementById('run-market-type-filter');const runSelect=document.getElementById('run-connector-select');if(!select||!runSelect)return;const enabledConnectors=(DASHBOARD_CACHE.connectors||[]).filter(c=>c&&c.is_enabled);const preference=selectedRunMarketTypePreference();const visibleConnectors=enabledConnectors.filter((connector)=>!preference||String(connector.market_type||'spot').toLowerCase()===preference);const previousSelection=selectedRunConnectorIds();runSelect.innerHTML=visibleConnectors.map(c=>`<option value="${c.id}" data-market-type="${c.market_type||'spot'}">${c.label} (${c.platform} - ${c.market_type||'spot'})</option>`).join('');Array.from(runSelect.options).forEach((option)=>{const id=Number(option.value);option.selected=previousSelection.includes(id)||(visibleConnectors.length===1&&id===Number(visibleConnectors[0]?.id));});if(!runSelect.options.length&&preference){runSelect.innerHTML=`<option value="" disabled>${t('connector_for_market_missing','No hay conectores para ese mercado')}</option>`;}renderStrategySelect();renderStrategyGuidance();updateSymbolSourceUI();loadSymbolCatalog();}function strategyGuidePreset(slug,marketType){const presets={spot:{take_profit_value:1.5,stop_loss_value:1.0,trailing_stop_value:0.8,leverage_profile:'none',max_open_positions:1},futures:{take_profit_value:1.2,stop_loss_value:0.6,trailing_stop_value:0.4,leverage_profile:'balanced',max_open_positions:1}};const base={...(presets[marketType]||presets.spot)};if(slug==='ema_rsi_adx_stack'){return {...base,take_profit_value:1.8,stop_loss_value:0.8,trailing_stop_value:0.55,max_open_positions:2};}if(slug==='volatility_breakout'||slug==='momentum_breakout'){return {...base,take_profit_value:1.2,stop_loss_value:0.5,trailing_stop_value:0.4,leverage_profile:'balanced'};}return base;}function applyRunMarketPreset(){const form=document.getElementById('run-form');if(!form)return;const marketType=resolveEffectiveRunMarketType();const slug=String(document.querySelector('select[name="strategy_slug"]')?.value||'');const preset=strategyGuidePreset(slug,marketType);const tp=form.querySelector('input[name="take_profit_value"]');const sl=form.querySelector('input[name="stop_loss_value"]');const trailing=form.querySelector('input[name="trailing_stop_value"]');const leverage=form.querySelector('input[name="leverage_profile"]');const maxPos=form.querySelector('input[name="max_open_positions"]');if(tp)tp.value=Number(preset.take_profit_value);if(sl)sl.value=Number(preset.stop_loss_value);if(trailing)trailing.value=Number(preset.trailing_stop_value);if(leverage)leverage.value=String(preset.leverage_profile||'none');if(maxPos)maxPos.value=Number(preset.max_open_positions||1);}
async function saveProfile(e){e.preventDefault();const fd=new FormData(e.target);const feedback=document.getElementById('profile-feedback');try{await api('/api/me',{method:'PUT',body:JSON.stringify({name:fd.get('name'),phone:fd.get('phone'),alert_language:fd.get('alert_language')})});if(feedback){feedback.textContent=t('profile_updated','Perfil actualizado con éxito.');feedback.className='status-msg status-ok';}const me=await api('/api/me');renderProfile(me);renderUserConfigReport(me);}catch(err){if(feedback){feedback.textContent=parseApiError(err);feedback.className='status-msg status-error';}}}

async function saveTradeAmountSettings(e){e.preventDefault();const fd=new FormData(e.target);const feedback=document.getElementById('profile-trade-amount-feedback');try{await api('/api/me',{method:'PUT',body:JSON.stringify({trade_amount_mode:fd.get('trade_amount_mode'),fixed_trade_amount_usd:Number(fd.get('fixed_trade_amount_usd')),trade_balance_percent:Number(fd.get('trade_balance_percent'))})});if(feedback){feedback.textContent='Monto por operación actualizado.';feedback.className='status-msg status-ok';}const me=await api('/api/me');renderProfile(me);renderUserConfigReport(me);}catch(err){if(feedback){feedback.textContent=parseApiError(err);feedback.className='status-msg status-error';}}}
function collectProfilePayload(){const form=document.getElementById('profile-form');const fd=new FormData(form||undefined);return {name:fd.get('name'),phone:fd.get('phone'),alert_language:fd.get('alert_language')};}
async function testTelegram(){try{await api('/api/me',{method:'PUT',body:JSON.stringify(collectProfilePayload())});const result=await api('/api/me/telegram/test',{method:'POST'});showToast(result.message||'Mensaje de prueba enviado al canal administrativo.');}catch(err){showToast(parseApiError(err),'error');}}

function renderRiskRadar(){const summary=DASHBOARD_CACHE.summary?.risk_summary||{};const alerts=Array.isArray(summary.alerts)?summary.alerts:[];const suggestions=Array.isArray(summary.suggestions)?summary.suggestions:[];const state=document.getElementById('risk-radar-state');const panel=document.getElementById('risk-radar-panel');setNodeText('risk-health-score',`${Number(summary.health_score||100).toFixed(0)}%`);setNodeText('risk-open-heat',Number(summary.estimated_open_risk||0).toFixed(2));setNodeText('risk-drawdown',`${(Number(summary.rolling_drawdown_pct||0)*100).toFixed(2)}%`);setNodeText('risk-kill-switch',summary.kill_switch_armed?'ARMED':'OFF');if(state){state.textContent=summary.kill_switch_armed?'Acción requerida':alerts.length?'Monitoreo':'Estable';state.classList.toggle('pill-off',Boolean(summary.kill_switch_armed));state.classList.toggle('pill-on',!summary.kill_switch_armed);}if(!panel)return;const topSymbols=(summary.by_symbol||[]).slice(0,3).map(item=>`${item.symbol} ${(Number(item.weight||0)*100).toFixed(1)}%`).join(' · ');panel.innerHTML=reportMarkup([{title:'Exposición abierta',body:`${Number(summary.open_positions||0)} posiciones · Notional ${Number(summary.open_notional||0).toFixed(2)} · Riesgo estimado ${Number(summary.estimated_open_risk||0).toFixed(2)}`},{title:'Alertas críticas',body:alerts.length?alerts.join(' · '):'Sin alertas estructurales activas.'},{title:'Concentración',body:topSymbols||'Sin posiciones abiertas.'},{title:'Sugerencia operativa',body:suggestions[0]||'Mantén sizing conservador y confirma calidad de datos antes de operar live.'}]);}

function compatibleStrategiesForSelection(){const markets=[...new Set([...(selectedMarketTypes()||[]),selectedRunMarketTypePreference()].filter(Boolean))];return Object.entries(STRATEGY_LIBRARY).filter(([_,meta])=>!meta.marketTypes||markets.every((market)=>meta.marketTypes.includes(market)));}
function renderStrategySelect(){const select=document.querySelector('select[name="strategy_slug"]');if(!select)return;const previous=select.value;select.innerHTML=compatibleStrategiesForSelection().map(([slug,meta])=>`<option value="${slug}">${meta.name}</option>`).join('');if(previous&&Array.from(select.options).some((option)=>option.value===previous))select.value=previous;else if(select.options.length)select.value=select.options[0].value;applyStrategyControlUI();applyRunMarketPreset();renderStrategyGuidance();}
function renderStrategyLibrary(){const node=document.getElementById('strategy-library');if(!node)return;node.innerHTML=Object.entries(STRATEGY_LIBRARY).map(([slug,meta])=>`<button class="connector-item strategy-card strategy-card-compact" type="button" data-slug="${slug}"><strong>${meta.name}</strong><small class="hint">${meta.summary}</small></button>`).join('');node.querySelectorAll('.strategy-card').forEach((btn)=>btn.addEventListener('click',()=>openStrategyInfo(btn.dataset.slug)));}
function openStrategyInfo(slug){const meta=STRATEGY_LIBRARY[slug];if(!meta)return;document.getElementById('strategy-modal-title').textContent=meta.name;document.getElementById('strategy-modal-summary').textContent=meta.summary;document.getElementById('strategy-modal-usecase').textContent=meta.useCase;document.getElementById('strategy-modal-timeframes').textContent=meta.timeframes;document.getElementById('strategy-modal-tips').innerHTML=meta.tips.map(t=>`<li>${t}</li>`).join('');document.getElementById('strategy-info-modal').classList.remove('hidden');}
const closeStrategyInfo=()=>document.getElementById('strategy-info-modal')?.classList.add('hidden');

const CONNECTOR_SETUP_GUIDES={
  mt5:{
    title:'Guía rápida MT5',
    steps:['Abre tu broker MT5 y entra a la cuenta que vas a usar para bots.','Copia el Login, Password inversionista/comercial y el nombre exacto del servidor del broker.','En este panel pega Login, Contraseña y Servidor; luego define símbolos y tamaño por operación.','Prueba primero en modo Paper si tu broker lo permite; cuando confirmes resultados, cambia a Live.'],
    warning:'Mensaje importante: guarda muy bien tus credenciales MT5 y no las compartas.'
  },
  ctrader:{
    title:'Guía rápida cTrader',
    steps:['En cTrader abre API Management y crea una app para obtener Client ID y Client Secret.','Genera el Access Token autorizando la app y copia también tu Account ID.','Completa esos cuatro campos en TradingSaaS y define mercado/símbolos.','Valida el conector con modo Paper o Signal antes de pasar a Live.'],
    warning:'Mensaje importante: guarda Client Secret y Access Token en un gestor seguro.'
  },
  binance:{
    title:'Guía rápida Binance',
    steps:['En la app/web de Binance entra a Perfil > API Management y crea una nueva API Key.','Guarda API Key y Secret Key apenas se muestren, porque el secret no se vuelve a mostrar completo.','Activa permisos de Spot para operar contado; completa los campos en TradingSaaS y guarda el conector.','Si quieres operar Futures, crea otra API Key separada para futuros y aísla permisos/riesgo.'],
    warning:'Mensaje importante: recuerda guardar bien el Secret y el API Key.'
  },
  bybit:{
    title:'Guía rápida Bybit',
    steps:['En Bybit entra a API Management y crea una API con permisos de lectura/trade según tu uso.','Copia API Key y Secret Key al momento de crearlas y revisa whitelist de IP si la usas.','Configura en TradingSaaS el modo (paper/live), mercado y símbolos antes de guardar.','Para Futures, utiliza una API separada para mantener control del riesgo por producto.'],
    warning:'Mensaje importante: no reutilices la misma API para todo; separa por estrategia/mercado.'
  },
  okx:{
    title:'Guía rápida OKX',
    steps:['En OKX abre API y crea una key nueva con nombre descriptivo.','Guarda API Key, Secret Key y Passphrase (las 3 son obligatorias).','En TradingSaaS pega esos valores y selecciona Spot o Futures según tu operativa.','Valida primero con operación mínima y luego escala tamaño de forma gradual.'],
    warning:'Mensaje importante: sin Passphrase correcta no podrás autenticar el conector.'
  },
  tradingview:{
    title:'Guía rápida TradingView',
    steps:['En TradingSaaS crea tu conector TradingView y define una passphrase robusta.','En TradingView abre la alerta, activa webhook URL y pega el endpoint de tu cuenta.','En el mensaje JSON incluye la misma passphrase y, si aplica, target_connector_id para enrutar órdenes.','Lanza una alerta de prueba para confirmar que llega y que la estrategia responde.'],
    warning:'Mensaje importante: protege la passphrase como si fuera una clave de producción.'
  },
};

function connectorSetupGuide(platform){const guide=CONNECTOR_SETUP_GUIDES[platform];if(!guide)return '';return `<aside class="term-box setup-box" id="connector-setup-${platform}"><h4>${guide.title}</h4><ol>${guide.steps.map((step)=>`<li>${step}</li>`).join('')}</ol><p class="setup-warning">${guide.warning}</p></aside>`;}
function activatePlatformTab(platform,allowed){const tabs=document.getElementById('platform-tabs');if(!tabs)return;tabs.querySelectorAll('.tab-btn').forEach((btn)=>btn.classList.toggle('active',btn.dataset.platform===platform));(allowed||[]).forEach((p)=>document.getElementById(`platform-panel-${p}`)?.classList.toggle('active',p===platform));}

function renderPlatformTabs(){const allowed=allowedPlatforms();const tabs=document.getElementById('platform-tabs');const panels=document.getElementById('platform-panels');if(!tabs||!panels)return;tabs.innerHTML=allowed.map((p,i)=>`<div class="platform-tab-entry"><button class="tab-btn ${i===0?'active':''}" type="button" data-platform="${p}">${p.toUpperCase()} y estrategias</button><a class="tab-link-guide" href="#connector-setup-${p}" data-platform-guide="${p}">Guía</a></div>`).join('');panels.innerHTML=allowed.map((platform,i)=>`<section class="platform-panel ${i===0?'active':''}" id="platform-panel-${platform}">${platformForm(platform)}</section>`).join('');tabs.querySelectorAll('.tab-btn').forEach(btn=>btn.addEventListener('click',()=>activatePlatformTab(btn.dataset.platform,allowed)));tabs.querySelectorAll('[data-platform-guide]').forEach((link)=>link.addEventListener('click',(e)=>{e.preventDefault();const platform=link.dataset.platformGuide;activatePlatformTab(platform,allowed);document.getElementById(`connector-setup-${platform}`)?.scrollIntoView({behavior:'smooth',block:'start'});}));}
function connectorTerminology(){return `<aside class="term-box"><h4>Terminología y recomendaciones</h4><ul><li><strong>Paper:</strong> simulación sin dinero real (ideal para validar estrategia).</li><li><strong>Live:</strong> órdenes reales con capital real (usar solo tras validar en paper).</li><li><strong>Signal:</strong> solo recibe/genera señales sin ejecutar automáticamente.</li><li><strong>Spot:</strong> compra/venta directa del activo.</li><li><strong>Futures:</strong> derivados con apalancamiento (mayor riesgo).</li><li><strong>Combinación recomendada:</strong> inicia en <span class="market-mini">Paper + Spot</span> y escala a <span class="market-mini">Live + Spot</span> antes de usar futures.</li></ul></aside>`;}
function platformForm(platform){const meta=platformMetaFor(platform);const marketTypes=connectorMarketTypesFor(platform);const fields=connectorFieldsFor(platform).map((field)=>connectorFieldMarkup(field)).join('');return `<div class="card"><h2>${meta.display_name||platform.toUpperCase()}</h2><p class="hint">Solo visible porque está activado por admin para tu cuenta.</p><div class="connector-layout"><form class="connector-form form-grid" data-platform="${platform}"><label>Etiqueta<input name="label" required placeholder="Cuenta principal"></label><label>Modo de operación<select name="mode"><option value="paper">paper (simulado)</option><option value="live">live (real)</option><option value="signal">signal (solo señales)</option></select></label><label>Tipo de mercado<select name="market_type">${marketTypes.map(m=>`<option value="${m}">${m}</option>`).join('')}</select></label><small class="hint">Los símbolos ya no se configuran aquí. Se eligen dentro de Estrategias para evitar duplicados y conflictos entre tabs.</small><div class="form-grid">${fields}</div><button class="btn primary" type="submit">Guardar conector ${platform.toUpperCase()}</button></form><div class="connector-help-stack">${connectorTerminology()}${connectorSetupGuide(platform)}</div></div><div id="list-${platform}" class="stack" style="margin-top:12px;"></div></div>`;}
function bindPlatformForms(){document.querySelectorAll('.connector-form').forEach((form)=>form.addEventListener('submit',async(e)=>{e.preventDefault();try{const payload=buildConnectorPayload(form,{includeSecrets:true});await api('/api/connectors',{method:'POST',body:JSON.stringify(payload)});form.reset();showToast('Conector guardado correctamente.');await refreshDashboard();}catch(err){setRunFeedback(parseApiError(err),'error');}}));}

function applyStrategyControlUI(){const select=document.querySelector('select[name="strategy_slug"]');const hint=document.getElementById('strategy-managed-hint');if(!select)return;const visibleOptions=Array.from(select.options);const allowed=STRATEGY_CONTROL.allowed_strategies?.length?STRATEGY_CONTROL.allowed_strategies:visibleOptions.map(o=>o.value);visibleOptions.forEach(option=>{option.hidden=!allowed.includes(option.value);option.disabled=!allowed.includes(option.value);});const firstAllowed=visibleOptions.find((option)=>!option.disabled)?.value||'';if(!allowed.includes(select.value)&&firstAllowed) select.value=firstAllowed;select.disabled=!!STRATEGY_CONTROL.managed_by_admin;if(hint){const selectionLabel=selectedMarketTypes().join(' + ');const baseHint=STRATEGY_CONTROL.managed_by_admin?'Estrategia gestionada por administrador para esta cuenta.':'Puedes elegir entre las estrategias habilitadas para tu cuenta.';hint.textContent=`${baseHint} Mercado seleccionado: ${selectionLabel}.`;if(!firstAllowed)hint.textContent=`No hay estrategias compatibles con la selección actual (${selectionLabel}).`; }renderStrategyEditors();renderStrategyGuidance();}
function selectedRunConnectors(){const ids=selectedRunConnectorIds();return ids.map((id)=>(DASHBOARD_CACHE.connectors||[]).find((item)=>item.id===id)).filter(Boolean);}
function renderStrategyGuidance(){const slug=String(document.querySelector('select[name="strategy_slug"]')?.value||'');const guide=STRATEGY_NUMERIC_GUIDES[slug]||STRATEGY_NUMERIC_GUIDES.default;const meta=STRATEGY_LIBRARY[slug]||{};const node=document.getElementById('strategy-dynamic-guidance');const connectors=selectedRunConnectors();const primaryConnector=connectors[0]||activeConnectorForMarket();const connectorLabel=primaryConnector?`${primaryConnector.label} · ${String(primaryConnector.platform||'-').toUpperCase()} / ${primaryConnector.market_type||'spot'}`:'Sin conector seleccionado';const timeframe=String(document.querySelector('#run-form input[name="timeframe"]')?.value||'1h');const timeframeMinutes=timeframeToMinutes(timeframe);const timeframeProfile=timeframeMinutes<=5?'Scalping / ejecución rápida':timeframeMinutes<=15?'Intradía / momentum controlado':timeframeMinutes<=60?'Swing corto / confirmación extra':'Posicional / menor frecuencia';const marketSelection=[...new Set([...(selectedMarketTypes()||[]),selectedRunMarketTypePreference()].filter(Boolean))].join(' + ');const checklist=[primaryConnector?`Confirma que ${primaryConnector.label} esté en ${primaryConnector.mode||'paper'} y con mercado ${primaryConnector.market_type||'spot'}.`:'Selecciona un conector antes de ejecutar o activar el bot.',meta.useCase?`La estrategia rinde mejor en: ${meta.useCase}`:'Valida la lógica con paper trading y logs recientes antes de mover capital real.',`Timeframe ${timeframe}: ${timeframeProfile}. ${timeframeMinutes<=5?'Usa TP/SL más ceñidos y evita demasiados símbolos a la vez.':timeframeMinutes>=60?'Prioriza menos señales pero mejor filtradas y con confirmación de tendencia.':'Balancea frecuencia y calidad de señal con monitoreo continuo.'}`,`Conector + estrategia + timeframe deben estar alineados. Si cambias de spot a futures, vuelve a validar leverage, SL y símbolos.`];if(node){node.innerHTML=`<strong>Guía dinámica para ${meta.name||slug||'la estrategia seleccionada'}</strong><p class="hint">Esta guía te ayuda a dejar el setup funcional y competitivo según conector, estrategia y timeframe. No garantiza ganancias, pero sí reduce errores de configuración.</p><div class="strategy-guidance-kpis"><article class="strategy-guidance-kpi"><small>Conector activo</small><strong>${connectorLabel}</strong></article><article class="strategy-guidance-kpi"><small>Mercado objetivo</small><strong>${marketSelection||'No definido'}</strong></article><article class="strategy-guidance-kpi"><small>Timeframe</small><strong>${timeframe} · ${timeframeProfile}</strong></article><article class="strategy-guidance-kpi"><small>Compatibilidad</small><strong>${meta.marketTypes?meta.marketTypes.join(' / '):'Spot y futures'}</strong></article></div><h4>Rangos sugeridos</h4><ul><li><b>Riesgo por trade:</b> ${guide.risk.join(' · ')}</li><li><b>Probabilidad ML:</b> ${guide.ml.join(' · ')}</li><li><b>Take profit:</b> ${guide.tp.join(' · ')}</li><li><b>Stop loss:</b> ${guide.sl.join(' · ')}</li><li><b>Trailing:</b> ${guide.trailing.join(' · ')}</li><li><b>Máx. posiciones:</b> ${guide.positions.join(' · ')}</li></ul><h4>Checklist operativo</h4><ul>${checklist.map((item)=>`<li>${item}</li>`).join('')}</ul>`;}const form=document.getElementById('run-form');if(!form)return;const risk=form.querySelector('input[name="risk_per_trade_percent"]');const ml=form.querySelector('input[name="min_ml_probability_percent"]');const tp=form.querySelector('input[name="take_profit_value"]');const sl=form.querySelector('input[name="stop_loss_value"]');const trailing=form.querySelector('input[name="trailing_stop_value"]');if(risk)risk.placeholder=guide.risk[1]||'';if(ml)ml.placeholder=guide.ml[1]||'';if(tp)tp.placeholder=guide.tp[1]||'';if(sl)sl.placeholder=guide.sl[1]||'';if(trailing)trailing.placeholder=guide.trailing[1]||'';}


function strategyMetaFor(slug){return STRATEGY_LIBRARY[slug]||{name:slug};}
function renderStrategyEditors(){const node=document.getElementById('profile-strategy-checks');if(!node)return;const allowed=STRATEGY_CONTROL.allowed_strategies?.length?STRATEGY_CONTROL.allowed_strategies:Object.keys(STRATEGY_LIBRARY);node.innerHTML=Object.keys(STRATEGY_LIBRARY).map((slug)=>{const meta=strategyMetaFor(slug);const checked=allowed.includes(slug)?'checked':'';const disabled=STRATEGY_CONTROL.managed_by_admin?'disabled':'';return `<label class="checkbox"><input type="checkbox" name="allowed_strategies" value="${slug}" ${checked} ${disabled}> ${meta.name}</label>`;}).join('');const feedbackNode=document.getElementById('profile-strategy-feedback');if(feedbackNode){feedbackNode.className='hint';feedbackNode.textContent=STRATEGY_CONTROL.managed_by_admin?'Estas estrategias son gestionadas por el administrador.':'Selecciona las estrategias activas que quieres mantener habilitadas.';}}
async function saveStrategySelection(e){e.preventDefault();const form=e.target;const feedback=document.getElementById('profile-strategy-feedback');const allowed=Array.from(form.querySelectorAll('input[name="allowed_strategies"]:checked')).map((n)=>n.value);try{const data=await api('/api/strategy-control',{method:'PUT',body:JSON.stringify({allowed_strategies:allowed})});STRATEGY_CONTROL=data;applyStrategyControlUI();if(feedback){feedback.textContent='Estrategias activas actualizadas.';feedback.className='status-msg status-ok';}}catch(err){if(feedback){feedback.textContent=parseApiError(err);feedback.className='status-msg status-error';}}}

function daysForFilter(v){if(v==='day')return 1;if(v==='month')return 30;return 7;}
function detectUserLocale(){return (navigator.languages&&navigator.languages[0])||navigator.language||'es-ES';}
function formatLocalDateTime(value){if(!value)return '-';const d=new Date(value);if(Number.isNaN(d.getTime()))return '-';return d.toLocaleString(detectUserLocale());}
function formatLocalTimeNow(){return new Date().toLocaleTimeString(detectUserLocale());}
function minutesSince(value){if(!value)return Number.POSITIVE_INFINITY;const time=new Date(value).getTime();if(Number.isNaN(time))return Number.POSITIVE_INFINITY;return Math.max(0,(Date.now()-time)/60000);}
function syncExecutiveBadge(){const map={day:'Día',week:'Semana',month:'Mes'};const value=document.getElementById('trade-range-filter')?.value||'week';setNodeText('reports-range-badge',map[value]||'Semana');}
function telemetryFilteredLogs(){const logs=Array.isArray(DASHBOARD_CACHE.executionLogs)?DASHBOARD_CACHE.executionLogs:[];const symbolFilter=String(TELEMETRY_FILTER.symbol||'').trim().toLowerCase();return logs.filter((item)=>{const symbol=String(item?.symbol||'').toLowerCase();return !symbolFilter||symbol.includes(symbolFilter);}).slice(0,Math.max(1,Number(TELEMETRY_FILTER.limit||EXECUTION_LOG_LIMIT)));}
function syncTelemetryControls(){const limitEl=document.getElementById('decision-telemetry-limit');const symbolEl=document.getElementById('decision-telemetry-symbol');if(limitEl)limitEl.value=String(TELEMETRY_FILTER.limit||TELEMETRY_FILTER_DEFAULTS.limit);if(symbolEl)symbolEl.value=TELEMETRY_FILTER.symbol||'';}
function initTelemetryControls(){syncTelemetryControls();document.getElementById('decision-telemetry-limit')?.addEventListener('change',(e)=>{TELEMETRY_FILTER.limit=Math.max(1,Number(e.target.value||TELEMETRY_FILTER_DEFAULTS.limit));renderDecisionTelemetry();});document.getElementById('decision-telemetry-symbol')?.addEventListener('input',(e)=>{TELEMETRY_FILTER.symbol=String(e.target.value||'');renderDecisionTelemetry();});}
function renderDecisionTelemetry(){const node=document.getElementById('decision-breakdown-panel');if(!node)return;const logs=telemetryFilteredLogs();syncTelemetryControls();if(!logs.length){node.innerHTML=reportMarkup([{title:'Sin telemetría reciente',body:'No hay eventos para el filtro actual. Ejecuta una estrategia, amplía la ventana o limpia el símbolo buscado.'}]);setNodeText('decision-report-state','0 eventos');return;}const decisionCount=logs.reduce((acc,item)=>{const key=String(decisionLabel(item)||'sin_decision').toLowerCase();acc[key]=(acc[key]||0)+1;return acc;},{});const statusCount=logs.reduce((acc,item)=>{const key=String(item?.status||'sin_estado').toLowerCase();acc[key]=(acc[key]||0)+1;return acc;},{});const topDecisions=Object.entries(decisionCount).sort((a,b)=>b[1]-a[1]).slice(0,3);const lastLog=logs[0];const dominantStatus=Object.entries(statusCount).sort((a,b)=>b[1]-a[1])[0];node.innerHTML=reportMarkup([{title:'Última evaluación',body:`${decisionLabel(lastLog)} · ${lastLog.symbol||'Sin símbolo'} · ${formatLocalDateTime(lastLog.created_at)}`},{title:'Estado dominante',body:dominantStatus?`${dominantStatus[0].replaceAll('_',' ')} · ${dominantStatus[1]} eventos en la muestra.`:'Sin estado dominante.'},{title:'Cómo usar esta telemetría',body:'Si predominan hold, skipped o rejected, revisa universo de símbolos, compatibilidad del conector, calidad del dato y umbrales ML antes de subir riesgo.'},...topDecisions.map(([label,count])=>({title:label.replaceAll('_',' '),body:`${count} eventos dentro de una ventana filtrada de ${logs.length} logs.`}))]);setNodeText('decision-report-state',`${logs.length} eventos filtrados`);}
function renderQuantumStatus(){const summary=DASHBOARD_CACHE.summary||{};const connectors=Array.isArray(DASHBOARD_CACHE.connectors)?DASHBOARD_CACHE.connectors:[];const trades=Array.isArray(DASHBOARD_CACHE.trades)?DASHBOARD_CACHE.trades:[];const logs=Array.isArray(DASHBOARD_CACHE.executionLogs)?DASHBOARD_CACHE.executionLogs:[];const liveConnectors=connectors.filter((item)=>item?.is_enabled).length;const totalConnectors=Math.max(connectors.length,1);const recentLogMinutes=minutesSince(logs[0]?.created_at);const syncHealthy=recentLogMinutes<=15;const healthScore=Math.max(8,Math.min(99,Math.round(((liveConnectors/totalConnectors)*55)+(summary.total_trades?20:8)+(syncHealthy?16:4)+(safeNumber(summary.realized_pnl)>=0?8:3))));setNodeText('quant-health-score',`${healthScore}%`);setNodeText('quant-sync-status',syncHealthy?'Sincronizado':'A revisar');setNodeText('quant-live-connectors',String(liveConnectors));setNodeText('quant-last-heartbeat',logs[0]?.created_at?formatLocalDateTime(logs[0].created_at):'Sin eventos');const pill=document.getElementById('quant-health-pill');if(pill){pill.textContent=healthScore>=75?'Operativo':healthScore>=45?'Estable':'Crítico';pill.classList.toggle('pill-on',healthScore>=75);pill.classList.toggle('pill-off',healthScore<75);}const statusStrip=document.getElementById('quant-status-strip');if(statusStrip){statusStrip.innerHTML=reportMarkup([{title:'Cobertura de conectores',body:`${liveConnectors} activos de ${connectors.length} configurados · ${allowedPlatforms().length} plataformas con acceso concedido.`},{title:'Sesiones automatizadas',body:`${(DASHBOARD_CACHE.botSessions||[]).filter((item)=>item?.is_active).length} bots activos · ${(DASHBOARD_CACHE.botSessions||[]).length} sesiones registradas.`},{title:'Exposición PnL',body:`${safeNumber(summary.realized_pnl).toFixed(2)} USD realizados · ${safeNumber(summary.winning_trades)} ganadas / ${safeNumber(summary.losing_trades)} perdidas.`}]);}const connectorPanel=document.getElementById('connector-health-panel');if(connectorPanel){connectorPanel.innerHTML=connectors.length?reportMarkup(connectors.slice(0,6).map((item)=>({title:`${item.label||'Conector'} · ${item.platform||'-'}`,body:`${item.is_enabled?'Activo':'Inactivo'} · ${item.mode||'-'} / ${item.market_type||'-'} · ${(Array.isArray(item.symbols)?item.symbols.length:0)} símbolos monitoreados`}))):reportMarkup([{title:'Sin conectores',body:'Crea al menos un conector para visualizar estado operativo por canal.'}]);}const execPanel=document.getElementById('executive-report-panel');if(execPanel){execPanel.innerHTML=reportMarkup([{title:'Actividad reciente',body:`${trades.length} trades históricos cargados · ${logs.length} logs operativos disponibles para auditoría rápida.`},{title:'Distribución por plataformas',body:Object.entries(summary.platforms||{}).length?Object.entries(summary.platforms||{}).map(([platform,count])=>`${platform}: ${count}`).join(' · '):'Sin actividad por plataforma todavía.'},{title:'Cadencia del reporte',body:`Rango activo: ${document.getElementById('reports-range-badge')?.textContent||'Semana'} · Última actualización UI: ${formatLocalTimeNow()}`}]);}}
function detectSessionMarketType(item){const explicit=String(item.market_type||item.connector_market_type||'').toLowerCase();if(explicit)return explicit.includes('future')?'futures':explicit.includes('spot')?'spot':explicit;const raw=[item.mode,item.connector_mode,item.connector_label,item.connector_name].filter(Boolean).join(' ').toLowerCase();return raw.includes('future')?'futures':'spot';}
function sortedSymbols(symbols){return (Array.isArray(symbols)?symbols:[]).map((s)=>String(s||'').trim()).filter(Boolean).sort((a,b)=>a.localeCompare(b));}
function renderTrades(){const range=document.getElementById('trade-range-filter')?.value||'week';const days=daysForFilter(range);const since=Date.now()-days*24*60*60*1000;const trades=DASHBOARD_CACHE.trades.filter((t)=>new Date(t.created_at).getTime()>=since);const tbody=document.querySelector('#trades-table tbody');if(tbody){if(!trades.length){tbody.innerHTML='<tr><td colspan="6"><small class="hint">No hay transacciones reales en este rango.</small></td></tr>';}else{tbody.innerHTML=trades.map(t=>{const inv=Number(t.investment_amount||0);const pnl=Number(t.pnl)||0;const result=pnl>0?'Ganó':pnl<0?'Perdió':'Sin cierre PNL';return `<tr><td>${formatLocalDateTime(t.created_at)}</td><td>${t.platform}</td><td>${t.symbol}</td><td>${inv.toFixed(2)}</td><td>${result}</td><td>${pnl.toFixed(2)}</td></tr>`;}).join('');}}const totalInv=trades.reduce((a,t)=>a+Number(t.investment_amount||0),0);const wins=trades.filter((t)=>(Number(t.pnl)||0)>0).length;const avg=trades.length?trades.reduce((a,t)=>a+(Number(t.pnl)||0),0)/trades.length:0;const pnlTotal=trades.reduce((a,t)=>a+(Number(t.pnl)||0),0);const metrics=document.getElementById('trade-metrics');if(metrics){metrics.innerHTML=`<div class="metric"><small>Operaciones</small><strong>${trades.length}</strong></div><div class="metric"><small>Capital real estimado</small><strong>${totalInv.toFixed(2)}</strong></div><div class="metric"><small>Ganadas</small><strong>${wins}</strong></div><div class="metric"><small>PNL promedio</small><strong>${avg.toFixed(2)}</strong></div><div class="metric"><small>PNL acumulado</small><strong>${pnlTotal.toFixed(2)}</strong></div>`;}}

function renderEconomicSummary(){const sessions=DASHBOARD_CACHE.botSessions||[];const activeSessions=sessions.filter((s)=>s&&s.is_active);const apps=new Set(activeSessions.map((s)=>String(s.platform||'').toLowerCase()).filter(Boolean));const avgSymbols=activeSessions.length?activeSessions.reduce((acc,s)=>acc+(Array.isArray(s.symbols)?s.symbols.length:0),0)/activeSessions.length:0;const appsEl=document.getElementById('eco-active-apps');const symbolsEl=document.getElementById('eco-symbols-per-app');const strategiesEl=document.getElementById('eco-active-strategies');if(appsEl)appsEl.textContent=String(apps.size);if(symbolsEl)symbolsEl.textContent=avgSymbols.toFixed(1);if(strategiesEl)strategiesEl.textContent=String(new Set(activeSessions.map((item)=>item.strategy_slug||'unknown')).size);const list=document.getElementById('strategy-performance-list');if(!list)return;if(!activeSessions.length){list.innerHTML='<small class="hint">Vista simplificada: aquí solo verás métricas generales del panel, sin nombres ni porcentajes por estrategia.</small>';return;}const botCount=activeSessions.length;const queuedCount=activeSessions.filter((item)=>String(item.last_status||'').toLowerCase()==='queued').length;const withErrors=activeSessions.filter((item)=>String(item.last_status||'').toLowerCase()==='error').length;list.innerHTML=[`<div class="strategy-performance-item"><div><strong>Resumen operativo</strong><small class="hint">Sin nombres ni porcentajes individuales</small></div><div class="strategy-performance-metric"><span>${botCount} bots</span></div></div>`,`<div class="strategy-performance-item"><div><strong>Símbolos cubiertos</strong><small class="hint">Universo promedio por app activa</small></div><div class="strategy-performance-metric"><span>${avgSymbols.toFixed(1)} símbolos/app</span></div></div>`,`<div class="strategy-performance-item"><div><strong>Estado de sesiones</strong><small class="hint">Cola inicial y errores detectados</small></div><div class="strategy-performance-metric"><span>${queuedCount} en cola · ${withErrors} con error</span></div></div>`].join('');}
function candleToText(candle){if(!candle||typeof candle!=='object')return '-';const o=Number(candle.open||0).toFixed(4);const h=Number(candle.high||0).toFixed(4);const l=Number(candle.low||0).toFixed(4);const c=Number(candle.close||0).toFixed(4);return `O:${o} H:${h} L:${l} C:${c}`;}
function candleFromNotes(note){if(!note||typeof note!=='object')return null;return note.candle||note?.scanner?.candle||null;}
function decisionLabel(item){const decision=String(item?.notes?.decision||'').toLowerCase();if(decision==='buy')return 'Compró';if(decision==='sell')return 'Vendió';if(decision==='no_action')return 'Sin acción';return '-';}
function setExecutionLogsMeta(message){const meta=document.getElementById('execution-logs-refresh-meta');if(meta)meta.textContent=message;}

function strategyName(slug){return STRATEGY_LIBRARY[slug]?.name||slug;}
function botStatusLabel(session){if(!session.is_active)return t('paused','Pausado');if(session.last_status==='ok')return t('active','Activo');if(session.last_status==='error')return t('operational_error','Error operativo: {error}',{error:session.last_error||'revisar logs'});if(session.last_status==='queued'||session.last_status==='scheduled'||session.last_status==='cloned'||session.last_status==='from_template')return t('pending_first_run','Pendiente de primera corrida');return session.last_status||t('active','Activo');}
async function setBotSessionActive(id,isActive){try{await api(`/api/bot-sessions/${id}`,{method:'PUT',body:JSON.stringify({is_active:isActive})});showToast(isActive?t('bot_resumed','Bot reanudado correctamente.'):t('bot_paused','Bot pausado correctamente.'));await refreshBotSessions();}catch(err){showToast(parseApiError(err),'error');}}
async function deleteBotSession(id){try{await api(`/api/bot-sessions/${id}`,{method:'DELETE'});showToast(t('bot_deleted','Bot eliminado correctamente.'));await refreshBotSessions();}catch(err){showToast(parseApiError(err),'error');}}
function activeConnectorForMarket(){const selected=selectedRunConnectorIds();if(selected.length){const picked=(DASHBOARD_CACHE.connectors||[]).find((c)=>c.id===selected[0]);if(picked)return picked;}return (DASHBOARD_CACHE.connectors||[]).find((c)=>c.is_enabled)||(DASHBOARD_CACHE.connectors||[])[0]||null;}
function renderLiveStrategiesPanel(){const panel=document.getElementById('strategies-live-panel');const countNode=document.getElementById('strategies-live-count');if(!panel)return;const sessions=(DASHBOARD_CACHE.botSessions||[]).filter((item)=>item.is_active);if(countNode)countNode.textContent=t('active_count','{count} activas',{count:sessions.length});if(!sessions.length){panel.innerHTML=`<small class="hint">${t('no_live_strategies','No hay estrategias en ejecución ahora mismo.')}</small>`;return;}const grouped={};sessions.forEach((item)=>{const platform=(item.platform||'sin app').toUpperCase();const market=detectSessionMarketType(item);if(!grouped[platform])grouped[platform]={spot:[],futures:[]};grouped[platform][market].push(item);});panel.innerHTML=Object.entries(grouped).sort((a,b)=>a[0].localeCompare(b[0])).map(([platform,markets])=>{const marketBlock=(type,label)=>{const rows=(markets[type]||[]).slice().sort((a,b)=>strategyName(a.strategy_slug).localeCompare(strategyName(b.strategy_slug)));if(!rows.length){return `<div class="strategy-live-market"><strong>${label}</strong><small class="hint">${t('no_active_strategies','Sin estrategias activas.')}</small></div>`;}return `<div class="strategy-live-market"><strong>${label} · ${rows.length}</strong><ul>${rows.map((item)=>`<li>${strategyName(item.strategy_slug)} · ${t('symbols_count','símbolos: {count}',{count:sortedSymbols(item.symbols).length})}</li>`).join('')}</ul></div>`;};return `<article class="strategy-live-app"><h4>${platform}</h4><div class="strategy-live-market-grid">${marketBlock('spot','Spot')}${marketBlock('futures','Futures')}</div></article>`;}).join('');}
async function editBotSession(id){const current=(DASHBOARD_CACHE.botSessions||[]).find((item)=>item.id===id);if(!current)return;const currentMarket=String(current.market_type||'spot');const compatible=Object.entries(STRATEGY_LIBRARY).filter(([_,meta])=>!meta.marketTypes||meta.marketTypes.includes(currentMarket));const currentTradeAmountMode=String(current.trade_amount_mode||'inherit');const modal=document.createElement('div');modal.className='modal';modal.innerHTML=`<div class="modal-card card strategy-modal-card"><div class="modal-head"><h3>Editar estrategia activa</h3><button class="btn" type="button" id="close-edit-session">Cerrar</button></div><form id="edit-session-form" class="form-grid"><label>Tipo de mercado<select name="market_type" id="edit-session-market-type"><option value="spot" ${currentMarket==='spot'?'selected':''}>Spot</option><option value="futures" ${currentMarket==='futures'?'selected':''}>Futures</option><option value="cfd" ${currentMarket==='cfd'?'selected':''}>CFD</option><option value="forex" ${currentMarket==='forex'?'selected':''}>Forex</option><option value="signals" ${currentMarket==='signals'?'selected':''}>Signals</option></select></label><label>Estrategia<select name="strategy_slug" id="edit-session-strategy">${compatible.map(([slug,meta])=>`<option value="${slug}" ${current.strategy_slug===slug?'selected':''}>${meta.name}</option>`).join('')}</select></label><label>Timeframe<input name="timeframe" value="${current.timeframe||'5m'}"/></label><label>Símbolos (coma)<input name="symbols" value="${(current.symbols||[]).join(',')}"/></label><label>Asignación por trade<select name="trade_amount_mode" id="edit-session-trade-amount-mode"><option value="inherit" ${currentTradeAmountMode==='inherit'?'selected':''}>Usar perfil global</option><option value="fixed_usd" ${currentTradeAmountMode==='fixed_usd'?'selected':''}>Cantidad fija</option><option value="balance_percent" ${currentTradeAmountMode==='balance_percent'?'selected':''}>Porcentaje del balance</option></select></label><label id="edit-session-amount-per-trade-wrap">Cantidad por trade<input name="amount_per_trade" id="edit-session-amount-per-trade" type="number" step="0.01" min="0.01" value="${Number(current.amount_per_trade||0)||''}"/></label><label id="edit-session-amount-percentage-wrap">Porcentaje por trade<input name="amount_percentage" id="edit-session-amount-percentage" type="number" step="0.1" min="0.1" max="100" value="${Number(current.amount_percentage||0)||''}"/></label><label>Take Win<div class="row-wrap"><select name="take_profit_mode"><option value="percent" ${(current.take_profit_mode||'percent')==='percent'?'selected':''}>%</option><option value="usdt" ${(current.take_profit_mode||'percent')==='usdt'?'selected':''}>USDT</option></select><input name="take_profit_value" type="number" step="0.1" min="0.1" value="${Number(current.take_profit_value||1.5)}"/></div></label><label>Stop Loss<div class="row-wrap"><select name="stop_loss_mode"><option value="percent" ${(current.stop_loss_mode||'percent')==='percent'?'selected':''}>%</option><option value="usdt" ${(current.stop_loss_mode||'percent')==='usdt'?'selected':''}>USDT</option></select><input name="stop_loss_value" type="number" step="0.1" min="0.1" value="${Number(current.stop_loss_value||1.0)}"/></div></label><label>Trailing Stop<div class="row-wrap"><select name="trailing_stop_mode"><option value="percent" ${(current.trailing_stop_mode||'percent')==='percent'?'selected':''}>%</option><option value="usdt" ${(current.trailing_stop_mode||'percent')==='usdt'?'selected':''}>USDT</option></select><input name="trailing_stop_value" type="number" step="0.1" min="0.1" value="${Number(current.trailing_stop_value||0.8)}"/></div></label><label>Máx. posiciones<input name="max_open_positions" type="number" min="1" max="20" value="${Number(current.max_open_positions||1)}"/></label><label class="checkbox"><input type="checkbox" name="indicator_exit_enabled" ${current.indicator_exit_enabled?'checked':''}/> Cierre por indicador</label><button class="btn primary" type="submit">Guardar cambios</button></form></div>`;document.body.appendChild(modal);const close=()=>modal.remove();const strategySelect=()=>modal.querySelector('#edit-session-strategy');const syncTradeAmountUI=()=>{const mode=String(modal.querySelector('#edit-session-trade-amount-mode')?.value||'inherit');const amountWrap=modal.querySelector('#edit-session-amount-per-trade-wrap');const percentageWrap=modal.querySelector('#edit-session-amount-percentage-wrap');const amountInput=modal.querySelector('#edit-session-amount-per-trade');const percentageInput=modal.querySelector('#edit-session-amount-percentage');if(amountWrap)amountWrap.hidden=mode!=='fixed_usd';if(percentageWrap)percentageWrap.hidden=mode!=='balance_percent';if(amountInput)amountInput.required=mode==='fixed_usd';if(percentageInput)percentageInput.required=mode==='balance_percent';};const syncStrategyOptions=(marketType)=>{const options=Object.entries(STRATEGY_LIBRARY).filter(([_,meta])=>!meta.marketTypes||meta.marketTypes.includes(marketType));const select=strategySelect();if(!select)return;const previous=select.value;select.innerHTML=options.map(([slug,meta])=>`<option value="${slug}">${meta.name}</option>`).join('');if(options.some(([slug])=>slug===previous))select.value=previous;};modal.querySelector('#edit-session-market-type')?.addEventListener('change',(event)=>syncStrategyOptions(String(event.target.value||'spot')));modal.querySelector('#edit-session-trade-amount-mode')?.addEventListener('change',syncTradeAmountUI);modal.querySelector('#close-edit-session').addEventListener('click',close);modal.addEventListener('click',(e)=>{if(e.target===modal)close();});syncTradeAmountUI();modal.querySelector('#edit-session-form').addEventListener('submit',async(e)=>{e.preventDefault();const fd=new FormData(e.target);const timeframe=String(fd.get('timeframe')||'5m');const interval=timeframeToMinutes(timeframe);await api(`/api/bot-sessions/${id}`,{method:'PUT',body:JSON.stringify({market_type:String(fd.get('market_type')||'spot'),strategy_slug:String(fd.get('strategy_slug')||current.strategy_slug),timeframe,symbols:parseCsv(fd.get('symbols')),interval_minutes:interval,trade_amount_mode:String(fd.get('trade_amount_mode')||'inherit'),amount_per_trade:fd.get('trade_amount_mode')==='fixed_usd'?Number(fd.get('amount_per_trade')):null,amount_percentage:fd.get('trade_amount_mode')==='balance_percent'?Number(fd.get('amount_percentage')):null,take_profit_mode:fd.get('take_profit_mode'),take_profit_value:Number(fd.get('take_profit_value')),stop_loss_mode:fd.get('stop_loss_mode'),stop_loss_value:Number(fd.get('stop_loss_value')),trailing_stop_mode:fd.get('trailing_stop_mode'),trailing_stop_value:Number(fd.get('trailing_stop_value')),max_open_positions:Number(fd.get('max_open_positions')||1),indicator_exit_enabled:fd.get('indicator_exit_enabled')==='on'})});close();showToast('Bot actualizado correctamente.');await refreshBotSessions();await refreshExecutionLogs();});}
function renderBotSessions(){const tbody=document.querySelector('#bot-sessions-table tbody');if(!tbody)return;const rows=DASHBOARD_CACHE.botSessions||[];if(!rows.length){tbody.innerHTML=`<tr><td colspan="9"><small class="hint">${t('no_bots_yet','No hay bots activos todavía. Activa uno desde "Ejecutar estrategia".')}</small></td></tr>`;return;}tbody.innerHTML=rows.map((item)=>{const capitalValue=Number(item.capital_display_value??item.capital_per_operation||0);const capitalUnit=String(item.capital_display_unit||item.capital_currency||'USDT');const capitalLabel=item.capital_display_mode==='balance_percent'?`${capitalValue.toFixed(2)}${capitalUnit}`:`${capitalValue.toFixed(2)} ${capitalUnit}`;const capitalHint=item.capital_display_mode==='balance_percent'?'Porcentaje del balance por operación':t('capital_per_trade','Capital por operación');return `<tr data-session-id="${item.id}"><td>${item.connector_label||'-'}</td><td>${item.platform||'-'} (${item.mode||'-'} · ${item.market_type||'spot'})</td><td>${(item.symbols||[]).join(', ')||'-'}</td><td>${strategyName(item.strategy_slug)}<br><small class="hint">TF ${item.timeframe||'-'} · Máx. posiciones ${Number(item.max_open_positions||1)} · ${item.symbol_source_mode==='dynamic'?t('dynamic_top','Dinámico top {count}',{count:Number(item.dynamic_symbol_limit||0)}):t('manual','Manual')}</small></td><td>${capitalLabel}<br><small class="hint">${capitalHint}</small></td><td>${t('every_minutes','Cada {minutes} min',{minutes:item.interval_minutes||5})}</td><td>${botStatusLabel(item)}</td><td>${formatLocalDateTime(item.last_run_at)}</td><td><div class="row-wrap"><button class="btn btn-sm" onclick="setBotSessionActive(${item.id}, ${!item.is_active})">${item.is_active?t('pause','Pausar'):t('resume','Reanudar')}</button><button class="btn btn-sm" onclick="editBotSession(${item.id})">${t('edit','Editar')}</button><button class="btn btn-sm" onclick="deleteBotSession(${item.id})">${t('delete','Eliminar')}</button></div></td></tr>`;}).join('');}
async function refreshBotSessions(){try{const rows=await api('/api/bot-sessions');DASHBOARD_CACHE.botSessions=Array.isArray(rows)?rows:[];renderBotSessions();renderLiveStrategiesPanel();renderQuantumStatus();}catch(err){const tbody=document.querySelector('#bot-sessions-table tbody');if(tbody)tbody.innerHTML=`<tr><td colspan="9"><div class="status-msg status-error">${t('bots_load_failed','No se pudieron cargar bots: {error}',{error:parseApiError(err)})}</div></td></tr>`;}}
function setRunFeedback(message,type='ok'){const box=document.getElementById('run-feedback');if(!box)return;box.hidden=false;box.textContent=message;box.classList.remove('status-ok','status-error');box.classList.add(type==='error'?'status-error':'status-ok');showToast(message,type==='error'?'error':'ok');}
function selectedPlatformPolicy(){const connector=activeConnectorForMarket();if(!connector)return null;return (METADATA.platforms||[]).find((item)=>item.platform===connector.platform)||null;}
function currentDynamicLimit(){return Math.max(1,Number(document.getElementById('dynamic-symbol-limit')?.value||20));}
function getDynamicSymbolUniverse(){const connector=activeConnectorForMarket();const policy=selectedPlatformPolicy();const top=Array.isArray(policy?.top_symbols)?policy.top_symbols:[];const allowed=Array.isArray(policy?.allowed_symbols)?policy.allowed_symbols:[];const catalog=Array.isArray(SYMBOL_CATALOG_CACHE[connector?.id]?.symbols)?SYMBOL_CATALOG_CACHE[connector.id].symbols:[];return [...new Set([...(catalog||[]),...(top||[]),...(allowed||[])].map((item)=>String(item||'').trim()).filter(Boolean))];}
function syncSelectedSymbolsInput(symbols){const input=document.querySelector('#run-form input[name="symbols"]');if(input)input.value=(symbols||[]).join(',');renderSelectedSymbolList(symbols||[]);}
function selectedManualSymbols(){return parseCsv(document.querySelector('#run-form input[name="symbols"]')?.value||'');}
function renderSelectedSymbolList(symbols){const select=document.getElementById('symbol-selected-list');if(select)select.innerHTML=(symbols||[]).map((symbol)=>`<option value="${symbol}">${symbol}</option>`).join('');}
function filterSymbolCatalog(){const list=document.getElementById('symbol-catalog-list');if(!list)return;const q=String(document.getElementById('symbol-search-input')?.value||'').trim().toLowerCase();const universe=getDynamicSymbolUniverse().filter((symbol)=>!q||symbol.toLowerCase().includes(q));list.innerHTML=universe.slice(0,800).map((symbol)=>`<option value="${symbol}">${symbol}</option>`).join('');}
async function loadSymbolCatalog(){const connector=activeConnectorForMarket();const status=document.getElementById('symbol-catalog-status');if(!connector){if(status)status.textContent=t('select_connector_for_catalog','Selecciona un conector para ver su catálogo.');filterSymbolCatalog();return;}if(status)status.textContent=t('loading_symbol_catalog','Cargando catálogo de símbolos...');try{SYMBOL_CATALOG_CACHE[connector.id]=await api(`/api/connectors/${connector.id}/symbols-catalog`);const cached=SYMBOL_CATALOG_CACHE[connector.id]||{};if(status)status.textContent=t('symbol_catalog_source','{count} símbolos · fuente {source}',{count:cached.count||0,source:cached.source||'local'});}catch(err){delete SYMBOL_CATALOG_CACHE[connector.id];const fallbackUniverse=getDynamicSymbolUniverse();if(status)status.textContent=fallbackUniverse.length?t('local_catalog','Catálogo local: {count} símbolos sugeridos para {market}.',{count:fallbackUniverse.length,market:String(connector.market_type||'spot').toUpperCase()}):t('remote_catalog_failed','No se pudo cargar el catálogo remoto. Usa selección manual y valida el conector.');}filterSymbolCatalog();}
function addSelectedSymbols(){const picked=Array.from(document.getElementById('symbol-catalog-list')?.selectedOptions||[]).map((option)=>option.value);const merged=[...new Set([...selectedManualSymbols(),...picked])];syncSelectedSymbolsInput(merged);}
function removeSelectedSymbols(){const selectedToRemove=new Set(Array.from(document.getElementById('symbol-selected-list')?.selectedOptions||[]).map((option)=>option.value));syncSelectedSymbolsInput(selectedManualSymbols().filter((symbol)=>!selectedToRemove.has(symbol)));}
function clearSelectedSymbols(){syncSelectedSymbolsInput([]);}
function resolveRunSymbols(fd){const mode=String(fd.get('symbol_source_mode')||'manual');const dynamicLimit=Math.max(1,Number(fd.get('dynamic_symbol_limit')||20));if(mode==='dynamic')return getDynamicSymbolUniverse().slice(0,dynamicLimit);return parseCsv(fd.get('symbols'));}
function updateSymbolSourceUI(){const mode=String(document.getElementById('symbol-source-mode')?.value||'manual');const symbolsInput=document.querySelector('#run-form input[name="symbols"]');const help=document.getElementById('symbol-source-help');const dynamicUniverse=getDynamicSymbolUniverse();const dynamicLimit=currentDynamicLimit();const picker=document.querySelector('.symbol-picker-shell');if(symbolsInput){const useDynamic=mode==='dynamic';symbolsInput.required=!useDynamic;symbolsInput.placeholder=useDynamic?(dynamicUniverse.slice(0,dynamicLimit).join(', ')||t('dynamic_universe_placeholder','El universo dinámico se tomará del catálogo del conector seleccionado')):'BTC/USDT,ETH/USDT';}if(picker)picker.classList.toggle('is-disabled',mode==='dynamic');if(help){help.textContent=mode==='dynamic'?(dynamicUniverse.length?t('dynamic_help','Dinámico: se priorizarán los {count} símbolos del catálogo filtrado por mercado del conector.',{count:Math.min(dynamicLimit,dynamicUniverse.length)}):t('dynamic_help_empty','Dinámico: no hay catálogo disponible todavía; prueba el conector o cambia a selección manual.')):t('manual_help','Manual: escribe los pares separados por coma o arma la lista desde el selector inferior.');}}
function buildRunPayload(form,{singleConnector=false}={}){const fd=new FormData(form);const connectorIds=selectedRunConnectorIds();const symbols=resolveRunSymbols(fd);if(!connectorIds.length)throw new Error(t('select_connector_before_continue','Selecciona explícitamente al menos un conector antes de continuar.'));if(singleConnector&&connectorIds.length!==1)throw new Error(t('activate_one_connector','Para activar un bot 24/7 debes dejar exactamente un conector seleccionado. Así evitamos crear bots en la app o mercado equivocados.'));if(!symbols.length)throw new Error(t('no_symbols_available','No hay símbolos disponibles. Configura símbolos manuales o usa un conector con universo dinámico.'));const timeframe=String(fd.get('timeframe')||'5m');const strategySlug=String(fd.get('strategy_slug')||'').trim();const marketType=String(fd.get('market_type')||resolveEffectiveRunMarketType()||'spot');const tradeAmountMode=String(fd.get('trade_amount_mode')||'inherit');if(!strategySlug)throw new Error(t('no_compatible_strategies','No hay estrategias compatibles para {markets}. Ajusta conectores o mercado.',{markets:[...new Set([...(selectedMarketTypes()||[]),marketType].filter(Boolean))].join(' + ')}));const payload={market_type:marketType,symbols,symbol_source_mode:String(fd.get('symbol_source_mode')||'manual'),dynamic_symbol_limit:Math.max(1,Number(fd.get('dynamic_symbol_limit')||20)),timeframe,strategy_slug:strategySlug,risk_per_trade:Number(fd.get('risk_per_trade_percent')),trade_amount_mode:tradeAmountMode,amount_per_trade:tradeAmountMode==='fixed_usd'?Number(fd.get('amount_per_trade')):null,amount_percentage:tradeAmountMode==='balance_percent'?Number(fd.get('amount_percentage')):null,min_ml_probability:Number(fd.get('min_ml_probability_percent')),use_live_if_available:fd.get('use_live_if_available')==='on',take_profit_mode:fd.get('take_profit_mode'),take_profit_value:Number(fd.get('take_profit_value')),stop_loss_mode:fd.get('stop_loss_mode'),stop_loss_value:Number(fd.get('stop_loss_value')),trailing_stop_mode:fd.get('trailing_stop_mode'),trailing_stop_value:Number(fd.get('trailing_stop_value')),indicator_exit_enabled:fd.get('indicator_exit_enabled')==='on',indicator_exit_rule:fd.get('indicator_exit_rule'),leverage_profile:fd.get('leverage_profile')||'none',max_open_positions:Number(fd.get('max_open_positions')||1),compound_growth_enabled:String(fd.get('compound_growth_enabled')).toLowerCase()==='true',atr_volatility_filter_enabled:String(fd.get('atr_volatility_filter_enabled')).toLowerCase()!=='false'};return singleConnector?{connector_id:connectorIds[0],interval_minutes:timeframeToMinutes(timeframe),...payload}:{connector_ids:connectorIds,...payload};}

function renderExecutionLogs(){const tbody=document.querySelector('#execution-logs-table tbody');if(!tbody)return;const rows=(DASHBOARD_CACHE.executionLogs||[]).slice(0,EXECUTION_LOG_LIMIT);if(!rows.length){tbody.innerHTML=`<tr><td colspan="8"><small class="hint">${t('no_logs_yet','Sin logs todavía. Ejecuta una estrategia para comenzar.')}</small></td></tr>`;setExecutionLogsMeta(t('execution_logs_meta_empty','Auto-refresh cada 5 minutos · Mostrando últimos {limit} logs · Sin datos todavía.',{limit:EXECUTION_LOG_LIMIT}));return;}tbody.innerHTML=rows.map((item)=>`<tr><td>${formatLocalDateTime(item.created_at)}</td><td>${item.symbol||'-'}</td><td>${item.timeframe||item?.notes?.timeframe||'-'}</td><td>${item.signal||'-'}</td><td>${decisionLabel(item)}</td><td>${item.status||'-'}</td><td>${Number(item.ml_probability||0).toFixed(3)}</td><td><small>${candleToText(candleFromNotes(item?.notes))}</small></td></tr>`).join('');setExecutionLogsMeta(t('execution_logs_meta','Auto-refresh cada 5 minutos · Mostrando {count} de {limit} logs · Última actualización: {time}',{count:rows.length,limit:EXECUTION_LOG_LIMIT,time:formatLocalTimeNow()}));}
async function refreshExecutionLogs(){try{const logs=await api(`/api/execution-logs?limit=${EXECUTION_LOG_LIMIT}`);DASHBOARD_CACHE.executionLogs=Array.isArray(logs)?logs:[];renderExecutionLogs();renderDecisionTelemetry();renderQuantumStatus();}catch(err){setExecutionLogsMeta(t('execution_logs_refresh_error','Auto-refresh cada 5 minutos · Error al refrescar: {error}',{error:parseApiError(err)}));const tbody=document.querySelector('#execution-logs-table tbody');if(tbody)tbody.innerHTML=`<tr><td colspan="8"><div class="status-msg status-error">${t('logs_load_failed','No se pudieron cargar logs: {error}',{error:parseApiError(err)})}</div></td></tr>`;}}

async function fetchOrFallback(path,fallback){try{return await api(path);}catch(err){console.warn(`[dashboard] ${path} failed`,err);return typeof fallback==='function'?fallback(err):fallback;}}

async function refreshDashboard(){const [connectors,data,trades,executionLogs,botSessions]=await Promise.all([fetchOrFallback('/api/connectors',[]),fetchOrFallback('/api/dashboard',{total_connectors:0,enabled_connectors:0,total_trades:0,realized_pnl:0,platforms:{},winning_trades:0,losing_trades:0,risk_summary:{health_score:100,estimated_open_risk:0,rolling_drawdown_pct:0,kill_switch_armed:false,alerts:[],suggestions:[],by_symbol:[]}}),fetchOrFallback('/api/trades',[]),fetchOrFallback(`/api/execution-logs?limit=${EXECUTION_LOG_LIMIT}`,[]),fetchOrFallback('/api/bot-sessions',[])]);DASHBOARD_CACHE={trades:Array.isArray(trades)?trades:[],summary:data||{},executionLogs:Array.isArray(executionLogs)?executionLogs:[],botSessions:Array.isArray(botSessions)?botSessions:[],connectors:Array.isArray(connectors)?connectors:[]};const statConnectors=document.getElementById('stat-connectors');if(statConnectors)statConnectors.textContent=Number(data?.total_connectors||0);const statEnabled=document.getElementById('stat-enabled');if(statEnabled)statEnabled.textContent=Number(data?.enabled_connectors||0);const statTrades=document.getElementById('stat-trades');if(statTrades)statTrades.textContent=Number(data?.total_trades||0);const statPnl=document.getElementById('stat-pnl');if(statPnl)statPnl.textContent=Number(data?.realized_pnl||0);const runSelect=document.getElementById('run-connector-select');if(runSelect){const marketTypeInput=document.getElementById('run-market-type-filter');if(marketTypeInput&&!marketTypeInput.dataset.bound){marketTypeInput.dataset.bound='true';marketTypeInput.addEventListener('change',()=>{syncRunMarketTypeUI();applyRunMarketPreset();});}runSelect.onchange=()=>{renderStrategySelect();applyRunMarketPreset();renderStrategyGuidance();updateSymbolSourceUI();loadSymbolCatalog();};syncRunMarketTypeUI();await loadSymbolCatalog();}allowedPlatforms().forEach((platform)=>{const el=document.getElementById(`list-${platform}`);if(el)el.innerHTML=(DASHBOARD_CACHE.connectors||[]).filter(c=>c&&c.platform===platform).map(c=>`<div class="connector-item"><div class="row-between"><strong>${c.label||'Connector'}</strong><span class="pill tiny ${c.is_enabled?'pill-on':'pill-off'}">${c.is_enabled?(isEnglishDashboard()?'Active':'Activo'):(isEnglishDashboard()?'Inactive':'Inactivo')}</span></div><div class="connector-meta"><span>${isEnglishDashboard()?'Mode':'Modo'}: ${c.mode||'-'}</span><span>${isEnglishDashboard()?'Market':'Mercado'}: ${c.market_type||'-'}</span><span>${isEnglishDashboard()?'Configuration':'Configuración'}: ${isEnglishDashboard()?'symbols are managed from Strategies':'símbolos gestionados desde Estrategias'}</span></div><div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap;"><button class="btn" onclick="editConnector(${c.id})">${t('edit','Editar')}</button><button class="btn" onclick="testConnector(${c.id})">Test</button><button class="btn" onclick="deleteConnector(${c.id})">${t('delete','Eliminar')}</button></div></div>`).join('')||`<small class="hint">${isEnglishDashboard()?'No connectors yet.':'Sin conectores todavía.'}</small>`;});const tradesForCharts=DASHBOARD_CACHE.trades||[];const pnlByPlatform={};let cumulative=0;const cumulativeLabels=[];const cumulativeValues=[];tradesForCharts.slice().reverse().forEach((t,i)=>{const key=t.platform||'other';pnlByPlatform[key]=(pnlByPlatform[key]||0)+(Number(t.pnl)||0);cumulative+=(Number(t.pnl)||0);cumulativeLabels.push(String(i+1));cumulativeValues.push(Number(cumulative.toFixed(4)));});const pnlCanvas=document.getElementById('pnl-platform-chart');if(pnlCanvas){if(window.pnlPlatformChart)window.pnlPlatformChart.destroy();window.pnlPlatformChart=new Chart(pnlCanvas,{type:'bar',data:{labels:Object.keys(pnlByPlatform),datasets:[{label:'PNL',data:Object.values(pnlByPlatform),backgroundColor:'#38bdf8'}]},options:{plugins:{legend:{labels:{color:'#f4f7fb'}}},scales:{x:{ticks:{color:'#f4f7fb'}},y:{ticks:{color:'#f4f7fb'}}}}});}const winLossCanvas=document.getElementById('win-loss-chart');if(winLossCanvas){if(window.winLossChart)window.winLossChart.destroy();window.winLossChart=new Chart(winLossCanvas,{type:'pie',data:{labels:isEnglishDashboard()?['Wins','Losses','Neutral']:['Ganadas','Perdidas','Neutras'],datasets:[{data:[Number(data?.winning_trades||0),Number(data?.losing_trades||0),Math.max(0,Number(data?.total_trades||0)-Number(data?.winning_trades||0)-Number(data?.losing_trades||0))],backgroundColor:['#22c55e','#ef4444','#94a3b8']}]},options:{plugins:{legend:{labels:{color:'#f4f7fb'}}}}});}const cumulativeCanvas=document.getElementById('pnl-cumulative-chart');if(cumulativeCanvas){if(window.cumulativePnlChart)window.cumulativePnlChart.destroy();window.cumulativePnlChart=new Chart(cumulativeCanvas,{type:'line',data:{labels:cumulativeLabels,datasets:[{label:isEnglishDashboard()?'Cumulative PNL':'PNL acumulado',data:cumulativeValues,borderColor:'#f59e0b',backgroundColor:'rgba(245,158,11,.2)',fill:true,tension:0.3}]},options:{plugins:{legend:{labels:{color:'#f4f7fb'}}},scales:{x:{ticks:{color:'#f4f7fb'}},y:{ticks:{color:'#f4f7fb'}}}}});}updateSymbolSourceUI();updateRunTradeAmountUI();renderSelectedSymbolList(selectedManualSymbols());renderTrades();renderEconomicSummary();renderBotSessions();renderLiveStrategiesPanel();renderExecutionLogs();syncExecutiveBadge();renderDecisionTelemetry();renderRiskRadar();renderQuantumStatus();}


async function refreshMarketBoard(){const context=document.getElementById('market-board-context');const range=document.getElementById('market-history-range')?.value||'day';const platform='binance';const query=new URLSearchParams({limit:'10',platform,range});if(context)context.textContent=range==='day'?t('top_moves_day','Top movimientos del día en pares USDT.'):t('top_moves_range','Top movimientos ({range}) en pares USDT.',{range:t(range,range==='week'?'semana':'mes')});try{const rows=await api(`/api/market/top-strength?${query.toString()}`);const tbody=document.querySelector('#market-movers-table tbody');if(tbody){tbody.innerHTML=rows.map((row,index)=>`<tr><td>${index+1}</td><td>${row.symbol}</td><td>${Number(row.price||0).toFixed(4)}</td><td class="${Number(row.change_percent||0)>=0?'ticker-up':'ticker-down'}">${Number(row.change_percent||0).toFixed(2)}%</td><td>${Number(row.volume||0).toFixed(2)}</td></tr>`).join('');}}catch(err){const tbody=document.querySelector('#market-movers-table tbody');if(tbody)tbody.innerHTML=`<tr><td colspan="5" class="status-msg status-error">${t('market_load_failed','No se pudo cargar mercado: {error}',{error:parseApiError(err)})}</td></tr>`;}}

async function runHeartbeat(){const out=document.getElementById('heartbeat-output');if(!out)return;out.innerHTML=`<small class="hint">${t('validating_connectors','Validando conectores...')}</small>`;try{const data=await api('/api/heartbeat');out.innerHTML=data.checks.length?data.checks.map(item=>`<div class="connector-item compact"><div class="row-between"><strong>${item.label} (${item.platform})</strong><span class="pill tiny ${item.ok?'pill-on':'pill-off'}">${item.ok?'OK':'Error'}</span></div><small class="hint">${item.message}</small></div>`).join(''):`<small class="hint">${t('no_active_connectors_validate','No hay conectores activos para validar.')}</small>`;}catch(err){out.innerHTML=`<div class="status-msg status-error">${parseApiError(err)}</div>`;}}
async function testConnector(id){try{const out=await api(`/api/connectors/${id}/test`,{method:'POST'});showToast(out.status==='ok'?t('connector_validated','Conector validado: {message}',{message:out.message}):t('connector_test_completed','Prueba completada: {message}',{message:out.message}),out.status==='ok'?'ok':'error');}catch(err){showToast(parseApiError(err),'error');}}
async function editConnector(id){const connector=(DASHBOARD_CACHE.connectors||[]).find((item)=>item.id===id);if(!connector)return;const fields=connectorFieldsFor(connector.platform).map((field)=>connectorFieldMarkup(field,{value:connector.config?.[field.key]??'',editing:true})).join('');const marketTypes=connectorMarketTypesFor(connector.platform);const modal=document.createElement('div');modal.className='modal';modal.innerHTML=`<div class="modal-card card strategy-modal-card"><div class="modal-head"><h3>${t('edit','Editar')} ${isEnglishDashboard()?'connector':'conector'}</h3><button class="btn" type="button" id="close-edit-connector">${isEnglishDashboard()?'Close':'Cerrar'}</button></div><form id="edit-connector-form" class="form-grid" data-platform="${connector.platform}"><label>${isEnglishDashboard()?'Label':'Etiqueta'}<input name="label" required value="${String(connector.label||'').replace(/"/g,'&quot;')}"></label><label>${isEnglishDashboard()?'Operation mode':'Modo de operación'}<select name="mode"><option value="paper" ${connector.mode==='paper'?'selected':''}>paper ${isEnglishDashboard()?'(simulated)':'(simulado)'}</option><option value="live" ${connector.mode==='live'?'selected':''}>live ${isEnglishDashboard()?'(real)':'(real)'}</option><option value="signal" ${connector.mode==='signal'?'selected':''}>signal ${isEnglishDashboard()?'(signals only)':'(solo señales)'}</option></select></label><label>${isEnglishDashboard()?'Market type':'Tipo de mercado'}<select name="market_type">${marketTypes.map((item)=>`<option value="${item}" ${String(connector.market_type||'spot')===item?'selected':''}>${item}</option>`).join('')}</select></label><label class="checkbox"><input name="is_enabled" type="checkbox" ${connector.is_enabled?'checked':''}> ${isEnglishDashboard()?'Connector enabled':'Conector activo'}</label><small class="hint">${isEnglishDashboard()?'Symbols are edited from Strategies. Here you only adjust app, market, mode, and credentials/config.':'Los símbolos se editan desde Estrategias. Aquí solo ajustas app, mercado, modo y credenciales/config.'}</small><div class="form-grid">${fields}</div><button class="btn primary" type="submit">${isEnglishDashboard()?'Save changes':'Guardar cambios'}</button></form></div>`;document.body.appendChild(modal);const close=()=>modal.remove();modal.querySelector('#close-edit-connector')?.addEventListener('click',close);modal.addEventListener('click',(event)=>{if(event.target===modal)close();});modal.querySelector('#edit-connector-form')?.addEventListener('submit',async(event)=>{event.preventDefault();try{const payload=buildConnectorPayload(event.target,{includeSecrets:true});payload.is_enabled=new FormData(event.target).get('is_enabled')==='on';await api(`/api/connectors/${id}`,{method:'PUT',body:JSON.stringify(payload)});close();showToast(t('connector_updated','Conector actualizado correctamente.'));await refreshDashboard();}catch(err){showToast(parseApiError(err),'error');}});}
async function deleteConnector(id){try{await api(`/api/connectors/${id}`,{method:'DELETE'});showToast(t('connector_deleted','Conector eliminado correctamente.'));refreshDashboard();}catch(err){showToast(parseApiError(err),'error');}}

window.testConnector=testConnector; window.editConnector=editConnector; window.deleteConnector=deleteConnector; window.setBotSessionActive=setBotSessionActive; window.deleteBotSession=deleteBotSession; window.editBotSession=editBotSession;
document.getElementById('profile-form')?.addEventListener('submit',saveProfile);



document.getElementById('heartbeat-btn')?.addEventListener('click',runHeartbeat);
document.getElementById('strategy-info-close')?.addEventListener('click',closeStrategyInfo);
document.getElementById('strategy-info-modal')?.addEventListener('click',(e)=>{if(e.target.id==='strategy-info-modal') closeStrategyInfo();});
document.getElementById('open-strategy-setup-help')?.addEventListener('click',()=>document.getElementById('strategy-setup-help-modal')?.classList.remove('hidden'));
document.getElementById('strategy-setup-help-close')?.addEventListener('click',()=>document.getElementById('strategy-setup-help-modal')?.classList.add('hidden'));
document.getElementById('strategy-setup-help-modal')?.addEventListener('click',(e)=>{if(e.target.id==='strategy-setup-help-modal')document.getElementById('strategy-setup-help-modal')?.classList.add('hidden');});
document.getElementById('trade-range-filter')?.addEventListener('change',renderTrades);
document.getElementById('trade-range-filter')?.addEventListener('change',()=>{syncExecutiveBadge();renderQuantumStatus();});
document.getElementById('refresh-market-btn')?.addEventListener('click',refreshMarketBoard);
document.getElementById('refresh-quantum-btn')?.addEventListener('click',()=>{renderQuantumStatus();refreshDashboard();});
document.getElementById('refresh-risk-radar-btn')?.addEventListener('click',()=>{renderRiskRadar();refreshDashboard();});
document.getElementById('symbol-source-mode')?.addEventListener('change',updateSymbolSourceUI);
document.getElementById('run-trade-amount-mode')?.addEventListener('change',updateRunTradeAmountUI);
document.getElementById('dynamic-symbol-limit')?.addEventListener('input',updateSymbolSourceUI);
document.querySelector('select[name="strategy_slug"]')?.addEventListener('change',()=>{applyRunMarketPreset();renderStrategyGuidance();});
document.querySelector('#run-form input[name="timeframe"]')?.addEventListener('input',renderStrategyGuidance);
document.getElementById('symbol-search-input')?.addEventListener('input',filterSymbolCatalog);
document.getElementById('symbol-add-selected')?.addEventListener('click',addSelectedSymbols);
document.getElementById('symbol-remove-selected')?.addEventListener('click',removeSelectedSymbols);
document.getElementById('symbol-clear-selected')?.addEventListener('click',clearSelectedSymbols);

document.getElementById('market-history-range')?.addEventListener('change',refreshMarketBoard);
document.getElementById('refresh-execution-logs-btn')?.addEventListener('click',refreshExecutionLogs);
document.getElementById('refresh-bot-sessions-btn')?.addEventListener('click',refreshBotSessions);
document.getElementById('refresh-connector-health-btn')?.addEventListener('click',()=>{renderQuantumStatus();runHeartbeat();});
document.getElementById('run-form')?.addEventListener('submit',async(e)=>{e.preventDefault();try{const payload=buildRunPayload(e.target,{singleConnector:true});const result=await api('/api/bot-sessions',{method:'POST',body:JSON.stringify(payload)});setRunFeedback(t('bot_activated','Bot 24/7 activado. Sesión #{session_id} en cola inicial.',{session_id:result.session_id}));await refreshBotSessions();await refreshExecutionLogs();}catch(err){setRunFeedback(parseApiError(err),'error');}});

async function init(){const [metadata,strategyControl,user]=await Promise.all([api('/api/platform-metadata'),api('/api/strategy-control'),api('/api/me')]);METADATA=metadata;STRATEGY_CONTROL=strategyControl;translateStaticDashboard();initTabs('#dashboard-tabs','tab-');renderProfile(user);renderUserConfigReport(user);renderStrategySelect();renderStrategyLibrary();initInlineRunWizard();initTelemetryControls();renderPlatformTabs();bindPlatformForms();applyStrategyControlUI();syncExecutiveBadge();await refreshDashboard();setInterval(refreshExecutionLogs,EXECUTION_LOG_REFRESH_MS);setInterval(refreshBotSessions,20*1000);await refreshMarketBoard();runHeartbeat();}
init().catch(err=>{setRunFeedback(`${t('dashboard_load_error','Error cargando dashboard: {error}',{error:parseApiError(err)})}`,'error');});

let SELECTED_BOT_SESSION_ID=null;

async function downloadExecutionLogs(){
  try{window.open('/api/execution-logs/download?limit=1000','_blank');}
  catch(err){showToast(parseApiError(err),'error');}
}

async function copySelectedBotSession(){
  const sourceId=SELECTED_BOT_SESSION_ID||Number(prompt(t('prompt_bot_session_id','ID de bot session a copiar:'),''));
  if(!sourceId)return;
  const targetConnector=Number(prompt(t('prompt_target_connector','ID de conector destino (opcional):'),'')||0)||null;
  try{
    await api(`/api/bot-sessions/${sourceId}/copy`,{method:'POST',body:JSON.stringify({connector_id:targetConnector})});
    showToast(t('bot_copied','Bot copiado correctamente.'));
    refreshBotSessions();
  }catch(err){showToast(parseApiError(err),'error');}
}

async function publishCurrentStrategyTemplate(){
  const fd=new FormData(document.getElementById('run-form'));
  const name=prompt('Nombre de la estrategia pública:','Mi estrategia');
  if(!name)return;
  const config={
    market_type:String(fd.get('market_type')||resolveEffectiveRunMarketType()||'spot'),
    strategy_slug:fd.get('strategy_slug'),
    timeframe:fd.get('timeframe'),
    risk_per_trade:Number(fd.get('risk_per_trade_percent')||3)/100,
    trade_amount_mode:String(fd.get('trade_amount_mode')||'inherit'),
    amount_per_trade:String(fd.get('trade_amount_mode')||'inherit')==='fixed_usd'?Number(fd.get('amount_per_trade')):null,
    amount_percentage:String(fd.get('trade_amount_mode')||'inherit')==='balance_percent'?Number(fd.get('amount_percentage')):null,
    min_ml_probability:Number(fd.get('min_ml_probability_percent')||58)/100,
    take_profit_mode:fd.get('take_profit_mode')||'percent',
    take_profit_value:Number(fd.get('take_profit_value')||1.8),
    stop_loss_mode:fd.get('stop_loss_mode')||'percent',
    stop_loss_value:Number(fd.get('stop_loss_value')||1.1),
    trailing_stop_mode:fd.get('trailing_stop_mode')||'percent',
    trailing_stop_value:Number(fd.get('trailing_stop_value')||0.9),
    leverage_profile:fd.get('leverage_profile')||'none',
    max_open_positions:Number(fd.get('max_open_positions')||1),
    compound_growth_enabled:String(fd.get('compound_growth_enabled')).toLowerCase()==='true',
    atr_volatility_filter_enabled:String(fd.get('atr_volatility_filter_enabled')).toLowerCase()!=='false',
    symbols:resolveRunSymbols(fd),
  };
  try{
    await api('/api/strategy-templates',{method:'POST',body:JSON.stringify({name,description:'Publicada desde dashboard',is_public:true,config})});
    showToast('Estrategia publicada en el pool público.');
    refreshTemplatePool();
  }catch(err){showToast(parseApiError(err),'error');}
}

async function refreshTemplatePool(){
  const node=document.getElementById('template-pool');
  if(!node)return;
  try{
    const rows=await api('/api/strategy-templates');
    node.innerHTML=rows.slice(0,20).map(item=>`<div class="connector-item"><div class="row-between"><strong>${item.name}</strong><span class="pill tiny ${item.is_public?'pill-on':'pill-off'}">${item.is_public?'Pública':'Privada'}</span></div><small class="hint">${item.description||''}</small><div style="margin-top:8px;"><button class="btn" type="button" onclick="copyTemplateToMe(${item.id})">Copiar</button></div></div>`).join('')||'<small class="hint">No hay estrategias en el pool aún.</small>';
  }catch(err){node.innerHTML=`<small class="status-msg status-error">${parseApiError(err)}</small>`;}
}

async function copyTemplateToMe(id){
  try{await api(`/api/strategy-templates/${id}/copy`,{method:'POST'});showToast('Template copiado en tu cuenta.');refreshTemplatePool();}
  catch(err){showToast(parseApiError(err),'error');}
}
window.copyTemplateToMe=copyTemplateToMe;

document.getElementById('download-execution-logs-btn')?.addEventListener('click',downloadExecutionLogs);
document.getElementById('copy-selected-bot-btn')?.addEventListener('click',copySelectedBotSession);
document.getElementById('publish-template-btn')?.addEventListener('click',publishCurrentStrategyTemplate);
document.getElementById('refresh-template-pool-btn')?.addEventListener('click',refreshTemplatePool);
document.querySelector('#bot-sessions-table tbody')?.addEventListener('click',(e)=>{const tr=e.target.closest('tr');if(!tr)return;const id=Number(tr.getAttribute('data-session-id')||0);if(id)SELECTED_BOT_SESSION_ID=id;});
setTimeout(refreshTemplatePool,1200);

const TERM_HELP={
  tp:{title:'Take Profit (TP)',body:'El TP es el nivel donde aseguras ganancia. En % para intradía suele usarse entre 1% y 3%; en USDT depende de tu tamaño. Regla básica: TP mayor que SL.'},
  sl:{title:'Stop Loss (SL)',body:'El SL limita pérdidas. En % para cuentas pequeñas suele usarse 0.8% a 1.5%. Si SL es muy grande, una operación mala afecta demasiado tu cuenta.'},
  trailing:{title:'Trailing Stop',body:'El trailing mueve el stop a favor de la operación cuando el precio avanza. Valores típicos: 0.5% a 1.2% según volatilidad.'},
  pnl:{title:'PNL %',body:'PNL% es el porcentaje de ganancia o pérdida respecto al capital invertido. Ejemplo: si inviertes 100 y ganas 5, PNL%=5%.'},
  risk:{title:'Riesgo por trade',body:'Porcentaje máximo de cuenta que arriesgas por operación. Para cuentas pequeñas y pruebas: 2% a 3%. En producción conservadora: 0.5% a 1.5%.'},
  trade_amount_examples:{title:'Ejemplos de monto por operación',body:'Monto fijo: si defines 12, cada orden usa 12 USDT. Porcentaje: si defines 25% y tienes 80 USDT, usará 20 USDT. Si el cálculo da menos de 10 USDT, se ajusta automáticamente a 10 USDT.'},
};

function openTermHelp(term){const meta=TERM_HELP[term]||{title:'Ayuda',body:'Sin definición disponible.'};const modal=document.getElementById('term-help-modal');if(!modal)return;document.getElementById('term-help-title').textContent=meta.title;document.getElementById('term-help-body').textContent=meta.body;modal.classList.remove('hidden');}
function closeTermHelp(){document.getElementById('term-help-modal')?.classList.add('hidden');}

async function refreshActivityPerformance(){
  let payload=null;
  try{payload=await api('/api/activity/performance');}catch(_err){payload={equity_curve:[],drawdown_curve:[],monthly_returns:[],yearly_returns:[],summary:{sharpe_ratio:0,max_drawdown:0,profit_factor:0,win_rate:0,total_trades:0,average_win:0,average_loss:0}};}
  const kpi=document.getElementById('activity-kpis');
  if(kpi){const s=payload.summary||{};kpi.innerHTML=`<div class="metric-card"><strong>Sharpe</strong><span>${Number(s.sharpe_ratio||0).toFixed(2)}</span></div><div class="metric-card"><strong>Max DD</strong><span>${Number(s.max_drawdown||0).toFixed(2)}%</span></div><div class="metric-card"><strong>Profit Factor</strong><span>${Number(s.profit_factor||0).toFixed(2)}</span></div><div class="metric-card"><strong>Win Rate</strong><span>${Number(s.win_rate||0).toFixed(1)}%</span></div><div class="metric-card"><strong>Trades</strong><span>${Number(s.total_trades||0)}</span></div><div class="metric-card"><strong>Prom. win/loss</strong><span>${Number(s.average_win||0).toFixed(2)} / ${Number(s.average_loss||0).toFixed(2)}</span></div>`;}
  const pointX=(item)=>item?.x||item?.timestamp||item?.period||null;
  const pointY=(item)=>Number(item?.y??item?.value??0);
  const equity=(payload.equity_curve||[]), dd=(payload.drawdown_curve||[]), monthly=(payload.monthly_returns||[]), yearly=(payload.yearly_returns||[]);
  const equityCanvas=document.getElementById('equity-curve-chart');
  if(equityCanvas){if(window.equityCurveChart)window.equityCurveChart.destroy();window.equityCurveChart=new Chart(equityCanvas,{type:'line',data:{labels:equity.map(i=>pointX(i)?new Date(pointX(i)).toLocaleDateString():''),datasets:[{label:'Cumulative Return',data:equity.map(pointY),borderColor:'#22c55e',backgroundColor:'rgba(34,197,94,.15)',fill:true,tension:.25}]},options:{plugins:{legend:{labels:{color:'#f4f7fb'}}},scales:{x:{ticks:{color:'#f4f7fb'}},y:{ticks:{color:'#f4f7fb'}}}}});}
  const ddCanvas=document.getElementById('drawdown-curve-chart');
  if(ddCanvas){if(window.drawdownCurveChart)window.drawdownCurveChart.destroy();window.drawdownCurveChart=new Chart(ddCanvas,{type:'bar',data:{labels:dd.map(i=>pointX(i)?new Date(pointX(i)).toLocaleDateString():''),datasets:[{label:'Drawdown %',data:dd.map(pointY),backgroundColor:'#ef4444'}]},options:{plugins:{legend:{labels:{color:'#f4f7fb'}}},scales:{x:{ticks:{color:'#f4f7fb'}},y:{ticks:{color:'#f4f7fb'}}}}});}
  const mCanvas=document.getElementById('monthly-returns-chart');
  if(mCanvas){if(window.monthlyReturnsChart)window.monthlyReturnsChart.destroy();window.monthlyReturnsChart=new Chart(mCanvas,{type:'bar',data:{labels:monthly.map(i=>i.period||pointX(i)||'-'),datasets:[{label:'Monthly Returns',data:monthly.map(pointY),backgroundColor:'#38bdf8'}]},options:{plugins:{legend:{labels:{color:'#f4f7fb'}}},scales:{x:{ticks:{color:'#f4f7fb'}},y:{ticks:{color:'#f4f7fb'}}}}});}
  const yCanvas=document.getElementById('yearly-returns-chart');
  if(yCanvas){if(window.yearlyReturnsChart)window.yearlyReturnsChart.destroy();window.yearlyReturnsChart=new Chart(yCanvas,{type:'bar',data:{labels:yearly.map(i=>i.period||pointX(i)||'-'),datasets:[{label:'Yearly Returns',data:yearly.map(pointY),backgroundColor:'#a78bfa'}]},options:{plugins:{legend:{labels:{color:'#f4f7fb'}}},scales:{x:{ticks:{color:'#f4f7fb'}},y:{ticks:{color:'#f4f7fb'}}}}});}
}

if(typeof refreshDashboard==='function'){
  const _refreshDashboardOriginal=refreshDashboard;
  refreshDashboard=async function(){await _refreshDashboardOriginal();await refreshActivityPerformance();};
}


function setRunWizardStep(step){const safe=Math.max(1,Math.min(3,Number(step)||1));document.querySelectorAll('[data-wizard-step]').forEach((btn)=>btn.classList.toggle('active',Number(btn.dataset.wizardStep)===safe));document.querySelectorAll('[data-wizard-content]').forEach((pane)=>pane.classList.toggle('active',Number(pane.dataset.wizardContent)===safe));const prev=document.getElementById('wizard-prev-inline');const next=document.getElementById('wizard-next-inline');if(prev)prev.disabled=safe===1;if(next)next.textContent=safe===3?'Finalizar':'Siguiente';document.getElementById('run-form')?.setAttribute('data-step',String(safe));}
function initInlineRunWizard(){setRunWizardStep(1);document.querySelectorAll('[data-wizard-step]').forEach((btn)=>btn.addEventListener('click',()=>setRunWizardStep(Number(btn.dataset.wizardStep))));document.getElementById('wizard-prev-inline')?.addEventListener('click',()=>setRunWizardStep(Number(document.getElementById('run-form')?.dataset.step||1)-1));document.getElementById('wizard-next-inline')?.addEventListener('click',()=>setRunWizardStep(Number(document.getElementById('run-form')?.dataset.step||1)+1));}

document.querySelectorAll('.term-help').forEach(btn=>btn.addEventListener('click',()=>openTermHelp(btn.dataset.term)));
document.addEventListener('click',(e)=>{
  if(e.target?.id==='term-help-close')closeTermHelp();
  if(e.target?.id==='term-help-modal')closeTermHelp();
});
