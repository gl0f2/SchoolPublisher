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

        unterrichtsliste = self._manuelle_lehrerwechsel_anwenden(unterrichtsliste)

        return sorted(
            unterrichtsliste,
            key=lambda e: (
                e.klasse.casefold(),
                e.anzeigename.casefold(),
                e.lehrer.casefold(),
            ),
        )

    def _manuelle_lehrerwechsel_anwenden(
        self, unterrichtsliste: list[Unterricht]
    ) -> list[Unterricht]:
        """Wendet lokale Lehrerwechsel nach dem Schoolmanager-Import an.

        Die Datei ``manuelle_aenderungen.json`` bleibt unabhängig von den
        automatisch aktualisierten A/B-Stundenplandaten erhalten.
        """
        pfad = self.datenverzeichnis / "manuelle_aenderungen.json"
        if not pfad.is_file():
            return unterrichtsliste

        with pfad.open("r", encoding="utf-8") as f:
            daten = json.load(f)

        wechsel = daten.get("lehrerwechsel", []) if isinstance(daten, dict) else []
        if not isinstance(wechsel, list):
            raise ValueError(f"'lehrerwechsel' muss eine Liste sein: {pfad}")

        ergebnis = list(unterrichtsliste)
        for eintrag in wechsel:
            if not isinstance(eintrag, dict):
                continue
            klasse = str(eintrag.get("klasse") or "").strip()
            fach = str(eintrag.get("fach") or "").strip().casefold()
            lehrer = str(eintrag.get("lehrer") or "").strip()
            if not klasse or not fach or not lehrer:
                raise ValueError(f"Unvollständiger Lehrerwechsel in {pfad}: {eintrag}")

            treffer = []
            for i, u in enumerate(ergebnis):
                fachwerte = {u.fach.strip().casefold(), u.fachname.strip().casefold()}
                if u.klasse.casefold() == klasse.casefold() and fach in fachwerte:
                    treffer.append(i)

            if not treffer:
                raise ValueError(
                    f"Manueller Lehrerwechsel nicht gefunden: {klasse} / {eintrag.get('fach')}"
                )

            # Ein Lehrerwechsel ersetzt alle bisher aus Schoolmanager gelesenen
            # Lehrkräfte für genau diese Klasse/Fach-Kombination. Bei mehreren
            # alten Einträgen wird nur ein Unterrichtsobjekt übernommen.
            basis = ergebnis[treffer[0]]
            neu = Unterricht(
                klasse=basis.klasse,
                fach=basis.fach,
                fachname=basis.fachname,
                lehrer=lehrer,
                wochenstunden=basis.wochenstunden,
                stundenplan_name=basis.stundenplan_name,
                kopplung=basis.kopplung,
            )
            ergebnis = [u for i, u in enumerate(ergebnis) if i not in set(treffer)]
            ergebnis.append(neu)

        return ergebnis

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

            # SchoolPublisher bildet die reguläre Unterrichtsverteilung ab.
            # Vertretungen/Änderungen (changedLesson) dürfen deshalb keine
            # zusätzlichen Fachlehrkräfte auf den Karteikarten erzeugen.
            if lesson.get("type") != "regularLesson":
                continue

            actual = lesson.get("actualLesson")
            if not isinstance(actual, dict):
                continue

            # In Klassen 10 sind die 7. und 8. Stunde für das Blatt nicht relevant.
            if klasse.startswith("10"):
                nummer = (lesson.get("classHour") or {}).get("number")
                try:
                    if int(nummer) in {7, 8}:
                        continue
                except (TypeError, ValueError):
                    pass

            subject = actual.get("subject") or {}
            fach = self._subject_code(subject)
            fachname = self._subject_name(subject)
            if not fach:
                continue

            # MPG-Sonderregeln für die Fachbezeichnungen im Stundenplan.
            fach, fachname = self._fach_normalisieren(klasse, fach, fachname)
            if fach is None:
                # z. B. Biologie-/Physik-Praktika: keine eigene Karteikarte.
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
    def _fach_normalisieren(klasse: str, fach: str, fachname: str) -> tuple[str | None, str]:
        code = fach.strip()
        name = fachname.strip()
        code_key = code.casefold().replace("–", "-").replace("—", "-").replace("‑", "-")
        text_key = f"{code} {name}".casefold()
        stufe_text = "".join(z for z in klasse if z.isdigit())
        stufe = int(stufe_text) if stufe_text else 0

        # Klassen 8-10: SPO = Profilfach, SPO-M/SPO-W = regulärer Sport.
        if 8 <= stufe <= 10:
            if code_key == "spo":
                return "SPO-PROFIL", "Sport (Profil)"
            if code_key in {"spo-m", "spo-w"}:
                return "SPO", "Sport"

        # Klassenlehrerstunden und Gesangsklassen erzeugen keine eigene Karte.
        # Sternstunde und MTW werden dagegen für die Elternabendübersicht benötigt.
        if (
            code_key in {"klassenlehrer", "kl"}
            or code_key.startswith("mug-")
        ):
            return None, name

        # Sternstunde:
        # Klasse 6 -> "Sternstunde"
        # Klasse 7 -> "Sternstunde/Mentoring"
        if "sternstunde" in text_key or code_key in {"stern", "sternstunde"}:
            if stufe == 7:
                return "Stern", "Sternstunde/Mentoring"
            return "Stern", "Sternstunde"

        # MTW wird in Klasse 5 als eigene Karte angezeigt.
        if code_key == "mtw":
            return "MTW", "Musik- und Theaterwerkstatt"

        # Praktika in Biologie, Physik und Chemie werden nicht dargestellt.
        if "prakt" in text_key and any(w in text_key for w in (
            "bio", "biologie", "phys", "physik", "chem", "chemie"
        )):
            return None, name

        return code, name

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
