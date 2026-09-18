"""Klassenstammdaten aus Schoolmanager plus manuelle Stellvertretungen."""

from __future__ import annotations

import json
from pathlib import Path

from models import Klasse


class SchoolmanagerKlassenImporter:
    """
    Erzeugt den Klassenkatalog aus den aktuellen Schoolmanager-Daten.

    Klassenlehrerteam:
      1. Hauptklassenlehrer: automatisch über mainClassTeacherId
      2. Stellvertretung:    optional aus stellvertretende_klassenlehrer.json

    Die manuelle Datei wird nie automatisch überschrieben.
    """

    def __init__(
        self,
        datenverzeichnis: Path,
        stellvertreter_datei: Path | None = None,
    ):
        self.datenverzeichnis = Path(datenverzeichnis)
        self.klassen_datei = self.datenverzeichnis / "klassen_aktuell.json"
        self.lehrer_datei = self.datenverzeichnis / "lehrer_aktuell.json"
        self.stundenplanverzeichnis = self.datenverzeichnis / "stundenplaene_ab"
        self.stellvertreter_datei = (
            Path(stellvertreter_datei)
            if stellvertreter_datei is not None
            else self.datenverzeichnis / "stellvertretende_klassenlehrer.json"
        )

    def load(self) -> dict[str, Klasse]:
        klassen = self._json_laden(self.klassen_datei)
        lehrer = self._json_laden(self.lehrer_datei)
        stellvertreter = self._stellvertreter_laden()

        lehrer_nach_id = {
            str(l.get("id")): str(l.get("abbreviation") or "").strip()
            for l in lehrer
            if isinstance(l, dict) and l.get("id") is not None
        }

        # Nur Klassen, die tatsächlich Unterrichtsdaten in A/B besitzen.
        aktive_klassen = {
            p.name
            for p in self.stundenplanverzeichnis.iterdir()
            if p.is_dir()
            and ((p / "woche_A.json").is_file() or (p / "woche_B.json").is_file())
            and self._hat_unterricht(p)
        } if self.stundenplanverzeichnis.is_dir() else set()

        katalog: dict[str, Klasse] = {}

        for k in klassen:
            if not isinstance(k, dict):
                continue

            name = str(k.get("name") or "").strip()
            if not name or name not in aktive_klassen or not self._ist_schulklasse(name):
                continue

            team = []

            haupt_id = k.get("mainClassTeacherId")
            if haupt_id is not None:
                kuerzel = lehrer_nach_id.get(str(haupt_id), "")
                if kuerzel:
                    team.append(kuerzel)

            vertretung = stellvertreter.get(name)
            if isinstance(vertretung, str):
                vertretungen = [vertretung]
            elif isinstance(vertretung, list):
                vertretungen = vertretung
            else:
                vertretungen = []

            for kuerzel in vertretungen:
                kuerzel = str(kuerzel).strip()
                if kuerzel and kuerzel not in team:
                    team.append(kuerzel)

            katalog[name.casefold()] = Klasse(
                name=name,
                klassenlehrer=tuple(team),
            )

        return katalog

    def _stellvertreter_laden(self) -> dict:
        if not self.stellvertreter_datei.is_file():
            return {}
        with self.stellvertreter_datei.open("r", encoding="utf-8") as f:
            daten = json.load(f)
        if not isinstance(daten, dict):
            raise ValueError(
                f"Erwartete Zuordnung Klasse -> Stellvertretung in "
                f"{self.stellvertreter_datei}"
            )
        return daten

    @staticmethod
    def _json_laden(path: Path):
        if not path.is_file():
            raise FileNotFoundError(f"Schoolmanager-Datei nicht gefunden: {path}")
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _ist_schulklasse(name: str) -> bool:
        # 5a ... 10f sowie Kursstufen 11 und 12.
        if name in {"11", "12"}:
            return True
        import re
        return re.fullmatch(r"(?:[5-9]|10)[A-Za-z]", name) is not None

    @staticmethod
    def _hat_unterricht(ordner: Path) -> bool:
        for dateiname in ("woche_A.json", "woche_B.json"):
            path = ordner / dateiname
            if not path.is_file():
                continue
            try:
                with path.open("r", encoding="utf-8") as f:
                    daten = json.load(f)
                if isinstance(daten, list) and daten:
                    return True
            except (OSError, json.JSONDecodeError):
                pass
        return False
