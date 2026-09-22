"""Lehrkräftestammdaten: Schoolmanager + lokale Zusatzdaten."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from models import Lehrkraft
from lehrkraefte_importer import LehrkraefteImporter


class SchoolmanagerLehrkraefteImporter:
    """Schoolmanager liefert Kürzel/Vorname/Nachname; lokale Quellen ergänzen."""

    def __init__(self, schoolmanager_daten_dir: Path, lokale_datei: Path | None = None):
        self.schoolmanager_daten_dir = Path(schoolmanager_daten_dir)
        self.lehrer_datei = self.schoolmanager_daten_dir / "lehrer_aktuell.json"
        self.zusatz_datei = self.schoolmanager_daten_dir / "lehrkraefte_zusatz.json"
        self.lokale_datei = Path(lokale_datei) if lokale_datei else None

    def load(self) -> dict[str, Lehrkraft]:
        sm_lehrer = self._schoolmanager_laden()

        lokal = {}
        if self.lokale_datei is not None and self.lokale_datei.is_file():
            lokal_roh = LehrkraefteImporter(self.lokale_datei).load()
            lokal = {str(key).casefold(): value for key, value in lokal_roh.items()}

        zusatz = self._zusatz_laden()

        # Nachnamen dürfen nur dann als Fallback für Zusatzdaten verwendet
        # werden, wenn sie im Schoolmanager eindeutig sind. Die eigentliche
        # Identität einer Lehrkraft ist immer das Kürzel.
        nachnamen_anzahl: dict[str, int] = {}
        for person in sm_lehrer:
            if isinstance(person, dict):
                nn = str(person.get("lastname") or "").strip().casefold()
                if nn:
                    nachnamen_anzahl[nn] = nachnamen_anzahl.get(nn, 0) + 1

        katalog: dict[str, Lehrkraft] = {}

        for eintrag in sm_lehrer:
            if not isinstance(eintrag, dict):
                continue

            kuerzel = str(eintrag.get("abbreviation") or "").strip()
            if not kuerzel:
                continue

            schluessel = kuerzel.casefold()
            alt = lokal.get(schluessel)

            vorname = str(eintrag.get("firstname") or "").strip() or (alt.vorname if alt else "")
            nachname = str(eintrag.get("lastname") or "").strip() or (alt.nachname if alt else "")

            # Zusatzdaten: Kürzel ist eindeutig und hat immer Vorrang.
            # Ein Nachname wird nur als Fallback akzeptiert, wenn er im
            # aktuellen Schoolmanager-Lehrerkatalog genau einmal vorkommt.
            nachname_key = nachname.casefold() if nachname else ""
            extra_nachname = (
                zusatz.get(nachname_key, {})
                if nachname_key and nachnamen_anzahl.get(nachname_key, 0) == 1
                else {}
            )
            extra_kuerzel = zusatz.get(schluessel, {})
            extra = {**extra_nachname, **extra_kuerzel}

            # Manuelle Namenskorrekturen aus lehrkraefte_zusatz.json anwenden.
            vorname = str(extra.get("vorname") or "").strip() or vorname
            nachname = str(extra.get("nachname") or "").strip() or nachname

            anrede = str(extra.get("anrede") or "").strip() or (alt.anrede if alt else "")

            # Priorität: JSON-Ausnahme -> lehrer.xlsx -> automatisch erzeugt.
            email = str(extra.get("email") or "").strip()
            if not email and alt and alt.email:
                email = str(alt.email).strip()
            if not email:
                email = self._email_erzeugen(vorname, nachname)

            # Bekannte Abweichungen vom normalen MPG-Mail-Schema.
            # Kürzelbezogen, damit gleichnamige Lehrkräfte nie verwechselt werden.
            email_ausnahmen = {
                "burk": "c.burkhardt@mpg-nt.de",
                "bkh": "tj.burkhard@mpg-nt.de",
            }
            if schluessel in email_ausnahmen:
                email = email_ausnahmen[schluessel]

            foto = str(extra.get("foto") or "").strip()
            if not foto:
                foto = alt.foto if alt and alt.foto else f"{kuerzel}.jpg"

            katalog[schluessel] = Lehrkraft(
                kuerzel=kuerzel,
                anrede=anrede,
                vorname=vorname,
                nachname=nachname,
                email=email,
                foto=foto,
            )

        # Lokale Sonderpersonen behalten, falls sie nicht im Schoolmanager stehen.
        for key, lehrkraft in lokal.items():
            katalog.setdefault(key, lehrkraft)

        return katalog

    @staticmethod
    def _email_erzeugen(vorname: str, nachname: str) -> str:
        if not vorname.strip() or not nachname.strip():
            return ""

        def norm(text: str) -> str:
            text = text.strip().casefold()
            text = (text.replace("ä", "ae").replace("ö", "oe")
                        .replace("ü", "ue").replace("ß", "ss"))
            text = unicodedata.normalize("NFKD", text)
            text = "".join(ch for ch in text if not unicodedata.combining(ch))
            return re.sub(r"[^a-z0-9-]", "", text)

        v = norm(vorname)
        n = norm(nachname)
        if not v or not n:
            return ""
        return f"{v[0]}.{n}@mpg-nt.de"

    def _zusatz_laden(self) -> dict[str, dict]:
        if not self.zusatz_datei.is_file():
            return {}
        with self.zusatz_datei.open("r", encoding="utf-8") as f:
            daten = json.load(f)
        if not isinstance(daten, dict):
            raise ValueError(f"Erwartetes Objekt in {self.zusatz_datei}")
        return {
            str(key).casefold(): value
            for key, value in daten.items()
            if isinstance(value, dict)
        }

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
