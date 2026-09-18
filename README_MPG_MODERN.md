# SchoolPublisher 2.0 – MPG Modern

## Installation als Update

Diese Dateien in das vorhandene Projekt kopieren und vorhandene Dateien ersetzen:

- `src/main.py`
- `src/renderer.py`
- `templates/elternabend.html`
- `images/MPGNürtingen.png`

Danach `START_SchoolPublisher.bat` starten.

## Ausgabe

Je Klasse entstehen im Ordner `output`:

- `Elternabend_<Klasse>.html`
- `Elternabend_<Klasse>.pdf` (wenn Edge oder Chrome gefunden wurde)

## Automatische Raster

- bis 16 Fachkarten: 4 × 4
- bis 20 Fachkarten: 4 × 5
- bis 24 Fachkarten: 4 × 6
- ab 25 Fachkarten: 5 × 6

Leere Bewertungseinträge werden nicht erfunden. Solange für ein Fach keine Bewertung hinterlegt ist, zeigt die Karte „Informationen folgen“.
