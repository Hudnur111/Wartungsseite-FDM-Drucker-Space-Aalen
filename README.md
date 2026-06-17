# Wartung FDM Space

Professionelle Wartungsverwaltung fuer die FDM-Space-Druckerflotte:

- PRUSA MK3.5
- PRUSA MINI+
- PRUSA XL 5-Tool / 5-Nozzle


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
  404.html           Fehlerseite fuer GitHub Pages
  assets/            CSS und JavaScript fuer GitHub Pages
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
- Registrierung nur mit Teamleiter-Code
- Passwoerter werden per PBKDF2 gehasht gespeichert
- Sessions laufen ueber HttpOnly-Cookies
- API-Schreibaktionen brauchen einen CSRF-Header
- Login-Fehlversuche werden begrenzt
- Rollen: `Administrator`, `Mentor`, `Benutzer`


## Daten nicht veroeffentlichen

Die Datei `.gitignore` verhindert, dass lokale Datenbanken, Backups, Logs, `teamleiter_code.txt` und der PDF-Scan veroeffentlicht werden. Diese Dateien gehoeren nicht in ein oeffentliches Repository.
