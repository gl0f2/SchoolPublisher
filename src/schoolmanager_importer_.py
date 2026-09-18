"""Import der aktuellen Schoolmanager-Unterrichtsdaten (A/B-Wochen)."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from models import Unterricht


class SchoolmanagerImporter:
    """
    Liest die von schoolmanager_import_v03_ab.py erzeugten Rohdaten ein.

    Erwartete Struktur:
        schoolmanager_daten/
            stundenplaene_ab/
                5a/
                    woche_A.json
                    woche_B.json
                ...

    Aus zwei aufeinanderfolgenden A/B-Wochen werden Unterricht-Objekte erzeugt.
    Die Wochenstunden sind der Mittelwert aus beiden Wochen.
    """

    IGNORIERTE_KLASSEN = {"AG", "Frei", "Fö", "KOOP_12", "ORG_13", "xy"}

    def __init__(self, datenverzeichnis: Path):
        self.datenverzeichnis = Path(datenverzeichnis)
        self.stundenplanverzeichnis = self.datenverzeichnis / "stundenplaene_ab"

    def load(self) -> list[Unterricht]:
        if not self.stundenplanverzeichnis.is_dir():
            raise FileNotFoundError(
                f"Schoolmanager-Stundenplandaten nicht gefunden: "
                f"{self.stundenplanverzeichnis}"
            )

        sammlung = {}

        for klassenordner in sorted(self.stundenplanverzeichnis.iterdir()):
            if not klassenordner.is_dir():
                continue

            klasse = klassenordner.name
            if klasse in self.IGNORIERTE_KLASSEN:
                continue

            datei_a = klassenordner / "woche_A.json"
            datei_b = klassenordner / "woche_B.json"

            if not datei_a.is_file() or not datei_b.is_file():
                continue

            woche_a = self._json_laden(datei_a)
            woche_b = self._json_laden(datei_b)

            zaehler_a = self._woche_auswerten(klasse, woche_a)
            zaehler_b = self._woche_auswerten(klasse, woche_b)

            alle_schluessel = set(zaehler_a) | set(zaehler_b)

            for schluessel in alle_schluessel:
                info_a = zaehler_a.get(schluessel)
                info_b = zaehler_b.get(schluessel)
                info = info_a or info_b

                stunden_a = info_a["stunden"] if info_a else 0
                stunden_b = info_b["stunden"] if info_b else 0

                # Durchschnittliche Wochenstundenzahl im A/B-Rhythmus.
                wochenstunden = (stunden_a + stunden_b) / 2.0

                sammlung[schluessel] = Unterricht(
                    klasse=info["klasse"],
                    fach=info["fach"],
                    fachname=info["fachname"],
                    lehrer=info["lehrer"],
                    wochenstunden=wochenstunden,
                    stundenplan_name=info["stundenplan_name"],
                    kopplung=info["kopplung"],
                )

        return sorted(
            sammlung.values(),
            key=lambda e: (
                e.klasse.casefold(),
                e.anzeigename.casefold(),
                e.lehrer.casefold(),
                (e.kopplung or "").casefold(),
            ),
        )

    def _woche_auswerten(self, klasse: str, lessons: list) -> dict:
        """
        Zählt Unterrichtsstunden einer Woche.

        Gruppiert wird nach:
          Klasse, Fach, Lehrkraft, Schülergruppe/Kopplung.
        """
        result = {}

        for lesson in lessons:
            if not isinstance(lesson, dict):
                continue

            actual = lesson.get("actualLesson")
            if not isinstance(actual, dict):
                continue

            subject = actual.get("subject") or {}
            fach = self._subject_code(subject)
            fachname = self._subject_name(subject)
            if not fach:
                continue

            gruppen = self._student_groups(actual)
            kopplung = ", ".join(gruppen) if gruppen else None

            teachers = actual.get("teachers") or []
            for teacher in teachers:
                if not isinstance(teacher, dict):
                    continue

                kuerzel = str(teacher.get("abbreviation") or "").strip()
                if not kuerzel:
                    continue

                schluessel = (
                    klasse.casefold(),
                    fach.casefold(),
                    kuerzel.casefold(),
                    (kopplung or "").casefold(),
                )

                if schluessel not in result:
                    result[schluessel] = {
                        "klasse": klasse,
                        "fach": fach,
                        "fachname": fachname,
                        "lehrer": kuerzel,
                        "stundenplan_name": fachname or fach,
                        "kopplung": kopplung,
                        "stunden": 0,
                    }

                # Jeder actual lesson-Eintrag entspricht einer belegten
                # Unterrichtsstunde. Doppelstunden erscheinen als zwei
                # classHours und werden daher korrekt zweimal gezählt.
                result[schluessel]["stunden"] += 1

        return result

    @staticmethod
    def _json_laden(path: Path) -> list:
        with path.open("r", encoding="utf-8") as f:
            daten = json.load(f)
        if not isinstance(daten, list):
            raise ValueError(f"Erwartete Liste in {path}")
        return daten

    @staticmethod
    def _subject_code(subject: dict) -> str:
        return str(
            subject.get("abbreviation")
            or subject.get("shortName")
            or subject.get("name")
            or subject.get("id")
            or ""
        ).strip()

    @staticmethod
    def _subject_name(subject: dict) -> str:
        return str(
            subject.get("name")
            or subject.get("abbreviation")
            or subject.get("shortName")
            or subject.get("id")
            or ""
        ).strip()

    @staticmethod
    def _student_groups(actual: dict) -> list[str]:
        namen = []
        for group in actual.get("studentGroups") or []:
            if not isinstance(group, dict):
                continue
            name = str(
                group.get("name")
                or group.get("abbreviation")
                or group.get("shortName")
                or ""
            ).strip()
            if name and name not in namen:
                namen.append(name)
        return sorted(namen, key=str.casefold)
