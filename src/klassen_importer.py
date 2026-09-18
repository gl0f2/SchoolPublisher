"""Importiert Klassenstammdaten aus klassen.xlsx."""

from __future__ import annotations

from pathlib import Path
import re
import pandas as pd

from models import Klasse


class KlassenImporter:
    """Liest Klasse und Klassenleitung aus einer Excel-Datei ein."""

    BENOETIGTE_SPALTEN = {"Klasse", "Klassenlehrer"}

    def __init__(self, dateipfad: Path) -> None:
        self.dateipfad = dateipfad

    def load(self) -> dict[str, Klasse]:
        if not self.dateipfad.is_file():
            raise FileNotFoundError(
                f"Klassendatei nicht gefunden: {self.dateipfad}"
            )

        tabelle = pd.read_excel(self.dateipfad, dtype=str)
        tabelle.columns = [str(spalte).strip() for spalte in tabelle.columns]

        fehlende_spalten = self.BENOETIGTE_SPALTEN - set(tabelle.columns)
        if fehlende_spalten:
            liste = ", ".join(sorted(fehlende_spalten))
            raise ValueError(
                "In klassen.xlsx fehlen folgende Spalten: " + liste
            )

        klassen: dict[str, Klasse] = {}

        for zeilennummer, zeile in tabelle.iterrows():
            klassenname = self._text(zeile.get("Klasse"))
            if not klassenname:
                continue

            schluessel = klassenname.casefold()
            if schluessel in klassen:
                raise ValueError(
                    f"Die Klasse {klassenname!r} kommt mehrfach vor "
                    f"(zuletzt in Excel-Zeile {zeilennummer + 2})."
                )

            kuerzel = self._kuerzel_liste(zeile.get("Klassenlehrer"))

            # Eine eventuell vorhandene Stellvertretung wird ebenfalls als
            # Klassenleitung berücksichtigt. Die Spalte darf fehlen.
            kuerzel += self._kuerzel_liste(zeile.get("Stellvertretung"))
            kuerzel = tuple({k.casefold(): k for k in kuerzel}.values())

            klassen[klassenname] = Klasse(
                name=klassenname,
                klassenlehrer=kuerzel,
            )

        if not klassen:
            raise ValueError("In klassen.xlsx wurden keine Klassen gefunden.")

        return klassen

    @classmethod
    def _kuerzel_liste(cls, wert: object) -> tuple[str, ...]:
        text = cls._text(wert)
        if not text:
            return ()

        teile = re.split(r"[,;/]+", text)
        return tuple(teil.strip() for teil in teile if teil.strip())

    @staticmethod
    def _text(wert: object) -> str:
        if pd.isna(wert):
            return ""
        return " ".join(str(wert).strip().split())
