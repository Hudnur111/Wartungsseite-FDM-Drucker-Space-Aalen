# Wartung FDM Space Portal

Diese Seite ist das statische Release-Portal und die Dokumentation für die Wartungs-App.

## App-URL

Die vollständige Wartungs-App läuft auf Railway:

[wartungsseite-fdm-drucker-space-aalen-production.up.railway.app](https://wartungsseite-fdm-drucker-space-aalen-production.up.railway.app/)

## Was diese Seite ist

- Öffentliche Projekt-Dokumentation
- Release-Informationen und Features
- Betriebsanleitung für lokales Setup

## Was diese Seite nicht ist

GitHub Pages ist eine statische Website. Die echte App braucht ein Python-Backend, eine SQLite-Datenbank, Login-Sessions und API-Endpunkte mit Schreibzugriff.

Diese Funktionen laufen auf einem Server wie Railway, Render oder einem lokalen Rechner im Netzwerk.

## Lokale Installation

```powershell
git clone https://github.com/Hudnur111/Wartungsseite-FDM-Drucker-Space-Aalen.git
cd Wartungsseite-FDM-Drucker-Space-Aalen
python run.py
```

Danach im Browser öffnen: `http://127.0.0.1:8080`

## GitHub Pages

Das Portal wird aus dem Ordner `docs/` veröffentlicht:

`https://hudnur111.github.io/Wartungsseite-FDM-Drucker-Space-Aalen/`
