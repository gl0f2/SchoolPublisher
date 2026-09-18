"""Schoolmanager-Aktualisierung für SchoolPublisher 2.4.

Der Bearer-Token wird nur im Arbeitsspeicher verwendet und nie gespeichert.
Die Datei stellvertretende_klassenlehrer.json wird nicht verändert.
"""

from __future__ import annotations

import getpass
import json
import re
import shutil
import tempfile
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import requests


API_URL = "https://login.schulmanager-online.de/api/calls"
BUNDLE_VERSION = "a6ef588fd2"

# Referenz-A-Woche des Schuljahres 2026/27.
FIRST_MONDAY = date(2026, 9, 14)

CLASS_ATTRIBUTES = [
    "id", "name", "aliases", "isCourseSystem", "gradeLevels",
    "mainClassTeacherId", "roomId", "termId", "createdAt", "updatedAt",
]
TEACHER_ATTRIBUTES = ["id", "firstname", "lastname", "abbreviation"]

MANUELLE_DATEIEN = {"stellvertretende_klassenlehrer.json", "lehrkraefte_zusatz.json"}


def week_range(monday: date) -> tuple[str, str]:
    sunday = monday + timedelta(days=6)
    return monday.isoformat(), sunday.isoformat()


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def api_call(session: requests.Session, token: str, req: dict):
    response = session.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json={"bundleVersion": BUNDLE_VERSION, "requests": [req]},
        timeout=45,
    )
    if response.status_code == 401:
        raise RuntimeError("401: Token abgelaufen oder nicht akzeptiert.")
    response.raise_for_status()

    answer = response.json()
    results = answer.get("results", [])
    if not results:
        raise RuntimeError("Antwort enthält kein 'results'.")

    result = results[0]
    if result.get("status") != 200:
        raise RuntimeError(
            json.dumps(result, ensure_ascii=False, indent=2)[:2000]
        )
    return result.get("data")


def poqa(model: str, attrs: list[str]) -> dict:
    return {
        "moduleName": "schedules",
        "endpointName": "poqa",
        "parameters": {
            "action": {
                "model": model,
                "action": "findAll",
                "parameters": [{"attributes": attrs}],
            },
            "uiState": "main.modules.schedules.view",
        },
    }


def lesson_request(class_obj: dict, start: str, end: str) -> dict:
    return {
        "moduleName": "schedules",
        "endpointName": "get-actual-lessons",
        "parameters": {
            "class": class_obj,
            "start": start,
            "end": end,
        },
    }


def detect_term(classes: list[dict]):
    with_term = [
        c for c in classes
        if isinstance(c, dict) and c.get("termId") is not None
    ]
    if not with_term:
        raise RuntimeError("Keine termId gefunden.")

    created = [
        str(c.get("createdAt", ""))[:10]
        for c in with_term if c.get("createdAt")
    ]
    if created:
        newest = max(created)
        candidates = [
            c for c in with_term
            if str(c.get("createdAt", "")).startswith(newest)
        ]
        if candidates:
            return Counter(
                c["termId"] for c in candidates
            ).most_common(1)[0][0]

    return Counter(
        c["termId"] for c in with_term
    ).most_common(1)[0][0]


def current_classes(classes: list[dict], term) -> list[dict]:
    by_name = {}
    for cls in classes:
        if cls.get("termId") != term or not cls.get("name"):
            continue
        name = cls["name"]
        old = by_name.get(name)
        if (
            old is None
            or str(cls.get("updatedAt", ""))
            > str(old.get("updatedAt", ""))
        ):
            by_name[name] = cls
    return sorted(by_name.values(), key=lambda x: x["name"])


def safe_name(value) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "_", str(value)).strip() or "unbenannt"


def lesson_identity(lesson):
    if not isinstance(lesson, dict):
        return json.dumps(lesson, sort_keys=True, ensure_ascii=False)

    actual = lesson.get("actualLesson") or {}
    return (
        lesson.get("date"),
        (lesson.get("classHour") or {}).get("number"),
        lesson.get("type"),
        (actual.get("subject") or {}).get("id"),
        tuple(sorted(
            t.get("id")
            for t in actual.get("teachers", [])
            if isinstance(t, dict)
        )),
        tuple(sorted(
            c.get("id")
            for c in actual.get("classes", [])
            if isinstance(c, dict)
        )),
        (actual.get("room") or {}).get("id"),
    )


def merge_weeks(week1: list, week2: list) -> list:
    seen = set()
    merged = []
    for lesson in (week1 or []) + (week2 or []):
        key = lesson_identity(lesson)
        if key not in seen:
            seen.add(key)
            merged.append(lesson)
    return merged


def subject_label(subject: dict) -> str:
    if not isinstance(subject, dict):
        return ""
    return str(
        subject.get("abbreviation")
        or subject.get("shortName")
        or subject.get("name")
        or subject.get("id")
        or ""
    ).strip()


def build_structure(plans: dict) -> dict:
    structure = {}
    for class_name, lessons in plans.items():
        subjects = defaultdict(dict)

        for lesson in lessons:
            actual = (
                lesson.get("actualLesson")
                if isinstance(lesson, dict)
                else None
            )
            if not isinstance(actual, dict):
                continue

            fach = subject_label(actual.get("subject") or {})
            if not fach:
                continue

            for teacher in actual.get("teachers") or []:
                if not isinstance(teacher, dict):
                    continue

                key = str(
                    teacher.get("id")
                    or teacher.get("abbreviation")
                    or f"{teacher.get('firstname', '')} "
                       f"{teacher.get('lastname', '')}"
                )
                kuerzel = teacher.get("abbreviation")
                subjects[fach][key] = {
                    "teacher_id": teacher.get("id"),
                    "kuerzel": kuerzel,
                    "vorname": teacher.get("firstname"),
                    "nachname": teacher.get("lastname"),
                    "bild": f"{kuerzel}.jpg" if kuerzel else None,
                }

        structure[class_name] = {
            fach: sorted(
                values.values(),
                key=lambda x: (
                    x.get("nachname") or "",
                    x.get("vorname") or "",
                ),
            )
            for fach, values in sorted(subjects.items())
        }

    return structure


def build_teacher_view(structure: dict) -> dict:
    result = {}

    for klasse, subjects in structure.items():
        for fach, teachers in subjects.items():
            for teacher in teachers:
                kuerzel = teacher.get("kuerzel")
                if not kuerzel:
                    continue

                entry = result.setdefault(
                    kuerzel,
                    {
                        "teacher_id": teacher.get("teacher_id"),
                        "vorname": teacher.get("vorname"),
                        "nachname": teacher.get("nachname"),
                        "bild": f"{kuerzel}.jpg",
                        "unterricht": [],
                    },
                )

                pair = {"klasse": klasse, "fach": fach}
                if pair not in entry["unterricht"]:
                    entry["unterricht"].append(pair)

    for entry in result.values():
        entry["unterricht"].sort(
            key=lambda x: (x["klasse"], x["fach"])
        )

    return dict(sorted(result.items()))


def _daten_uebernehmen(temp_dir: Path, target_dir: Path) -> None:
    """Ersetzt nur automatisch erzeugte Daten.

    Manuell gepflegte Dateien im Zielordner bleiben unangetastet.
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    # Alte automatisch erzeugte Stundenpläne komplett entfernen, damit
    # ausgeschiedene Klassen nicht als Altlast zurückbleiben.
    old_week_dir = target_dir / "stundenplaene_ab"
    if old_week_dir.exists():
        shutil.rmtree(old_week_dir)

    for source in temp_dir.iterdir():
        if source.name in MANUELLE_DATEIEN:
            continue

        target = target_dir / source.name
        if source.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)


def aktualisieren(
    daten_dir: Path,
    token: str | None = None,
) -> dict:
    """Lädt Schoolmanager-Daten und übernimmt sie erst nach Erfolg."""

    week_a = week_range(FIRST_MONDAY)
    week_b = week_range(FIRST_MONDAY + timedelta(days=7))

    print("\nSchoolmanager-Aktualisierung")
    print(f"Woche A: {week_a[0]} bis {week_a[1]}")
    print(f"Woche B: {week_b[0]} bis {week_b[1]}")
    print("Der Bearer-Token wird nicht gespeichert.\n")

    if token is None:
        token = getpass.getpass(
            "Bearer-Token (ohne 'Bearer '): "
        ).strip()

    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    if not token:
        raise RuntimeError("Kein Bearer-Token eingegeben.")

    daten_dir = Path(daten_dir)

    # Alles zunächst in einen temporären Ordner schreiben. Bei einem Fehler
    # bleibt der letzte funktionierende Datenbestand dadurch erhalten.
    with tempfile.TemporaryDirectory(
        prefix="schoolpublisher_schoolmanager_"
    ) as temp_name:
        out = Path(temp_name)
        week_dir = out / "stundenplaene_ab"

        with requests.Session() as session:
            print("[1/5] Lehrkräfte laden ...")
            teachers = api_call(
                session,
                token,
                poqa("main/teacher", TEACHER_ATTRIBUTES),
            )
            if not isinstance(teachers, list):
                raise RuntimeError("Ungültige Lehrkräfteliste erhalten.")
            save_json(out / "lehrer_aktuell.json", teachers)
            print(f"      {len(teachers)} Einträge")

            print("[2/5] Klassen laden ...")
            classes = api_call(
                session,
                token,
                poqa("main/class", CLASS_ATTRIBUTES),
            )
            if not isinstance(classes, list):
                raise RuntimeError("Ungültige Klassenliste erhalten.")

            term = detect_term(classes)
            classes_now = current_classes(classes, term)
            save_json(out / "klassen_aktuell.json", classes_now)
            print(
                f"      termId {term}, "
                f"{len(classes_now)} Klassen/Kursobjekte"
            )

            print("[3/5] A/B-Stundenpläne laden ...")
            merged_plans = {}
            errors = []

            for index, cls in enumerate(classes_now, 1):
                name = cls["name"]
                print(
                    f"      [{index:>2}/{len(classes_now)}] "
                    f"{name:<15}",
                    end="",
                    flush=True,
                )
                try:
                    a = api_call(
                        session,
                        token,
                        lesson_request(cls, *week_a),
                    )
                    time.sleep(0.08)
                    b = api_call(
                        session,
                        token,
                        lesson_request(cls, *week_b),
                    )

                    a = a if isinstance(a, list) else []
                    b = b if isinstance(b, list) else []
                    merged = merge_weeks(a, b)
                    merged_plans[name] = merged

                    class_dir = week_dir / safe_name(name)
                    save_json(class_dir / "woche_A.json", a)
                    save_json(class_dir / "woche_B.json", b)
                    save_json(
                        class_dir / "beide_wochen.json",
                        merged,
                    )
                    print(
                        f" A:{len(a):>3} B:{len(b):>3} "
                        f"ges:{len(merged):>3}"
                    )
                except Exception as exc:
                    errors.append(
                        {
                            "klasse": name,
                            "id": cls.get("id"),
                            "fehler": str(exc),
                        }
                    )
                    print(" FEHLER")

                time.sleep(0.08)

        # Bei Teilfehlern nicht den funktionierenden Datenbestand ersetzen.
        if errors:
            save_json(out / "import_fehler_ab.json", errors)
            raise RuntimeError(
                f"{len(errors)} Klassen-/Kursabruf(e) fehlgeschlagen. "
                "Der bisherige Datenbestand wurde nicht verändert."
            )

        print("[4/5] Unterrichtsstruktur erzeugen ...")
        structure = build_structure(merged_plans)
        teacher_view = build_teacher_view(structure)

        save_json(
            out / "schulstruktur_2026_27.json",
            structure,
        )
        save_json(
            out / "lehrer_unterricht_2026_27.json",
            teacher_view,
        )

        relations = sum(
            len(teachers)
            for subjects in structure.values()
            for teachers in subjects.values()
        )

        print("[5/5] Importinformationen speichern ...")
        info = {
            "schuljahr": "2026/27",
            "termId": term,
            "bundleVersion": BUNDLE_VERSION,
            "importiert_am": datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
            "woche_A": {
                "start": week_a[0],
                "ende": week_a[1],
            },
            "woche_B": {
                "start": week_b[0],
                "ende": week_b[1],
            },
            "anzahl_klassen_kursobjekte": len(classes_now),
            "anzahl_zuordnungen": relations,
            "anzahl_lehrer_mit_unterricht": len(teacher_view),
            "fehler": 0,
            "quelle": (
                "Schoolmanager get-actual-lessons, "
                "zwei aufeinanderfolgende Wochen"
            ),
        }
        save_json(out / "import_info_2026_27.json", info)

        _daten_uebernehmen(out, daten_dir)

    print("\n✓ Schoolmanager-Daten erfolgreich aktualisiert.")
    print(
        "✓ stellvertretende_klassenlehrer.json "
        "wurde nicht verändert."
    )
    return info


def letzter_import(daten_dir: Path) -> str | None:
    info_file = Path(daten_dir) / "import_info_2026_27.json"
    if not info_file.is_file():
        return None

    try:
        info = json.loads(info_file.read_text(encoding="utf-8"))
        value = info.get("importiert_am")
        if value:
            return str(value)
    except (OSError, json.JSONDecodeError):
        pass

    # Alte 2.3-Daten besitzen noch kein importiert_am.
    try:
        timestamp = info_file.stat().st_mtime
        return datetime.fromtimestamp(timestamp).astimezone().isoformat(
            timespec="seconds"
        )
    except OSError:
        return None
