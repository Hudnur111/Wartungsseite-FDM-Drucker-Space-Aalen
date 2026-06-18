# Wartung FDM Space

Streamlit-App für die Wartungsverwaltung der FDM-Space-Druckerflotte:

- PRUSA MK3.5
- PRUSA MINI+
- PRUSA XL 5-Tool / 5-Nozzle

## Streamlit Cloud

Beim Deploy auf Streamlit Community Cloud:

```text
Main file path: streamlit_app.py
Python version: 3.12
```

`run.py` ist als Kompatibilitäts-Einstieg ebenfalls auf Streamlit umgestellt. Falls Streamlit Cloud versehentlich noch `run.py` startet, läuft trotzdem die Streamlit-App und nicht mehr der alte HTTP-Server.

Die App liest Streamlit-Secrets im TOML-Format und übernimmt Root-Level-Secrets als Umgebungsvariablen. Für den ersten Admin und die Registrierung kannst du z. B. eintragen:

```toml
TEAMLEITER_CODE = "DEIN-TEAMLEITER-CODE"

WARTUNG_BOOTSTRAP_ADMIN_EMAIL = "admin@example.org"
WARTUNG_BOOTSTRAP_ADMIN_NAME = "Admin"
WARTUNG_BOOTSTRAP_ADMIN_PASSWORD = "NEUES-SICHERES-PASSWORT"

WARTUNG_STATE_RECENT_LOG_LIMIT = "1000"
WARTUNG_STATE_RECENT_NOTE_LIMIT = "500"
```

Nach dem ersten erfolgreichen Login die drei `WARTUNG_BOOTSTRAP_ADMIN_*` Secrets wieder entfernen, sonst wird das Admin-Passwort bei jedem Start erneut auf diesen Wert gesetzt.

Wenn noch kein aktiver Administrator existiert, ist kein Teamleiter-Code nötig: Das nächste registrierte Konto wird automatisch `Administrator`. Danach ist Registrierung wieder über den Teamleiter-Code geschützt.

Für Passwort-Reset per E-Mail zusätzlich SMTP-Secrets setzen:

```toml
WARTUNG_PUBLIC_URL = "https://deine-app.streamlit.app"
WARTUNG_SMTP_HOST = "smtp.example.org"
WARTUNG_SMTP_PORT = "587"
WARTUNG_SMTP_USER = "mailer@example.org"
WARTUNG_SMTP_PASSWORD = "DEIN-SMTP-PASSWORT"
WARTUNG_SMTP_FROM = "mailer@example.org"
WARTUNG_SMTP_STARTTLS = "1"
WARTUNG_PASSWORD_RESET_MINUTES = "30"
```

## Lokal starten

```powershell
python -m pip install -r requirements.txt
streamlit run .\streamlit_app.py
```

Danach öffnet Streamlit die App normalerweise automatisch. Manuell:

```text
http://localhost:8501
```

## Tests ausführen

```powershell
python -m unittest discover -s tests
```

## Ordnerstruktur

```text
streamlit_app.py       Streamlit-Einstiegspunkt
app/
  streamlit_services.py Streamlit-Service-Schicht
  config.py             Konfiguration
  database.py           Migration, Seed-Daten, Backups, Audit
  security.py           Passwort-Hashing, Rollen, Tokens
  maintenance.py        Fälligkeiten und Teams-Payload
  reports.py            CSV/PDF-Export
  server.py             Legacy-HTTP-Server
data/
  wartung.db            Lokale SQLite-Datenbank
backups/
  *.db                  Backups
docs/                   Statisches GitHub-Pages-Portal
```

## Rollen

- `Administrator`: Benutzer, Teamleiter-Code, Drucker, Wartungspunkte, Backups und Einstellungen
- `Mentor`: Wartungen, Vermerke, Druckstunden und XL-Toolheads
- `Benutzer`: Basis-Wartungen und Vermerke

## Login reparieren

Lokal:

```powershell
.\scripts\reset-admin-password.ps1 -Email "admin@example.org" -Name "Admin"
```

Streamlit Cloud: die `WARTUNG_BOOTSTRAP_ADMIN_*` Secrets setzen, App neu starten, anmelden, danach diese drei Secrets wieder entfernen.

## Railway

Das Repo kann auch auf Railway als Streamlit-App laufen. `Procfile`, `railway.toml` und `start.sh` starten jetzt:

```text
streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port $PORT
```

Für persistente SQLite-Daten auf Railway ein Volume verwenden und diese Variablen setzen:

```text
WARTUNG_DATA_DIR=/data
WARTUNG_BACKUP_DIR=/data/backups
WARTUNG_DB_PATH=/data/wartung.db
WARTUNG_TRUST_PROXY=1
```

## Daten nicht veröffentlichen

Nicht committen:

- lokale Datenbanken (`*.db`, `*.db-shm`, `*.db-wal`)
- Backups (`backups/`)
- `teamleiter_code.txt`
- `.streamlit/secrets.toml`
