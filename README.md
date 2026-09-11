# SchoolPublisher 1.3

SchoolPublisher liest die Unterrichtsmatrix und die Lehrkräftestammdaten direkt aus Excel ein und erzeugt Klassenübersichten sowie ein Elternabendblatt.

## Voraussetzungen

- Python 3.10 oder neuer
- pandas
- openpyxl

Installation im PyCharm-Terminal:

```bash
pip install pandas openpyxl
```

## Daten

- `data/Matrix_Test.xlsx`
- `data/lehrer.xlsx`
- Lehrerfotos im Ordner `images/`

Eine `lehrkraefte.csv` wird nicht mehr benötigt.

## Start

In PyCharm `src/main.py` ausführen.

## Ausgabe

Die Dateien werden in `output/` erzeugt:

- `Klassenuebersicht_10a.txt`
- `Klassenuebersicht_10a.html`
- `Elternabend_10a.html`

## Besonderheit der Lehrkräftedatei

In der vorhandenen `lehrer.xlsx` stehen die Vornamen unter `Nachname` und die Nachnamen unter `Vorname`. Der Importer korrigiert dies beim Einlesen automatisch.
