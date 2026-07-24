"""
Importiert Lehrkräftestammdaten aus lehrer.xlsx.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from models import Lehrkraft


class LehrkraefteImporter:
    """
    Liest die vorhandene Excel-Stammdatendatei ein.

    Liest Kürzel, Vorname, Nachname, Anrede, E-Mail und Foto
    unverändert aus der Lehrkräftedatei ein.
    """

    BENOETIGTE_SPALTEN = {
        "Kürzel",
        "Nachname",
        "Vorname",
        "Anrede",
        "E-Mail",
        "Foto",
    }

    def __init__(
        self,
        dateipfad: Path,
    ) -> None:
        self.dateipfad = dateipfad

    def load(self) -> dict[str, Lehrkraft]:
        if not self.dateipfad.is_file():
            raise FileNotFoundError(
                f"Lehrkräftedatei nicht gefunden: {self.dateipfad}"
            )

        tabelle = pd.read_excel(
            self.dateipfad,
            dtype=str,
        )

        tabelle.columns = [
            str(spalte).strip()
            for spalte in tabelle.columns
        ]

        fehlende_spalten = (
            self.BENOETIGTE_SPALTEN
            - set(tabelle.columns)
        )

        if fehlende_spalten:
            liste = ", ".join(
                sorted(fehlende_spalten)
            )

            raise ValueError(
                "In lehrer.xlsx fehlen folgende Spalten: "
                f"{liste}"
            )

        lehrkraefte: dict[str, Lehrkraft] = {}

        for zeilennummer, zeile in tabelle.iterrows():
            excel_zeile = zeilennummer + 2

            kuerzel = self._text(
                zeile["Kürzel"]
            )

            if not kuerzel:
                continue

            if kuerzel.casefold() in {
                schluessel.casefold()
                for schluessel in lehrkraefte
            }:
                raise ValueError(
                    f"Das Kürzel {kuerzel!r} kommt mehrfach vor "
                    f"(zuletzt in Excel-Zeile {excel_zeile})."
                )

            vorname = self._text(
                zeile["Vorname"]
            )
            nachname = self._text(
                zeile["Nachname"]
            )

            lehrkraft = Lehrkraft(
                kuerzel=kuerzel,
                anrede=self._text(zeile["Anrede"]),
                vorname=vorname,
                nachname=nachname,
                email=self._text(zeile["E-Mail"]),
                foto=self._text(zeile["Foto"]),
            )

            lehrkraefte[kuerzel] = lehrkraft

        if not lehrkraefte:
            raise ValueError(
                "In lehrer.xlsx wurden keine Lehrkräfte gefunden."
            )

        return lehrkraefte

    @staticmethod
    def _text(wert: object) -> str:
        if pd.isna(wert):
            return ""

        return " ".join(
            str(wert).strip().split()
        )
