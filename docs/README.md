# GitHub Pages — Wartung FDM Space Portal

Diese Seite ist das **Release Portal und die Dokumentation** für die Wartungs-App.

## App-URL

Die vollständige Wartungs-App läuft auf Railway:

👉 **[wartungsseite-fdm-drucker-space-aalen-production.up.railway.app](https://wartungsseite-fdm-drucker-space-aalen-production.up.railway.app/)**

## Was diese Seite ist

- Öffentliche Projekt-Dokumentation
- Release-Informationen und Features
- Betriebsanleitung für lokales Setup

## Was diese Seite NICHT ist

GitHub Pages ist eine **statische Website**. Die echte App braucht:

- Python-Backend
- SQLite-Datenbank
- Login & Sessions
- API-Endpunkte mit Schreibzugriff

Diese Funktionen können nur auf einem echter Server laufen (wie Railway, Render, etc.).

## Lokale Installation

Wenn du die App selbst hosten oder entwickeln möchtest:

```powershell
# Repository clonen
git clone https://github.com/your-org/wartung-fdm-space.git
cd wartung-fdm-space

# App starten
python run.py
```

Dann öffne im Browser: `http://127.0.0.1:8080`

## GitHub Pages Einstellungen

Falls du dieses Portal selbst hosten möchtest:

1. In GitHub: `Settings` → `Pages`
2. `Source`: `Deploy from a branch`
3. `Branch`: `main`
4. `Folder`: `/docs`
5. Speichern

Dann wird diese Seite automatisch unter `https://username.github.io/repository` veröffentlicht.

