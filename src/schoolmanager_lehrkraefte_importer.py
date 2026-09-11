"""Lehrkräftestammdaten: Schoolmanager + vorhandene lokale Zusatzdaten."""

from __future__ import annotations

import json
from pathlib import Path

from models import Lehrkraft
from lehrkraefte_importer import LehrkraefteImporter


class SchoolmanagerLehrkraefteImporter:
    """
    Schoolmanager liefert die aktuellen Grunddaten:
        Kürzel, Vorname, Nachname

    Die bisherige Lehrkräftedatei ergänzt – sofern vorhanden:
        Anrede, E-Mail, Foto

    Schoolmanager hat Vorrang bei Kürzel, Vorname und Nachname.
    Lokale Zusatzdaten werden dadurch nicht überschrieben oder verändert.
    """

    def __init__(self, schoolmanager_daten_dir: Path, lokale_datei: Path | None = None):
        self.schoolmanager_daten_dir = Path(schoolmanager_daten_dir)
        self.lehrer_datei = self.schoolmanager_daten_dir / "lehrer_aktuell.json"
        self.lokale_datei = Path(lokale_datei) if lokale_datei else None

    def load(self) -> dict[str, Lehrkraft]:
        sm_lehrer = self._schoolmanager_laden()

        lokal = {}
        if self.lokale_datei is not None and self.lokale_datei.is_file():
            lokal = LehrkraefteImporter(self.lokale_datei).load()

        katalog: dict[str, Lehrkraft] = {}

        for eintrag in sm_lehrer:
            if not isinstance(eintrag, dict):
                continue

            kuerzel = str(eintrag.get("abbreviation") or "").strip()
            if not kuerzel:
                continue

            schluessel = kuerzel.casefold()
            alt = lokal.get(schluessel)

            katalog[schluessel] = Lehrkraft(
                kuerzel=kuerzel,
                anrede=alt.anrede if alt else "",
                vorname=str(eintrag.get("firstname") or "").strip()
                    or (alt.vorname if alt else ""),
                nachname=str(eintrag.get("lastname") or "").strip()
                    or (alt.nachname if alt else ""),
                email=alt.email if alt else "",
                foto=alt.foto if alt else f"{kuerzel}.jpg",
            )

        # Lokale Einträge behalten, falls sie derzeit nicht in der
        # Schoolmanager-Liste vorkommen (z.B. besondere Zusatzpersonen).
        for schluessel, lehrkraft in lokal.items():
            katalog.setdefault(schluessel, lehrkraft)

        return katalog

    def _schoolmanager_laden(self) -> list:
        if not self.lehrer_datei.is_file():
            raise FileNotFoundError(
                f"Schoolmanager-Lehrerliste nicht gefunden: {self.lehrer_datei}"
            )
        with self.lehrer_datei.open("r", encoding="utf-8") as f:
            daten = json.load(f)
        if not isinstance(daten, list):
            raise ValueError(f"Erwartete Lehrerliste in {self.lehrer_datei}")
        return daten
