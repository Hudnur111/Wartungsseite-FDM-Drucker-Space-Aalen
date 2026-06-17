from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

from . import config, defaults
from .security import hash_password, normalize_email, now_iso


class AppConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()


def ensure_directories() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def migrate_legacy_database() -> None:
    ensure_directories()
    if config.DB_PATH.exists() or not config.LEGACY_DB_PATH.exists():
        return
    with sqlite3.connect(config.LEGACY_DB_PATH) as source:
        source.execute("PRAGMA wal_checkpoint(FULL)")
        with sqlite3.connect(config.DB_PATH) as target:
            source.backup(target)


def connect() -> sqlite3.Connection:
    migrate_legacy_database()
    conn = sqlite3.connect(config.DB_PATH, timeout=10, factory=AppConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def rows(conn: sqlite3.Connection, query: str, params: tuple = ()) -> list[dict]:
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def row(conn: sqlite3.Connection, query: str, params: tuple = ()) -> dict | None:
    item = conn.execute(query, params).fetchone()
    return dict(item) if item else None


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {item["name"] for item in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    migrate_legacy_database()
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'Benutzer',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                last_login_at TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                csrf_token TEXT NOT NULL DEFAULT '',
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                user_agent TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                success INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,
                request_ip TEXT NOT NULL DEFAULT '',
                user_agent TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS devices (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                mentors TEXT NOT NULL,
                type_label TEXT NOT NULL DEFAULT '',
                source_page TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 100,
                current_print_hours INTEGER,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                applies_to TEXT NOT NULL,
                title TEXT NOT NULL,
                details TEXT NOT NULL,
                level TEXT NOT NULL,
                interval_text TEXT NOT NULL,
                cadence_days INTEGER,
                cadence_hours INTEGER,
                sort_order INTEGER NOT NULL DEFAULT 100,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
                task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE RESTRICT,
                done_on TEXT NOT NULL,
                print_hours INTEGER,
                user_name TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                source_ref TEXT UNIQUE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
                note_date TEXT NOT NULL,
                user_name TEXT NOT NULL,
                text TEXT NOT NULL,
                source_ref TEXT UNIQUE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS xl_tools (
                device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
                tool_number INTEGER NOT NULL,
                nozzle_type TEXT NOT NULL DEFAULT '',
                material TEXT NOT NULL DEFAULT '',
                last_nozzle_change TEXT NOT NULL DEFAULT '',
                issue_note TEXT NOT NULL DEFAULT '',
                updated_by TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (device_id, tool_number)
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                user_name TEXT NOT NULL,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT '{}',
                ip_address TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS backup_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_expires_at
                ON sessions(expires_at);
            CREATE INDEX IF NOT EXISTS idx_login_attempts_scope
                ON login_attempts(email, ip_address, success, created_at);
            CREATE INDEX IF NOT EXISTS idx_password_reset_token_hash
                ON password_reset_tokens(token_hash);
            CREATE INDEX IF NOT EXISTS idx_password_reset_recent
                ON password_reset_tokens(user_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_password_reset_ip_recent
                ON password_reset_tokens(request_ip, created_at);
            CREATE INDEX IF NOT EXISTS idx_logs_device_task_date
                ON logs(device_id, task_id, done_on, id);
            CREATE INDEX IF NOT EXISTS idx_logs_device_recent
                ON logs(device_id, id);
            CREATE INDEX IF NOT EXISTS idx_notes_device_recent
                ON notes(device_id, note_date, id);
            CREATE INDEX IF NOT EXISTS idx_audit_log_recent
                ON audit_log(created_at, id);
            CREATE INDEX IF NOT EXISTS idx_backup_log_recent
                ON backup_log(created_at, id);
            """
        )
        ensure_column(conn, "users", "is_active", "INTEGER NOT NULL DEFAULT 1")
        ensure_column(conn, "sessions", "csrf_token", "TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "devices", "type_label", "TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "devices", "source_page", "TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "devices", "current_print_hours", "INTEGER")
        ensure_column(conn, "devices", "active", "INTEGER NOT NULL DEFAULT 1")
        ensure_column(conn, "devices", "created_at", "TEXT")
        ensure_column(conn, "devices", "updated_at", "TEXT")
        ensure_column(conn, "tasks", "cadence_hours", "INTEGER")
        ensure_column(conn, "tasks", "active", "INTEGER NOT NULL DEFAULT 1")
        ensure_column(conn, "tasks", "created_at", "TEXT")
        ensure_column(conn, "tasks", "updated_at", "TEXT")
        ensure_column(conn, "logs", "print_hours", "INTEGER")

        for device in defaults.DEVICES:
            conn.execute(
                """
                INSERT OR IGNORE INTO devices
                    (id, kind, name, mentors, type_label, source_page, sort_order, active, created_at, updated_at)
                VALUES
                    (:id, :kind, :name, :mentors, :type_label, :type_label, :sort_order, 1, :created_at, :updated_at)
                """,
                {**device, "created_at": now_iso(), "updated_at": now_iso()},
            )
            if device["kind"] == "xl5":
                for number in range(1, 6):
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO xl_tools (device_id, tool_number, updated_at)
                        VALUES (?, ?, ?)
                        """,
                        (device["id"], number, now_iso()),
                    )
        if setting(conn, "device_seed_version") != "2":
            for device in defaults.DEVICES:
                conn.execute(
                    """
                    UPDATE devices
                    SET kind = ?, name = ?, mentors = ?, type_label = ?, source_page = ?,
                        sort_order = ?, active = 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        device["kind"],
                        device["name"],
                        device["mentors"],
                        device["type_label"],
                        device["type_label"],
                        device["sort_order"],
                        now_iso(),
                        device["id"],
                    ),
                )
            set_setting(conn, "device_seed_version", "2")

        for task in defaults.TASKS:
            conn.execute(
                """
                INSERT OR IGNORE INTO tasks
                    (id, applies_to, title, details, level, interval_text, cadence_days, cadence_hours, sort_order, active, created_at, updated_at)
                VALUES
                    (:id, :applies_to, :title, :details, :level, :interval_text, :cadence_days, :cadence_hours, :sort_order, 1, :created_at, :updated_at)
                """,
                {**task, "created_at": now_iso(), "updated_at": now_iso()},
            )
        if setting(conn, "seed_version") != "2":
            for task in defaults.TASKS:
                conn.execute(
                    """
                    UPDATE tasks
                    SET applies_to = ?, title = ?, details = ?, level = ?, interval_text = ?,
                        cadence_days = ?, cadence_hours = ?, sort_order = ?, active = 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        task["applies_to"],
                        task["title"],
                        task["details"],
                        task["level"],
                        task["interval_text"],
                        task["cadence_days"],
                        task["cadence_hours"],
                        task["sort_order"],
                        now_iso(),
                        task["id"],
                    ),
                )
            conn.execute("UPDATE tasks SET active = 0 WHERE id IN ('software-update-mk3s', 'mmu-clean')")
            set_setting(conn, "seed_version", "2")
        conn.execute("DELETE FROM sessions WHERE expires_at <= ? OR csrf_token = ''", (now_iso(),))
        conn.execute("DELETE FROM password_reset_tokens WHERE expires_at <= ? OR used_at IS NOT NULL", (now_iso(),))
        bootstrap_admin(conn)


def bootstrap_admin(conn: sqlite3.Connection) -> None:
    email = normalize_email(config.BOOTSTRAP_ADMIN_EMAIL)
    password = config.BOOTSTRAP_ADMIN_PASSWORD
    display_name = config.BOOTSTRAP_ADMIN_NAME or "Administrator"
    if not email and not password:
        return
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ValueError("WARTUNG_BOOTSTRAP_ADMIN_EMAIL ist keine gültige E-Mail-Adresse.")
    if len(display_name.strip()) < 2:
        raise ValueError("WARTUNG_BOOTSTRAP_ADMIN_NAME muss mindestens 2 Zeichen haben.")
    if len(password) < 8:
        raise ValueError("WARTUNG_BOOTSTRAP_ADMIN_PASSWORD muss mindestens 8 Zeichen haben.")

    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    password_hash = hash_password(password)
    if existing:
        user_id = int(existing["id"])
        conn.execute(
            """
            UPDATE users
            SET display_name = ?, password_hash = ?, role = ?, is_active = 1
            WHERE id = ?
            """,
            (display_name.strip(), password_hash, config.ADMIN_ROLE, user_id),
        )
        action = "reset"
    else:
        cursor = conn.execute(
            """
            INSERT INTO users (email, display_name, password_hash, role, is_active, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
            """,
            (email, display_name.strip(), password_hash, config.ADMIN_ROLE, now_iso()),
        )
        user_id = int(cursor.lastrowid)
        action = "create"

    conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM login_attempts WHERE email = ?", (email,))
    audit(
        conn,
        None,
        action,
        "bootstrap_admin",
        str(user_id),
        {"email": email, "sessions_cleared": True, "login_attempts_cleared": True},
    )


def setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    item = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return item["value"] if item else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO settings (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (key, value, now_iso()),
    )


def audit(conn: sqlite3.Connection, user: dict | None, action: str, entity_type: str, entity_id: str, details: dict | None = None, ip: str = "") -> None:
    conn.execute(
        """
        INSERT INTO audit_log (user_id, user_name, action, entity_type, entity_id, details, ip_address, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user.get("id") if user else None,
            (user.get("display_name") or user.get("email")) if user else "System",
            action,
            entity_type,
            str(entity_id),
            json.dumps(details or {}, ensure_ascii=False),
            ip,
            now_iso(),
        ),
    )


def create_backup(reason: str, created_by: str = "System") -> Path:
    ensure_directories()
    stamp = now_iso().replace(":", "").replace("-", "").split("+", 1)[0]
    safe_reason = "".join(ch for ch in reason.lower().replace(" ", "-") if ch.isalnum() or ch in "-_")[:40] or "backup"
    target = config.BACKUP_DIR / f"wartung-{stamp}-{safe_reason}.db"
    with connect() as source:
        with sqlite3.connect(target) as dest:
            source.backup(dest)
        source.execute(
            "INSERT INTO backup_log (file_name, reason, created_by, created_at) VALUES (?, ?, ?, ?)",
            (target.name, reason, created_by, now_iso()),
        )
    return target


def backup_path(file_name: str) -> Path:
    ensure_directories()
    safe_name = Path(file_name).name
    if safe_name != file_name or not safe_name.endswith(".db"):
        raise ValueError("Ungültiger Backup-Dateiname.")
    path = config.BACKUP_DIR / safe_name
    if not path.exists() or not path.is_file():
        raise ValueError("Backup wurde nicht gefunden.")
    return path


def backup_inventory(conn: sqlite3.Connection) -> list[dict]:
    ensure_directories()
    logged = rows(conn, "SELECT * FROM backup_log ORDER BY id DESC")
    by_name = {item["file_name"]: item for item in logged}
    inventory = []
    for path in sorted(config.BACKUP_DIR.glob("*.db"), key=lambda item: item.stat().st_mtime, reverse=True):
        item = dict(by_name.get(path.name, {}))
        item.setdefault("id", None)
        item.setdefault("file_name", path.name)
        item.setdefault("reason", "external")
        item.setdefault("created_by", "System")
        item.setdefault("created_at", "")
        item["size_bytes"] = path.stat().st_size
        inventory.append(item)
    return inventory


def restore_backup(file_name: str, restored_by: str) -> Path:
    source = backup_path(file_name)
    with sqlite3.connect(source) as probe:
        probe.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
    safety = create_backup("before-restore", restored_by)
    for suffix in ("", "-wal", "-shm"):
        path = Path(str(config.DB_PATH) + suffix)
        if path.exists():
            path.unlink()
    shutil.copy2(source, config.DB_PATH)
    with connect() as conn:
        conn.execute(
            "INSERT INTO backup_log (file_name, reason, created_by, created_at) VALUES (?, ?, ?, ?)",
            (source.name, "restore", restored_by, now_iso()),
        )
    return safety


def prune_backups(keep: int = 20) -> list[str]:
    ensure_directories()
    keep = max(1, min(keep, 200))
    files = sorted(config.BACKUP_DIR.glob("*.db"), key=lambda item: item.stat().st_mtime, reverse=True)
    removed = []
    for path in files[keep:]:
        path.unlink()
        removed.append(path.name)
    return removed


def ensure_daily_backup() -> None:
    today = now_iso()[:10]
    with connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM backup_log WHERE reason = 'daily' AND substr(created_at, 1, 10) = ?",
            (today,),
        ).fetchone()
    if not exists:
        create_backup("daily", "System")


def copy_tree_overview() -> list[str]:
    return [str(path.relative_to(config.ROOT_DIR)) for path in sorted(config.ROOT_DIR.rglob("*")) if path.is_file()]
