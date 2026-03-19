(function () {
  const locale = (document.documentElement.lang || 'es').slice(0, 2);
  const T = {
    es: {
      title: 'Wizard · Configuración profesional',
      step1: '1) Mercado y estrategia',
      step2: '2) Timeframe, TP/SL y riesgo',
      step3: '3) Validación cuantitativa',
      done: 'Aplicar al formulario',
      next: 'Siguiente',
      prev: 'Atrás',
      noPromise: 'Nota: Ninguna estrategia garantiza resultados. Usa gestión de riesgo y validación continua.',
    },
    en: {
      title: 'Wizard · Professional setup', step1: '1) Market and strategy', step2: '2) Timeframe, TP/SL and risk', step3: '3) Quant validation', done: 'Apply to form', next: 'Next', prev: 'Back',
      noPromise: 'Note: No strategy can guarantee results. Use strict risk management and ongoing validation.',
    },
    pt: {
      title: 'Wizard · Configuração profissional', step1: '1) Mercado e estratégia', step2: '2) Timeframe, TP/SL e risco', step3: '3) Validação quantitativa', done: 'Aplicar ao formulário', next: 'Próximo', prev: 'Voltar',
      noPromise: 'Nota: Nenhuma estratégia garante resultado. Use gestão de risco e validação contínua.',
    }
  }[locale] || {};

  const EXTRA = {
    volatility_breakout: { name: 'Volatility Breakout', summary: 'Open + k×(Highprev-Lowprev), con filtro ATR > promedio ATR.', marketTypes: ['futures'], timeframes: '5m, 15m, 1h' },
    ema_rsi_adx_stack: { name: 'EMA20/50 + RSI14 + ADX', summary: 'Long: EMA20>EMA50, RSI>55, ADX>20. Short inverso.', marketTypes: ['spot', 'futures'], timeframes: '3m, 5m, 15m, 1h' },
    volatility_compression_breakout: { name: 'Volatility Compression Breakout', summary: 'Detecta squeeze (BB/Keltner + ATR contraction) y opera expansión.', marketTypes: ['spot', 'futures'], timeframes: '15m, 1h' }
  };

  function extendLibrary() {
    if (typeof STRATEGY_LIBRARY === 'undefined') return;
    Object.entries(EXTRA).forEach(([slug, meta]) => {
      if (!STRATEGY_LIBRARY[slug]) STRATEGY_LIBRARY[slug] = meta;
    });
    if (typeof renderStrategySelect === 'function') renderStrategySelect();
    if (typeof renderStrategyLibrary === 'function') renderStrategyLibrary();
  }

  function setField(name, value) {
    const el = document.querySelector(`[name="${name}"]`);
    if (el) el.value = String(value);
  }

  function getStepHtml(step) {
    if (step === 0) {
      return `
      <h4>${T.step1 || '1) Mercado y estrategia'}</h4>
      <label>Tipo de mercado
        <select id="wiz-market-type"><option value="spot">Spot</option><option value="futures">Futures</option></select>
      </label>
      <small class="hint">Se mostrarán estrategias compatibles por mercado y app.</small>
      <label>Estrategia sugerida
        <select id="wiz-strategy"></select>
      </label>
      <label>Crear estrategia personalizada (opcional)
        <textarea id="wiz-custom" rows="5" placeholder="EMA20>EMA50, RSI>55, ADX>20..."></textarea>
      </label>`;
    }
    if (step === 1) {
      return `
      <h4>${T.step2 || '2) Timeframe, TP/SL y riesgo'}</h4>
      <label>Perfil de timeframe
        <select id="wiz-timeframe-profile"><option value="scalping">Scalping (1m-3m)</option><option value="intraday">Intraday (5m-15m)</option><option value="swing">Swing corto (1h)</option><option value="manual">Manual</option></select>
      </label>
      <label>Timeframe final
        <input id="wiz-timeframe" value="5m" />
      </label>
      <label>TP (%)<input id="wiz-tp" type="number" min="0.1" step="0.1" value="1.2"></label>
      <label>SL (%) máximo 1.5<input id="wiz-sl" type="number" min="0.1" max="1.5" step="0.1" value="0.8"></label>
      <label>Leverage (solo futures)
        <select id="wiz-leverage"><option value="none">N/A</option><option value="conservative">Conservador 2x</option><option value="balanced">Balanceado 3x</option><option value="aggressive">Agresivo 5x</option></select>
      </label>
      <label>Posiciones simultáneas
        <input id="wiz-max-pos" type="number" min="1" max="20" value="2">
      </label>`;
    }
    return `
      <h4>${T.step3 || '3) Validación cuantitativa'}</h4>
      <label class="checkbox"><input id="wiz-atr" type="checkbox" checked> Activar filtro ATR &gt; ATR promedio (evita mercado muerto)</label>
      <label class="checkbox"><input id="wiz-compound" type="checkbox" checked> Activar crecimiento compuesto automático</label>
      <div class="card soft-card">
        <strong>Backtesting / Walk Forward / Paper Trading</strong>
        <ul class="modal-list">
          <li>Backtest histórico (BTC desde 2018, ETH desde 2019).</li>
          <li>Walk forward: entrena en año N, prueba en N+1.</li>
          <li>Paper trading para medir slippage, fees y latencia real.</li>
          <li>Métricas objetivo: win rate 45-60%, profit factor > 1.5, sharpe > 1, drawdown < 20%.</li>
        </ul>
      </div>
      <small class="hint">${T.noPromise || ''}</small>`;
  }

  function fillStrategyOptions(marketType) {
    const select = document.getElementById('wiz-strategy');
    if (!select || typeof STRATEGY_LIBRARY === 'undefined') return;
    const options = Object.entries(STRATEGY_LIBRARY)
      .filter(([_, meta]) => !meta.marketTypes || meta.marketTypes.includes(marketType))
      .map(([slug, meta]) => `<option value="${slug}">${meta.name}</option>`)
      .join('');
    select.innerHTML = options;
  }

  function openWizard() {
    const modal = document.getElementById('strategy-wizard-modal');
    if (!modal) return;
    let step = 0;
    const title = document.getElementById('strategy-wizard-title');
    const body = document.getElementById('strategy-wizard-content');
    const prev = document.getElementById('strategy-wizard-prev');
    const next = document.getElementById('strategy-wizard-next');
    if (title) title.textContent = T.title || title.textContent;

    function render() {
      body.innerHTML = getStepHtml(step);
      prev.style.visibility = step === 0 ? 'hidden' : 'visible';
      next.textContent = step === 2 ? (T.done || 'Aplicar al formulario') : (T.next || 'Siguiente');
      if (step === 0) {
        fillStrategyOptions('spot');
        document.getElementById('wiz-market-type')?.addEventListener('change', (e) => fillStrategyOptions(e.target.value));
      }
      if (step === 1) {
        document.getElementById('wiz-timeframe-profile')?.addEventListener('change', (e) => {
          const map = { scalping: '3m', intraday: '15m', swing: '1h', manual: '' };
          const input = document.getElementById('wiz-timeframe');
          if (input && map[e.target.value] !== undefined) input.value = map[e.target.value];
        });
      }
    }

    prev.onclick = () => { if (step > 0) { step -= 1; render(); } };
    next.onclick = () => {
      if (step < 2) {
        step += 1;
        render();
        return;
      }
      const marketType = document.getElementById('wiz-market-type')?.value || 'spot';
      const strategy = document.getElementById('wiz-strategy')?.value || 'ema_rsi';
      const tf = document.getElementById('wiz-timeframe')?.value || '5m';
      const tp = Number(document.getElementById('wiz-tp')?.value || 1.2);
      const slRaw = Number(document.getElementById('wiz-sl')?.value || 0.8);
      const sl = Math.min(1.5, Math.min(slRaw, tp * 0.8));
      const leverage = marketType === 'futures' ? (document.getElementById('wiz-leverage')?.value || 'balanced') : 'none';
      const maxPos = Number(document.getElementById('wiz-max-pos')?.value || 1);
      const atrFilter = !!document.getElementById('wiz-atr')?.checked;
      const compound = !!document.getElementById('wiz-compound')?.checked;

      setField('timeframe', tf);
      setField('market_type', marketType);
      setField('take_profit_value', tp);
      setField('stop_loss_value', sl);
      setField('leverage_profile', leverage);
      setField('max_open_positions', maxPos);
      setField('atr_volatility_filter_enabled', atrFilter);
      setField('compound_growth_enabled', compound);

      const strategySelect = document.querySelector('select[name="strategy_slug"]');
      if (strategySelect) strategySelect.value = strategy;
      document.getElementById('run-market-type-filter')?.dispatchEvent(new Event('change'));

      modal.classList.add('hidden');
    };

    modal.classList.remove('hidden');
    render();
  }

  extendLibrary();
  document.getElementById('open-strategy-wizard')?.addEventListener('click', openWizard);
  document.getElementById('strategy-wizard-close')?.addEventListener('click', () => document.getElementById('strategy-wizard-modal')?.classList.add('hidden'));
  document.getElementById('strategy-wizard-modal')?.addEventListener('click', (e) => {
    if (e.target.id === 'strategy-wizard-modal') document.getElementById('strategy-wizard-modal')?.classList.add('hidden');
  });
})();
