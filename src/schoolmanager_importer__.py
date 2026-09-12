"""Import der aktuellen Schoolmanager-Unterrichtsdaten (A/B-Wochen)."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from models import Unterricht


class SchoolmanagerImporter:
    """
    Liest die von schoolmanager_import_v03_ab.py erzeugten A/B-Wochen ein.

    Pro Kombination (Klasse, Fach, Lehrkraft) wird GENAU EIN Unterricht-Objekt
    erzeugt. Unterschiedliche studentGroups werden als Kopplungsinformation
    zusammengeführt und erzeugen keine doppelten Unterrichtseinträge.
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

        unterrichtsliste = []

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

            woche_a = self._woche_auswerten(klasse, self._json_laden(datei_a))
            woche_b = self._woche_auswerten(klasse, self._json_laden(datei_b))

            alle_schluessel = set(woche_a) | set(woche_b)

            for key in alle_schluessel:
                a = woche_a.get(key)
                b = woche_b.get(key)
                info = a or b

                stunden_a = len(a["termine"]) if a else 0
                stunden_b = len(b["termine"]) if b else 0
                wochenstunden = (stunden_a + stunden_b) / 2.0

                gruppen = set()
                if a:
                    gruppen.update(a["gruppen"])
                if b:
                    gruppen.update(b["gruppen"])

                kopplung = ", ".join(sorted(gruppen, key=str.casefold)) or None

                unterrichtsliste.append(
                    Unterricht(
                        klasse=info["klasse"],
                        fach=info["fach"],
                        fachname=info["fachname"],
                        lehrer=info["lehrer"],
                        wochenstunden=wochenstunden,
                        stundenplan_name=info["stundenplan_name"],
                        kopplung=kopplung,
                    )
                )

        return sorted(
            unterrichtsliste,
            key=lambda e: (
                e.klasse.casefold(),
                e.anzeigename.casefold(),
                e.lehrer.casefold(),
            ),
        )

    def _woche_auswerten(self, klasse: str, lessons: list) -> dict:
        """
        Gruppiert ausschließlich nach (Klasse, Fach, Lehrer).

        Die Schülergruppen werden nur gesammelt. Für die Stundenzahl werden
        eindeutige (Datum, Unterrichtsstunde)-Termine gezählt. Dadurch erzeugt
        dieselbe Stunde mit mehreren studentGroups keine Mehrfachzählung.
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
            termin = self._termin_key(lesson)

            for teacher in actual.get("teachers") or []:
                if not isinstance(teacher, dict):
                    continue

                kuerzel = str(teacher.get("abbreviation") or "").strip()
                if not kuerzel:
                    continue

                key = (
                    klasse.casefold(),
                    fach.casefold(),
                    kuerzel.casefold(),
                )

                if key not in result:
                    result[key] = {
                        "klasse": klasse,
                        "fach": fach,
                        "fachname": fachname,
                        "lehrer": kuerzel,
                        "stundenplan_name": fachname or fach,
                        "gruppen": set(),
                        "termine": set(),
                    }

                result[key]["gruppen"].update(gruppen)
                result[key]["termine"].add(termin)

        return result

    @staticmethod
    def _termin_key(lesson: dict):
        class_hour = lesson.get("classHour") or {}
        nummer = class_hour.get("number")
        # Fallback auf IDs/Zeiten, falls number einmal fehlen sollte.
        if nummer is None:
            nummer = (
                class_hour.get("id")
                or class_hour.get("startTime")
                or class_hour.get("start")
                or json.dumps(class_hour, sort_keys=True, ensure_ascii=False)
            )
        return (lesson.get("date"), str(nummer))

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
    def _student_groups(actual: dict) -> set[str]:
        namen = set()
        for group in actual.get("studentGroups") or []:
            if not isinstance(group, dict):
                continue
            name = str(
                group.get("name")
                or group.get("abbreviation")
                or group.get("shortName")
                or ""
            ).strip()
            if name:
                namen.add(name)
        return namen
