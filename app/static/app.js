const state = {
  user: null,
  csrfToken: "",
  devices: [],
  tasks: [],
  logs: [],
  notes: [],
  xlTools: [],
  selectedDeviceId: null,
  admin: null,
};

const $ = (selector) => document.querySelector(selector);
const els = {
  currentUser: $("#currentUser"),
  adminToggle: $("#adminToggle"),
  logoutButton: $("#logoutButton"),
  deviceCount: $("#deviceCount"),
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
  taskSummary: $("#taskSummary"),
  xlToolsPanel: $("#xlToolsPanel"),
  xlToolsGrid: $("#xlToolsGrid"),
  noteForm: $("#noteForm"),
  noteDate: $("#noteDate"),
  noteText: $("#noteText"),
  noteList: $("#noteList"),
  historyList: $("#historyList"),
  refreshButton: $("#refreshButton"),
  adminPanel: $("#adminPanel"),
  adminSummary: $("#adminSummary"),
  adminUsers: $("#adminUsers"),
  teamCodeForm: $("#teamCodeForm"),
  teamCodeInput: $("#teamCodeInput"),
  deviceForm: $("#deviceForm"),
  adminDevices: $("#adminDevices"),
  taskForm: $("#taskForm"),
  backupButton: $("#backupButton"),
  backupList: $("#backupList"),
  notificationForm: $("#notificationForm"),
  teamsWebhook: $("#teamsWebhook"),
  auditList: $("#auditList"),
};

function todayIso() {
  return new Date().toISOString().slice(0, 10);
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
    if (ageHours > task.cadence_hours) return { className: "due", label: "faellig", detail: `${ageHours} h` };
    if (task.cadence_hours - ageHours <= 25) return { className: "due-soon", label: "bald", detail: `${ageHours} h` };
    return { className: "ok", label: "ok", detail: `${ageHours} h` };
  }
  if (task.cadence_hours && !task.cadence_days) return { className: "open", label: "Stunden fehlen" };
  const date = parseIso(log.done_on);
  if (!date) return { className: "open", label: "Datum pruefen" };
  const ageDays = Math.floor((new Date() - date) / 86400000);
  if (ageDays > task.cadence_days) return { className: "due", label: "faellig", detail: `${ageDays} Tage` };
  if (task.cadence_days - ageDays <= 7) return { className: "due-soon", label: "bald", detail: `${ageDays} Tage` };
  return { className: "ok", label: "ok", detail: `${ageDays} Tage` };
}

function canLogTask(task) {
  if (!state.user) return false;
  if (state.user.role === "Administrator" || state.user.role === "Mentor") return true;
  return task.level === "B";
}

function renderDevices() {
  els.deviceCount.textContent = state.devices.filter((device) => device.active !== 0).length;
  els.deviceList.innerHTML = state.devices
    .filter((device) => device.active !== 0)
    .map((device) => `
      <button class="device-button ${device.id === state.selectedDeviceId ? "active" : ""}" data-device="${escapeHtml(device.id)}">
        <strong>${escapeHtml(device.name)}</strong>
        <span>${escapeHtml(device.type_label || device.kind)} · ${escapeHtml(device.mentors || "ohne Mentor")}</span>
      </button>
    `).join("");
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
      <span class="pill">${logsForDevice(device.id).length} Eintraege</span>
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
    <article class="stat-card accent-red"><span>Offen / faellig</span><strong>${due}</strong></article>
    <article class="stat-card accent-amber"><span>Bald faellig</span><strong>${counts["due-soon"] || 0}</strong></article>
    <article class="stat-card accent-green"><span>Aktuell ok</span><strong>${counts.ok || 0}</strong></article>
    <article class="stat-card accent-blue"><span>Letzter Eintrag</span><strong>${escapeHtml(formatDate(latest))}</strong></article>
  `;
  if (due) {
    els.notificationBanner.textContent = `${due} Wartungspunkt(e) sind offen oder faellig.`;
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
  });
  els.taskRows.innerHTML = rows.join("") || '<tr><td colspan="5"><div class="empty">Keine passenden Wartungspunkte.</div></td></tr>';
  els.taskSummary.textContent = dueCount ? `${dueCount} offen/faellig` : "alles ohne offene Frist";
}

function renderNotes(device) {
  const notes = notesForDevice(device.id).sort((a, b) => (isoDate(b.note_date) || "").localeCompare(isoDate(a.note_date) || "") || b.id - a.id);
  els.noteList.innerHTML = notes.length ? notes.map((note) => `
    <article class="note-item">
      <div class="item-head"><strong>${escapeHtml(formatDate(note.note_date))}</strong><button class="delete-button" data-note-id="${note.id}" type="button">Loeschen</button></div>
      <div>${escapeHtml(note.text)}</div>
      <div class="item-meta">${escapeHtml(note.user_name || "-")}</div>
    </article>
  `).join("") : '<div class="empty">Keine Vermerke vorhanden.</div>';
  els.noteList.querySelectorAll("[data-note-id]").forEach((button) => button.addEventListener("click", () => deleteItem("notes", button.dataset.noteId)));
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
      <div class="item-head"><strong>${escapeHtml(taskMap[log.task_id]?.title || log.task_id)}</strong><button class="delete-button" data-log-id="${log.id}" type="button">Loeschen</button></div>
      <div class="item-meta">${escapeHtml(formatDate(log.done_on))}${numberOrNull(log.print_hours) !== null ? ` - ${escapeHtml(log.print_hours)} h` : ""} - ${escapeHtml(log.user_name || "-")}</div>
      ${log.note ? `<div>${escapeHtml(log.note)}</div>` : ""}
    </article>
  `).join("") : '<div class="empty">Keine Wartungseintraege vorhanden.</div>';
  els.historyList.querySelectorAll("[data-log-id]").forEach((button) => button.addEventListener("click", () => deleteItem("logs", button.dataset.logId)));
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
        <label>Auffaelligkeiten<input name="issue_note" value="${escapeHtml(tool.issue_note)}"></label>
        <button class="button ghost" type="submit">Tool speichern</button>
      </form>
    </article>
  `).join("");
  els.xlToolsGrid.querySelectorAll("[data-xl-tool]").forEach((form) => form.addEventListener("submit", saveXlTool));
}

function renderAdmin() {
  if (state.user?.role !== "Administrator") {
    els.adminToggle.classList.add("hidden");
    els.adminPanel.classList.add("hidden");
    return;
  }
  els.adminToggle.classList.remove("hidden");
  if (!state.admin) return;
  els.adminSummary.textContent = `${state.admin.users.length} Benutzer`;
  els.adminUsers.innerHTML = state.admin.users.map((user) => `
    <div class="admin-row">
      <div><strong>${escapeHtml(user.display_name)}</strong><div class="item-meta">${escapeHtml(user.email)} · ${escapeHtml(user.role)} · ${user.is_active ? "aktiv" : "deaktiviert"}</div></div>
      <div class="admin-row-controls">
        <select data-user-role="${user.id}"><option ${user.role === "Administrator" ? "selected" : ""}>Administrator</option><option ${user.role === "Mentor" ? "selected" : ""}>Mentor</option><option ${user.role === "Benutzer" ? "selected" : ""}>Benutzer</option></select>
        <button class="button ghost" data-user-active="${user.id}" data-active="${user.is_active ? 0 : 1}" type="button">${user.is_active ? "Deaktivieren" : "Aktivieren"}</button>
      </div>
    </div>
  `).join("");
  els.adminUsers.querySelectorAll("[data-user-role]").forEach((select) => select.addEventListener("change", () => updateUser(select.dataset.userRole, { role: select.value })));
  els.adminUsers.querySelectorAll("[data-user-active]").forEach((button) => button.addEventListener("click", () => updateUser(button.dataset.userActive, { is_active: Number(button.dataset.active) })));
  els.adminDevices.innerHTML = state.admin.devices.map((device) => `
    <div class="admin-row"><div><strong>${escapeHtml(device.name)}</strong><div class="item-meta">${escapeHtml(device.id)} · ${escapeHtml(device.kind)} · ${device.active ? "aktiv" : "deaktiviert"}</div></div><button class="button ghost" data-edit-device="${escapeHtml(device.id)}" type="button">Laden</button></div>
  `).join("");
  els.adminDevices.querySelectorAll("[data-edit-device]").forEach((button) => button.addEventListener("click", () => loadDeviceForm(button.dataset.editDevice)));
  els.backupList.innerHTML = state.admin.backups.map((backup) => `<div class="admin-row"><div><strong>${escapeHtml(backup.file_name)}</strong><div class="item-meta">${escapeHtml(backup.reason)} · ${escapeHtml(backup.created_at)}</div></div></div>`).join("") || '<div class="empty">Noch keine Backups.</div>';
  els.auditList.innerHTML = state.admin.audit.map((item) => `<div class="audit-row"><strong>${escapeHtml(item.action)} · ${escapeHtml(item.entity_type)}</strong><div class="item-meta">${escapeHtml(item.user_name)} · ${escapeHtml(item.created_at)} · ${escapeHtml(item.entity_id)}</div></div>`).join("") || '<div class="empty">Noch kein Audit-Log.</div>';
  els.teamsWebhook.value = state.admin.settings.teams_webhook_url || "";
}

function render() {
  const device = selectedDevice();
  if (!device) return;
  const tasks = tasksForDevice(device);
  state.selectedDeviceId = device.id;
  els.currentUser.textContent = `${state.user.display_name} (${state.user.role})`;
  renderDevices();
  renderHeader(device, tasks);
  renderStats(device, tasks);
  renderTaskSelect(device, tasks);
  renderTaskRows(device, tasks);
  renderNotes(device);
  renderHistory(device);
  renderXlTools(device);
  renderAdmin();
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
  if (!confirm("Eintrag wirklich loeschen?")) return;
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
  alert("Teamleiter-Code gespeichert.");
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

async function logout() {
  await api("/auth/logout", { method: "POST" });
  location.href = "/login";
}

els.doneOn.value = todayIso();
els.noteDate.value = todayIso();
els.logoutButton.addEventListener("click", logout);
els.refreshButton.addEventListener("click", loadState);
els.logForm.addEventListener("submit", (event) => saveLog(event).catch((error) => alert(error.message)));
els.noteForm.addEventListener("submit", (event) => saveNote(event).catch((error) => alert(error.message)));
els.hoursForm.addEventListener("submit", (event) => saveHours(event).catch((error) => alert(error.message)));
els.searchInput.addEventListener("input", render);
els.statusFilter.addEventListener("change", render);
els.levelFilter.addEventListener("change", render);
els.adminToggle.addEventListener("click", () => els.adminPanel.classList.toggle("hidden"));
els.teamCodeForm.addEventListener("submit", (event) => saveTeamCode(event).catch((error) => alert(error.message)));
els.deviceForm.addEventListener("submit", (event) => saveDevice(event).catch((error) => alert(error.message)));
els.taskForm.addEventListener("submit", (event) => saveTask(event).catch((error) => alert(error.message)));
els.backupButton.addEventListener("click", () => createBackup().catch((error) => alert(error.message)));
els.notificationForm.addEventListener("submit", (event) => saveNotification(event).catch((error) => alert(error.message)));

loadState().catch((error) => {
  document.body.innerHTML = `<main class="workspace"><div class="empty">${escapeHtml(error.message)}</div></main>`;
});
