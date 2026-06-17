# Wartung FDM Space

Professionelle Wartungsverwaltung für die FDM-Space-Druckerflotte:

- PRUSA MK3.5
- PRUSA MINI+
- PRUSA XL 5-Tool / 5-Nozzle

## App öffnen

Die Wartungs-App läuft **live auf Railway**:

**[wartungsseite-fdm-drucker-space-aalen-production.up.railway.app](https://wartungsseite-fdm-drucker-space-aalen-production.up.railway.app/)**

Login oder Registrierung mit Teamleiter-Code.

## Dokumentation

GitHub Pages Portal mit Features und Betriebsanleitung:

[Release Portal (GitHub Pages)](https://hudnur111.github.io/Wartungsseite-FDM-Drucker-Space-Aalen/)

## Wichtig zu GitHub Pages

GitHub Pages kann nur statische Dateien ausliefern. Die echte Wartungs-App aus dem Screenshot braucht Python, SQLite, Login-Sessions, CSRF-Schutz und Schreibzugriff. Deshalb läuft die komplette App nicht auf GitHub Pages, sondern auf Railway (oder lokal/auf einem Server).

Der Ordner `docs/` ist ein professionelles Release-Portal mit Erklärung und Betriebsanleitung.

## Start der echten App

### Lokal testen

```powershell
python .\run.py
```

Danach im Browser öffnen:

```text
http://127.0.0.1:8080
```

### Tests ausführen

```powershell
python -m unittest discover -s tests
```

Im lokalen Netzwerk kann die App über die IP des Rechners erreicht werden, zum Beispiel:

```text
http://192.168.188.24:8080
```

### Im Netzwerk/Cloud

Die App läuft jetzt auf Railway und ist öffentlich unter der URL oben erreichbar. Für andere Hosting-Optionen siehe Betrieb weiter unten.

## Ordnerstruktur

```text
app/
  config.py          Konfiguration
  database.py        Migration, Seed-Daten, Backups, Audit
  security.py        Passwort-Hashing, Rollen, Tokens
  server.py          HTTP-Routing und API
  static/            CSS und JavaScript der echten App
  templates/         HTML-Templates der echten App
data/
  wartung.db         Produktive SQLite-Datenbank
backups/
  *.db               Automatische und manuelle Backups
docs/
  index.html         Statische GitHub-Pages-Seite
  404.html           Fehlerseite für GitHub Pages
  assets/            CSS und JavaScript für GitHub Pages
scripts/
  start.ps1
  start-https.ps1
  install-scheduled-task.ps1
  install-windows-service-nssm.ps1
  create-self-signed-cert.ps1
run.py               Startpunkt
wartung_app.py       Kompatibler Startpunkt
```

## Sicherheit

- Login und Registrierung mit CSRF-Schutz
- Registrierung nur mit Teamleiter-Code (konfigurierbar)
- Passwörter werden per PBKDF2 gehasht und gespeichert
- Sessions laufen über HttpOnly-Cookies
- API-Schreibaktionen brauchen einen CSRF-Header
- Login-Fehlversuche werden begrenzt (15 Minuten Blockade nach 5 Fehlversuchen)
- Rollen: `Administrator`, `Mentor`, `Benutzer` mit unterschiedlichen Rechten
- Audit-Log für alle Änderungen (wer, wann, was)

### Teamleiter-Code

Ein Administrator kann den Code in der App im Admin-Bereich setzen.

Alternativ beim Start:

```powershell
$env:TEAMLEITER_CODE='DEIN-CODE-HIER'
python .\run.py
```

Oder eine Datei `teamleiter_code.txt` im Projektordner anlegen und dort nur den Code eintragen.

## Betrieb

### Cloud-Hosting (Railway)

Die App läuft auf Railway unter:

```text
https://wartungsseite-fdm-drucker-space-aalen-production.up.railway.app
```

Automatisches Deployment bei Push auf `main` (konfiguriert via `railway.toml`).

Für produktiven Betrieb sollte ein persistentes Volume verwendet werden. Die App unterstützt dafür diese Variablen:

```text
WARTUNG_DATA_DIR=/data
WARTUNG_BACKUP_DIR=/data/backups
WARTUNG_DB_PATH=/data/wartung.db
WARTUNG_TRUST_PROXY=1
WARTUNG_STATE_RECENT_LOG_LIMIT=1000
WARTUNG_STATE_RECENT_NOTE_LIMIT=500
```

Ohne persistentes Volume kann SQLite-Datenbestand bei Neuaufbau des Containers verloren gehen.

`WARTUNG_TRUST_PROXY=1` sollte nur gesetzt werden, wenn die App hinter einem vertrauenswürdigen Reverse Proxy läuft, zum Beispiel bei Railway. Für lokale oder direkt erreichbare Installationen bleibt die Einstellung ausgeschaltet, damit Login-Limits und Secure-Cookies nicht durch gefälschte Forwarded-Header beeinflusst werden.

Die State-Limits begrenzen nur die Oberfläche. Exporte und Backups arbeiten weiterhin mit dem vollständigen Datenbestand.

### Release-Checks

GitHub Actions enthält zwei aktive Workflows:

- `.github/workflows/tests.yml` kompiliert die Python-Module und führt die Test-Suite aus.
- `.github/workflows/pages.yml` validiert den Release ebenfalls und veröffentlicht anschließend das GitHub-Pages-Portal aus `docs/`.

### Health-Check

Für Monitoring, Railway oder einen Reverse Proxy liefert die App einen einfachen Health-Endpoint:

```text
GET /healthz
```

Antwort:

```json
{"ok": true, "service": "wartung-fdm-space"}
```

### Lokaler Betrieb auf Windows

Autostart mit Windows-Bordmitteln:

```powershell
.\scripts\install-scheduled-task.ps1
```

Windows-Service mit NSSM:

```powershell
.\scripts\install-windows-service-nssm.ps1
```

### HTTPS/SSL

HTTPS kann über `WARTUNG_SSL_CERT` und `WARTUNG_SSL_KEY` aktiviert werden. Für produktiven Einsatz ist ein internes CA-Zertifikat oder ein Reverse Proxy mit HTTPS empfohlen.

```powershell
$env:WARTUNG_SSL_CERT='/path/to/cert.pem'
$env:WARTUNG_SSL_KEY='/path/to/key.pem'
python .\run.py
```

Oder siehe Hilfsskript:

```powershell
.\scripts\start-https.ps1
```

## Daten nicht veröffentlichen

Die Datei `.gitignore` verhindert, dass folgende Dateien ins öffentliche Repository gelangen:

- Lokale Datenbanken (`*.db`, `*.db-shm`, `*.db-wal`)
- Server-Logs (`wartung_server.err.log`, `wartung_server.out.log`)
- Backups (`backups/`)
- Teamleiter-Code (`teamleiter_code.txt`)
- Python-Cache (`__pycache__/`)

Diese Dateien gehören nicht in ein öffentliches Repo und werden automatisch ignoriert.
