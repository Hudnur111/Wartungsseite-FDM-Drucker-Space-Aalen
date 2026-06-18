from __future__ import annotations

import html
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

PAGES = ["Übersicht", "Wartung erfassen", "Drucker & Tools", "Historie & Export", "Admin"]


st.markdown(
    """
    <style>
      :root {
        --bg: #f5f7f8;
        --panel: #ffffff;
        --panel-soft: #f8fafb;
        --ink: #17242b;
        --muted: #63727b;
        --line: #dce4e8;
        --line-strong: #c7d3d9;
        --teal: #1f6b7d;
        --teal-dark: #164d5a;
        --green: #2f745a;
        --red: #a84949;
        --amber: #93671f;
        --shadow: 0 12px 34px rgba(23,36,43,.07);
      }

      html, body, [class*="css"] {
        font-family: Inter, "Segoe UI", system-ui, sans-serif;
        letter-spacing: 0;
      }
      .stApp { background: var(--bg); color: var(--ink); }
      .block-container { max-width: 1480px; padding: 1.25rem 2rem 3rem; }
      [data-testid="stHeader"] { background: transparent; }
      [data-testid="stToolbar"], [data-testid="stSidebar"], #MainMenu, footer { display: none !important; }
      h1, h2, h3, p { letter-spacing: 0; }
      h1, h2, h3 { color: var(--ink); }
      div[data-testid="stAlert"] { border-radius: 8px; }

      .app-topbar {
        align-items: center;
        background: #111f26;
        border: 1px solid rgba(255,255,255,.08);
        border-radius: 8px;
        box-shadow: var(--shadow);
        color: #ffffff;
        display: flex;
        gap: 1rem;
        justify-content: space-between;
        margin-bottom: .9rem;
        padding: .9rem 1rem;
      }
      .brand-block { display: grid; gap: .1rem; }
      .brand-name { color: #ffffff; font-size: 1.08rem; font-weight: 850; line-height: 1.1; }
      .brand-sub { color: #aac0c8; font-size: .82rem; }
      .top-status {
        align-items: center;
        display: flex;
        flex-wrap: wrap;
        gap: .55rem;
        justify-content: flex-end;
      }
      .status-chip {
        background: rgba(255,255,255,.08);
        border: 1px solid rgba(255,255,255,.14);
        border-radius: 999px;
        color: #e9f2f5;
        font-size: .82rem;
        font-weight: 750;
        padding: .3rem .65rem;
      }

      div[role="radiogroup"] {
        background: #ffffff;
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: 0 8px 22px rgba(23,36,43,.045);
        gap: 4px;
        padding: 5px;
      }
      div[role="radiogroup"] label {
        border-radius: 6px !important;
        min-height: 38px;
        padding: 6px 12px !important;
      }
      div[role="radiogroup"] label > div:first-child {
        display: none !important;
      }
      div[role="radiogroup"] label:has(input:checked) {
        background: #e8f2f5 !important;
        color: var(--teal-dark) !important;
        font-weight: 800;
      }

      .page-head {
        align-items: end;
        display: flex;
        gap: 1rem;
        justify-content: space-between;
        margin: 1.25rem 0 1rem;
      }
      .page-title { display: grid; gap: .22rem; }
      .eyebrow {
        color: var(--teal-dark);
        font-size: .76rem;
        font-weight: 850;
        letter-spacing: .06em;
        text-transform: uppercase;
      }
      .page-title h1 {
        font-size: 2rem;
        line-height: 1.08;
        margin: 0;
      }
      .page-title p {
        color: var(--muted);
        margin: 0;
        max-width: 760px;
      }
      .mode-note {
        background: #fff8e8;
        border: 1px solid #ead9aa;
        border-radius: 8px;
        color: #684b18;
        font-size: .86rem;
        font-weight: 750;
        padding: .65rem .8rem;
      }

      .metrics {
        display: grid;
        gap: .8rem;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        margin: .85rem 0 1.2rem;
      }
      .metric {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: 0 8px 24px rgba(23,36,43,.045);
        padding: .9rem .95rem;
      }
      .metric span {
        color: var(--muted);
        display: block;
        font-size: .82rem;
        font-weight: 800;
      }
      .metric strong {
        color: var(--ink);
        display: block;
        font-size: 2rem;
        line-height: 1.08;
        margin-top: .28rem;
      }
      .metric small {
        color: var(--muted);
        display: block;
        font-size: .76rem;
        margin-top: .12rem;
      }
      .metric.teal { border-top: 4px solid var(--teal); }
      .metric.red { border-top: 4px solid var(--red); }
      .metric.amber { border-top: 4px solid var(--amber); }
      .metric.green { border-top: 4px solid var(--green); }

      .section {
        align-items: end;
        display: flex;
        gap: 1rem;
        justify-content: space-between;
        margin: 1.25rem 0 .6rem;
      }
      .section h2 { font-size: 1.18rem; margin: 0; }
      .section p { color: var(--muted); margin: .18rem 0 0; }

      .table-wrap {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: 0 8px 24px rgba(23,36,43,.04);
        overflow: hidden;
      }
      .table-scroll { max-height: 560px; overflow: auto; }
      table.data-table {
        border-collapse: collapse;
        font-size: .9rem;
        width: 100%;
      }
      .data-table th {
        background: #f3f6f7;
        color: #53656f;
        font-size: .75rem;
        font-weight: 850;
        letter-spacing: .04em;
        padding: .72rem .8rem;
        position: sticky;
        text-align: left;
        text-transform: uppercase;
        top: 0;
        z-index: 1;
      }
      .data-table td {
        border-top: 1px solid var(--line);
        color: var(--ink);
        padding: .68rem .8rem;
        vertical-align: top;
      }
      .data-table tr:hover td { background: #fbfcfd; }

      .badge {
        border-radius: 999px;
        display: inline-block;
        font-size: .76rem;
        font-weight: 850;
        min-width: 74px;
        padding: .18rem .55rem;
        text-align: center;
      }
      .badge.open { background: #eaf1f4; color: #3d5661; }
      .badge.due { background: #faeaea; color: var(--red); }
      .badge.soon { background: #f8efd9; color: var(--amber); }
      .badge.active { background: #e5f2ec; color: var(--green); }
      .badge.inactive { background: #eceff1; color: #60717a; }

      .work-grid {
        display: grid;
        gap: 1rem;
        grid-template-columns: minmax(0, 1.12fr) minmax(320px, .88fr);
      }
      .panel {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: 0 8px 24px rgba(23,36,43,.04);
        padding: 1rem;
      }

      div[data-testid="stForm"] {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: 0 8px 24px rgba(23,36,43,.035);
        padding: 1rem;
      }
      .stButton > button, .stDownloadButton > button, [data-testid="baseButton-primary"] {
        border-radius: 8px !important;
        font-weight: 800;
        min-height: 2.48rem;
      }
      input, textarea, select {
        border-radius: 7px !important;
      }

      @media (max-width: 980px) {
        .block-container { padding: .9rem; }
        .app-topbar, .page-head { align-items: flex-start; flex-direction: column; }
        .top-status { justify-content: flex-start; }
        .metrics, .work-grid { grid-template-columns: 1fr; }
        .page-title h1 { font-size: 1.55rem; }
      }
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


def esc(value) -> str:
    if value is None or value == "":
        return "-"
    return html.escape(str(value))


def status_label(value: str) -> str:
    return {"due": "Fällig", "open": "Offen", "due-soon": "Bald fällig"}.get(value, value)


def badge(value: str, kind: str) -> str:
    return f"<span class='badge {esc(kind)}'>{esc(value)}</span>"


def selected_by_label(items: list[dict], label: str, field: str = "name") -> dict | None:
    return next((item for item in items if item.get(field) == label), None)


def table(rows: list[dict], columns: list[tuple[str, str]], empty: str = "Keine Daten vorhanden.") -> None:
    if not rows:
        st.info(empty)
        return
    header = "".join(f"<th>{esc(label)}</th>" for label, _ in columns)
    body_rows = []
    for item in rows:
        cells = []
        for _, key in columns:
            value = item.get(key, "")
            cells.append(f"<td>{value}</td>" if key.endswith("_html") else f"<td>{esc(value)}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    st.markdown(
        f"""
        <div class="table-wrap">
          <div class="table-scroll">
            <table class="data-table">
              <thead><tr>{header}</tr></thead>
              <tbody>{''.join(body_rows)}</tbody>
            </table>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def topbar(state: dict) -> None:
    st.markdown(
        f"""
        <div class="app-topbar">
          <div class="brand-block">
            <div class="brand-name">Wartung FDM Space</div>
            <div class="brand-sub">Interne Wartungsverwaltung für Druckerflotte und Nachweise</div>
          </div>
          <div class="top-status">
            <span class="status-chip">{len(state["devices"])} Drucker</span>
            <span class="status-chip">{len(state["tasks"])} Wartungspunkte</span>
            <span class="status-chip">Interner Betrieb</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, eyebrow: str, subtitle: str = "", note: str = "") -> None:
    st.markdown(
        f"""
        <div class="page-head">
          <div class="page-title">
            <div class="eyebrow">{esc(eyebrow)}</div>
            <h1>{esc(title)}</h1>
            {f"<p>{esc(subtitle)}</p>" if subtitle else ""}
          </div>
          {f"<div class='mode-note'>{esc(note)}</div>" if note else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )


def section(title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div class="section">
          <div>
            <h2>{esc(title)}</h2>
            {f"<p>{esc(subtitle)}</p>" if subtitle else ""}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metrics(cards: list[tuple[str, str | int, str, str]]) -> None:
    body = "".join(
        f"<article class='metric {esc(style)}'><span>{esc(label)}</span>"
        f"<strong>{esc(value)}</strong><small>{esc(detail)}</small></article>"
        for label, value, style, detail in cards
    )
    st.markdown(f"<div class='metrics'>{body}</div>", unsafe_allow_html=True)


def nav() -> str:
    return st.radio(
        "Navigation",
        PAGES,
        horizontal=True,
        label_visibility="collapsed",
    )


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
    metrics(
        [
            ("Aktive Drucker", len(state["devices"]), "teal", "Geräte in Pflege"),
            ("Fällig", due_count, "red", "Priorität sofort"),
            ("Offen", open_count, "amber", "Noch ohne Eintrag"),
            ("Bald fällig", soon_count, "green", "Nächste Wartung"),
        ]
    )

    section("Fälligkeiten", "Sortiert nach Priorität und Drucker.")
    table(
        [
            {
                "Status_html": badge(status_label(item["status"]), {"due": "due", "open": "open", "due-soon": "soon"}.get(item["status"], "open")),
                "Drucker": item["device"],
                "Wartung": item["task"],
                "Level": item["level"],
                "Detail": item["detail"],
                "Letzter Eintrag": item["last_done"] or "-",
            }
            for item in due
        ],
        [
            ("Status", "Status_html"),
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
    table(
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

    selected_name = st.selectbox("Drucker", [item["name"] for item in devices])
    device = selected_by_label(devices, selected_name)
    assert device is not None
    matching_tasks = [task for task in tasks if task["applies_to"] in {"all", device["kind"]}]
    if not is_mentor_or_admin(current_user):
        matching_tasks = [task for task in matching_tasks if task["level"] == "B"]
    if not matching_tasks:
        st.warning("Für diesen Drucker gibt es keine Wartungspunkte, die du mit deiner Rolle erfassen kannst.")
        return

    left, right = st.columns([1.1, 1], gap="large")
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


def devices_page(current_user: dict, state: dict) -> None:
    page_header("Drucker & Tools", "Geräte", "Flotte, aktuelle Druckstunden und XL-Toolheads.")
    devices = state["devices"]
    table(
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
        with st.form("update-hours"):
            selected_name = st.selectbox("Drucker", [item["name"] for item in devices], key="hours-device")
            device = selected_by_label(devices, selected_name)
            hours = st.number_input("Aktuelle Druckstunden", min_value=0, step=1, value=int((device or {}).get("current_print_hours") or 0))
            submitted = st.form_submit_button("Druckstunden speichern")
        if submitted and device:
            handle_action(lambda: svc.update_hours(current_user, device["id"], hours), "Druckstunden aktualisiert.")

    xl_devices = [item for item in devices if item["kind"] == "xl5"]
    if xl_devices:
        section("XL Toolheads")
        table(
            state["xlTools"],
            [("Drucker", "device_id"), ("Tool", "tool_number"), ("Düse", "nozzle_type"), ("Material", "material"), ("Letzter Wechsel", "last_nozzle_change"), ("Hinweis", "issue_note")],
        )
        if is_mentor_or_admin(current_user):
            with st.form("xl-tool"):
                selected_name = st.selectbox("XL Drucker", [item["name"] for item in xl_devices])
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


def history_page(current_user: dict, state: dict) -> None:
    page_header("Historie & Export", "Nachweise", "Wartungs- und Vermerkshistorie prüfen und exportieren.")
    devices = {item["id"]: item["name"] for item in state["devices"]}
    tasks = {item["id"]: item["title"] for item in state["tasks"]}
    month = st.text_input("Monat für Export, optional", placeholder="2026-06")
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
    table(
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
    )

    section("Vermerke")
    table(
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
            entry_table = st.selectbox("Typ", ["logs", "notes"], format_func=lambda value: "Wartung" if value == "logs" else "Vermerk")
            item_id = st.number_input("ID", min_value=1, step=1)
            if st.button("Eintrag löschen", type="secondary"):
                handle_action(lambda: svc.delete_entry(current_user, entry_table, int(item_id)), "Eintrag gelöscht.")


def admin_devices(current_user: dict, admin_state: dict) -> None:
    section("Drucker verwalten")
    table(
        [
            {"ID": item["id"], "Name": item["name"], "Typ": item["type_label"], "Mentoren": item["mentors"], "Aktiv": "Ja" if item["active"] else "Nein"}
            for item in admin_state["devices"]
        ],
        [("ID", "ID"), ("Name", "Name"), ("Typ", "Typ"), ("Mentoren", "Mentoren"), ("Aktiv", "Aktiv")],
    )
    with st.form("admin-device"):
        device_id = st.text_input("ID", placeholder="mini-alpha-1")
        kind = st.selectbox("Typ", ["mini", "mk3_5", "xl5"], format_func=lambda value: {"mini": "MINI+", "mk3_5": "MK3.5", "xl5": "XL 5-Tool"}[value])
        name = st.text_input("Name")
        mentors = st.text_input("Mentoren")
        active = st.checkbox("Aktiv", value=True)
        submitted = st.form_submit_button("Drucker speichern")
    if submitted:
        handle_action(lambda: svc.save_device(current_user, device_id, kind, name, mentors, active), "Drucker gespeichert.")


def admin_tasks(current_user: dict, admin_state: dict) -> None:
    section("Wartungspunkte verwalten")
    table(
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


def admin_backups(current_user: dict, admin_state: dict) -> None:
    section("Backups")
    reason = st.text_input("Grund", value="manual")
    if st.button("Backup erstellen", type="primary"):
        handle_action(lambda: svc.create_manual_backup(current_user, reason), "Backup erstellt.")
    table(admin_state["backups"], [("Datei", "file_name"), ("Grund", "reason"), ("Erstellt von", "created_by"), ("Erstellt", "created_at"), ("Größe", "size_bytes")])
    if admin_state["backups"]:
        names = [item["file_name"] for item in admin_state["backups"]]
        selected = st.selectbox("Backup-Datei", names)
        st.download_button("Backup herunterladen", svc.backup_bytes(selected), file_name=selected, mime="application/octet-stream")
        col1, col2 = st.columns(2)
        if col1.button("Ausgewähltes Backup wiederherstellen"):
            handle_action(lambda: svc.restore_backup_file(current_user, selected), "Backup wiederhergestellt.")
        keep = col2.number_input("Behalten", min_value=1, max_value=200, value=20)
        if col2.button("Alte Backups löschen"):
            handle_action(lambda: svc.prune_backup_files(current_user, int(keep)), "Backups bereinigt.")


def admin_settings(current_user: dict, admin_state: dict) -> None:
    section("Einstellungen")
    with st.form("teams-webhook"):
        webhook = st.text_input("Teams Webhook URL", value=admin_state["settings"]["teams_webhook_url"])
        submitted = st.form_submit_button("Webhook speichern")
    if submitted:
        handle_action(lambda: svc.set_teams_webhook(current_user, webhook), "Webhook gespeichert.")
    section("Audit")
    table(admin_state["audit"], [("Zeit", "created_at"), ("Benutzer", "user_name"), ("Aktion", "action"), ("Typ", "entity_type"), ("ID", "entity_id"), ("Details", "details")])


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
    topbar(state)
    page = nav()
    if page == "Übersicht":
        dashboard(state)
    elif page == "Wartung erfassen":
        log_form(current_user, state)
    elif page == "Drucker & Tools":
        devices_page(current_user, state)
    elif page == "Historie & Export":
        history_page(current_user, state)
    elif page == "Admin" and is_admin(current_user):
        admin_page(current_user)


if __name__ == "__main__":
    main()
