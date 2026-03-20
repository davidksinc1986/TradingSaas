const PLATFORM_MARKET_TYPES={mt5:['forex','cfd'],ctrader:['forex','cfd','spot','futures'],tradingview:['signals'],binance:['spot','futures'],bybit:['spot','futures'],okx:['spot','futures']};
const CATEGORY_TITLES = { broker: 'Mercado de valores / Brokers', crypto: 'Cryptos', signals: 'Señales' };
const PLATFORM_FIELD_MAP = {
  mt5: [
    { key: 'login', label: 'Usuario / Login MT5', target: 'secrets', required: true, placeholder: 'Ej: 12345678' },
    { key: 'password', label: 'Contraseña MT5', target: 'secrets', required: true, placeholder: 'Tu contraseña de trading' },
    { key: 'server', label: 'Servidor del broker', target: 'secrets', required: true, placeholder: 'Ej: Broker-Server' },
    { key: 'default_quantity', label: 'Tamaño por operación (lotes)', target: 'config', type: 'number', step: '0.01', placeholder: '0.10' },
  ],
  ctrader: [
    { key: 'client_id', label: 'Client ID', target: 'secrets', required: true, placeholder: 'Pega aquí tu Client ID' },
    { key: 'client_secret', label: 'Client Secret', target: 'secrets', required: true, placeholder: 'Pega aquí tu Client Secret' },
    { key: 'access_token', label: 'Access Token', target: 'secrets', required: true, placeholder: 'Pega aquí tu token' },
    { key: 'account_id', label: 'Account ID', target: 'secrets', required: true, placeholder: 'Ej: 123456' },
    { key: 'default_quantity', label: 'Tamaño por operación', target: 'config', type: 'number', step: '0.01', placeholder: '1000' },
  ],
  tradingview: [
    { key: 'passphrase', label: 'Clave secreta del webhook', target: 'config', required: true, placeholder: 'Crea una clave fácil de recordar' },
  ],
  binance: [
    { key: 'api_key', label: 'Inserta aquí tu API Key', target: 'secrets', required: true, placeholder: 'Pega aquí tu API Key' },
    { key: 'secret_key', label: 'Inserta aquí tu Secret Key', target: 'secrets', required: true, placeholder: 'Pega aquí tu Secret Key' },
    { key: 'default_quantity', label: 'Cantidad fija por operación', target: 'config', type: 'number', step: '0.0001', placeholder: '0.001' },
  ],
  bybit: [
    { key: 'api_key', label: 'Inserta aquí tu API Key', target: 'secrets', required: true, placeholder: 'Pega aquí tu API Key' },
    { key: 'secret_key', label: 'Inserta aquí tu Secret Key', target: 'secrets', required: true, placeholder: 'Pega aquí tu Secret Key' },
    { key: 'default_quantity', label: 'Cantidad fija por operación', target: 'config', type: 'number', step: '0.0001', placeholder: '0.001' },
  ],
  okx: [
    { key: 'api_key', label: 'Inserta aquí tu API Key', target: 'secrets', required: true, placeholder: 'Pega aquí tu API Key' },
    { key: 'secret_key', label: 'Inserta aquí tu Secret Key', target: 'secrets', required: true, placeholder: 'Pega aquí tu Secret Key' },
    { key: 'passphrase', label: 'Passphrase', target: 'secrets', required: true, placeholder: 'Pega aquí tu passphrase' },
    { key: 'default_quantity', label: 'Cantidad fija por operación', target: 'config', type: 'number', step: '0.0001', placeholder: '0.001' },
  ],
};
let METADATA={platforms:[]};
let STRATEGY_CONTROL = { managed_by_admin: false, allowed_strategies: [], all_strategies: [] };
async function api(url,options={}){const res=await fetch(url,{headers:{'Content-Type':'application/json'},credentials:'same-origin',...options});if(!res.ok) throw new Error(await res.text());return res.json();}
function parseCsv(value){return String(value || '').split(',').map(x=>x.trim()).filter(Boolean);}
function getPlatformMeta(platform){return METADATA.platforms.find(p=>p.platform===platform);}
function renderMarketTypeSelect(platform){const select=document.getElementById('market-type-select');if(!select) return;const marketTypes=PLATFORM_MARKET_TYPES[platform]||['spot'];select.innerHTML=marketTypes.map(mt=>`<option value="${mt}">${mt}</option>`).join('');}
function renderFriendlyFields(platform){
  const container = document.getElementById('connector-friendly-fields');
  if (!container) return;
  const fields = PLATFORM_FIELD_MAP[platform] || [];
  container.innerHTML = fields.map((field) => `
    <label>${field.label}
      <input
        name="field_${field.target}_${field.key}"
        type="${field.type || 'text'}"
        ${field.step ? `step="${field.step}"` : ''}
        ${field.required ? 'required' : ''}
        placeholder="${field.placeholder || ''}"
      >
    </label>
  `).join('');
}
function readFriendlyFields(formEl, platform){
  const fields = PLATFORM_FIELD_MAP[platform] || [];
  const config = {};
  const secrets = {};
  fields.forEach((field) => {
    const raw = String(new FormData(formEl).get(`field_${field.target}_${field.key}`) || '').trim();
    if (!raw) return;
    const parsed = field.type === 'number' ? Number(raw) : raw;
    if (field.target === 'secrets') secrets[field.key] = parsed;
    else config[field.key] = parsed;
  });
  config.market_type = new FormData(formEl).get('market_type');
  return { config, secrets };
}
function renderPlatformCatalog(){
  const container = document.getElementById('platform-catalog');
  if (!container) return;
  const grouped = METADATA.platforms.reduce((acc, platform) => {
    const key = platform.category || 'others';
    if (!acc[key]) acc[key] = [];
    acc[key].push(platform);
    return acc;
  }, {});

  container.innerHTML = Object.entries(grouped).map(([category, platforms]) => `
    <div class="catalog-card">
      <h3>${CATEGORY_TITLES[category] || category}</h3>
      <div class="stack">
        ${platforms.map(platform => `
          <div class="connector-item compact">
            <div class="row-between">
              <strong>${platform.display_name}</strong>
              <span class="pill tiny ${platform.is_enabled_global && platform.grant?.is_enabled ? 'pill-on' : 'pill-off'}">
                ${platform.is_enabled_global && platform.grant?.is_enabled ? 'Disponible' : 'No disponible'}
              </span>
            </div>
            <small class="hint">${platform.guide?.summary || 'Conector configurable para operar.'}</small>
          </div>
        `).join('')}
      </div>
    </div>
  `).join('');
}
function setPlatformExample(platform){const meta=getPlatformMeta(platform);renderMarketTypeSelect(platform);renderFriendlyFields(platform);if(meta){document.getElementById('symbol-limit-hint').textContent=`Máx. símbolos permitidos: ${meta.grant.max_symbols}. Manual: ${meta.allow_manual_symbols?'sí':'no'}.`;}renderSymbolPresets(platform);}
function renderPlatformSelect(){const select=document.getElementById('platform-select');if(!select) return;const enabled=METADATA.platforms.filter(p=>p.is_enabled_global&&p.grant?.is_enabled);select.innerHTML=enabled.map(p=>`<option value="${p.platform}">${p.display_name}</option>`).join('');if (!enabled.length) {select.innerHTML='';document.getElementById('connector-friendly-fields').innerHTML='<p class="hint">No tienes conectores habilitados por el administrador.</p>';return;}setPlatformExample(enabled[0].platform);}
function renderSymbolPresets(platform){const wrap=document.getElementById('symbol-preset-list');const card=document.getElementById('suggested-symbol-card');if(!wrap||!card) return;const meta=getPlatformMeta(platform);const symbols=meta?.top_symbols||[];card.style.display=symbols.length?'block':'none';wrap.innerHTML=symbols.map(s=>`<button type="button" class="chip" data-symbol="${s}">${s}</button>`).join('');wrap.querySelectorAll('.chip').forEach(btn=>btn.addEventListener('click',()=>addSymbol(btn.dataset.symbol)));}
function addSymbol(symbol){const input=document.getElementById('symbols-input');const current=new Set(parseCsv(input.value||''));const platform=document.getElementById('platform-select').value;const meta=getPlatformMeta(platform);const limit=meta?.grant?.max_symbols||0;if(limit&&current.size>=limit&&!current.has(symbol)){alert(`Tu límite en ${platform} es de ${limit} símbolos.`);return;}current.add(symbol);input.value=Array.from(current).join(',');}
function openGuideModal(platform){const meta=getPlatformMeta(platform);if(!meta) return;const guide=meta.guide||{};document.getElementById('guide-title').textContent=guide.title||meta.display_name;document.getElementById('guide-summary').textContent=guide.summary||'';document.getElementById('guide-fields').innerHTML=(guide.fields_needed||[]).map(x=>`<li>${x}</li>`).join('');document.getElementById('guide-steps').innerHTML=(guide.steps||[]).map(x=>`<li>${x}</li>`).join('');document.getElementById('guide-modal').classList.remove('hidden');}
window.closeGuideModal=function(){document.getElementById('guide-modal').classList.add('hidden');};

function renderRunConnectorSelect(connectors) {
  const select = document.getElementById('run-connector-select');
  if (!select) return;
  select.innerHTML = connectors.map(c => `<option value="${c.id}">#${c.id} · ${c.label} (${c.platform} / ${c.mode})</option>`).join('');
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

function applyStrategyControlUI() {
  const select = document.querySelector('select[name="strategy_slug"]');
  const hint = document.getElementById('strategy-managed-hint');
  if (!select) return;

  const allowed = STRATEGY_CONTROL.allowed_strategies?.length ? STRATEGY_CONTROL.allowed_strategies : Array.from(select.options).map((o) => o.value);
  Array.from(select.options).forEach((option) => {
    option.hidden = !allowed.includes(option.value);
    option.disabled = !allowed.includes(option.value);
  });
  if (!allowed.includes(select.value) && allowed.length) select.value = allowed[0];

  if (STRATEGY_CONTROL.managed_by_admin) {
    select.disabled = true;
    if (hint) hint.textContent = 'Estrategia gestionada por administrador para esta cuenta.';
  } else {
    select.disabled = false;
    if (hint) hint.textContent = 'Puedes elegir entre las estrategias habilitadas para tu cuenta.';
  }
}
async function testConnector(id){const out=await api(`/api/connectors/${id}/test`,{method:'POST'});alert(`${out.status}: ${out.message}\n\n${JSON.stringify(out.raw,null,2)}`);}async function deleteConnector(id){await api(`/api/connectors/${id}`,{method:'DELETE'});refreshDashboard();}
document.getElementById('platform-select')?.addEventListener('change',e=>{setPlatformExample(e.target.value);});
document.getElementById('market-type-select')?.addEventListener('change',()=>{setPlatformExample(document.getElementById('platform-select').value);});
document.getElementById('open-guide-btn')?.addEventListener('click',()=>{const platform=document.getElementById('platform-select').value;openGuideModal(platform);});
document.getElementById('connector-form')?.addEventListener('submit',async e=>{
  e.preventDefault();
  const fd=new FormData(e.target);
  const platform=String(fd.get('platform')||'');
  const friendly = readFriendlyFields(e.target, platform);
  await api('/api/connectors',{method:'POST',body:JSON.stringify({platform,label:fd.get('label'),mode:fd.get('mode'),market_type:fd.get('market_type'),symbols:parseCsv(fd.get('symbols')),config:friendly.config,secrets:friendly.secrets})});
  e.target.reset();
  renderPlatformSelect();
  refreshDashboard();
});
document.getElementById('run-form')?.addEventListener('submit',async e=>{
  e.preventDefault();
  const fd=new FormData(e.target);
  const connectorIds = selectedRunConnectorIds();
  if (!connectorIds.length) {
    document.getElementById('run-output').textContent = 'Selecciona al menos un conector para ejecutar la estrategia.';
    return;
  }
  const result=await api('/api/strategies/run',{method:'POST',body:JSON.stringify({connector_ids:connectorIds,symbols:parseCsv(fd.get('symbols')),timeframe:fd.get('timeframe'),strategy_slug:fd.get('strategy_slug'),risk_per_trade:Number(fd.get('risk_per_trade')),min_ml_probability:Number(fd.get('min_ml_probability')),use_live_if_available:fd.get('use_live_if_available')==='on'})});document.getElementById('run-output').textContent=JSON.stringify(result,null,2);refreshDashboard();
});
async function init(){
  METADATA=await api('/api/platform-metadata');
  STRATEGY_CONTROL = await api('/api/strategy-control');
  renderPlatformCatalog();
  renderPlatformSelect();
  applyStrategyControlUI();
  await refreshDashboard();
}
init().catch(err=>{console.error(err);const out=document.getElementById('run-output');if(out) out.textContent='Error cargando dashboard: '+err.message;});
