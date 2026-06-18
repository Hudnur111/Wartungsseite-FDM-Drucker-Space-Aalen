from __future__ import annotations

import os
from datetime import date

import streamlit as st


def load_streamlit_secrets_into_env() -> None:
    try:
        secrets = st.secrets
        for key, value in secrets.items():
            if isinstance(value, (str, int, float, bool)):
                os.environ.setdefault(key, str(value))
    except Exception:
        return


load_streamlit_secrets_into_env()

from app import config  # noqa: E402
from app.database import ensure_daily_backup, init_db  # noqa: E402
from app.security import is_admin, is_mentor_or_admin  # noqa: E402
from app import streamlit_services as svc  # noqa: E402


st.set_page_config(
    page_title="Wartung FDM Space",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
      .block-container { padding-top: 1.4rem; }
      [data-testid="stMetric"] { border: 1px solid #d8e1e6; border-radius: 8px; padding: 12px; background: #ffffff; }
      div[data-testid="stAlert"] { border-radius: 8px; }
      .fdm-muted { color: #5d6f78; font-size: .92rem; }
      .fdm-title { margin-bottom: .2rem; }
      .fdm-pill { display: inline-block; border: 1px solid #d8e1e6; border-radius: 999px; padding: 2px 9px; margin-right: 4px; font-size: .82rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def boot_database() -> bool:
    init_db()
    ensure_daily_backup()
    return True


boot_database()


def user() -> dict | None:
    return st.session_state.get("user")


def set_user(value: dict | None) -> None:
    st.session_state["user"] = value


def rerun() -> None:
    st.rerun()


def success_then_rerun(message: str) -> None:
    st.success(message)
    rerun()


def handle_action(fn, success: str) -> None:
    try:
        fn()
    except ValueError as exc:
        st.error(str(exc))
    else:
        success_then_rerun(success)


def status_label(value: str) -> str:
    return {"due": "Fällig", "open": "Offen", "due-soon": "Bald fällig"}.get(value, value)


def selected_by_label(items: list[dict], label: str, field: str = "name") -> dict | None:
    for item in items:
        if item.get(field) == label:
            return item
    return None


def render_reset_page(token: str) -> None:
    st.title("Passwort neu setzen")
    with st.form("reset-password"):
        password = st.text_input("Neues Passwort", type="password")
        confirm = st.text_input("Passwort wiederholen", type="password")
        submitted = st.form_submit_button("Passwort speichern", type="primary")
    if submitted:
        error = svc.reset_password(token, password, confirm)
        if error:
            st.error(error)
        else:
            st.query_params.clear()
            st.success("Passwort wurde aktualisiert. Bitte melde dich neu an.")
            set_user(None)
            rerun()


def render_auth() -> None:
    st.markdown("<h1 class='fdm-title'>Wartung FDM Space</h1>", unsafe_allow_html=True)
    st.markdown("<p class='fdm-muted'>Interne Wartungsverwaltung für Drucker, Druckstunden, Vermerke und Historie.</p>", unsafe_allow_html=True)

    login_tab, register_tab, forgot_tab = st.tabs(["Anmelden", "Registrieren", "Passwort vergessen"])

    with login_tab:
        with st.form("login-form"):
            email = st.text_input("E-Mail", autocomplete="email")
            password = st.text_input("Passwort", type="password")
            submitted = st.form_submit_button("Anmelden", type="primary")
        if submitted:
            authenticated, error = svc.authenticate(email, password)
            if error:
                st.error(error)
            else:
                set_user(authenticated)
                rerun()

    with register_tab:
        if svc.team_code_is_configured():
            st.info("Registrierung ist mit Teamleiter-Code freigeschaltet.")
        else:
            st.warning("Registrierung ist gesperrt, bis ein Teamleiter-Code gesetzt wurde.")
        with st.form("register-form"):
            display_name = st.text_input("Name")
            email = st.text_input("E-Mail", key="register-email")
            password = st.text_input("Passwort", type="password", key="register-password")
            code = st.text_input("Teamleiter-Code", type="password")
            submitted = st.form_submit_button("Konto erstellen", type="primary")
        if submitted:
            created, error = svc.register(display_name, email, password, code)
            if error:
                st.error(error)
            else:
                set_user(created)
                rerun()

    with forgot_tab:
        with st.form("forgot-form"):
            email = st.text_input("E-Mail", key="forgot-email")
            submitted = st.form_submit_button("Reset-Link senden", type="primary")
        if submitted:
            st.info(svc.request_password_reset(email))


def render_sidebar(current_user: dict) -> str:
    st.sidebar.title("Wartung")
    st.sidebar.caption(f"{current_user['display_name']} · {current_user['role']}")
    pages = ["Übersicht", "Wartung erfassen", "Drucker & Tools", "Historie & Export", "Profil"]
    if is_admin(current_user):
        pages.append("Admin")
    page = st.sidebar.radio("Bereich", pages, label_visibility="collapsed")
    st.sidebar.divider()
    st.sidebar.caption(f"Datenbank: {svc.data_path_label()}")
    if st.sidebar.button("Abmelden", use_container_width=True):
        set_user(None)
        rerun()
    return page


def render_dashboard(state: dict) -> None:
    st.title("Übersicht")
    due = state["due"]
    due_count = sum(1 for item in due if item["status"] == "due")
    open_count = sum(1 for item in due if item["status"] == "open")
    soon_count = sum(1 for item in due if item["status"] == "due-soon")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Aktive Drucker", len(state["devices"]))
    c2.metric("Fällig", due_count)
    c3.metric("Offen", open_count)
    c4.metric("Bald fällig", soon_count)

    st.subheader("Fälligkeiten")
    if due:
        rows = [
            {
                "Status": status_label(item["status"]),
                "Drucker": item["device"],
                "Wartung": item["task"],
                "Level": item["level"],
                "Detail": item["detail"],
                "Letzter Eintrag": item["last_done"] or "-",
            }
            for item in due
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.success("Aktuell sind keine Wartungen fällig.")

    st.subheader("Letzte Einträge")
    logs = state["logs"][:20]
    devices = {item["id"]: item["name"] for item in state["devices"]}
    tasks = {item["id"]: item["title"] for item in state["tasks"]}
    st.dataframe(
        [
            {
                "Datum": log["done_on"],
                "Drucker": devices.get(log["device_id"], log["device_id"]),
                "Wartung": tasks.get(log["task_id"], log["task_id"]),
                "Stunden": log["print_hours"],
                "Benutzer": log["user_name"],
                "Vermerk": log["note"],
            }
            for log in logs
        ],
        use_container_width=True,
        hide_index=True,
    )


def render_log_form(current_user: dict, state: dict) -> None:
    st.title("Wartung erfassen")
    devices = state["devices"]
    tasks = state["tasks"]
    if not devices or not tasks:
        st.warning("Es sind noch keine aktiven Drucker oder Wartungspunkte vorhanden.")
        return

    device_names = [item["name"] for item in devices]
    selected_name = st.selectbox("Drucker", device_names)
    device = selected_by_label(devices, selected_name)
    assert device is not None
    matching_tasks = [task for task in tasks if task["applies_to"] in {"all", device["kind"]}]
    if not is_mentor_or_admin(current_user):
        matching_tasks = [task for task in matching_tasks if task["level"] == "B"]
    if not matching_tasks:
        st.warning("Für diesen Drucker gibt es keine Wartungspunkte, die du mit deiner Rolle erfassen kannst.")
        return

    left, right = st.columns([1.1, 1])
    with left:
        with st.form("create-log"):
            task_labels = [f"{task['title']} · Level {task['level']}" for task in matching_tasks]
            task_label = st.selectbox("Wartungspunkt", task_labels)
            task = matching_tasks[task_labels.index(task_label)]
            done_on = st.date_input("Datum", value=date.today(), max_value=date.today())
            print_hours = st.number_input("Druckstunden", min_value=0, step=1, value=int(device["current_print_hours"] or 0))
            note = st.text_area("Vermerk", max_chars=1000)
            submitted = st.form_submit_button("Wartung speichern", type="primary")
        if submitted:
            handle_action(lambda: svc.create_log(current_user, device["id"], task["id"], str(done_on), print_hours, note), "Wartung gespeichert.")

    with right:
        with st.form("create-note"):
            note_date = st.date_input("Datum", value=date.today(), max_value=date.today(), key="note-date")
            note_text = st.text_area("Allgemeiner Vermerk", max_chars=1000)
            submitted = st.form_submit_button("Vermerk speichern")
        if submitted:
            handle_action(lambda: svc.create_note(current_user, device["id"], str(note_date), note_text), "Vermerk gespeichert.")


def render_devices(current_user: dict, state: dict) -> None:
    st.title("Drucker & Tools")
    devices = state["devices"]
    xl_tools = state["xlTools"]
    st.dataframe(
        [
            {
                "Drucker": item["name"],
                "Typ": item["type_label"],
                "Mentoren": item["mentors"],
                "Druckstunden": item["current_print_hours"],
                "Aktualisiert": item["updated_at"],
            }
            for item in devices
        ],
        use_container_width=True,
        hide_index=True,
    )

    if is_mentor_or_admin(current_user):
        st.subheader("Druckstunden aktualisieren")
        with st.form("update-hours"):
            device_names = [item["name"] for item in devices]
            selected_name = st.selectbox("Drucker", device_names, key="hours-device")
            device = selected_by_label(devices, selected_name)
            hours = st.number_input("Aktuelle Druckstunden", min_value=0, step=1, value=int((device or {}).get("current_print_hours") or 0))
            submitted = st.form_submit_button("Druckstunden speichern")
        if submitted and device:
            handle_action(lambda: svc.update_hours(current_user, device["id"], hours), "Druckstunden aktualisiert.")

    xl_devices = [item for item in devices if item["kind"] == "xl5"]
    if xl_devices:
        st.subheader("XL Toolheads")
        st.dataframe(xl_tools, use_container_width=True, hide_index=True)
        if is_mentor_or_admin(current_user):
            with st.form("xl-tool"):
                device_names = [item["name"] for item in xl_devices]
                selected_name = st.selectbox("XL Drucker", device_names)
                device = selected_by_label(xl_devices, selected_name)
                tool_number = st.selectbox("Tool", [1, 2, 3, 4, 5])
                nozzle_type = st.text_input("Düse")
                material = st.text_input("Material")
                last_change = st.date_input("Letzter Düsenwechsel", value=date.today(), max_value=date.today())
                issue_note = st.text_area("Hinweis / Problem", max_chars=500)
                submitted = st.form_submit_button("Toolhead speichern")
            if submitted and device:
                handle_action(
                    lambda: svc.update_xl_tool(current_user, device["id"], tool_number, nozzle_type, material, str(last_change), issue_note),
                    "Toolhead aktualisiert.",
                )


def render_history(current_user: dict, state: dict) -> None:
    st.title("Historie & Export")
    devices = {item["id"]: item["name"] for item in state["devices"]}
    tasks = {item["id"]: item["title"] for item in state["tasks"]}
    month = st.text_input("Monat für Export, optional", placeholder="2026-06")

    c1, c2 = st.columns(2)
    suffix = f"_{month.strip()}" if month.strip() else ""
    try:
        csv_data = svc.export_csv_bytes(month)
        c1.download_button("CSV herunterladen", csv_data, file_name=f"wartung_fdm_space{suffix}.csv", mime="text/csv", use_container_width=True)
    except ValueError as exc:
        c1.error(str(exc))
    try:
        pdf_data = svc.export_pdf_bytes(month)
        c2.download_button("PDF herunterladen", pdf_data, file_name=f"wartung_fdm_space{suffix}.pdf", mime="application/pdf", use_container_width=True)
    except ValueError as exc:
        c2.error(str(exc))

    st.subheader("Wartungseinträge")
    logs = [
        {
            "ID": item["id"],
            "Datum": item["done_on"],
            "Drucker": devices.get(item["device_id"], item["device_id"]),
            "Wartung": tasks.get(item["task_id"], item["task_id"]),
            "Stunden": item["print_hours"],
            "Benutzer": item["user_name"],
            "Vermerk": item["note"],
        }
        for item in state["logs"]
    ]
    st.dataframe(logs, use_container_width=True, hide_index=True)

    st.subheader("Vermerke")
    notes = [
        {
            "ID": item["id"],
            "Datum": item["note_date"],
            "Drucker": devices.get(item["device_id"], item["device_id"]),
            "Benutzer": item["user_name"],
            "Text": item["text"],
        }
        for item in state["notes"]
    ]
    st.dataframe(notes, use_container_width=True, hide_index=True)

    if is_mentor_or_admin(current_user):
        with st.expander("Eintrag löschen"):
            table = st.selectbox("Typ", ["logs", "notes"], format_func=lambda value: "Wartung" if value == "logs" else "Vermerk")
            item_id = st.number_input("ID", min_value=1, step=1)
            if st.button("Eintrag löschen", type="secondary"):
                handle_action(lambda: svc.delete_entry(current_user, table, int(item_id)), "Eintrag gelöscht.")


def render_profile(current_user: dict) -> None:
    st.title("Profil")
    with st.form("profile"):
        display_name = st.text_input("Name", value=current_user["display_name"])
        st.text_input("E-Mail", value=current_user["email"], disabled=True)
        password = st.text_input("Neues Passwort", type="password")
        confirm = st.text_input("Passwort wiederholen", type="password")
        submitted = st.form_submit_button("Profil speichern", type="primary")
    if submitted:
        if password != confirm:
            st.error("Die Passwörter stimmen nicht überein.")
        else:
            try:
                set_user(svc.update_profile(current_user, display_name, password))
            except ValueError as exc:
                st.error(str(exc))
            else:
                success_then_rerun("Profil gespeichert.")


def render_admin_users(current_user: dict, admin_state: dict) -> None:
    st.subheader("Benutzer")
    st.dataframe(admin_state["users"], use_container_width=True, hide_index=True)
    if not admin_state["users"]:
        return
    labels = [f"{item['display_name']} · {item['email']} · ID {item['id']}" for item in admin_state["users"]]
    selected = st.selectbox("Benutzer auswählen", labels)
    target = admin_state["users"][labels.index(selected)]
    with st.form("admin-user"):
        role = st.selectbox("Rolle", list(config.ROLES), index=list(config.ROLES).index(target["role"]))
        active = st.checkbox("Aktiv", value=bool(target["is_active"]))
        password = st.text_input("Neues Passwort", type="password")
        submitted = st.form_submit_button("Benutzer aktualisieren")
    if submitted:
        handle_action(lambda: svc.update_user(current_user, target["id"], role, active, password), "Benutzer aktualisiert.")


def render_admin_devices(current_user: dict, admin_state: dict) -> None:
    st.subheader("Drucker verwalten")
    st.dataframe(admin_state["devices"], use_container_width=True, hide_index=True)
    with st.form("admin-device"):
        device_id = st.text_input("ID", placeholder="mini-alpha-1")
        kind = st.selectbox("Typ", ["mini", "mk3_5", "xl5"], format_func=lambda value: {"mini": "MINI+", "mk3_5": "MK3.5", "xl5": "XL 5-Tool"}[value])
        name = st.text_input("Name")
        mentors = st.text_input("Mentoren")
        active = st.checkbox("Aktiv", value=True)
        submitted = st.form_submit_button("Drucker speichern")
    if submitted:
        handle_action(lambda: svc.save_device(current_user, device_id, kind, name, mentors, active), "Drucker gespeichert.")


def render_admin_tasks(current_user: dict, admin_state: dict) -> None:
    st.subheader("Wartungspunkte verwalten")
    st.dataframe(admin_state["tasks"], use_container_width=True, hide_index=True)
    with st.form("admin-task"):
        task_id = st.text_input("ID", placeholder="bed-clean")
        applies_to = st.selectbox("Gilt für", ["all", "mini", "mk3_5", "xl5"])
        title = st.text_input("Titel")
        details = st.text_area("Details", max_chars=1200)
        level = st.selectbox("Level", ["B", "E", "M"])
        interval_text = st.text_input("Intervalltext")
        cadence_days = st.text_input("Tage", placeholder="optional")
        cadence_hours = st.text_input("Stunden", placeholder="optional")
        active = st.checkbox("Aktiv", value=True)
        submitted = st.form_submit_button("Wartungspunkt speichern")
    if submitted:
        handle_action(lambda: svc.save_task(current_user, task_id, applies_to, title, details, level, interval_text, cadence_days, cadence_hours, active), "Wartungspunkt gespeichert.")


def render_admin_backups(current_user: dict, admin_state: dict) -> None:
    st.subheader("Backups")
    reason = st.text_input("Grund", value="manual")
    if st.button("Backup erstellen", type="primary"):
        handle_action(lambda: svc.create_manual_backup(current_user, reason), "Backup erstellt.")

    backups = admin_state["backups"]
    st.dataframe(backups, use_container_width=True, hide_index=True)
    if backups:
        names = [item["file_name"] for item in backups]
        selected = st.selectbox("Backup-Datei", names)
        st.download_button("Backup herunterladen", svc.backup_bytes(selected), file_name=selected, mime="application/octet-stream")
        col1, col2 = st.columns(2)
        if col1.button("Ausgewähltes Backup wiederherstellen"):
            handle_action(lambda: svc.restore_backup_file(current_user, selected), "Backup wiederhergestellt.")
        keep = col2.number_input("Behalten", min_value=1, max_value=200, value=20)
        if col2.button("Alte Backups löschen"):
            handle_action(lambda: svc.prune_backup_files(current_user, int(keep)), "Backups bereinigt.")


def render_admin_settings(current_user: dict, admin_state: dict) -> None:
    st.subheader("Einstellungen")
    st.write("Teamleiter-Code:", "gesetzt" if admin_state["settings"]["team_code_configured"] else "nicht gesetzt")
    with st.form("team-code"):
        code = st.text_input("Neuer Teamleiter-Code", type="password")
        submitted = st.form_submit_button("Code speichern")
    if submitted:
        handle_action(lambda: svc.set_team_code(current_user, code), "Teamleiter-Code gespeichert.")

    with st.form("teams-webhook"):
        webhook = st.text_input("Teams Webhook URL", value=admin_state["settings"]["teams_webhook_url"])
        submitted = st.form_submit_button("Webhook speichern")
    if submitted:
        handle_action(lambda: svc.set_teams_webhook(current_user, webhook), "Webhook gespeichert.")

    st.subheader("Audit")
    st.dataframe(admin_state["audit"], use_container_width=True, hide_index=True)


def render_admin(current_user: dict) -> None:
    st.title("Admin")
    admin_state = svc.load_admin_state()
    users_tab, devices_tab, tasks_tab, backups_tab, settings_tab = st.tabs(["Benutzer", "Drucker", "Wartung", "Backups", "Einstellungen"])
    with users_tab:
        render_admin_users(current_user, admin_state)
    with devices_tab:
        render_admin_devices(current_user, admin_state)
    with tasks_tab:
        render_admin_tasks(current_user, admin_state)
    with backups_tab:
        render_admin_backups(current_user, admin_state)
    with settings_tab:
        render_admin_settings(current_user, admin_state)


def main() -> None:
    reset_token = st.query_params.get("reset_token", "")
    if isinstance(reset_token, list):
        reset_token = reset_token[0] if reset_token else ""
    if reset_token:
        render_reset_page(str(reset_token))
        return

    current_user = user()
    if not current_user:
        render_auth()
        return

    page = render_sidebar(current_user)
    state = svc.load_state()
    if page == "Übersicht":
        render_dashboard(state)
    elif page == "Wartung erfassen":
        render_log_form(current_user, state)
    elif page == "Drucker & Tools":
        render_devices(current_user, state)
    elif page == "Historie & Export":
        render_history(current_user, state)
    elif page == "Profil":
        render_profile(current_user)
    elif page == "Admin" and is_admin(current_user):
        render_admin(current_user)


if __name__ == "__main__":
    main()
