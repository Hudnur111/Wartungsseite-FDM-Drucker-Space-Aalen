const state = {
  user: null,
  csrfToken: "",
  devices: [],
  tasks: [],
  logs: [],
  notes: [],
  xlTools: [],
  selectedDeviceId: null,
  view: "maintenance",
  adminTab: "profile",
  admin: null,
};

const $ = (selector) => document.querySelector(selector);
const els = {
  currentUser: $("#currentUser"),
  mainMenu: $("#mainMenu"),
  adminToggle: $("#adminToggle"),
  logoutButton: $("#logoutButton"),
  exportMonth: $("#exportMonth"),
  exportCsvButton: $("#exportCsvButton"),
  exportPdfButton: $("#exportPdfButton"),
  deviceCount: $("#deviceCount"),
  deviceSearch: $("#deviceSearch"),
  fleetHealth: $("#fleetHealth"),
  deviceList: $("#deviceList"),
  notificationBanner: $("#notificationBanner"),
  deviceHeader: $("#deviceHeader"),
  overviewStats: $("#overviewStats"),
  hoursForm: $("#hoursForm"),
  currentHoursInput: $("#currentHoursInput"),
  taskSelect: $("#taskSelect"),
  doneOn: $("#doneOn"),
  printHours: $("#printHours"),
  logNote: $("#logNote"),
  logForm: $("#logForm"),
  searchInput: $("#searchInput"),
  statusFilter: $("#statusFilter"),
  levelFilter: $("#levelFilter"),
  taskRows: $("#taskRows"),
  taskCards: $("#taskCards"),
  taskSummary: $("#taskSummary"),
  maintenanceTimeline: $("#maintenanceTimeline"),
  xlToolsPanel: $("#xlToolsPanel"),
  xlToolsGrid: $("#xlToolsGrid"),
  noteForm: $("#noteForm"),
  noteDate: $("#noteDate"),
  noteText: $("#noteText"),
  noteList: $("#noteList"),
  historyList: $("#historyList"),
  refreshButton: $("#refreshButton"),
  adminPanel: $("#adminPanel"),
  adminCloseButton: $("#adminCloseButton"),
  adminSummary: $("#adminSummary"),
  adminTabs: $("#adminTabs"),
  profileForm: $("#profileForm"),
  profileName: $("#profileName"),
  profileEmail: $("#profileEmail"),
  profilePassword: $("#profilePassword"),
  profilePasswordConfirm: $("#profilePasswordConfirm"),
  adminUsers: $("#adminUsers"),
  userSearch: $("#userSearch"),
  userRoleFilter: $("#userRoleFilter"),
  userStatusFilter: $("#userStatusFilter"),
  teamCodeForm: $("#teamCodeForm"),
  teamCodeInput: $("#teamCodeInput"),
  deviceForm: $("#deviceForm"),
  adminDevices: $("#adminDevices"),
  taskForm: $("#taskForm"),
  backupButton: $("#backupButton"),
  backupKeep: $("#backupKeep"),
  backupPruneButton: $("#backupPruneButton"),
  backupList: $("#backupList"),
  notificationForm: $("#notificationForm"),
  teamsWebhook: $("#teamsWebhook"),
  sendDueButton: $("#sendDueButton"),
  auditSearch: $("#auditSearch"),
  auditActionFilter: $("#auditActionFilter"),
  auditEntityFilter: $("#auditEntityFilter"),
  auditList: $("#auditList"),
  toastStack: $("#toastStack"),
  confirmDialog: $("#confirmDialog"),
  confirmTitle: $("#confirmTitle"),
  confirmText: $("#confirmText"),
};

function todayIso() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDate(value) {
  if (!value) return "-";
  const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return value;
  return `${match[3]}.${match[2]}.${match[1]}`;
}

function isoDate(value) {
  return /^\d{4}-\d{2}-\d{2}$/.test(String(value || "")) ? value : null;
}

function parseIso(value) {
  const iso = isoDate(value);
  return iso ? new Date(`${iso}T00:00:00`) : null;
}

function numberOrNull(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function showToast(message, type = "success") {
  const toast = document.createElement("article");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  els.toastStack.append(toast);
  window.setTimeout(() => {
    toast.classList.add("closing");
    toast.addEventListener("animationend", () => toast.remove(), { once: true });
  }, 3200);
}

async function runAction(action, successMessage = "") {
  try {
    await action();
    if (successMessage) showToast(successMessage);
  } catch (error) {
    showToast(error.message || "Aktion fehlgeschlagen.", "error");
  }
}

function confirmAction(title, text) {
  if (!els.confirmDialog?.showModal) return Promise.resolve(window.confirm(text));
  els.confirmTitle.textContent = title;
  els.confirmText.textContent = text;
  return new Promise((resolve) => {
    els.confirmDialog.addEventListener("close", () => resolve(els.confirmDialog.returnValue === "ok"), { once: true });
    els.confirmDialog.showModal();
  });
}

function openAdminModal() {
  if (!state.admin || state.user?.role !== "Administrator") return;
  state.adminTab = state.adminTab || "profile";
  els.adminPanel.classList.remove("hidden");
  renderAdmin();
  if (els.adminPanel.showModal && !els.adminPanel.open) {
    els.adminPanel.showModal();
  }
}

function closeAdminModal() {
  if (els.adminPanel.open) els.adminPanel.close();
}

async function api(path, options = {}) {
  const method = options.method || "GET";
  const headers = new Headers(options.headers || {});
  if (method !== "GET") headers.set("X-CSRF-Token", state.csrfToken);
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401) {
    location.href = "/login";
    throw new Error("Nicht angemeldet.");
  }
  if (!response.ok) {
    let message = await response.text();
    try {
      message = JSON.parse(message).error || message;
    } catch {}
    throw new Error(message || "Anfrage fehlgeschlagen.");
  }
  const type = response.headers.get("Content-Type") || "";
  return type.includes("application/json") ? response.json() : response.text();
}

function selectedDevice() {
  return state.devices.find((device) => device.id === state.selectedDeviceId) || state.devices[0];
}

function tasksForDevice(device) {
  return state.tasks
    .filter((task) => task.active !== 0)
    .filter((task) => task.applies_to === "all" || task.applies_to === device.kind)
    .sort((a, b) => a.sort_order - b.sort_order);
}

function logsForDevice(deviceId) {
  return state.logs.filter((log) => log.device_id === deviceId);
}

function notesForDevice(deviceId) {
  return state.notes.filter((note) => note.device_id === deviceId);
}

function latestLog(deviceId, taskId) {
  const logs = logsForDevice(deviceId).filter((log) => log.task_id === taskId);
  if (!logs.length) return null;
  return logs.sort((a, b) => {
    const aIso = isoDate(a.done_on) || "0000-00-00";
    const bIso = isoDate(b.done_on) || "0000-00-00";
    if (aIso !== bIso) return bIso.localeCompare(aIso);
    return b.id - a.id;
  })[0];
}

function currentHours(device) {
  const explicit = numberOrNull(device.current_print_hours);
  if (explicit !== null) return explicit;
  const fromLogs = logsForDevice(device.id).map((log) => numberOrNull(log.print_hours)).filter((value) => value !== null);
  return fromLogs.length ? Math.max(...fromLogs) : null;
}

function statusFor(device, task, log) {
  const current = currentHours(device);
  if (!task.cadence_days && !task.cadence_hours) {
    return { className: "optional", label: task.interval_text === "vor jedem Druck" ? "pro Druck" : "bei Bedarf" };
  }
  if (!log) return { className: "open", label: "offen" };
  const logHours = numberOrNull(log.print_hours);
  if (task.cadence_hours && logHours !== null && current !== null) {
    const ageHours = Math.max(0, current - logHours);
    if (ageHours > task.cadence_hours) return { className: "due", label: "fällig", detail: `${ageHours} h` };
    if (task.cadence_hours - ageHours <= 25) return { className: "due-soon", label: "bald", detail: `${ageHours} h` };
    return { className: "ok", label: "ok", detail: `${ageHours} h` };
  }
  if (task.cadence_hours && !task.cadence_days) return { className: "open", label: "Stunden fehlen" };
  const date = parseIso(log.done_on);
  if (!date) return { className: "open", label: "Datum prüfen" };
  const ageDays = Math.floor((new Date() - date) / 86400000);
  if (ageDays > task.cadence_days) return { className: "due", label: "fällig", detail: `${ageDays} Tage` };
  if (task.cadence_days - ageDays <= 7) return { className: "due-soon", label: "bald", detail: `${ageDays} Tage` };
  return { className: "ok", label: "ok", detail: `${ageDays} Tage` };
}

function timelineItem(device, task) {
  const log = latestLog(device.id, task.id);
  const status = statusFor(device, task, log);
  if (status.className === "optional" || status.className === "ok") return null;
  const priority = { due: 0, open: 1, "due-soon": 2 }[status.className] ?? 9;
  return { device, task, log, status, priority };
}

function allTimelineItems() {
  return state.devices
    .filter((device) => device.active !== 0)
    .flatMap((device) => tasksForDevice(device).map((task) => timelineItem(device, task)).filter(Boolean))
    .sort((a, b) => a.priority - b.priority || a.device.name.localeCompare(b.device.name) || a.task.title.localeCompare(b.task.title));
}

function canLogTask(task) {
  if (!state.user) return false;
  if (state.user.role === "Administrator" || state.user.role === "Mentor") return true;
  return task.level === "B";
}

function updateExportLinks() {
  const month = els.exportMonth.value ? `?month=${encodeURIComponent(els.exportMonth.value)}` : "";
  els.exportCsvButton.href = `/api/export.csv${month}`;
  els.exportPdfButton.href = `/api/export.pdf${month}`;
}

function filteredDevices() {
  const search = (els.deviceSearch.value || "").toLowerCase().trim();
  return state.devices
    .filter((device) => device.active !== 0)
    .filter((device) => {
      if (!search) return true;
      return `${device.name} ${device.type_label} ${device.mentors}`.toLowerCase().includes(search);
    });
}

function fleetStatus() {
  const counts = { due: 0, soon: 0, ok: 0 };
  state.devices.filter((device) => device.active !== 0).forEach((device) => {
    tasksForDevice(device).forEach((task) => {
      const status = statusFor(device, task, latestLog(device.id, task.id));
      if (status.className === "due" || status.className === "open") counts.due += 1;
      if (status.className === "due-soon") counts.soon += 1;
      if (status.className === "ok") counts.ok += 1;
    });
  });
  return counts;
}

function renderFleetHealth() {
  const counts = fleetStatus();
  els.fleetHealth.innerHTML = `
    <span><strong>${counts.due}</strong> fällig</span>
    <span><strong>${counts.soon}</strong> bald</span>
    <span><strong>${counts.ok}</strong> ok</span>
  `;
}

function renderDevices() {
  const devices = filteredDevices();
  els.deviceCount.textContent = state.devices.filter((device) => device.active !== 0).length;
  els.deviceList.innerHTML = devices.length ? devices
    .map((device) => `
      <button class="device-button ${device.id === state.selectedDeviceId ? "active" : ""}" data-device="${escapeHtml(device.id)}">
        <strong>${escapeHtml(device.name)}</strong>
        <span>${escapeHtml(device.type_label || device.kind)} · ${escapeHtml(device.mentors || "ohne Mentor")}</span>
      </button>
    `).join("") : '<div class="empty compact">Kein Gerät gefunden.</div>';
  els.deviceList.querySelectorAll("[data-device]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedDeviceId = button.dataset.device;
      render();
    });
  });
}

function renderHeader(device, tasks) {
  const hours = currentHours(device);
  els.deviceHeader.innerHTML = `
    <div>
      <h2>${escapeHtml(device.name)}</h2>
      <div class="device-meta">
        <span class="pill">${escapeHtml(device.type_label || device.kind)}</span>
        <span class="pill">Mentoren: ${escapeHtml(device.mentors || "-")}</span>
        <span class="pill">${tasks.length} Wartungspunkte</span>
      </div>
    </div>
    <div class="device-meta">
      <span class="pill">${logsForDevice(device.id).length} Einträge</span>
      <span class="pill">${notesForDevice(device.id).length} Vermerke</span>
      ${hours !== null ? `<span class="pill">${escapeHtml(hours)} h</span>` : ""}
    </div>
  `;
  els.currentHoursInput.value = hours ?? "";
}

function renderStats(device, tasks) {
  const counts = {};
  tasks.forEach((task) => {
    const status = statusFor(device, task, latestLog(device.id, task.id));
    counts[status.className] = (counts[status.className] || 0) + 1;
  });
  const due = (counts.open || 0) + (counts.due || 0);
  const latest = logsForDevice(device.id).map((log) => isoDate(log.done_on)).filter(Boolean).sort().pop();
  els.overviewStats.innerHTML = `
    <article class="stat-card accent-red"><span>Offen / fällig</span><strong>${due}</strong></article>
    <article class="stat-card accent-amber"><span>Bald fällig</span><strong>${counts["due-soon"] || 0}</strong></article>
    <article class="stat-card accent-green"><span>Aktuell ok</span><strong>${counts.ok || 0}</strong></article>
    <article class="stat-card accent-blue"><span>Letzter Eintrag</span><strong>${escapeHtml(formatDate(latest))}</strong></article>
  `;
  if (due) {
    els.notificationBanner.textContent = `${due} Wartungspunkt(e) sind offen oder fällig.`;
    els.notificationBanner.classList.remove("hidden");
  } else {
    els.notificationBanner.classList.add("hidden");
  }
}

function renderTaskSelect(device, tasks) {
  els.taskSelect.innerHTML = tasks
    .filter(canLogTask)
    .map((task) => `<option value="${escapeHtml(task.id)}">${escapeHtml(task.title)}</option>`)
    .join("");
}

function filterText() {
  return (els.searchInput.value || "").toLowerCase().trim();
}

function renderTaskRows(device, tasks) {
  const search = filterText();
  const wantedStatus = els.statusFilter.value;
  const wantedLevel = els.levelFilter.value;
  let dueCount = 0;
  const rows = [];
  const cards = [];
  tasks.forEach((task) => {
    const log = latestLog(device.id, task.id);
    const status = statusFor(device, task, log);
    if (status.className === "due" || status.className === "open") dueCount += 1;
    if (wantedStatus && !(wantedStatus === "due" ? ["due", "open"].includes(status.className) : status.className === wantedStatus)) return;
    if (wantedLevel && task.level !== wantedLevel) return;
    const haystack = `${task.title} ${task.details} ${task.interval_text} ${log?.note || ""}`.toLowerCase();
    if (search && !haystack.includes(search)) return;
    const hours = numberOrNull(log?.print_hours);
    rows.push(`
      <tr>
        <td><div class="task-title">${escapeHtml(task.title)}</div><div class="task-detail">${escapeHtml(task.details)}</div></td>
        <td><span class="level">${escapeHtml(task.level)}</span></td>
        <td>${escapeHtml(task.interval_text)}</td>
        <td><strong>${escapeHtml(formatDate(log?.done_on))}</strong>${hours !== null ? `<div class="task-detail">${hours} Druckstunden</div>` : ""}${log?.note ? `<div class="task-detail">${escapeHtml(log.note)}</div>` : ""}</td>
        <td><span class="status ${status.className}">${escapeHtml(status.label)}</span>${status.detail ? `<div class="status-detail">${escapeHtml(status.detail)}</div>` : ""}</td>
      </tr>
    `);
    cards.push(`
      <article class="task-card">
        <div class="item-head"><strong>${escapeHtml(task.title)}</strong><span class="status ${status.className}">${escapeHtml(status.label)}</span></div>
        <div class="item-meta">Level ${escapeHtml(task.level)} · ${escapeHtml(task.interval_text)}</div>
        <p>${escapeHtml(task.details || "-")}</p>
        <div class="item-meta">Letzter Eintrag: ${escapeHtml(formatDate(log?.done_on))}${hours !== null ? ` · ${hours} h` : ""}${status.detail ? ` · ${escapeHtml(status.detail)}` : ""}</div>
      </article>
    `);
  });
  els.taskRows.innerHTML = rows.join("") || '<tr><td colspan="5"><div class="empty">Keine passenden Wartungspunkte.</div></td></tr>';
  els.taskCards.innerHTML = cards.join("") || '<div class="empty">Keine passenden Wartungspunkte.</div>';
  els.taskSummary.textContent = dueCount ? `${dueCount} offen/fällig` : "alles ohne offene Frist";
}

function renderTimeline() {
  const items = allTimelineItems().slice(0, 12);
  els.maintenanceTimeline.innerHTML = items.length ? items.map((item) => `
    <article class="timeline-item ${item.status.className}">
      <span class="timeline-dot"></span>
      <div>
        <div class="item-head"><strong>${escapeHtml(item.device.name)}</strong><span class="status ${item.status.className}">${escapeHtml(item.status.label)}</span></div>
        <div>${escapeHtml(item.task.title)}</div>
        <div class="item-meta">${escapeHtml(item.status.detail || "Priorität prüfen")} · ${escapeHtml(item.task.interval_text)}</div>
      </div>
    </article>
  `).join("") : '<div class="empty">Keine offenen Fälligkeiten.</div>';
}

function renderNotes(device) {
  const notes = notesForDevice(device.id).sort((a, b) => (isoDate(b.note_date) || "").localeCompare(isoDate(a.note_date) || "") || b.id - a.id);
  els.noteList.innerHTML = notes.length ? notes.map((note) => `
    <article class="note-item">
      <div class="item-head"><strong>${escapeHtml(formatDate(note.note_date))}</strong><button class="delete-button" data-note-id="${note.id}" type="button">Löschen</button></div>
      <div>${escapeHtml(note.text)}</div>
      <div class="item-meta">${escapeHtml(note.user_name || "-")}</div>
    </article>
  `).join("") : '<div class="empty">Keine Vermerke vorhanden.</div>';
  els.noteList.querySelectorAll("[data-note-id]").forEach((button) => {
    button.addEventListener("click", () => runAction(() => deleteItem("notes", button.dataset.noteId), "Vermerk gelöscht."));
  });
}

function renderHistory(device) {
  const taskMap = Object.fromEntries(state.tasks.map((task) => [task.id, task]));
  const search = filterText();
  const logs = logsForDevice(device.id).filter((log) => {
    if (!search) return true;
    return `${taskMap[log.task_id]?.title || ""} ${log.note || ""} ${log.user_name || ""}`.toLowerCase().includes(search);
  }).sort((a, b) => (isoDate(b.done_on) || "").localeCompare(isoDate(a.done_on) || "") || b.id - a.id);
  els.historyList.innerHTML = logs.length ? logs.map((log) => `
    <article class="history-item">
      <div class="item-head"><strong>${escapeHtml(taskMap[log.task_id]?.title || log.task_id)}</strong><button class="delete-button" data-log-id="${log.id}" type="button">Löschen</button></div>
      <div class="item-meta">${escapeHtml(formatDate(log.done_on))}${numberOrNull(log.print_hours) !== null ? ` - ${escapeHtml(log.print_hours)} h` : ""} - ${escapeHtml(log.user_name || "-")}</div>
      ${log.note ? `<div>${escapeHtml(log.note)}</div>` : ""}
    </article>
  `).join("") : '<div class="empty">Keine Wartungseinträge vorhanden.</div>';
  els.historyList.querySelectorAll("[data-log-id]").forEach((button) => {
    button.addEventListener("click", () => runAction(() => deleteItem("logs", button.dataset.logId), "Eintrag gelöscht."));
  });
}

function renderXlTools(device) {
  if (device.kind !== "xl5") {
    els.xlToolsPanel.classList.add("hidden");
    return;
  }
  els.xlToolsPanel.classList.remove("hidden");
  const tools = state.xlTools.filter((tool) => tool.device_id === device.id).sort((a, b) => a.tool_number - b.tool_number);
  els.xlToolsGrid.innerHTML = tools.map((tool) => `
    <article class="xl-tool-card">
      <h3>Tool ${escapeHtml(tool.tool_number)}</h3>
      <form data-xl-tool="${escapeHtml(tool.tool_number)}">
        <label>Nozzle-Typ<input name="nozzle_type" value="${escapeHtml(tool.nozzle_type)}" placeholder="z.B. 0.4 brass"></label>
        <label>Material<input name="material" value="${escapeHtml(tool.material)}" placeholder="PLA, PETG ..."></label>
        <label>Letzter Wechsel<input name="last_nozzle_change" type="date" value="${escapeHtml(isoDate(tool.last_nozzle_change) || "")}"></label>
        <label>Auffälligkeiten<input name="issue_note" value="${escapeHtml(tool.issue_note)}"></label>
        <button class="button ghost" type="submit">Tool speichern</button>
      </form>
    </article>
  `).join("");
  els.xlToolsGrid.querySelectorAll("[data-xl-tool]").forEach((form) => form.addEventListener("submit", saveXlTool));
}

function filteredAdminUsers() {
  const search = (els.userSearch.value || "").toLowerCase().trim();
  const role = els.userRoleFilter.value;
  const status = els.userStatusFilter.value;
  return state.admin.users.filter((user) => {
    if (search && !`${user.display_name} ${user.email}`.toLowerCase().includes(search)) return false;
    if (role && user.role !== role) return false;
    if (status !== "" && String(user.is_active ? 1 : 0) !== status) return false;
    return true;
  });
}

function filteredAudit() {
  const search = (els.auditSearch.value || "").toLowerCase().trim();
  const action = (els.auditActionFilter.value || "").toLowerCase().trim();
  const entity = (els.auditEntityFilter.value || "").toLowerCase().trim();
  return state.admin.audit.filter((item) => {
    const haystack = `${item.user_name} ${item.action} ${item.entity_type} ${item.entity_id}`.toLowerCase();
    if (search && !haystack.includes(search)) return false;
    if (action && !String(item.action).toLowerCase().includes(action)) return false;
    if (entity && !String(item.entity_type).toLowerCase().includes(entity)) return false;
    return true;
  });
}

function renderAdmin() {
  if (state.user?.role !== "Administrator") {
    els.adminToggle.classList.add("hidden");
    closeAdminModal();
    els.adminPanel.classList.add("hidden");
    return;
  }
  els.adminToggle.classList.remove("hidden");
  els.adminPanel.classList.remove("hidden");
  if (!state.admin) return;
  els.adminSummary.textContent = `${state.admin.users.length} Benutzer`;
  els.profileName.value = state.user.display_name || "";
  els.profileEmail.value = state.user.email || "";
  els.adminUsers.innerHTML = filteredAdminUsers().map((user) => `
    <div class="admin-row">
      <div><strong>${escapeHtml(user.display_name)}</strong><div class="item-meta">${escapeHtml(user.email)} · ${escapeHtml(user.role)} · ${user.is_active ? "aktiv" : "deaktiviert"}</div></div>
      <div class="admin-row-controls">
        <select data-user-role="${user.id}"><option ${user.role === "Administrator" ? "selected" : ""}>Administrator</option><option ${user.role === "Mentor" ? "selected" : ""}>Mentor</option><option ${user.role === "Benutzer" ? "selected" : ""}>Benutzer</option></select>
        <input class="inline-secret" data-user-password-input="${user.id}" type="password" minlength="8" placeholder="Neues Passwort">
        <button class="button ghost" data-user-password="${user.id}" type="button">Passwort setzen</button>
        <button class="button ghost" data-user-active="${user.id}" data-active="${user.is_active ? 0 : 1}" type="button">${user.is_active ? "Deaktivieren" : "Aktivieren"}</button>
      </div>
    </div>
  `).join("") || '<div class="empty">Keine Benutzer gefunden.</div>';
  els.adminUsers.querySelectorAll("[data-user-role]").forEach((select) => {
    select.addEventListener("change", () => runAction(() => updateUser(select.dataset.userRole, { role: select.value }), "Rolle aktualisiert."));
  });
  els.adminUsers.querySelectorAll("[data-user-active]").forEach((button) => {
    button.addEventListener("click", () => runAction(() => updateUser(button.dataset.userActive, { is_active: Number(button.dataset.active) }), "Benutzerstatus aktualisiert."));
  });
  els.adminUsers.querySelectorAll("[data-user-password]").forEach((button) => {
    button.addEventListener("click", () => {
      const input = els.adminUsers.querySelector(`[data-user-password-input="${button.dataset.userPassword}"]`);
      const password = input?.value || "";
      if (password.length < 8) {
        showToast("Passwort muss mindestens 8 Zeichen haben.", "error");
        return;
      }
      runAction(async () => {
        await updateUser(button.dataset.userPassword, { password });
        input.value = "";
      }, "Passwort zurückgesetzt.");
    });
  });
  els.adminDevices.innerHTML = state.admin.devices.map((device) => `
    <div class="admin-row"><div><strong>${escapeHtml(device.name)}</strong><div class="item-meta">${escapeHtml(device.id)} · ${escapeHtml(device.kind)} · ${device.active ? "aktiv" : "deaktiviert"}</div></div><button class="button ghost" data-edit-device="${escapeHtml(device.id)}" type="button">Laden</button></div>
  `).join("");
  els.adminDevices.querySelectorAll("[data-edit-device]").forEach((button) => button.addEventListener("click", () => loadDeviceForm(button.dataset.editDevice)));
  els.backupList.innerHTML = state.admin.backups.map((backup) => `
    <div class="admin-row">
      <div><strong>${escapeHtml(backup.file_name)}</strong><div class="item-meta">${escapeHtml(backup.reason)} · ${escapeHtml(backup.created_at || "-")} · ${Math.round((backup.size_bytes || 0) / 1024)} KB</div></div>
      <div class="admin-row-controls">
        <a class="button ghost" href="/api/admin/backups/${encodeURIComponent(backup.file_name)}/download">Download</a>
        <button class="button danger" data-restore-backup="${escapeHtml(backup.file_name)}" type="button">Restore</button>
      </div>
    </div>
  `).join("") || '<div class="empty">Noch keine Backups.</div>';
  els.backupList.querySelectorAll("[data-restore-backup]").forEach((button) => {
    button.addEventListener("click", () => runAction(() => restoreBackup(button.dataset.restoreBackup), "Backup wiederhergestellt."));
  });
  els.auditList.innerHTML = filteredAudit().map((item) => `<div class="audit-row"><strong>${escapeHtml(item.action)} · ${escapeHtml(item.entity_type)}</strong><div class="item-meta">${escapeHtml(item.user_name)} · ${escapeHtml(item.created_at)} · ${escapeHtml(item.entity_id)}</div></div>`).join("") || '<div class="empty">Kein passender Audit-Eintrag.</div>';
  els.teamsWebhook.value = state.admin.settings.teams_webhook_url || "";
  renderAdminTabs();
}

function renderAdminTabs() {
  els.adminTabs.querySelectorAll("[data-admin-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.adminTab === state.adminTab);
  });
  document.querySelectorAll("[data-admin-panel]").forEach((panel) => {
    panel.classList.toggle("admin-panel-hidden", panel.dataset.adminPanel !== state.adminTab);
  });
}

function renderViews() {
  document.querySelectorAll(".app-view").forEach((section) => {
    section.classList.toggle("view-hidden", section.dataset.view !== state.view);
  });
  els.mainMenu.querySelectorAll("[data-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === state.view);
  });
}

function render() {
  const device = selectedDevice();
  if (!device) return;
  const tasks = tasksForDevice(device);
  state.selectedDeviceId = device.id;
  els.currentUser.textContent = `${state.user.display_name} (${state.user.role})`;
  renderFleetHealth();
  renderDevices();
  renderHeader(device, tasks);
  renderStats(device, tasks);
  renderTaskSelect(device, tasks);
  renderTaskRows(device, tasks);
  renderTimeline();
  renderNotes(device);
  renderHistory(device);
  renderXlTools(device);
  renderAdmin();
  updateExportLinks();
  renderViews();
}

async function loadState() {
  const payload = await api("/api/state");
  Object.assign(state, payload);
  if (!state.selectedDeviceId) state.selectedDeviceId = state.devices.find((device) => device.active !== 0)?.id;
  if (state.user?.role === "Administrator") {
    state.admin = await api("/api/admin/state");
  }
  render();
}

async function saveLog(event) {
  event.preventDefault();
  const device = selectedDevice();
  await api("/api/logs", { method: "POST", body: JSON.stringify({ device_id: device.id, task_id: els.taskSelect.value, done_on: els.doneOn.value, print_hours: els.printHours.value, note: els.logNote.value.trim() }) });
  els.printHours.value = "";
  els.logNote.value = "";
  await loadState();
}

async function saveNote(event) {
  event.preventDefault();
  const device = selectedDevice();
  await api("/api/notes", { method: "POST", body: JSON.stringify({ device_id: device.id, note_date: els.noteDate.value, text: els.noteText.value.trim() }) });
  els.noteText.value = "";
  await loadState();
}

async function saveHours(event) {
  event.preventDefault();
  const device = selectedDevice();
  await api(`/api/devices/${encodeURIComponent(device.id)}/hours`, { method: "POST", body: JSON.stringify({ current_print_hours: els.currentHoursInput.value }) });
  await loadState();
}

async function saveXlTool(event) {
  event.preventDefault();
  const device = selectedDevice();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form).entries());
  data.tool_number = Number(form.dataset.xlTool);
  await api(`/api/devices/${encodeURIComponent(device.id)}/xl-tools`, { method: "POST", body: JSON.stringify(data) });
  await loadState();
}

async function deleteItem(type, id) {
  const ok = await confirmAction("Eintrag löschen?", "Diese Aktion kann nicht rückgängig gemacht werden.");
  if (!ok) return;
  await api(`/api/${type}/${id}`, { method: "DELETE" });
  await loadState();
}

async function updateUser(id, payload) {
  await api(`/api/admin/users/${id}`, { method: "POST", body: JSON.stringify(payload) });
  await loadState();
}

function loadDeviceForm(id) {
  const device = state.admin.devices.find((item) => item.id === id);
  if (!device) return;
  $("#deviceId").value = device.id;
  $("#deviceName").value = device.name;
  $("#deviceKind").value = device.kind;
  $("#deviceMentors").value = device.mentors || "";
}

async function saveDevice(event) {
  event.preventDefault();
  await api("/api/admin/devices", { method: "POST", body: JSON.stringify({ id: $("#deviceId").value.trim(), name: $("#deviceName").value.trim(), kind: $("#deviceKind").value, mentors: $("#deviceMentors").value.trim() }) });
  event.currentTarget.reset();
  await loadState();
}

async function saveTask(event) {
  event.preventDefault();
  await api("/api/admin/tasks", { method: "POST", body: JSON.stringify({ id: $("#taskId").value.trim(), title: $("#taskTitle").value.trim(), details: $("#taskDetails").value.trim(), applies_to: $("#taskApplies").value, level: $("#taskLevel").value, interval_text: $("#taskInterval").value.trim(), cadence_days: $("#taskDays").value, cadence_hours: $("#taskHours").value }) });
  event.currentTarget.reset();
  await loadState();
}

async function saveTeamCode(event) {
  event.preventDefault();
  await api("/api/admin/team-code", { method: "POST", body: JSON.stringify({ team_code: els.teamCodeInput.value }) });
  els.teamCodeInput.value = "";
  await loadState();
}

async function saveProfile(event) {
  event.preventDefault();
  const password = els.profilePassword.value;
  const confirm = els.profilePasswordConfirm.value;
  if (password || confirm) {
    if (password !== confirm) throw new Error("Die Passwörter stimmen nicht überein.");
    if (password.length < 8) throw new Error("Das neue Passwort muss mindestens 8 Zeichen haben.");
  }
  await api("/api/profile", {
    method: "POST",
    body: JSON.stringify({ display_name: els.profileName.value.trim(), password }),
  });
  els.profilePassword.value = "";
  els.profilePasswordConfirm.value = "";
  await loadState();
}

async function saveNotification(event) {
  event.preventDefault();
  await api("/api/admin/settings", { method: "POST", body: JSON.stringify({ teams_webhook_url: els.teamsWebhook.value.trim() }) });
  await loadState();
}

async function createBackup() {
  await api("/api/admin/backups", { method: "POST", body: JSON.stringify({ reason: "manual" }) });
  await loadState();
}

async function restoreBackup(fileName) {
  const ok = await confirmAction("Backup wiederherstellen?", "Die aktuelle Datenbank wird vorher gesichert und danach durch dieses Backup ersetzt.");
  if (!ok) return;
  await api(`/api/admin/backups/${encodeURIComponent(fileName)}/restore`, { method: "POST", body: JSON.stringify({}) });
  await loadState();
}

async function pruneBackups() {
  const keep = Number(els.backupKeep.value || 20);
  await api("/api/admin/backups/prune", { method: "POST", body: JSON.stringify({ keep }) });
  await loadState();
}

async function sendDueNotifications() {
  await api("/api/admin/notifications/due", { method: "POST", body: JSON.stringify({}) });
}

async function logout() {
  await api("/auth/logout", { method: "POST" });
  location.href = "/login";
}

els.doneOn.value = todayIso();
els.noteDate.value = todayIso();
els.logoutButton.addEventListener("click", () => runAction(logout));
els.adminToggle.addEventListener("click", openAdminModal);
els.adminCloseButton.addEventListener("click", closeAdminModal);
els.adminPanel.addEventListener("click", (event) => {
  if (event.target === els.adminPanel) closeAdminModal();
});
els.exportMonth.addEventListener("change", updateExportLinks);
els.refreshButton.addEventListener("click", () => runAction(loadState, "Daten aktualisiert."));
els.logForm.addEventListener("submit", (event) => runAction(() => saveLog(event), "Eintrag gespeichert."));
els.noteForm.addEventListener("submit", (event) => runAction(() => saveNote(event), "Vermerk gespeichert."));
els.hoursForm.addEventListener("submit", (event) => runAction(() => saveHours(event), "Druckstunden aktualisiert."));
els.searchInput.addEventListener("input", render);
els.deviceSearch.addEventListener("input", renderDevices);
els.statusFilter.addEventListener("change", render);
els.levelFilter.addEventListener("change", render);
els.mainMenu.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => {
    state.view = button.dataset.view;
    renderViews();
  });
});
els.adminTabs.querySelectorAll("[data-admin-tab]").forEach((button) => {
  button.addEventListener("click", () => {
    state.adminTab = button.dataset.adminTab;
    renderAdminTabs();
  });
});
els.profileForm.addEventListener("submit", (event) => runAction(() => saveProfile(event), "Profil gespeichert."));
els.userSearch.addEventListener("input", renderAdmin);
els.userRoleFilter.addEventListener("change", renderAdmin);
els.userStatusFilter.addEventListener("change", renderAdmin);
els.auditSearch.addEventListener("input", renderAdmin);
els.auditActionFilter.addEventListener("input", renderAdmin);
els.auditEntityFilter.addEventListener("input", renderAdmin);
els.teamCodeForm.addEventListener("submit", (event) => runAction(() => saveTeamCode(event), "Teamleiter-Code gespeichert."));
els.deviceForm.addEventListener("submit", (event) => runAction(() => saveDevice(event), "Drucker gespeichert."));
els.taskForm.addEventListener("submit", (event) => runAction(() => saveTask(event), "Wartungspunkt gespeichert."));
els.backupButton.addEventListener("click", () => runAction(createBackup, "Backup erstellt."));
els.backupPruneButton.addEventListener("click", () => runAction(pruneBackups, "Backups aufgeräumt."));
els.notificationForm.addEventListener("submit", (event) => runAction(() => saveNotification(event), "Benachrichtigungen gespeichert."));
els.sendDueButton.addEventListener("click", () => runAction(sendDueNotifications, "Teams-Benachrichtigung gesendet."));

loadState().catch((error) => {
  document.body.innerHTML = `<main class="workspace"><div class="empty">${escapeHtml(error.message)}</div></main>`;
});
