"""
Import der ASV-Unterrichtsmatrix.
"""

from pathlib import Path

import pandas as pd

from models import Unterricht


class MatrixImporter:
    def __init__(self, filename: Path):
        self.filename = filename

    def load(self) -> list[Unterricht]:
        """
        Liest die ASV-Matrix ein und erzeugt Unterricht-Objekte.
        """

        df = pd.read_excel(self.filename)

        # Spaltennamen von überflüssigen Leerzeichen befreien
        df.columns = [str(spalte).strip() for spalte in df.columns]

        # Nur unbenannte ASV-Spalten entfernen.
        # Benannte, aber leere Spalten bleiben erhalten.
        df = df.loc[
            :,
            ~df.columns.str.startswith("Unnamed:")
        ]

        unterrichtsliste: list[Unterricht] = []

        for _, row in df.iterrows():
            kopplung = self._text_oder_none(row.get("Kopplung"))
            stundenplan_name = self._text_oder_leer(
                row.get("Bezeichnung im Stundenplan")
            )

            eintrag = Unterricht(
                klasse=self._text_oder_leer(row.get("Klasse")),
                fach=self._text_oder_leer(row.get("Fach")),
                lehrer=self._text_oder_leer(row.get("Lehrer")),
                fachname=self._text_oder_leer(row.get("Fachname")),
                stundenplan_name=stundenplan_name,
                wochenstunden=float(row.get("Wochenstunden", 0)),
                kopplung=kopplung,
            )

            unterrichtsliste.append(eintrag)

        return unterrichtsliste

    @staticmethod
    def _text_oder_leer(wert) -> str:
        """Wandelt einen Excel-Wert in Text um; leere Zellen werden zu ''."""
        if pd.isna(wert):
            return ""

        return str(wert).strip()

    @staticmethod
    def _text_oder_none(wert) -> str | None:
        """Wandelt einen Excel-Wert in Text um; leere Zellen werden zu None."""
        if pd.isna(wert):
            return None

        return str(wert).strip()