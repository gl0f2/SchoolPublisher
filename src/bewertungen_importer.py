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

        # Zuerst werden die vollständigen Standardregeln ("alle") eingelesen.
        # Danach werden klassenspezifische Zeilen darauf angewendet.
        # Leere Zellen in einer Klassenzeile bedeuten: Wert aus "alle" übernehmen.
        standardregeln: dict[tuple[int, str], Bewertungsinfo] = {}
        klassenzeilen: list[tuple[int, str, str, object, int]] = []

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

            if klasse != "alle" and len(klasse) == 1 and klasse.isalpha():
                klasse = f"{stufe}{klasse}"

            if klasse == "alle":
                info = self._info_aus_zeile(
                    zeile=zeile,
                    excel_zeile=excel_zeile,
                    basis=None,
                    erlaube_vererbung=False,
                )
                # Noch nicht ausgefüllte Standardzeilen bleiben während
                # der Eingabephase erlaubt.
                if info is not None:
                    schluessel = (stufe, fach.casefold())
                    if schluessel in standardregeln:
                        raise ValueError(
                            "Doppelte Bewertungsregel in Excel-Zeile "
                            f"{excel_zeile}: Stufe {stufe}, Klasse alle, Fach {fach}."
                        )
                    standardregeln[schluessel] = info
            else:
                klassenzeilen.append((stufe, klasse, fach, zeile, excel_zeile))

        regeln: dict[tuple[int, str, str], Bewertungsinfo] = {
            (stufe, "alle", fach): info
            for (stufe, fach), info in standardregeln.items()
        }

        for stufe, klasse, fach, zeile, excel_zeile in klassenzeilen:
            fach_key = fach.casefold()
            basis = standardregeln.get((stufe, fach_key))

            info = self._info_aus_zeile(
                zeile=zeile,
                excel_zeile=excel_zeile,
                basis=basis,
                erlaube_vererbung=True,
            )
            if info is None:
                continue

            schluessel = (stufe, klasse, fach_key)
            if schluessel in regeln:
                raise ValueError(
                    "Doppelte Bewertungsregel in Excel-Zeile "
                    f"{excel_zeile}: Stufe {stufe}, Klasse {klasse}, Fach {fach}."
                )
            regeln[schluessel] = info

        return Bewertungskatalog(regeln=regeln)

    def _info_aus_zeile(
        self,
        zeile,
        excel_zeile: int,
        basis: Bewertungsinfo | None,
        erlaube_vererbung: bool,
    ) -> Bewertungsinfo | None:
        def zahl_oder_basis(spalte: str, basiswert: float | None) -> float | None:
            wert = zeile[spalte]
            if pd.isna(wert) or str(wert).strip() == "":
                return basiswert if erlaube_vererbung else None
            return self._positive_zahl(
                wert, spalte, excel_zeile, pflicht=False
            )

        muendlich = zahl_oder_basis(
            "Mündlich",
            basis.gewicht_muendlich if basis else None,
        )
        schriftlich = zahl_oder_basis(
            "Schriftlich",
            basis.gewicht_schriftlich if basis else None,
        )
        praktisch = zahl_oder_basis(
            "Praktisch",
            basis.gewicht_praktisch if basis else None,
        )

        if muendlich is None or schriftlich is None:
            return None

        basis_erhebungen = {
            e.bezeichnung: e.anzahl
            for e in (basis.erhebungen if basis else ())
        }

        erhebungen = []
        for bezeichnung in (
            "Klassenarbeiten",
            "Tests",
            "Projekte",
            "Praktische Arbeiten",
            "Sonstige",
        ):
            wert = zeile[bezeichnung]
            if pd.isna(wert) or str(wert).strip() == "":
                anzahl = (
                    basis_erhebungen.get(bezeichnung, 0)
                    if erlaube_vererbung
                    else 0
                )
            else:
                anzahl = self._anzahl(
                    wert, bezeichnung, excel_zeile
                )
            if anzahl > 0:
                erhebungen.append(
                    Leistungserhebung(
                        bezeichnung=bezeichnung,
                        anzahl=anzahl,
                    )
                )

        zusatz = self._text(zeile["Zusatzinformation"])
        if not zusatz and erlaube_vererbung and basis is not None:
            zusatz = basis.zusatzinformation

        return Bewertungsinfo(
            gewicht_muendlich=muendlich,
            gewicht_schriftlich=schriftlich,
            gewicht_praktisch=praktisch,
            erhebungen=tuple(erhebungen),
            zusatzinformation=zusatz,
        )

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
