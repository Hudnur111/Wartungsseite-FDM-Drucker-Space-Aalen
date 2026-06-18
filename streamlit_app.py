from __future__ import annotations

import os
from datetime import date

import streamlit as st


st.set_page_config(
    page_title="Wartung FDM Space",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def load_streamlit_secrets_into_env() -> None:
    try:
        for key, value in st.secrets.items():
            if isinstance(value, (str, int, float, bool)):
                os.environ.setdefault(key, str(value))
    except Exception:
        return


load_streamlit_secrets_into_env()

from app import config  # noqa: E402
from app import streamlit_services as svc  # noqa: E402
from app.database import ensure_daily_backup, init_db  # noqa: E402
from app.security import is_admin, is_mentor_or_admin  # noqa: E402


OPEN_APP_USER = {
    "id": 0,
    "email": "open-mode@local",
    "display_name": "FDM Space",
    "role": config.ADMIN_ROLE,
}


st.markdown(
    """
    <style>
      [data-testid="stSidebar"], #MainMenu, footer { display: none !important; }
      [data-testid="stHeader"] { background: rgba(244,247,248,.88); }
      .block-container { max-width: 1480px; padding-top: 1.35rem; padding-bottom: 3rem; }
      h1, h2, h3, p, label { letter-spacing: 0; }
      div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 8px; }
      div[data-testid="stMetric"] { padding: .15rem 0 .1rem; }
      div[data-testid="stMetricValue"] { font-weight: 800; }
      button[kind="primary"], div[data-testid="stDownloadButton"] button { font-weight: 700; }
      button[data-baseweb="tab"] { font-weight: 700; }
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


def rerun() -> None:
    st.rerun()


def handle_action(fn, success: str) -> None:
    try:
        fn()
    except ValueError as exc:
        st.error(str(exc))
    else:
        st.success(success)
        rerun()


def value_or_dash(value):
    if value is None or value == "":
        return "-"
    return value


def status_label(value: str) -> str:
    return {"due": "Fällig", "open": "Offen", "due-soon": "Bald fällig"}.get(value, value)


def selected_by_label(items: list[dict], label: str, field: str = "name") -> dict | None:
    return next((item for item in items if item.get(field) == label), None)


def table_height(row_count: int, maximum: int = 520) -> int:
    if row_count <= 0:
        return 120
    return min(maximum, 38 * (row_count + 1) + 8)


def data_table(rows: list[dict], columns: list[tuple[str, str]], empty: str = "Keine Daten vorhanden.", height: int | None = None) -> None:
    if not rows:
        st.info(empty)
        return
    visible_rows = [
        {label: value_or_dash(item.get(key)) for label, key in columns}
        for item in rows
    ]
    st.dataframe(
        visible_rows,
        hide_index=True,
        use_container_width=True,
        height=height or table_height(len(visible_rows)),
    )


def app_header(state: dict) -> None:
    with st.container(border=True):
        st.markdown("### Wartung FDM Space")
        st.caption("Interne Wartungsverwaltung für Druckerflotte, Nachweise und Druckstunden")
        st.markdown(f"**{len(state['devices'])} Drucker** · **{len(state['tasks'])} Wartungspunkte** · **Interner Betrieb**")


def page_header(title: str, eyebrow: str, subtitle: str = "") -> None:
    st.caption(eyebrow.upper())
    st.header(title)
    if subtitle:
        st.write(subtitle)


def section(title: str, subtitle: str = "") -> None:
    st.subheader(title)
    if subtitle:
        st.caption(subtitle)


def metric_cards(cards: list[tuple[str, int | str, str]]) -> None:
    cols = st.columns(len(cards), gap="medium")
    for col, (label, value, detail) in zip(cols, cards):
        with col:
            with st.container(border=True):
                st.metric(label, value)
                st.caption(detail)


def dashboard(state: dict) -> None:
    due = state["due"]
    due_count = sum(1 for item in due if item["status"] == "due")
    open_count = sum(1 for item in due if item["status"] == "open")
    soon_count = sum(1 for item in due if item["status"] == "due-soon")

    page_header(
        "Übersicht",
        "Betriebsstatus",
        "Aktuelle Lage der Druckerflotte, offene Wartungen und zuletzt dokumentierte Arbeiten.",
    )
    metric_cards(
        [
            ("Aktive Drucker", len(state["devices"]), "Geräte in Pflege"),
            ("Fällig", due_count, "Priorität sofort"),
            ("Offen", open_count, "Noch ohne Eintrag"),
            ("Bald fällig", soon_count, "Nächste Wartung"),
        ]
    )

    section("Fälligkeiten", "Sortiert nach Priorität und Drucker.")
    data_table(
        [
            {
                "Status": status_label(item["status"]),
                "Drucker": item["device"],
                "Wartung": item["task"],
                "Level": item["level"],
                "Detail": item["detail"],
                "Letzter Eintrag": item["last_done"] or "-",
            }
            for item in due
        ],
        [
            ("Status", "Status"),
            ("Drucker", "Drucker"),
            ("Wartung", "Wartung"),
            ("Level", "Level"),
            ("Detail", "Detail"),
            ("Letzter Eintrag", "Letzter Eintrag"),
        ],
        "Aktuell sind keine Wartungen fällig.",
    )

    section("Letzte Einträge")
    devices = {item["id"]: item["name"] for item in state["devices"]}
    tasks = {item["id"]: item["title"] for item in state["tasks"]}
    data_table(
        [
            {
                "Datum": log["done_on"],
                "Drucker": devices.get(log["device_id"], log["device_id"]),
                "Wartung": tasks.get(log["task_id"], log["task_id"]),
                "Stunden": log["print_hours"],
                "Benutzer": log["user_name"],
                "Vermerk": log["note"],
            }
            for log in state["logs"][:20]
        ],
        [
            ("Datum", "Datum"),
            ("Drucker", "Drucker"),
            ("Wartung", "Wartung"),
            ("Stunden", "Stunden"),
            ("Benutzer", "Benutzer"),
            ("Vermerk", "Vermerk"),
        ],
        "Noch keine Einträge vorhanden.",
    )


def log_form(current_user: dict, state: dict) -> None:
    page_header("Wartung erfassen", "Dokumentation", "Wartung, Druckstunden und allgemeine Vermerke sauber erfassen.")
    devices = state["devices"]
    tasks = state["tasks"]
    if not devices or not tasks:
        st.warning("Es sind noch keine aktiven Drucker oder Wartungspunkte vorhanden.")
        return

    selected_name = st.selectbox("Drucker", [item["name"] for item in devices], key="log-device")
    device = selected_by_label(devices, selected_name)
    assert device is not None
    matching_tasks = [task for task in tasks if task["applies_to"] in {"all", device["kind"]}]
    if not is_mentor_or_admin(current_user):
        matching_tasks = [task for task in matching_tasks if task["level"] == "B"]
    if not matching_tasks:
        st.warning("Für diesen Drucker gibt es keine Wartungspunkte, die du mit deiner Rolle erfassen kannst.")
        return

    left, right = st.columns([1.15, .85], gap="large")
    with left:
        with st.container(border=True):
            st.markdown("#### Wartung speichern")
            with st.form("create-log"):
                task_labels = [f"{task['title']} · Level {task['level']}" for task in matching_tasks]
                task_label = st.selectbox("Wartungspunkt", task_labels, key="log-task")
                task = matching_tasks[task_labels.index(task_label)]
                done_on = st.date_input("Datum", value=date.today(), max_value=date.today(), key="log-date")
                print_hours = st.number_input("Druckstunden", min_value=0, step=1, value=int(device["current_print_hours"] or 0), key="log-hours")
                note = st.text_area("Vermerk", max_chars=1000, key="log-note")
                submitted = st.form_submit_button("Wartung speichern", type="primary")
            if submitted:
                handle_action(lambda: svc.create_log(current_user, device["id"], task["id"], str(done_on), print_hours, note), "Wartung gespeichert.")
    with right:
        with st.container(border=True):
            st.markdown("#### Allgemeiner Vermerk")
            with st.form("create-note"):
                note_date = st.date_input("Datum", value=date.today(), max_value=date.today(), key="note-date")
                note_text = st.text_area("Vermerk", max_chars=1000, key="note-text")
                submitted = st.form_submit_button("Vermerk speichern")
            if submitted:
                handle_action(lambda: svc.create_note(current_user, device["id"], str(note_date), note_text), "Vermerk gespeichert.")


def devices_page(current_user: dict, state: dict) -> None:
    page_header("Drucker & Tools", "Geräte", "Flotte, aktuelle Druckstunden und XL-Toolheads.")
    devices = state["devices"]
    data_table(
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
        [("Drucker", "Drucker"), ("Typ", "Typ"), ("Mentoren", "Mentoren"), ("Druckstunden", "Druckstunden"), ("Aktualisiert", "Aktualisiert")],
    )

    if is_mentor_or_admin(current_user):
        section("Druckstunden aktualisieren")
        with st.container(border=True):
            with st.form("update-hours"):
                selected_name = st.selectbox("Drucker", [item["name"] for item in devices], key="hours-device")
                device = selected_by_label(devices, selected_name)
                hours = st.number_input("Aktuelle Druckstunden", min_value=0, step=1, value=int((device or {}).get("current_print_hours") or 0), key="hours-value")
                submitted = st.form_submit_button("Druckstunden speichern")
            if submitted and device:
                handle_action(lambda: svc.update_hours(current_user, device["id"], hours), "Druckstunden aktualisiert.")

    xl_devices = [item for item in devices if item["kind"] == "xl5"]
    if xl_devices:
        section("XL Toolheads")
        data_table(
            state["xlTools"],
            [("Drucker", "device_id"), ("Tool", "tool_number"), ("Düse", "nozzle_type"), ("Material", "material"), ("Letzter Wechsel", "last_nozzle_change"), ("Hinweis", "issue_note")],
        )
        if is_mentor_or_admin(current_user):
            with st.container(border=True):
                with st.form("xl-tool"):
                    selected_name = st.selectbox("XL Drucker", [item["name"] for item in xl_devices], key="xl-device")
                    device = selected_by_label(xl_devices, selected_name)
                    tool_number = st.selectbox("Tool", [1, 2, 3, 4, 5], key="xl-tool-number")
                    nozzle_type = st.text_input("Düse", key="xl-nozzle")
                    material = st.text_input("Material", key="xl-material")
                    last_change = st.date_input("Letzter Düsenwechsel", value=date.today(), max_value=date.today(), key="xl-change")
                    issue_note = st.text_area("Hinweis / Problem", max_chars=500, key="xl-issue")
                    submitted = st.form_submit_button("Toolhead speichern")
                if submitted and device:
                    handle_action(
                        lambda: svc.update_xl_tool(current_user, device["id"], tool_number, nozzle_type, material, str(last_change), issue_note),
                        "Toolhead aktualisiert.",
                    )


def history_page(current_user: dict, state: dict) -> None:
    page_header("Historie & Export", "Nachweise", "Wartungs- und Vermerkshistorie prüfen und exportieren.")
    devices = {item["id"]: item["name"] for item in state["devices"]}
    tasks = {item["id"]: item["title"] for item in state["tasks"]}

    with st.container(border=True):
        month = st.text_input("Monat für Export, optional", placeholder="2026-06", key="export-month")
        col1, col2 = st.columns(2)
        suffix = f"_{month.strip()}" if month.strip() else ""
        try:
            col1.download_button("CSV herunterladen", svc.export_csv_bytes(month), file_name=f"wartung_fdm_space{suffix}.csv", mime="text/csv", use_container_width=True)
        except ValueError as exc:
            col1.error(str(exc))
        try:
            col2.download_button("PDF herunterladen", svc.export_pdf_bytes(month), file_name=f"wartung_fdm_space{suffix}.pdf", mime="application/pdf", use_container_width=True)
        except ValueError as exc:
            col2.error(str(exc))

    section("Wartungseinträge")
    data_table(
        [
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
        ],
        [("ID", "ID"), ("Datum", "Datum"), ("Drucker", "Drucker"), ("Wartung", "Wartung"), ("Stunden", "Stunden"), ("Benutzer", "Benutzer"), ("Vermerk", "Vermerk")],
        height=520,
    )

    section("Vermerke")
    data_table(
        [
            {
                "ID": item["id"],
                "Datum": item["note_date"],
                "Drucker": devices.get(item["device_id"], item["device_id"]),
                "Benutzer": item["user_name"],
                "Text": item["text"],
            }
            for item in state["notes"]
        ],
        [("ID", "ID"), ("Datum", "Datum"), ("Drucker", "Drucker"), ("Benutzer", "Benutzer"), ("Text", "Text")],
    )

    if is_mentor_or_admin(current_user):
        with st.expander("Eintrag löschen"):
            entry_table = st.selectbox("Typ", ["logs", "notes"], format_func=lambda value: "Wartung" if value == "logs" else "Vermerk", key="delete-type")
            item_id = st.number_input("ID", min_value=1, step=1, key="delete-id")
            if st.button("Eintrag löschen", type="secondary", key="delete-entry"):
                handle_action(lambda: svc.delete_entry(current_user, entry_table, int(item_id)), "Eintrag gelöscht.")


def admin_devices(current_user: dict, admin_state: dict) -> None:
    section("Drucker verwalten")
    data_table(
        [
            {"ID": item["id"], "Name": item["name"], "Typ": item["type_label"], "Mentoren": item["mentors"], "Aktiv": "Ja" if item["active"] else "Nein"}
            for item in admin_state["devices"]
        ],
        [("ID", "ID"), ("Name", "Name"), ("Typ", "Typ"), ("Mentoren", "Mentoren"), ("Aktiv", "Aktiv")],
    )
    with st.container(border=True):
        with st.form("admin-device"):
            device_id = st.text_input("ID", placeholder="mini-alpha-1", key="admin-device-id")
            kind = st.selectbox("Typ", ["mini", "mk3_5", "xl5"], format_func=lambda value: {"mini": "MINI+", "mk3_5": "MK3.5", "xl5": "XL 5-Tool"}[value], key="admin-device-kind")
            name = st.text_input("Name", key="admin-device-name")
            mentors = st.text_input("Mentoren", key="admin-device-mentors")
            active = st.checkbox("Aktiv", value=True, key="admin-device-active")
            submitted = st.form_submit_button("Drucker speichern")
        if submitted:
            handle_action(lambda: svc.save_device(current_user, device_id, kind, name, mentors, active), "Drucker gespeichert.")


def admin_tasks(current_user: dict, admin_state: dict) -> None:
    section("Wartungspunkte verwalten")
    data_table(
        [
            {
                "ID": item["id"],
                "Titel": item["title"],
                "Gilt für": item["applies_to"],
                "Level": item["level"],
                "Intervall": item["interval_text"],
                "Aktiv": "Ja" if item["active"] else "Nein",
            }
            for item in admin_state["tasks"]
        ],
        [("ID", "ID"), ("Titel", "Titel"), ("Gilt für", "Gilt für"), ("Level", "Level"), ("Intervall", "Intervall"), ("Aktiv", "Aktiv")],
    )
    with st.container(border=True):
        with st.form("admin-task"):
            task_id = st.text_input("ID", placeholder="bed-clean", key="admin-task-id")
            applies_to = st.selectbox("Gilt für", ["all", "mini", "mk3_5", "xl5"], key="admin-task-applies")
            title = st.text_input("Titel", key="admin-task-title")
            details = st.text_area("Details", max_chars=1200, key="admin-task-details")
            level = st.selectbox("Level", ["B", "E", "M"], key="admin-task-level")
            interval_text = st.text_input("Intervalltext", key="admin-task-interval")
            cadence_days = st.text_input("Tage", placeholder="optional", key="admin-task-days")
            cadence_hours = st.text_input("Stunden", placeholder="optional", key="admin-task-hours")
            active = st.checkbox("Aktiv", value=True, key="admin-task-active")
            submitted = st.form_submit_button("Wartungspunkt speichern")
        if submitted:
            handle_action(lambda: svc.save_task(current_user, task_id, applies_to, title, details, level, interval_text, cadence_days, cadence_hours, active), "Wartungspunkt gespeichert.")


def admin_backups(current_user: dict, admin_state: dict) -> None:
    section("Backups")
    with st.container(border=True):
        reason = st.text_input("Grund", value="manual", key="backup-reason")
        if st.button("Backup erstellen", type="primary", key="create-backup"):
            handle_action(lambda: svc.create_manual_backup(current_user, reason), "Backup erstellt.")
    data_table(admin_state["backups"], [("Datei", "file_name"), ("Grund", "reason"), ("Erstellt von", "created_by"), ("Erstellt", "created_at"), ("Größe", "size_bytes")])
    if admin_state["backups"]:
        with st.container(border=True):
            names = [item["file_name"] for item in admin_state["backups"]]
            selected = st.selectbox("Backup-Datei", names, key="backup-file")
            st.download_button("Backup herunterladen", svc.backup_bytes(selected), file_name=selected, mime="application/octet-stream", use_container_width=True)
            col1, col2 = st.columns(2)
            if col1.button("Ausgewähltes Backup wiederherstellen", key="restore-backup"):
                handle_action(lambda: svc.restore_backup_file(current_user, selected), "Backup wiederhergestellt.")
            keep = col2.number_input("Behalten", min_value=1, max_value=200, value=20, key="backup-keep")
            if col2.button("Alte Backups löschen", key="prune-backups"):
                handle_action(lambda: svc.prune_backup_files(current_user, int(keep)), "Backups bereinigt.")


def admin_settings(current_user: dict, admin_state: dict) -> None:
    section("Einstellungen")
    with st.container(border=True):
        with st.form("teams-webhook"):
            webhook = st.text_input("Teams Webhook URL", value=admin_state["settings"]["teams_webhook_url"], key="teams-webhook-url")
            submitted = st.form_submit_button("Webhook speichern")
        if submitted:
            handle_action(lambda: svc.set_teams_webhook(current_user, webhook), "Webhook gespeichert.")
    section("Audit")
    data_table(admin_state["audit"], [("Zeit", "created_at"), ("Benutzer", "user_name"), ("Aktion", "action"), ("Typ", "entity_type"), ("ID", "entity_id"), ("Details", "details")], height=520)


def admin_page(current_user: dict) -> None:
    page_header("Admin", "Verwaltung", "Drucker, Wartungspunkte, Backups und Einstellungen.")
    admin_state = svc.load_admin_state()
    tabs = st.tabs(["Drucker", "Wartung", "Backups", "Einstellungen"])
    with tabs[0]:
        admin_devices(current_user, admin_state)
    with tabs[1]:
        admin_tasks(current_user, admin_state)
    with tabs[2]:
        admin_backups(current_user, admin_state)
    with tabs[3]:
        admin_settings(current_user, admin_state)


def main() -> None:
    current_user = OPEN_APP_USER
    state = svc.load_state()
    app_header(state)
    tabs = st.tabs(["Übersicht", "Wartung erfassen", "Drucker & Tools", "Historie & Export", "Admin"])
    with tabs[0]:
        dashboard(state)
    with tabs[1]:
        log_form(current_user, state)
    with tabs[2]:
        devices_page(current_user, state)
    with tabs[3]:
        history_page(current_user, state)
    with tabs[4]:
        if is_admin(current_user):
            admin_page(current_user)
        else:
            st.warning("Für diesen Bereich sind Admin-Rechte erforderlich.")


if __name__ == "__main__":
    main()
