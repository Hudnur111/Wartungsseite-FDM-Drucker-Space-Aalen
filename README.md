# Wartung FDM Space

Streamlit-App fuer die Wartungsverwaltung der FDM-Space-Druckerflotte:

- PRUSA MK3.5
- PRUSA MINI+
- PRUSA XL 5-Tool / 5-Nozzle

## Status

Die Streamlit-App laeuft aktuell bewusst im offenen Wartungsmodus:

- kein Login
- keine Registrierung
- kein Passwort-Reset
- interner Admin-Kontext fuer alle App-Funktionen

Das Auth-System wird spaeter neu ergaenzt.

## Streamlit Cloud

Beim Deploy auf Streamlit Community Cloud:

```text
Main file path: streamlit_app.py
Python version: 3.12
```

`run.py` ist als Kompatibilitaets-Einstieg ebenfalls auf Streamlit umgestellt. Falls Streamlit Cloud versehentlich noch `run.py` startet, laeuft trotzdem die Streamlit-App und nicht mehr der alte HTTP-Server.

Optionale Streamlit-Secrets:

```toml
WARTUNG_STATE_RECENT_LOG_LIMIT = "1000"
WARTUNG_STATE_RECENT_NOTE_LIMIT = "500"
```

## Lokal starten

```powershell
python -m pip install -r requirements.txt
streamlit run .\streamlit_app.py
```

Danach oeffnet Streamlit die App normalerweise automatisch. Manuell:

```text
http://localhost:8501
```

## Tests ausfuehren

```powershell
python -m unittest discover -s tests
```

## Ordnerstruktur

```text
streamlit_app.py        Streamlit-Einstiegspunkt
app/
  streamlit_services.py Streamlit-Service-Schicht
  config.py             Konfiguration
  database.py           Migration, Seed-Daten, Backups, Audit
  security.py           Legacy-Auth-Helfer fuer spaeter
  maintenance.py        Faelligkeiten und Teams-Payload
  reports.py            CSV/PDF-Export
  server.py             Legacy-HTTP-Server
data/
  wartung.db            Lokale SQLite-Datenbank
backups/
  *.db                  Backups
docs/                   Statisches GitHub-Pages-Portal
```

## Railway

Das Repo kann auch auf Railway als Streamlit-App laufen. `Procfile`, `railway.toml` und `start.sh` starten:

```text
streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port $PORT
```

Fuer persistente SQLite-Daten auf Railway ein Volume verwenden und diese Variablen setzen:

```text
WARTUNG_DATA_DIR=/data
WARTUNG_BACKUP_DIR=/data/backups
WARTUNG_DB_PATH=/data/wartung.db
WARTUNG_TRUST_PROXY=1
```

## Daten nicht veroeffentlichen

Nicht committen:

- lokale Datenbanken (`*.db`, `*.db-shm`, `*.db-wal`)
- Backups (`backups/`)
- `teamleiter_code.txt`
- `.streamlit/secrets.toml`
