async function api(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    ...options,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function showFeedback(message, kind = "ok") {
  const el = document.getElementById("admin-feedback");
  if (!el) return;
  el.classList.remove("hidden", "status-ok", "status-error");
  el.classList.add(kind === "ok" ? "status-ok" : "status-error");
  el.textContent = message;
}

let USERS = [];

function renderUserPicker() {
  const select = document.getElementById("selected-user");
  if (!select) return;
  const prev = select.value;
  select.innerHTML = USERS.map((u) => `<option value="${u.id}">${u.name} (${u.email})</option>`).join("");
  if (prev && USERS.find((u) => String(u.id) === prev)) select.value = prev;
}

async function refreshSelectedUserProfile() {
  const select = document.getElementById("selected-user");
  const out = document.getElementById("selected-user-profile");
  if (!select || !out || !select.value) return;

  const data = await api(`/api/admin/users/${select.value}/profile`);
  const { user, policies, grants, connectors, strategy_control } = data;
  const grantMap = grants.reduce((acc, g) => ({ ...acc, [g.platform]: g }), {});

  out.innerHTML = `
    <div class="connector-item">
      <strong>${user.name}</strong>
      <div class="connector-meta">
        <span>${user.email}</span>
        <span>Admin: ${user.is_admin ? "Sí" : "No"}</span>
        <span>Activo: ${user.is_active ? "Sí" : "No"}</span>
        ${user.is_root ? '<span class="pill tiny pill-on">Jerárquico</span>' : ''}
      </div>
      <div class="row-wrap" style="margin-top:10px;">
        <button class="btn" onclick="toggleUser(${user.id}, ${!user.is_active}, null)">${user.is_active ? "Desactivar" : "Activar"}</button>
        <button class="btn" onclick="toggleUser(${user.id}, null, ${!user.is_admin})">${user.is_admin ? "Quitar admin" : "Hacer admin"}</button>
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
                <label>Notas<input name="notes" value="${grant.notes || ""}" placeholder="Ej: fixed:10 o percent:75"></label>
                <button class="btn save-btn" type="submit">Guardar</button>
              </div>
            </form>
          `;
        }).join("")}
      </div>
    </div>

    <div class="connector-item">
      <strong>Conectores del usuario (editar monto fijo o %)</strong>
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
              <label>Valor<input name="allocation_value" type="number" step="0.01" value="${c.allocation_value || 0}"></label>
              <label>Símbolos autorizados<input name="symbols" value="${(c.symbols || []).join(",")}" placeholder="BTC/USDT,ETH/USDT"></label>
              <button class="btn save-btn" type="submit">Guardar conector</button>
            </div>
          </form>
        `).join("") || '<small class="hint">Este usuario aún no tiene conectores.</small>'}
      </div>
    </div>

    <div class="connector-item">
      <strong>Estrategias del usuario</strong>
      <p class="hint">Puedes dejar el usuario "Manejado por admin" o permitir que lo gestione él mismo.</p>
      <form id="strategy-control-form" class="form-grid admin-form-grid" style="margin-top:8px;">
        <label>Modo de gestión
          <select name="managed_by_admin">
            <option value="true" ${strategy_control?.managed_by_admin ? "selected" : ""}>Manejado por admin</option>
            <option value="false" ${!strategy_control?.managed_by_admin ? "selected" : ""}>Manejado por usuario</option>
          </select>
        </label>
        <label>Estrategias permitidas
          <select name="allowed_strategies" multiple size="3">
            ${(strategy_control?.all_strategies || []).map((slug) => `<option value="${slug}" ${(strategy_control?.allowed_strategies || []).includes(slug) ? "selected" : ""}>${slug}</option>`).join("")}
          </select>
        </label>
        <button class="btn save-btn" type="submit">Guardar estrategias</button>
      </form>
    </div>
  `;

  out.querySelectorAll(".grant-inline-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const fd = new FormData(form);
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
    });
  });

  out.querySelectorAll(".connector-inline-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const fd = new FormData(form);
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
    });
  });

  out.querySelector("#strategy-control-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const fd = new FormData(form);
    const selected = Array.from(form.querySelector('select[name="allowed_strategies"]').selectedOptions).map((option) => option.value);
    await api(`/api/admin/users/${user.id}/strategy-control`, {
      method: "PUT",
      body: JSON.stringify({
        managed_by_admin: fd.get("managed_by_admin") === "true",
        allowed_strategies: selected,
      }),
    });
    showFeedback("Estrategias actualizadas correctamente.");
    refreshSelectedUserProfile();
  });
}

async function refreshAdmin() {
  const [users, policies] = await Promise.all([
    api("/api/admin/users"),
    api("/api/admin/policies"),
  ]);
  USERS = users;

  renderUserPicker();

  document.getElementById("admin-users").innerHTML = users.map(u => `
    <div class="connector-item">
      <strong>${u.name}</strong>
      <div class="connector-meta"><span>${u.email}</span><span>ID: ${u.id}</span><span>Admin: ${u.is_admin ? "Sí" : "No"}</span><span>Activo: ${u.is_active ? "Sí" : "No"}</span></div>
    </div>
  `).join("");

  document.getElementById("admin-policies").innerHTML = policies.map(p => {
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
          <button class="btn" onclick='togglePolicy(${JSON.stringify(p.platform)}, ${!p.is_enabled_global}, null)'>${p.is_enabled_global ? "Desactivar acceso global" : "Activar acceso global"}</button>
          <button class="btn" onclick='togglePolicy(${JSON.stringify(p.platform)}, null, ${!p.allow_manual_symbols})'>${p.allow_manual_symbols ? "Bloquear carga manual" : "Permitir carga manual"}</button>
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
    showFeedback(`No se pudo actualizar el usuario: ${err.message}`, "error");
  }
}

async function togglePolicy(platform, is_enabled_global, allow_manual_symbols) {
  await api(`/api/admin/policies/${platform}`, { method: "PUT", body: JSON.stringify({ platform, is_enabled_global, allow_manual_symbols }) });
  refreshAdmin();
}

document.getElementById("selected-user")?.addEventListener("change", refreshSelectedUserProfile);

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
    showFeedback(`No se pudo crear el usuario: ${err.message}`, "error");
  }
});

refreshAdmin().catch(err => {
  const output = document.getElementById("selected-user-profile");
  if (output) output.innerHTML = `<div class="status-msg status-error">${err.message}</div>`;
});
