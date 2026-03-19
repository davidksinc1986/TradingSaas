async function api(url, options = {}) {
  const res = await fetch(url, { headers: { "Content-Type": "application/json" }, credentials: "same-origin", ...options });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function parseApiError(error) {
  const raw = String(error?.message || "Error inesperado");
  try {
    const payload = JSON.parse(raw);
    if (payload?.detail) return Array.isArray(payload.detail) ? payload.detail.map((d) => d.msg || JSON.stringify(d)).join(" | ") : String(payload.detail);
  } catch (_e) {}
  return raw;
}

function showFeedback(message, kind = "ok") {
  const el = document.getElementById("admin-feedback");
  if (!el) return;
  el.classList.remove("hidden", "status-ok", "status-error");
  el.classList.add(kind === "ok" ? "status-ok" : "status-error");
  el.textContent = message;
}

const STRATEGY_LABELS = {
  ema_rsi: "EMA + RSI",
  mean_reversion_zscore: "Mean Reversion Z-Score",
  momentum_breakout: "Momentum Breakout",
  macd_trend_pullback: "MACD Trend Pullback",
  bollinger_rsi_reversal: "Bollinger + RSI Reversal",
  adx_trend_follow: "ADX Trend Follow",
  stochastic_rebound: "Stochastic Rebound",
};

let USERS = [];
let SELECTED_USER_ID = null;
let SELECTED_PROFILE = null;
let GLOBAL_POLICIES = [];
let ADMIN_PLANS = [];

function setAdminText(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value;
}

function renderAdminReport(nodeId, items) {
  const node = document.getElementById(nodeId);
  if (!node) return;
  node.innerHTML = (items || []).filter(Boolean).map((item) => `
    <article class="quantum-report-item">
      <strong>${item.title || '-'}<\/strong>
      <small>${item.body || '-'}<\/small>
    <\/article>`).join("");
}

function refreshAdminExecutiveSummary() {
  const activeUsers = USERS.filter((u) => u.is_active).length;
  const adminUsers = USERS.filter((u) => u.is_admin).length;
  const activePlans = ADMIN_PLANS.filter((p) => p.is_active).length;
  setAdminText('admin-metric-users', String(USERS.length));
  setAdminText('admin-metric-active-users', String(activeUsers));
  setAdminText('admin-metric-admins', String(adminUsers));
  setAdminText('admin-metric-plans', String(ADMIN_PLANS.length));
  setAdminText('admin-ops-state', USERS.length ? `${activeUsers} activos` : 'Sin datos');
  renderAdminReport('admin-system-report', [
    { title: 'Estado global', body: `${GLOBAL_POLICIES.filter((p) => p.is_enabled_global).length} plataformas con acceso global activo de ${GLOBAL_POLICIES.length}.` },
    { title: 'Base de usuarios', body: `${adminUsers} admins / ${Math.max(USERS.length - adminUsers, 0)} usuarios estándar · ${activeUsers} cuentas activas.` },
    { title: 'Oferta comercial', body: `${activePlans} planes activos de ${ADMIN_PLANS.length} configurados para monetización y gobierno.` },
  ]);
}

function refreshSelectedUserInsights(profile = SELECTED_PROFILE) {
  if (!profile?.user) {
    setAdminText('admin-selected-user-state', 'Sin selección');
    renderAdminReport('admin-user-insights', [{ title: 'Selecciona un usuario', body: 'Elige una cuenta de la columna izquierda para ver resumen ejecutivo, conectores y gobierno.' }]);
    return;
  }
  const user = profile.user;
  const connectors = profile.connectors || [];
  const enabledConnectors = connectors.filter((c) => c.is_enabled).length;
  const grantedPlatforms = (profile.grants || []).filter((g) => g.is_enabled).length;
  const allowedStrategies = (profile.strategy_control?.allowed_strategies || []).length;
  setAdminText('admin-selected-user-state', user.is_active ? 'Cuenta activa' : 'Cuenta inactiva');
  renderAdminReport('admin-user-insights', [
    { title: user.name || user.email || `Usuario ${user.id}`, body: `${user.email}${user.phone ? ` · ${user.phone}` : ''}` },
    { title: 'Supervisión operativa', body: `${enabledConnectors} conectores activos de ${connectors.length} · ${grantedPlatforms} grants activos.` },
    { title: 'Control de estrategia', body: `${profile.strategy_control?.managed_by_admin ? 'Administrado por admin' : 'Libre por usuario'} · ${allowedStrategies} estrategias habilitadas.` },
  ]);
}

function boolPill(v, textOn = "ON", textOff = "OFF") {
  return `<span class="pill tiny ${v ? "pill-on" : "pill-off"}">${v ? textOn : textOff}</span>`;
}

function toCsv(value) {
  if (!Array.isArray(value)) return "";
  return value.join(", ");
}

function fromCsv(value) {
  return String(value || "").split(",").map((s) => s.trim()).filter(Boolean);
}

function renderUserList() {
  const wrap = document.getElementById("admin-users");
  if (!wrap) return;
  document.getElementById("admin-total-users").textContent = `${USERS.length} usuarios`;
  wrap.innerHTML = USERS.map((u) => `
    <button class="admin-user-item ${Number(SELECTED_USER_ID) === u.id ? "selected" : ""}" data-user-id="${u.id}">
      <div class="row-between">
        <strong>${u.name}</strong>
        ${boolPill(u.is_active, "Activo", "Inactivo")}
      </div>
      <small>${u.email}</small>
      <div class="admin-mini-actions">
        <span class="hint">ID ${u.id}</span>
        ${boolPill(u.is_admin, "Admin", "User")}
      </div>
    </button>
  `).join("");

  wrap.querySelectorAll(".admin-user-item").forEach((btn) => btn.addEventListener("click", async () => {
    SELECTED_USER_ID = Number(btn.dataset.userId);
    renderUserList();
    await refreshSelectedUserProfile();
  }));
}

function bindTabs(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const tabs = container.querySelectorAll(".admin-tab");
  tabs.forEach((tab) => tab.addEventListener("click", () => {
    const next = tab.dataset.tab;
    tabs.forEach((t) => t.classList.toggle("active", t === tab));
    container.parentElement.querySelectorAll(".admin-tab-panel").forEach((p) => p.classList.toggle("active", p.dataset.panel === next));
  }));
}

function profileHeader(user) {
  return `
  <div class="row-between">
    <div>
      <h2 style="margin:0;">${user.name}</h2>
      <small class="hint">${user.email} ${user.phone ? `· ${user.phone}` : ""}</small>
    </div>
    <div class="admin-mini-actions">
      ${boolPill(user.is_active, "Activo", "Inactivo")}
      ${boolPill(user.is_admin, "Admin", "User")}
      ${user.is_root ? '<span class="pill tiny pill-on">Jerárquico</span>' : ""}
    </div>
  </div>
  <div class="admin-mini-actions" style="margin-top:10px;">
    <button class="btn btn-sm" onclick="openEditUserModal(${user.id})">Editar</button>
    <button class="btn btn-sm" onclick="toggleUser(${user.id}, ${!user.is_active}, null)">${user.is_active ? "OFF activo" : "ON activo"}</button>
    <button class="btn btn-sm" onclick="toggleUser(${user.id}, null, ${!user.is_admin})">${user.is_admin ? "OFF admin" : "ON admin"}</button>
    ${user.is_root ? "" : `<button class="btn btn-sm" onclick="deleteUser(${user.id})">Eliminar</button>`}
    <button id="open-strategy-modal" class="btn btn-sm">Estrategias</button>
  </div>`;
}

function permissionsPanel(profile) {
  const grants = profile.grants || [];
  const map = grants.reduce((acc, g) => ({ ...acc, [g.platform]: g }), {});
  return `<div class="admin-compact-grid">${GLOBAL_POLICIES.map((p) => {
    const g = map[p.platform] || { is_enabled: false, max_symbols: 5, max_daily_movements: 20, notes: "" };
    return `<form class="admin-box grant-inline-form" data-platform="${p.platform}">
      <div class="row-between"><strong>${p.display_name}</strong>${boolPill(p.is_enabled_global, "Global ON", "Global OFF")}</div>
      <label>Acceso usuario<select name="is_enabled"><option value="true" ${g.is_enabled ? "selected" : ""}>ON</option><option value="false" ${!g.is_enabled ? "selected" : ""}>OFF</option></select></label>
      <label>Máx símbolos<input name="max_symbols" type="number" min="0" value="${g.max_symbols}"></label>
      <label>Máx movimientos<input name="max_daily_movements" type="number" min="0" value="${g.max_daily_movements}"></label>
      <label>Notas<input name="notes" value="${g.notes || ""}"></label>
      <button class="btn btn-sm primary" type="submit">Guardar</button>
    </form>`;
  }).join("")}</div>`;
}

function connectorsPanel(connectors) {
  if (!connectors?.length) return '<div class="hint">Sin conectores para este usuario.</div>';
  return `<div class="admin-compact-grid">${connectors.map((c) => `
    <form class="admin-box connector-inline-form" data-id="${c.id}">
      <div class="row-between"><strong>${c.label}</strong>${boolPill(c.is_enabled, "ON", "OFF")}</div>
      <small class="hint">${c.platform} · ${c.mode} · ${c.market_type}</small>
      <label>Asignación<select name="allocation_mode"><option value="fixed" ${c.allocation_mode === "fixed" ? "selected" : ""}>Fijo</option><option value="percent" ${c.allocation_mode === "percent" ? "selected" : ""}>%</option></select></label>
      <label>Valor<input name="allocation_value" type="number" min="0" value="${c.allocation_value || 0}"></label>
      <label>Símbolos (CSV)<input name="symbols" value="${toCsv(c.symbols)}"></label>
      <label>Estado<select name="is_enabled"><option value="true" ${c.is_enabled ? "selected" : ""}>ON</option><option value="false" ${!c.is_enabled ? "selected" : ""}>OFF</option></select></label>
      <button class="btn btn-sm" type="submit">Actualizar</button>
    </form>
  `).join("")}</div>`;
}

function strategyPanel(control) {
  const all = control?.all_strategies || Object.keys(STRATEGY_LABELS);
  const allowed = new Set(control?.allowed_strategies || []);
  return `<div class="admin-box"><div class="row-between"><strong>Estrategias</strong>${boolPill(control?.managed_by_admin, "Admin controla", "Libre")}</div><div class="chip-wrap">${all.map((s) => `<span class="chip chip-static ${allowed.has(s) ? "pill-on" : ""}">${STRATEGY_LABELS[s] || s}</span>`).join("")}</div></div>`;
}

function renderSelectedProfile(profile) {
  const wrap = document.getElementById("selected-user-profile");
  if (!wrap) return;
  wrap.innerHTML = `
    ${profileHeader(profile.user)}
    <div class="admin-tabs" id="profile-tabs" style="margin-top:12px;">
      <button class="admin-tab active" data-tab="summary">Resumen</button>
      <button class="admin-tab" data-tab="permissions">Permisos</button>
      <button class="admin-tab" data-tab="connectors">Conectores</button>
    </div>
    <div class="admin-tab-panel active" data-panel="summary">
      <div class="admin-compact-grid" style="margin-top:10px;">
        <div class="admin-box">${strategyPanel(profile.strategy_control)}</div>
        <div class="admin-box"><strong>Conectores activos</strong><p>${(profile.connectors || []).filter((x) => x.is_enabled).length} de ${(profile.connectors || []).length}</p></div>
      </div>
    </div>
    <div class="admin-tab-panel" data-panel="permissions" style="margin-top:10px;">${permissionsPanel(profile)}</div>
    <div class="admin-tab-panel" data-panel="connectors" style="margin-top:10px;">${connectorsPanel(profile.connectors)}</div>
  `;

  bindTabs("profile-tabs");
  document.getElementById("open-strategy-modal")?.addEventListener("click", openStrategyModal);

  wrap.querySelectorAll(".grant-inline-form").forEach((form) => form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    try {
      await api("/api/admin/grants", {
        method: "PUT",
        body: JSON.stringify({
          user_id: SELECTED_USER_ID,
          platform: form.dataset.platform,
          is_enabled: fd.get("is_enabled") === "true",
          max_symbols: Number(fd.get("max_symbols") || 0),
          max_daily_movements: Number(fd.get("max_daily_movements") || 0),
          notes: String(fd.get("notes") || ""),
        }),
      });
      showFeedback("Permiso actualizado.");
      await refreshSelectedUserProfile();
    } catch (err) { showFeedback(parseApiError(err), "error"); }
  }));

  wrap.querySelectorAll(".connector-inline-form").forEach((form) => form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    try {
      await api(`/api/connectors/${form.dataset.id}`, {
        method: "PUT",
        body: JSON.stringify({
          is_enabled: fd.get("is_enabled") === "true",
          symbols: fromCsv(fd.get("symbols")),
          config: {
            allocation_mode: String(fd.get("allocation_mode") || "fixed"),
            allocation_value: Number(fd.get("allocation_value") || 0),
          },
        }),
      });
      showFeedback("Conector actualizado.");
      await refreshSelectedUserProfile();
    } catch (err) { showFeedback(parseApiError(err), "error"); }
  }));
}

async function refreshSelectedUserProfile() {
  if (!SELECTED_USER_ID) { refreshSelectedUserInsights(null); return; }
  SELECTED_PROFILE = await api(`/api/admin/users/${SELECTED_USER_ID}/profile`);
  renderSelectedProfile(SELECTED_PROFILE);
  refreshSelectedUserInsights(SELECTED_PROFILE);
}

function renderPolicies(policies) {
  GLOBAL_POLICIES = policies;
  const wrap = document.getElementById("admin-policies");
  wrap.innerHTML = policies.map((p) => `
    <form class="admin-box policy-inline-form" data-platform="${p.platform}">
      <div class="row-between"><strong>${p.display_name}</strong>${boolPill(p.is_enabled_global, "Global ON", "Global OFF")}</div>
      <label>Global<select name="is_enabled_global"><option value="true" ${p.is_enabled_global ? "selected" : ""}>ON</option><option value="false" ${!p.is_enabled_global ? "selected" : ""}>OFF</option></select></label>
      <label>Manual symbols<select name="allow_manual_symbols"><option value="true" ${p.allow_manual_symbols ? "selected" : ""}>ON</option><option value="false" ${!p.allow_manual_symbols ? "selected" : ""}>OFF</option></select></label>
      <label>Top symbols (CSV)<input name="top_symbols" value="${toCsv(p.top_symbols)}"></label>
      <label>Allowed symbols (CSV)<input name="allowed_symbols" value="${toCsv(p.allowed_symbols)}"></label>
      <button class="btn btn-sm" type="submit">Guardar</button>
    </form>
  `).join("");

  wrap.querySelectorAll(".policy-inline-form").forEach((form) => form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    try {
      await api(`/api/admin/policies/${form.dataset.platform}`, {
        method: "PUT",
        body: JSON.stringify({
          platform: form.dataset.platform,
          is_enabled_global: fd.get("is_enabled_global") === "true",
          allow_manual_symbols: fd.get("allow_manual_symbols") === "true",
          top_symbols: fromCsv(fd.get("top_symbols")),
          allowed_symbols: fromCsv(fd.get("allowed_symbols")),
        }),
      });
      showFeedback("Política actualizada.");
      await refreshAdmin();
    } catch (err) { showFeedback(parseApiError(err), "error"); }
  }));
}

function renderPricing(pricing) {
  const form = document.getElementById("pricing-config-form");
  const keys = [
    ["base_commission_usd", "Comisión base USD"],
    ["cost_per_app_usd", "Costo por app"],
    ["cost_per_symbol_usd", "Costo por símbolo"],
    ["cost_per_movement_usd", "Costo por movimiento"],
    ["cost_per_gb_ram_usd", "Costo por GB RAM"],
    ["cost_per_gb_disk_usd", "Costo por GB DISK"],
    ["suggested_ram_per_app_gb", "RAM sugerida/app"],
    ["suggested_disk_per_app_gb", "DISK sugerido/app"],
  ];
  form.innerHTML = `${keys.map(([k, label]) => `<label>${label}<input name="${k}" type="number" step="0.01" min="0" value="${pricing[k]}"></label>`).join("")}<button class="btn btn-sm primary" type="submit">Guardar pricing</button>`;
  form.onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const payload = Object.fromEntries(keys.map(([k]) => [k, Number(fd.get(k) || 0)]));
    try {
      await api("/api/admin/pricing-config", { method: "PUT", body: JSON.stringify(payload) });
      showFeedback("Pricing actualizado.");
    } catch (err) { showFeedback(parseApiError(err), "error"); }
  };
}

function renderPlans(plans) {
  const wrap = document.getElementById("admin-plans");
  wrap.innerHTML = plans.map((p) => `
    <form class="plan-card plan-edit-form" data-plan-id="${p.id}">
      <label>Nombre<input name="name" value="${p.name}"></label>
      <label>Descripción<textarea name="description">${p.description || ""}</textarea></label>
      <div class="admin-compact-grid">
        <label>Apps<input name="apps" type="number" min="0" value="${p.apps}"></label>
        <label>Símbolos<input name="symbols" type="number" min="0" value="${p.symbols}"></label>
        <label>Mov/día<input name="daily_movements" type="number" min="0" value="${p.daily_movements}"></label>
        <label>Precio USD<input name="monthly_price_usd" type="number" min="0" step="0.01" value="${p.monthly_price_usd}"></label>
        <label>Orden<input name="sort_order" type="number" value="${p.sort_order}"></label>
        <label>Custom<select name="is_custom"><option value="true" ${p.is_custom ? "selected" : ""}>Sí</option><option value="false" ${!p.is_custom ? "selected" : ""}>No</option></select></label>
        <label>Activo<select name="is_active"><option value="true" ${p.is_active ? "selected" : ""}>Sí</option><option value="false" ${!p.is_active ? "selected" : ""}>No</option></select></label>
      </div>
      <div class="admin-mini-actions">
        <button class="btn btn-sm" type="submit">Guardar</button>
        <button class="btn btn-sm delete-plan-btn" type="button">Eliminar</button>
      </div>
    </form>
  `).join("");

  wrap.querySelectorAll(".plan-edit-form").forEach((form) => form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const payload = {
      name: String(fd.get("name") || ""),
      description: String(fd.get("description") || ""),
      apps: Number(fd.get("apps") || 0),
      symbols: Number(fd.get("symbols") || 0),
      daily_movements: Number(fd.get("daily_movements") || 0),
      monthly_price_usd: Number(fd.get("monthly_price_usd") || 0),
      is_custom: fd.get("is_custom") === "true",
      is_active: fd.get("is_active") === "true",
      sort_order: Number(fd.get("sort_order") || 0),
    };
    try {
      await api(`/api/admin/plans/${form.dataset.planId}`, { method: "PUT", body: JSON.stringify(payload) });
      showFeedback("Plan actualizado.");
      await refreshAdmin();
    } catch (err) { showFeedback(parseApiError(err), "error"); }
  }));

  wrap.querySelectorAll(".delete-plan-btn").forEach((btn) => btn.addEventListener("click", async () => {
    const id = btn.closest(".plan-edit-form")?.dataset.planId;
    if (!id) return;
    try {
      await api(`/api/admin/plans/${id}`, { method: "DELETE" });
      showFeedback("Plan eliminado.");
      await refreshAdmin();
    } catch (err) { showFeedback(parseApiError(err), "error"); }
  }));
}

async function refreshAdmin() {
  const [users, policies, pricing, plans] = await Promise.all([
    api("/api/admin/users"), api("/api/admin/policies"), api("/api/admin/pricing-config"), api("/api/admin/plans"),
  ]);
  USERS = users;
  ADMIN_PLANS = plans;
  if (!SELECTED_USER_ID && USERS.length) SELECTED_USER_ID = USERS[0].id;
  if (SELECTED_USER_ID && !USERS.find((u) => u.id === SELECTED_USER_ID)) SELECTED_USER_ID = USERS[0]?.id || null;
  renderUserList();
  renderPolicies(policies);
  renderPricing(pricing);
  renderPlans(plans);
  refreshAdminExecutiveSummary();
  if (SELECTED_USER_ID) await refreshSelectedUserProfile();
}

async function toggleUser(id, is_active, is_admin) {
  try { await api(`/api/admin/users/${id}`, { method: "PUT", body: JSON.stringify({ is_active, is_admin }) }); await refreshAdmin(); }
  catch (err) { showFeedback(parseApiError(err), "error"); }
}

async function deleteUser(id) {
  if (!confirm("¿Seguro que deseas eliminar este usuario?")) return;
  try {
    await api(`/api/admin/users/${id}`, { method: "DELETE" });
    if (SELECTED_USER_ID === id) SELECTED_USER_ID = null;
    showFeedback("Usuario eliminado.");
    await refreshAdmin();
  } catch (err) { showFeedback(parseApiError(err), "error"); }
}

function openEditUserModal(userId) {
  const modal = document.getElementById("edit-user-modal");
  const form = document.getElementById("edit-user-form");
  const user = (SELECTED_PROFILE?.user && SELECTED_PROFILE.user.id === userId) ? SELECTED_PROFILE.user : USERS.find((u) => u.id === userId);
  if (!modal || !form || !user) return;
  form.dataset.userId = String(user.id);
  form.email.value = user.email || "";
  form.name.value = user.name || "";
  form.phone.value = user.phone || "";
  form.is_active.value = String(Boolean(user.is_active));
  form.is_admin.value = String(Boolean(user.is_admin));
  const delBtn = document.getElementById("delete-user-in-modal");
  delBtn.dataset.userId = String(user.id);
  delBtn.disabled = Boolean(user.is_root);
  modal.classList.remove("hidden");
}

function closeEditUserModal() { document.getElementById("edit-user-modal")?.classList.add("hidden"); }
function openStrategyModal() {
  const form = document.getElementById("strategy-control-form");
  const control = SELECTED_PROFILE?.strategy_control;
  if (!form || !control) return;
  const all = control.all_strategies || Object.keys(STRATEGY_LABELS);
  const selected = new Set(control.allowed_strategies || []);
  form.innerHTML = `
    <label class="checkbox"><input type="checkbox" name="managed_by_admin" ${control.managed_by_admin ? "checked" : ""}>Administrado por admin</label>
    <div class="strategy-check-grid">${all.map((s) => `<label class="checkbox"><input type="checkbox" name="allowed_strategies" value="${s}" ${selected.has(s) ? "checked" : ""}>${STRATEGY_LABELS[s] || s}</label>`).join("")}</div>
    <button class="btn primary btn-sm" type="submit">Guardar</button>`;
  document.getElementById("strategy-modal")?.classList.remove("hidden");
}
function closeStrategyModal() { document.getElementById("strategy-modal")?.classList.add("hidden"); }

window.toggleUser = toggleUser;
window.deleteUser = deleteUser;
window.openEditUserModal = openEditUserModal;

document.getElementById("create-user-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const password = String(fd.get("password") || "");
  if (password.length < 6) return showFeedback("La contraseña debe tener mínimo 6 caracteres.", "error");
  try {
    await api("/api/admin/users", { method: "POST", body: JSON.stringify({ email: String(fd.get("email") || "").trim().toLowerCase(), name: String(fd.get("name") || "").trim(), password }) });
    showFeedback("Usuario creado.");
    e.target.reset();
    await refreshAdmin();
  } catch (err) { showFeedback(parseApiError(err), "error"); }
});

document.getElementById("edit-user-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.currentTarget;
  const fd = new FormData(form);
  const userId = Number(form.dataset.userId || 0);
  if (!userId) return;
  try {
    await api(`/api/admin/users/${userId}`, { method: "PUT", body: JSON.stringify({ email: String(fd.get("email") || "").trim().toLowerCase(), name: String(fd.get("name") || "").trim(), phone: String(fd.get("phone") || "").trim(), is_active: fd.get("is_active") === "true", is_admin: fd.get("is_admin") === "true" }) });
    closeEditUserModal();
    showFeedback("Usuario actualizado.");
    await refreshAdmin();
  } catch (err) { showFeedback(parseApiError(err), "error"); }
});

document.getElementById("delete-user-in-modal")?.addEventListener("click", async (e) => {
  const id = Number(e.currentTarget.dataset.userId || 0);
  if (!id) return;
  await deleteUser(id);
  closeEditUserModal();
});

document.getElementById("add-plan-btn")?.addEventListener("click", async () => {
  try {
    await api("/api/admin/plans", { method: "POST", body: JSON.stringify({ name: "Nuevo plan", description: "Describe este plan", apps: 1, symbols: 5, daily_movements: 10, monthly_price_usd: 25, is_custom: false, is_active: true, sort_order: 99 }) });
    showFeedback("Plan creado.");
    await refreshAdmin();
  } catch (err) { showFeedback(parseApiError(err), "error"); }
});

document.getElementById("strategy-control-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!SELECTED_USER_ID) return;
  const fd = new FormData(e.target);
  try {
    await api(`/api/admin/users/${SELECTED_USER_ID}/strategy-control`, { method: "PUT", body: JSON.stringify({ managed_by_admin: fd.get("managed_by_admin") === "on", allowed_strategies: fd.getAll("allowed_strategies") }) });
    closeStrategyModal();
    showFeedback("Estrategias actualizadas.");
    await refreshSelectedUserProfile();
  } catch (err) { showFeedback(parseApiError(err), "error"); }
});

document.getElementById("close-edit-user-modal")?.addEventListener("click", closeEditUserModal);
document.getElementById("edit-user-modal")?.addEventListener("click", (e) => { if (e.target.id === "edit-user-modal") closeEditUserModal(); });
document.getElementById("close-strategy-modal")?.addEventListener("click", closeStrategyModal);
document.getElementById("strategy-modal")?.addEventListener("click", (e) => { if (e.target.id === "strategy-modal") closeStrategyModal(); });

bindTabs("settings-tabs");
refreshAdmin().catch((err) => showFeedback(parseApiError(err), "error"));
