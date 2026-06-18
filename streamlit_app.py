from __future__ import annotations

import html
import os
from datetime import date

import streamlit as st


st.set_page_config(
    page_title="Wartung FDM Space",
    layout="wide",
    initial_sidebar_state="expanded",
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


st.markdown(
    """
    <style>
      :root {
        --fdm-bg: #eef3f5;
        --fdm-panel: #ffffff;
        --fdm-panel-soft: #f7fafb;
        --fdm-text: #17242b;
        --fdm-muted: #62727b;
        --fdm-line: #d8e2e7;
        --fdm-teal: #1f6b7d;
        --fdm-teal-dark: #164d5a;
        --fdm-green: #2e7658;
        --fdm-red: #ad4545;
        --fdm-amber: #9a6b1f;
      }
      html, body, [class*="css"] { font-family: Inter, "Segoe UI", system-ui, sans-serif; }
      .stApp { background: var(--fdm-bg); color: var(--fdm-text); }
      .block-container { max-width: 1420px; padding: 2rem 3rem 3rem; }
      [data-testid="stHeader"] { background: transparent; }
      [data-testid="stToolbar"], #MainMenu, footer { display: none !important; }
      [data-testid="stSidebar"] {
        background: #101d23;
        border-right: 1px solid rgba(255,255,255,.08);
      }
      [data-testid="stSidebar"] * { color: #edf5f7 !important; }
      [data-testid="stSidebar"] .stCaption, [data-testid="stSidebar"] small { color: #a9bdc5 !important; }
      [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #ffffff !important;
        letter-spacing: 0;
      }
      [data-testid="stSidebar"] [role="radiogroup"] label {
        border-radius: 8px;
        margin: 2px 0;
        padding: 8px 10px;
        transition: background .15s ease;
      }
      [data-testid="stSidebar"] [role="radiogroup"] label:hover { background: rgba(255,255,255,.08); }
      [data-testid="stSidebar"] button {
        background: rgba(255,255,255,.06) !important;
        border-color: rgba(255,255,255,.25) !important;
        border-radius: 8px !important;
      }
      h1, h2, h3 { color: var(--fdm-text); letter-spacing: 0; }
      div[data-testid="stForm"] {
        background: var(--fdm-panel);
        border: 1px solid var(--fdm-line);
        border-radius: 8px;
        padding: 1.1rem;
        box-shadow: 0 10px 28px rgba(28,48,58,.045);
      }
      div[data-testid="stAlert"] { border-radius: 8px; }
      .stButton > button, .stDownloadButton > button, [data-testid="baseButton-primary"] {
        border-radius: 8px !important;
        font-weight: 700;
        min-height: 2.55rem;
      }
      .fdm-hero {
        background: linear-gradient(135deg, #ffffff 0%, #f6fafb 68%, #edf5f7 100%);
        border: 1px solid var(--fdm-line);
        border-left: 5px solid var(--fdm-teal);
        border-radius: 8px;
        box-shadow: 0 14px 35px rgba(28,48,58,.07);
        margin-bottom: 1.1rem;
        padding: 1.25rem 1.35rem;
      }
      .fdm-eyebrow {
        color: var(--fdm-teal-dark);
        font-size: .78rem;
        font-weight: 800;
        letter-spacing: .08em;
        margin-bottom: .25rem;
        text-transform: uppercase;
      }
      .fdm-hero h1, .fdm-brand h1 { font-size: 2.35rem; line-height: 1.05; margin: 0; }
      .fdm-hero p, .fdm-brand p { color: var(--fdm-muted); margin: .45rem 0 0; max-width: 780px; }
      .fdm-auth-wrap {
        max-width: 1060px;
        margin: 7vh auto 0;
      }
      .fdm-auth-head {
        margin-bottom: 1.1rem;
      }
      .fdm-auth-head h1 {
        font-size: 2.15rem;
        line-height: 1.08;
        margin: 0;
      }
      .fdm-auth-head p {
        color: var(--fdm-muted);
        margin: .42rem 0 0;
      }
      .fdm-brand {
        background: linear-gradient(145deg, #101d23 0%, #16313b 62%, #1f6b7d 100%);
        border: 1px solid rgba(255,255,255,.1);
        border-radius: 8px;
        box-shadow: 0 18px 46px rgba(16,29,35,.16);
        min-height: 358px;
        padding: 1.45rem;
      }
      .fdm-brand .fdm-eyebrow { color: #9fd4df; }
      .fdm-brand h1 { color: #ffffff; }
      .fdm-brand p { color: #c6d7dd; }
      .fdm-auth-kpis {
        display: grid;
        gap: .55rem;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        margin-top: 1.35rem;
      }
      .fdm-mini-stat {
        background: rgba(255,255,255,.08);
        border: 1px solid rgba(255,255,255,.13);
        border-radius: 8px;
        padding: .75rem;
      }
      .fdm-mini-stat strong { color: #ffffff; display: block; font-size: 1.05rem; }
      .fdm-mini-stat span { color: #bad0d7; display: block; font-size: .8rem; margin-top: .12rem; }
      .fdm-auth-note {
        background: #ffffff;
        border: 1px solid var(--fdm-line);
        border-radius: 8px;
        box-shadow: 0 18px 46px rgba(28,48,58,.08);
        padding: 1rem 1.05rem 1.1rem;
      }
      .fdm-auth-note h2 { font-size: 1.18rem; margin: 0; }
      .fdm-auth-note p { color: var(--fdm-muted); margin: .25rem 0 0; }
      .fdm-metrics {
        display: grid;
        gap: .9rem;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        margin: 1.1rem 0 1.45rem;
      }
      .fdm-metric {
        background: var(--fdm-panel);
        border: 1px solid var(--fdm-line);
        border-radius: 8px;
        box-shadow: 0 10px 28px rgba(28,48,58,.055);
        padding: 1rem;
      }
      .fdm-metric span { color: var(--fdm-muted); display: block; font-size: .86rem; font-weight: 700; }
      .fdm-metric strong { color: var(--fdm-text); display: block; font-size: 2rem; line-height: 1.12; margin-top: .35rem; }
      .fdm-metric.accent { border-top: 4px solid var(--fdm-teal); }
      .fdm-metric.red { border-top: 4px solid var(--fdm-red); }
      .fdm-metric.amber { border-top: 4px solid var(--fdm-amber); }
      .fdm-metric.green { border-top: 4px solid var(--fdm-green); }
      .fdm-section-title { margin: 1.15rem 0 .7rem; }
      .fdm-section-title h2 { font-size: 1.35rem; margin: 0; }
      .fdm-section-title p { color: var(--fdm-muted); margin: .22rem 0 0; }
      .fdm-table-wrap {
        background: var(--fdm-panel);
        border: 1px solid var(--fdm-line);
        border-radius: 8px;
        box-shadow: 0 10px 28px rgba(28,48,58,.045);
        overflow: hidden;
      }
      .fdm-table-scroll { max-height: 540px; overflow: auto; }
      table.fdm-table { border-collapse: collapse; font-size: .92rem; width: 100%; }
      .fdm-table th {
        background: #f4f7f9;
        color: #52636d;
        font-size: .78rem;
        font-weight: 800;
        letter-spacing: .04em;
        padding: .78rem .85rem;
        position: sticky;
        text-align: left;
        text-transform: uppercase;
        top: 0;
        z-index: 1;
      }
      .fdm-table td {
        border-top: 1px solid var(--fdm-line);
        color: var(--fdm-text);
        padding: .74rem .85rem;
        vertical-align: top;
      }
      .fdm-table tr:hover td { background: #fbfdfd; }
      .fdm-badge {
        border-radius: 999px;
        display: inline-block;
        font-size: .78rem;
        font-weight: 800;
        min-width: 74px;
        padding: .18rem .55rem;
        text-align: center;
      }
      .fdm-badge.open { background: #eaf1f4; color: #3d5661; }
      .fdm-badge.due { background: #faeaea; color: var(--fdm-red); }
      .fdm-badge.soon { background: #f8efd9; color: var(--fdm-amber); }
      .fdm-badge.active { background: #e5f2ec; color: var(--fdm-green); }
      .fdm-badge.inactive { background: #eceff1; color: #60717a; }
      .fdm-card-grid {
        display: grid;
        gap: .9rem;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        margin: .8rem 0 1.2rem;
      }
      .fdm-card {
        background: var(--fdm-panel);
        border: 1px solid var(--fdm-line);
        border-radius: 8px;
        box-shadow: 0 10px 28px rgba(28,48,58,.045);
        padding: 1rem;
      }
      .fdm-card h3 { font-size: 1.02rem; margin: 0 0 .25rem; }
      .fdm-card p { color: var(--fdm-muted); margin: 0; }
      @media (max-width: 900px) {
        .block-container { padding: 1rem; }
        .fdm-metrics, .fdm-card-grid, .fdm-auth-kpis { grid-template-columns: 1fr; }
        .fdm-auth-wrap { margin-top: 1rem; }
        .fdm-brand { min-height: auto; }
        .fdm-hero h1, .fdm-brand h1 { font-size: 1.75rem; }
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


def esc(value) -> str:
    if value is None or value == "":
        return "-"
    return html.escape(str(value))


def status_label(value: str) -> str:
    return {"due": "Fällig", "open": "Offen", "due-soon": "Bald fällig"}.get(value, value)


def badge(value: str, kind: str) -> str:
    return f"<span class='fdm-badge {esc(kind)}'>{esc(value)}</span>"


def render_page_header(title: str, eyebrow: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <section class="fdm-hero">
          <div class="fdm-eyebrow">{esc(eyebrow)}</div>
          <h1>{esc(title)}</h1>
          {f"<p>{esc(subtitle)}</p>" if subtitle else ""}
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_section(title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div class="fdm-section-title">
          <h2>{esc(title)}</h2>
          {f"<p>{esc(subtitle)}</p>" if subtitle else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metrics(cards: list[tuple[str, str | int, str]]) -> None:
    body = "".join(
        f"""
        <article class="fdm-metric {esc(style)}">
          <span>{esc(label)}</span>
          <strong>{esc(value)}</strong>
        </article>
        """
        for label, value, style in cards
    )
    st.markdown(f"<div class='fdm-metrics'>{body}</div>", unsafe_allow_html=True)


def render_table(rows: list[dict], columns: list[tuple[str, str]], empty: str = "Keine Daten vorhanden.") -> None:
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
        <div class="fdm-table-wrap">
          <div class="fdm-table-scroll">
            <table class="fdm-table">
              <thead><tr>{header}</tr></thead>
              <tbody>{''.join(body_rows)}</tbody>
            </table>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def selected_by_label(items: list[dict], label: str, field: str = "name") -> dict | None:
    return next((item for item in items if item.get(field) == label), None)


def render_reset_page(token: str) -> None:
    render_page_header("Passwort neu setzen", "Zugang", "Lege ein neues Passwort für deinen Wartungszugang fest.")
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
    setup_available = svc.first_user_setup_available()
    team_code_ready = svc.team_code_is_configured()
    st.markdown("<div class='fdm-auth-wrap'>", unsafe_allow_html=True)
    left, right = st.columns([0.95, 1.05], gap="large")
    with left:
        st.markdown(
            """
            <section class="fdm-brand">
              <div class="fdm-eyebrow">SFZ / FDM Space</div>
              <h1>Wartung FDM Space</h1>
              <p>Wartungsstände, Druckstunden und Nachweise für die FDM-Druckerflotte an einem Ort.</p>
              <div class="fdm-auth-kpis">
                <div class="fdm-mini-stat"><strong>Rollen</strong><span>Admin, Mentor, Benutzer</span></div>
                <div class="fdm-mini-stat"><strong>Nachweise</strong><span>CSV und PDF Export</span></div>
                <div class="fdm-mini-stat"><strong>Wartung</strong><span>Fälligkeiten und Historie</span></div>
                <div class="fdm-mini-stat"><strong>Geräte</strong><span>MINI+, MK3.5, XL</span></div>
              </div>
            </section>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            """
            <section class="fdm-auth-note">
              <div class="fdm-eyebrow">Zugang</div>
              <h2>Anmelden oder Konto einrichten</h2>
              <p>Wenn noch kein aktiver Administrator existiert, wird das nächste registrierte Konto als Administrator angelegt.</p>
            </section>
            """,
            unsafe_allow_html=True,
        )
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
            if setup_available:
                st.success("Ersteinrichtung aktiv: Dieses Konto wird als Administrator angelegt.")
            elif team_code_ready:
                st.info("Registrierung ist mit Teamleiter-Code freigeschaltet.")
            else:
                st.warning("Registrierung ist gesperrt. Ein Administrator muss zuerst einen Teamleiter-Code setzen.")
            with st.form("register-form"):
                display_name = st.text_input("Name")
                email = st.text_input("E-Mail", key="register-email")
                password = st.text_input("Passwort", type="password", key="register-password")
                code = "" if setup_available else st.text_input("Teamleiter-Code", type="password")
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
    st.markdown("</div>", unsafe_allow_html=True)


def render_sidebar(current_user: dict) -> str:
    st.sidebar.markdown("## Wartung")
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
    render_page_header(
        "Übersicht",
        "Betriebsstatus",
        "Schneller Überblick über aktive Drucker, offene Wartungen und die neuesten Einträge.",
    )
    due = state["due"]
    due_count = sum(1 for item in due if item["status"] == "due")
    open_count = sum(1 for item in due if item["status"] == "open")
    soon_count = sum(1 for item in due if item["status"] == "due-soon")
    render_metrics(
        [
            ("Aktive Drucker", len(state["devices"]), "accent"),
            ("Fällig", due_count, "red"),
            ("Offen", open_count, "amber"),
            ("Bald fällig", soon_count, "green"),
        ]
    )

    render_section("Fälligkeiten", "Nach Priorität sortiert. Offene Einträge entstehen, wenn noch kein Wartungslog vorhanden ist.")
    render_table(
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

    render_section("Letzte Einträge")
    logs = state["logs"][:20]
    devices = {item["id"]: item["name"] for item in state["devices"]}
    tasks = {item["id"]: item["title"] for item in state["tasks"]}
    render_table(
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


def render_log_form(current_user: dict, state: dict) -> None:
    render_page_header("Wartung erfassen", "Erfassung", "Neue Wartungen und allgemeine Vermerke für einen Drucker dokumentieren.")
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


def render_devices(current_user: dict, state: dict) -> None:
    render_page_header("Drucker & Tools", "Geräteflotte", "Aktive Drucker, Druckstunden und XL-Toolhead-Informationen.")
    devices = state["devices"]
    render_table(
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
        render_section("Druckstunden aktualisieren")
        with st.form("update-hours"):
            selected_name = st.selectbox("Drucker", [item["name"] for item in devices], key="hours-device")
            device = selected_by_label(devices, selected_name)
            hours = st.number_input("Aktuelle Druckstunden", min_value=0, step=1, value=int((device or {}).get("current_print_hours") or 0))
            submitted = st.form_submit_button("Druckstunden speichern")
        if submitted and device:
            handle_action(lambda: svc.update_hours(current_user, device["id"], hours), "Druckstunden aktualisiert.")

    xl_devices = [item for item in devices if item["kind"] == "xl5"]
    if xl_devices:
        render_section("XL Toolheads")
        render_table(state["xlTools"], [("Drucker", "device_id"), ("Tool", "tool_number"), ("Düse", "nozzle_type"), ("Material", "material"), ("Letzter Wechsel", "last_nozzle_change"), ("Hinweis", "issue_note")])
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


def render_history(current_user: dict, state: dict) -> None:
    render_page_header("Historie & Export", "Nachweise", "Wartungs- und Vermerkshistorie prüfen und als CSV oder PDF exportieren.")
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

    render_section("Wartungseinträge")
    render_table(
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

    render_section("Vermerke")
    render_table(
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
            table = st.selectbox("Typ", ["logs", "notes"], format_func=lambda value: "Wartung" if value == "logs" else "Vermerk")
            item_id = st.number_input("ID", min_value=1, step=1)
            if st.button("Eintrag löschen", type="secondary"):
                handle_action(lambda: svc.delete_entry(current_user, table, int(item_id)), "Eintrag gelöscht.")


def render_profile(current_user: dict) -> None:
    render_page_header("Profil", "Konto", "Name und Passwort des angemeldeten Benutzers verwalten.")
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
    render_section("Benutzer", "Rollen, Aktivstatus und Passwörter verwalten.")
    render_table(
        [
            {
                "ID": item["id"],
                "Name": item["display_name"],
                "E-Mail": item["email"],
                "Rolle": item["role"],
                "Status_html": badge("Aktiv" if item["is_active"] else "Inaktiv", "active" if item["is_active"] else "inactive"),
                "Letzter Login": item["last_login_at"],
            }
            for item in admin_state["users"]
        ],
        [("ID", "ID"), ("Name", "Name"), ("E-Mail", "E-Mail"), ("Rolle", "Rolle"), ("Status", "Status_html"), ("Letzter Login", "Letzter Login")],
    )
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
    render_section("Drucker verwalten")
    render_table(
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


def render_admin_tasks(current_user: dict, admin_state: dict) -> None:
    render_section("Wartungspunkte verwalten")
    render_table(
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


def render_admin_backups(current_user: dict, admin_state: dict) -> None:
    render_section("Backups")
    reason = st.text_input("Grund", value="manual")
    if st.button("Backup erstellen", type="primary"):
        handle_action(lambda: svc.create_manual_backup(current_user, reason), "Backup erstellt.")
    render_table(admin_state["backups"], [("Datei", "file_name"), ("Grund", "reason"), ("Erstellt von", "created_by"), ("Erstellt", "created_at"), ("Größe", "size_bytes")])
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


def render_admin_settings(current_user: dict, admin_state: dict) -> None:
    render_section("Einstellungen")
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
    render_section("Audit")
    render_table(admin_state["audit"], [("Zeit", "created_at"), ("Benutzer", "user_name"), ("Aktion", "action"), ("Typ", "entity_type"), ("ID", "entity_id"), ("Details", "details")])


def render_admin(current_user: dict) -> None:
    render_page_header("Admin", "Verwaltung", "Benutzer, Drucker, Wartungspunkte, Backups und Einstellungen.")
    admin_state = svc.load_admin_state()
    tabs = st.tabs(["Benutzer", "Drucker", "Wartung", "Backups", "Einstellungen"])
    with tabs[0]:
        render_admin_users(current_user, admin_state)
    with tabs[1]:
        render_admin_devices(current_user, admin_state)
    with tabs[2]:
        render_admin_tasks(current_user, admin_state)
    with tabs[3]:
        render_admin_backups(current_user, admin_state)
    with tabs[4]:
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
