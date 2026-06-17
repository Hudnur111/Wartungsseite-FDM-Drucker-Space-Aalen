# Wartung FDM Space Portal

Der Ordner `docs/` enthält das statische GitHub-Pages-Portal für die Wartungs-App.

## Zweck

- öffentliche Projekt- und Release-Informationen
- kurze Funktionsübersicht
- Betriebs- und Installationshinweise
- Link zur produktiven App auf Railway

## Abgrenzung

GitHub Pages kann nur statische Dateien ausliefern. Die eigentliche Wartungs-App benötigt ein Python-Backend, eine SQLite-Datenbank, Login-Sessions und API-Endpunkte mit Schreibzugriff. Diese Funktionen laufen auf Railway, lokal oder auf einem eigenen Server.

## App-URL

Die vollständige Wartungs-App läuft auf Railway:

[wartungsseite-fdm-drucker-space-aalen-production.up.railway.app](https://wartungsseite-fdm-drucker-space-aalen-production.up.railway.app/)

## Lokaler Start

```powershell
git clone https://github.com/Hudnur111/Wartungsseite-FDM-Drucker-Space-Aalen.git
cd Wartungsseite-FDM-Drucker-Space-Aalen
python run.py
```

Danach im Browser öffnen:

```text
http://127.0.0.1:8080
```

## Veröffentlichung

Das Portal wird über den aktiven Workflow `.github/workflows/pages.yml` aus `docs/` veröffentlicht. Vor dem Deploy kompiliert der Workflow die Python-Module und führt die Tests aus. Der separate Workflow `.github/workflows/tests.yml` prüft dieselben App-Checks bei Pushes und Pull Requests.

```text
https://hudnur111.github.io/Wartungsseite-FDM-Drucker-Space-Aalen/
```

## Release-Dateien

- `.nojekyll` deaktiviert die Jekyll-Verarbeitung auf GitHub Pages.
- `site.webmanifest` beschreibt das Portal für Browser und Installationsdialoge.
- `robots.txt` und `sitemap.xml` geben Suchmaschinen eine saubere, eindeutige Struktur.
- `assets/favicon.svg` und `assets/social-card.svg` verbessern Browser-Tab, Lesezeichen und Link-Vorschauen.
- Die Startseite zeigt Workflow-Badges, den Health-Check der Live-App und eine Sitemap-Verlinkung.
