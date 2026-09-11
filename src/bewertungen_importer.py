"""Importiert Bewertungsregeln aus data/bewertungen.xlsx."""
from __future__ import annotations

from pathlib import Path
import pandas as pd

from models import Bewertungskatalog, Bewertungsinfo, Leistungserhebung


class BewertungenImporter:
    """Liest Standardregeln und klassenbezogene Ausnahmen aus Excel."""

    TABELLENBLATT = "Bewertungsregeln"
    BENOETIGTE_SPALTEN = {
        "Klassenstufe",
        "Klasse",
        "Fach",
        "Mündlich",
        "Schriftlich",
        "Praktisch",
        "Klassenarbeiten",
        "Tests",
        "Projekte",
        "Praktische Arbeiten",
        "Sonstige",
        "Zusatzinformation",
    }

    def __init__(self, dateipfad: Path) -> None:
        self.dateipfad = dateipfad

    def load(self) -> Bewertungskatalog:
        if not self.dateipfad.is_file():
            raise FileNotFoundError(
                f"Bewertungsdatei nicht gefunden: {self.dateipfad}"
            )

        tabelle = pd.read_excel(
            self.dateipfad,
            sheet_name=self.TABELLENBLATT,
            dtype=object,
        )
        tabelle.columns = [str(spalte).strip() for spalte in tabelle.columns]

        fehlende_spalten = self.BENOETIGTE_SPALTEN - set(tabelle.columns)
        if fehlende_spalten:
            raise ValueError(
                "In bewertungen.xlsx fehlen folgende Spalten: "
                + ", ".join(sorted(fehlende_spalten))
            )

        regeln: dict[tuple[int, str, str], Bewertungsinfo] = {}

        for zeilennummer, zeile in tabelle.iterrows():
            excel_zeile = zeilennummer + 2
            stufe = self._stufe(zeile["Klassenstufe"], excel_zeile)
            klasse = self._text(zeile["Klasse"]).casefold()
            fach = self._text(zeile["Fach"])

            if not fach and not klasse and stufe is None:
                continue
            if stufe is None or not klasse or not fach:
                raise ValueError(
                    f"Unvollständige Bewertungsregel in Excel-Zeile {excel_zeile}."
                )

            muendlich = self._positive_zahl(
                zeile["Mündlich"], "Mündlich", excel_zeile, pflicht=False
            )
            schriftlich = self._positive_zahl(
                zeile["Schriftlich"], "Schriftlich", excel_zeile, pflicht=False
            )

            # Während der gemeinsamen Eingabephase dürfen Zeilen noch
            # unvollständig sein. Erst vollständig gewichtete Regeln werden
            # für die Ausgabe übernommen.
            if muendlich is None or schriftlich is None:
                continue
            praktisch = self._positive_zahl(
                zeile["Praktisch"], "Praktisch", excel_zeile, pflicht=False
            )

            erhebungen = tuple(
                Leistungserhebung(bezeichnung=bezeichnung, anzahl=anzahl)
                for bezeichnung, anzahl in (
                    ("Klassenarbeiten", self._anzahl(zeile["Klassenarbeiten"], "Klassenarbeiten", excel_zeile)),
                    ("Tests", self._anzahl(zeile["Tests"], "Tests", excel_zeile)),
                    ("Projekte", self._anzahl(zeile["Projekte"], "Projekte", excel_zeile)),
                    ("Praktische Arbeiten", self._anzahl(zeile["Praktische Arbeiten"], "Praktische Arbeiten", excel_zeile)),
                    ("Sonstige", self._anzahl(zeile["Sonstige"], "Sonstige", excel_zeile)),
                )
                if anzahl > 0
            )

            schluessel = (stufe, klasse, fach.casefold())
            if schluessel in regeln:
                raise ValueError(
                    "Doppelte Bewertungsregel in Excel-Zeile "
                    f"{excel_zeile}: Stufe {stufe}, Klasse {klasse}, Fach {fach}."
                )

            regeln[schluessel] = Bewertungsinfo(
                gewicht_muendlich=muendlich,
                gewicht_schriftlich=schriftlich,
                gewicht_praktisch=praktisch,
                erhebungen=erhebungen,
                zusatzinformation=self._text(zeile["Zusatzinformation"]),
            )

        # Eine noch nicht ausgefüllte Tabelle ist während der Eingabephase
        # erlaubt. In diesem Fall zeigt der Renderer „Informationen folgen“.
        return Bewertungskatalog(regeln=regeln)

    @staticmethod
    def _text(wert: object) -> str:
        if pd.isna(wert):
            return ""
        return " ".join(str(wert).strip().split())

    @staticmethod
    def _stufe(wert: object, excel_zeile: int) -> int | None:
        if pd.isna(wert) or str(wert).strip() == "":
            return None
        try:
            stufe = int(float(str(wert).strip().replace(",", ".")))
        except ValueError as exc:
            raise ValueError(
                f"Ungültige Klassenstufe in Excel-Zeile {excel_zeile}: {wert!r}"
            ) from exc
        if stufe <= 0:
            raise ValueError(
                f"Ungültige Klassenstufe in Excel-Zeile {excel_zeile}: {wert!r}"
            )
        return stufe

    @staticmethod
    def _positive_zahl(
        wert: object,
        spalte: str,
        excel_zeile: int,
        pflicht: bool,
    ) -> float | None:
        if pd.isna(wert) or str(wert).strip() == "":
            if pflicht:
                raise ValueError(
                    f"In Excel-Zeile {excel_zeile} fehlt das Gewicht {spalte}."
                )
            return None
        try:
            zahl = float(str(wert).strip().replace(",", "."))
        except ValueError as exc:
            raise ValueError(
                f"Ungültiges Gewicht {spalte} in Excel-Zeile {excel_zeile}: {wert!r}"
            ) from exc
        if zahl < 0:
            raise ValueError(
                f"Das Gewicht {spalte} darf in Excel-Zeile {excel_zeile} nicht negativ sein."
            )
        return zahl

    @staticmethod
    def _anzahl(wert: object, spalte: str, excel_zeile: int) -> int:
        if pd.isna(wert) or str(wert).strip() == "":
            return 0
        try:
            zahl = float(str(wert).strip().replace(",", "."))
        except ValueError as exc:
            raise ValueError(
                f"Ungültige Anzahl {spalte} in Excel-Zeile {excel_zeile}: {wert!r}"
            ) from exc
        if zahl < 0 or not zahl.is_integer():
            raise ValueError(
                f"{spalte} muss in Excel-Zeile {excel_zeile} eine ganze Zahl ab 0 sein."
            )
        return int(zahl)
