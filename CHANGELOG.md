# Version 1.4.3

- ASV-Wochenstunden mit deutschem Dezimalkomma werden unterstützt (`0,5`, `1,5`).
- Englische Dezimalpunkte und numerische Excel-Zellen bleiben kompatibel.
- Gewichtungen aus JSON akzeptieren ebenfalls Dezimalkommas.

# Changelog

## Version 1.3

- `lehrer.xlsx` als direkte Stammdatenquelle integriert
- `lehrkraefte.csv` entfernt
- Lehrkraftmodell um Anrede, Vorname, Nachname, E-Mail und Foto erweitert
- Feldnamen zwischen `MatrixImporter` und `Unterricht` vereinheitlicht
- beschädigte `main.py` wiederhergestellt
- `school.py` als Kompatibilitätsmodul ergänzt
- echte Lehrkräftenamen im Renderer aktiviert
- gruppierte Fachkarten mit mehreren Bildern unterstützt
- vollständiger Testlauf mit den gelieferten Daten erfolgreich

## Version 1.4.2

- Elternabendblatt auf exakt eine DIN-A4-Seite optimiert.
- Kompaktes 4×5-Kartenraster für bis zu 20 Fachkarten.
- Lehrerbilder, Abstände und Schriftgrößen druckgerecht verkleinert.
- Bewertungsangaben bleiben direkt in den jeweiligen Fachkarten.
- Überflüssiger zusätzlicher Bewertungsblock unter den Karten entfernt.
- Drucklayout auf A4-Hochformat mit festen Seitenmaßen begrenzt.
