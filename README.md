# Wartung FDM Space

Python-Web-App fuer die Wartungsverwaltung der FDM-Space-Druckerflotte:

- PRUSA MK3.5
- PRUSA MINI+
- PRUSA XL 5-Tool / 5-Nozzle

## Status

Die App laeuft aktuell bewusst als offene interne Python-App:

- reine Python-Web-App ohne UI-Framework-Zwang
- kein Login
- keine Registrierung
- kein Passwort-Reset
- interner Admin-Kontext fuer Wartung, Export, Backups und Einstellungen

Ein externes Auth-/Provider-System kann spaeter davor gesetzt werden.

## Lokal starten

```powershell
python -m pip install -r requirements.txt
python .\run.py
```

Danach im Browser oeffnen:

```text
http://127.0.0.1:8080
```

Optional:

```powershell
$env:WARTUNG_HOST="127.0.0.1"
$env:WARTUNG_PORT="8080"
python .\run.py
```

## Deployment

Der Einstiegspunkt ist:

```text
python run.py
```

`Procfile`, `railway.toml` und `start.sh` sind darauf vorbereitet. Die App liest `PORT`, falls der Anbieter einen Port vorgibt.

Fuer persistente SQLite-Daten ein Volume verwenden und diese Variablen setzen:

```text
WARTUNG_DATA_DIR=/data
WARTUNG_BACKUP_DIR=/data/backups
WARTUNG_DB_PATH=/data/wartung.db
WARTUNG_TRUST_PROXY=1
```

## Tests ausfuehren

```powershell
python -m unittest discover -s tests
```

## Ordnerstruktur

```text
run.py                 Python-Einstiegspunkt
wartung_app.py         Kompatibilitaets-Einstiegspunkt
app/
  server.py            HTTP-Server und API
  templates/app.html   App-Shell
  static/styles.css    Design
  static/app.js        Frontend-Logik
  config.py            Konfiguration
  database.py          Migration, Seed-Daten, Backups, Audit
  maintenance.py       Faelligkeiten und Teams-Payload
  reports.py           CSV/PDF-Export
data/
  wartung.db           Lokale SQLite-Datenbank
backups/
  *.db                 Backups
docs/                  Statisches GitHub-Pages-Portal
```

## Daten nicht veroeffentlichen

Nicht committen:

- lokale Datenbanken (`*.db`, `*.db-shm`, `*.db-wal`)
- Backups (`backups/`)
- `teamleiter_code.txt`
