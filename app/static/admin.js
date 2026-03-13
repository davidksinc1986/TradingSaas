async function api(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    ...options,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function parseApiError(error) {
  const raw = String(error?.message || "Error inesperado");
  try {
    const parsed = JSON.parse(raw);
    if (parsed?.detail) {
      if (Array.isArray(parsed.detail)) return parsed.detail.map((d) => d.msg || JSON.stringify(d)).join(" | ");
      return String(parsed.detail);
    }
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

function cleanNote(value) {
  if (!value) return "Sin notas";
  if (String(value).toLowerCase().includes("auto-created default grant")) return "Permiso base generado automáticamente.";
  return value;
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

function renderUserList() {
  const container = document.getElementById("admin-users");
  if (!container) return;
  container.innerHTML = USERS.map((u) => `
    <button class="connector-item user-card ${Number(SELECTED_USER_ID) === u.id ? "selected" : ""}" data-user-id="${u.id}">
      <strong>${u.name}</strong>
      <div class="connector-meta"><span>${u.email}</span><span>ID: ${u.id}</span><span>Admin: ${u.is_admin ? "Sí" : "No"}</span><span>Activo: ${u.is_active ? "Sí" : "No"}</span></div>
    </button>
  `).join("");
  container.querySelectorAll(".user-card").forEach((btn) => {
    btn.addEventListener("click", async () => {
      SELECTED_USER_ID = Number(btn.dataset.userId);
      renderUserList();
      await refreshSelectedUserProfile();
    });
  });
}

function openStrategyModal() {
  const modal = document.getElementById("strategy-modal");
  if (!modal || !SELECTED_PROFILE) return;
  const control = SELECTED_PROFILE.strategy_control || { managed_by_admin: false, all_strategies: [], allowed_strategies: [] };
  const form = document.getElementById("strategy-control-form");
  form.innerHTML = `
    <label class="checkbox"><input type="checkbox" name="managed_by_admin" ${control.managed_by_admin ? "checked" : ""}> Gestionado por admin (el usuario no puede cambiarla)</label>
    <div class="stack">
      ${control.all_strategies.map((slug) => `
        <label class="checkbox">
          <input type="checkbox" name="allowed_strategies" value="${slug}" ${control.allowed_strategies.includes(slug) ? "checked" : ""}>
          ${STRATEGY_LABELS[slug] || slug}
        </label>
      `).join("")}
    </div>
    <button class="btn primary btn-sm" type="submit">Guardar estrategias</button>
  `;
  modal.classList.remove("hidden");
}

function closeStrategyModal() {
  document.getElementById("strategy-modal")?.classList.add("hidden");
}

async function refreshSelectedUserProfile() {
  const out = document.getElementById("selected-user-profile");
  if (!out || !SELECTED_USER_ID) return;
  const data = await api(`/api/admin/users/${SELECTED_USER_ID}/profile`);
  SELECTED_PROFILE = data;
  const { user, policies, grants, connectors } = data;
  const grantMap = grants.reduce((acc, g) => ({ ...acc, [g.platform]: g }), {});

  out.innerHTML = `
    <div class="connector-item">
      <strong>${user.name}</strong>
      <div class="connector-meta">
        <span>${user.email}</span>
        <span>Admin: ${user.is_admin ? "Sí" : "No"}</span>
        <span>Activo: ${user.is_active ? "Sí" : "No"}</span>
        ${user.is_root ? '<span class="pill tiny pill-on">Jerárquico</span>' : ""}
      </div>
      <div class="row-wrap" style="margin-top:10px;">
        <button class="btn btn-sm" onclick="toggleUser(${user.id}, ${!user.is_active}, null)">${user.is_active ? "Desactivar" : "Activar"}</button>
        <button class="btn btn-sm" onclick="toggleUser(${user.id}, null, ${!user.is_admin})">${user.is_admin ? "Quitar admin" : "Hacer admin"}</button>
      </div>
    </div>

    <div class="connector-item">
      <strong>Permisos por plataforma (solo de este usuario)</strong>
      <div class="stack">
        ${policies.map((policy) => {
          const grant = grantMap[policy.platform] || { is_enabled: false, max_symbols: 5, max_daily_movements: 20, notes: "" };
          return `
            <form class="grant-inline-form" data-platform="${policy.platform}" style="border:1px solid rgba(255,255,255,0.08);padding:10px;border-radius:12px;">
              <div class="row-between">
                <strong>${policy.display_name}</strong>
                <span class="pill tiny ${policy.is_enabled_global ? "pill-on" : "pill-off"}">${policy.is_enabled_global ? "Global activo" : "Global bloqueado"}</span>
              </div>
              <div class="form-grid admin-form-grid" style="margin-top:8px;">
                <label>Habilitado usuario
                  <select name="is_enabled">
                    <option value="true" ${grant.is_enabled ? "selected" : ""}>Sí</option>
                    <option value="false" ${!grant.is_enabled ? "selected" : ""}>No</option>
                  </select>
                </label>
                <label>Máx. símbolos<input name="max_symbols" type="number" value="${grant.max_symbols}"></label>
                <label>Máx. movimientos diarios<input name="max_daily_movements" type="number" value="${grant.max_daily_movements}"></label>
                <label>Notas<input name="notes" value="${cleanNote(grant.notes || "")}" placeholder="Ej: fixed:10 o percent:75"></label>
                <button class="btn primary btn-sm" type="submit">Guardar</button>
              </div>
            </form>
          `;
        }).join("")}
      </div>
    </div>

    <div class="connector-item">
      <strong>Conectores del usuario</strong>
      <div class="stack">
        ${connectors.map((c) => `
          <form class="connector-inline-form" data-id="${c.id}" style="border:1px solid rgba(255,255,255,0.08);padding:10px;border-radius:12px;">
            <div class="row-between">
              <strong>${c.label} (${c.platform})</strong>
              <span class="pill tiny ${c.is_enabled ? "pill-on" : "pill-off"}">${c.is_enabled ? "Activo" : "Desactivado"}</span>
            </div>
            <div class="form-grid admin-form-grid" style="margin-top:8px;">
              <label>Modo asignación
                <select name="allocation_mode">
                  <option value="fixed" ${c.allocation_mode === "fixed" ? "selected" : ""}>Monto fijo</option>
                  <option value="percent" ${c.allocation_mode === "percent" ? "selected" : ""}>Porcentaje disponible</option>
                </select>
              </label>
              <label>Valor<input name="allocation_value" type="number" step="1" value="${c.allocation_value || 0}"></label>
              <label>Símbolos autorizados<input name="symbols" value="${(c.symbols || []).join(",")}" placeholder="BTC/USDT,ETH/USDT"></label>
              <button class="btn primary btn-sm" type="submit">Guardar conector</button>
            </div>
          </form>
        `).join("") || '<small class="hint">Este usuario aún no tiene conectores.</small>'}
      </div>
    </div>
  `;

  out.querySelectorAll(".grant-inline-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const fd = new FormData(form);
      try {
        await api("/api/admin/grants", {
          method: "PUT",
          body: JSON.stringify({
            user_id: Number(user.id),
            platform: form.dataset.platform,
            is_enabled: fd.get("is_enabled") === "true",
            max_symbols: Number(fd.get("max_symbols")),
            max_daily_movements: Number(fd.get("max_daily_movements")),
            notes: String(fd.get("notes") || ""),
          }),
        });
        showFeedback("Permisos actualizados correctamente.");
        refreshSelectedUserProfile();
      } catch (err) {
        showFeedback(parseApiError(err), "error");
      }
    });
  });

  out.querySelectorAll(".connector-inline-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const fd = new FormData(form);
      try {
        await api(`/api/connectors/${form.dataset.id}`, {
          method: "PUT",
          body: JSON.stringify({
            symbols: String(fd.get("symbols") || "").split(",").map((v) => v.trim()).filter(Boolean),
            config: {
              allocation_mode: fd.get("allocation_mode"),
              allocation_value: Number(fd.get("allocation_value")),
            },
          }),
        });
        showFeedback("Conector actualizado correctamente.");
        refreshSelectedUserProfile();
      } catch (err) {
        showFeedback(parseApiError(err), "error");
      }
    });
  });
}

async function refreshAdmin() {
  const [users, policies] = await Promise.all([api("/api/admin/users"), api("/api/admin/policies")]);
  USERS = users;
  if (!SELECTED_USER_ID && USERS.length) SELECTED_USER_ID = USERS[0].id;
  if (SELECTED_USER_ID && !USERS.find((u) => u.id === SELECTED_USER_ID)) SELECTED_USER_ID = USERS[0]?.id || null;
  renderUserList();

  document.getElementById("admin-policies").innerHTML = policies.map((p) => {
    const globalBadge = p.is_enabled_global ? "Global: Activado" : "Global: Desactivado";
    const manualBadge = p.allow_manual_symbols ? "Carga manual: Permitida" : "Carga manual: Bloqueada";
    return `
      <div class="connector-item">
        <div class="row-between">
          <strong>${p.display_name}</strong>
          <div class="row-wrap">
            <span class="pill tiny ${p.is_enabled_global ? "pill-on" : "pill-off"}">${globalBadge}</span>
            <span class="pill tiny ${p.allow_manual_symbols ? "pill-on" : "pill-off"}">${manualBadge}</span>
          </div>
        </div>
        <div class="row-wrap" style="margin-top:8px;">
          <button class="btn btn-sm" onclick='togglePolicy(${JSON.stringify(p.platform)}, ${!p.is_enabled_global}, null)'>${p.is_enabled_global ? "Desactivar acceso global" : "Activar acceso global"}</button>
          <button class="btn btn-sm" onclick='togglePolicy(${JSON.stringify(p.platform)}, null, ${!p.allow_manual_symbols})'>${p.allow_manual_symbols ? "Bloquear carga manual" : "Permitir carga manual"}</button>
        </div>
      </div>
    `;
  }).join("");

  await refreshSelectedUserProfile();
}

async function toggleUser(id, is_active, is_admin) {
  try {
    await api(`/api/admin/users/${id}`, { method: "PUT", body: JSON.stringify({ is_active, is_admin }) });
    await refreshAdmin();
  } catch (err) {
    showFeedback(parseApiError(err), "error");
  }
}

async function togglePolicy(platform, is_enabled_global, allow_manual_symbols) {
  try {
    await api(`/api/admin/policies/${platform}`, { method: "PUT", body: JSON.stringify({ platform, is_enabled_global, allow_manual_symbols }) });
    refreshAdmin();
  } catch (err) {
    showFeedback(parseApiError(err), "error");
  }
}

document.getElementById("create-user-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const fd = new FormData(e.target);
    const password = String(fd.get("password") || "");
    if (password.length < 6) {
      showFeedback("La contraseña debe tener al menos 6 caracteres.", "error");
      return;
    }
    await api("/api/admin/users", {
      method: "POST",
      body: JSON.stringify({
        email: String(fd.get("email") || "").trim(),
        name: String(fd.get("name") || "").trim(),
        password,
      }),
    });
    showFeedback("Usuario creado exitosamente.");
    e.target.reset();
    refreshAdmin();
  } catch (err) {
    showFeedback(parseApiError(err), "error");
  }
});

document.getElementById("open-strategy-modal")?.addEventListener("click", openStrategyModal);
document.getElementById("close-strategy-modal")?.addEventListener("click", closeStrategyModal);
document.getElementById("strategy-control-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!SELECTED_USER_ID) return;
  const fd = new FormData(e.target);
  try {
    await api(`/api/admin/users/${SELECTED_USER_ID}/strategy-control`, {
      method: "PUT",
      body: JSON.stringify({
        managed_by_admin: fd.get("managed_by_admin") === "on",
        allowed_strategies: fd.getAll("allowed_strategies"),
      }),
    });
    showFeedback("Estrategias asignadas correctamente.");
    closeStrategyModal();
    refreshSelectedUserProfile();
  } catch (err) {
    showFeedback(parseApiError(err), "error");
  }
});

refreshAdmin().catch((err) => {
  const output = document.getElementById("selected-user-profile");
  if (output) output.innerHTML = `<div class="status-msg status-error">${parseApiError(err)}</div>`;
});
