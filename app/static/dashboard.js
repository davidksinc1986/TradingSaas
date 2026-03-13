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

function selectedRunConnectorIds() {
  const select = document.getElementById('run-connector-select');
  if (!select) return [];
  return Array.from(select.selectedOptions).map(option => Number(option.value));
}

async function refreshDashboard(){
  const [connectors,summary,trades]=await Promise.all([api('/api/connectors'),api('/api/dashboard'),api('/api/trades')]);
  document.getElementById('stat-connectors').textContent=summary.total_connectors;document.getElementById('stat-enabled').textContent=summary.enabled_connectors;document.getElementById('stat-trades').textContent=summary.total_trades;document.getElementById('stat-pnl').textContent=summary.realized_pnl;
  renderRunConnectorSelect(connectors);

  const limits=document.getElementById('limits-list');
  limits.innerHTML=(summary.limits||[]).map(l=>`<div class="connector-item"><strong>${l.platform}</strong><div class="connector-meta"><span>Estado: ${l.enabled ? 'Habilitado' : 'Deshabilitado'}</span><span>Máx. símbolos: ${l.max_symbols}</span><span>Máx. mov/día: ${l.max_daily_movements}</span></div><small class="hint">${l.notes||'Sin notas'}</small></div>`).join('');

  const list=document.getElementById('connectors-list');
  list.innerHTML=connectors.map(c=>`<div class="connector-item"><strong>${c.label}</strong><div class="connector-meta"><span>${c.platform}</span><span>mercado: ${c.market_type||'spot'}</span><span>modo: ${c.mode}</span><span>enabled: ${c.is_enabled}</span><span>symbols: ${(c.symbols||[]).join(', ')||'-'}</span></div><div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap"><button class="btn" onclick="testConnector(${c.id})">Test</button><button class="btn" onclick="deleteConnector(${c.id})">Eliminar</button></div><pre class="mini-pre">${JSON.stringify(c.config||{},null,2)}</pre></div>`).join('');

  const tbody=document.querySelector('#trades-table tbody');tbody.innerHTML=trades.map(t=>`<tr><td>${new Date(t.created_at).toLocaleString()}</td><td>${t.platform}</td><td>${(t.meta&&t.meta.market_type)||'-'}</td><td>${t.symbol}</td><td>${t.side}</td><td>${t.quantity}</td><td>${Number(t.price).toFixed(4)}</td><td>${t.status}</td><td>${t.pnl}</td></tr>`).join('');
  const labels=Object.keys(summary.platforms||{});const values=Object.values(summary.platforms||{});const canvas=document.getElementById('platform-chart');if(window.platformChart) window.platformChart.destroy();window.platformChart=new Chart(canvas,{type:'doughnut',data:{labels,datasets:[{data:values}]},options:{plugins:{legend:{labels:{color:'#f4f7fb'}}}}});
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
