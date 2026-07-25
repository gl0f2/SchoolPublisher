"""Datenmodelle für SchoolPublisher."""
from __future__ import annotations
from dataclasses import dataclass, field
import json
from pathlib import Path

@dataclass(frozen=True)
class Leistungserhebung:
    bezeichnung: str
    anzahl: int
    gewicht: float | None = None

    @property
    def vorhanden(self) -> bool:
        return bool(self.bezeichnung.strip()) and self.anzahl > 0

@dataclass(frozen=True)
class Bewertungsinfo:
    bereich_links: str = "Mündlich"
    bereich_rechts: str = "Schriftlich"
    gewicht_links: float = 2
    gewicht_rechts: float = 1
    erhebungen: tuple[Leistungserhebung, ...] = ()

    @property
    def bezeichnung(self) -> str:
        return f"{self.bereich_links} : {self.bereich_rechts}"

    @property
    def verhaeltnis(self) -> str:
        return f"{zahl_text(self.gewicht_links)} : {zahl_text(self.gewicht_rechts)}"

    def vorhandene_erhebungen(self) -> list[Leistungserhebung]:
        return [e for e in self.erhebungen if e.vorhanden]

    def gewichtete_erhebungen(self) -> list[Leistungserhebung]:
        return [e for e in self.vorhandene_erhebungen() if e.gewicht is not None and e.gewicht > 0]

@dataclass
class Bewertungskatalog:
    fachwerte: dict[str, Bewertungsinfo] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.fachwerte = {k.strip().casefold(): v for k, v in self.fachwerte.items() if k.strip()}

    def fuer_fach(self, fachname: str) -> Bewertungsinfo | None:
        return self.fachwerte.get(fachname.strip().casefold())

    @classmethod
    def aus_json(cls, pfad: Path) -> "Bewertungskatalog":
        if not pfad.is_file():
            return cls()
        daten = json.loads(pfad.read_text(encoding="utf-8"))
        fachwerte = {}
        for fachname, fach in daten.get("faecher", {}).items():
            erhebungen = tuple(
                Leistungserhebung(
                    bezeichnung=str(e.get("bezeichnung", "")).strip(),
                    anzahl=max(0, int(e.get("anzahl", 0) or 0)),
                    gewicht=positive_zahl_oder_none(e.get("gewicht")),
                )
                for e in fach.get("leistungserhebungen", [])
            )
            fachwerte[fachname] = Bewertungsinfo(
                bereich_links=str(fach.get("bereich_links", "Mündlich")).strip() or "Mündlich",
                bereich_rechts=str(fach.get("bereich_rechts", "Schriftlich")).strip() or "Schriftlich",
                gewicht_links=positive_zahl(fach.get("gewicht_links", 2), 2),
                gewicht_rechts=positive_zahl(fach.get("gewicht_rechts", 1), 1),
                erhebungen=erhebungen,
            )
        return cls(fachwerte=fachwerte)

def positive_zahl(wert: object, standard: float) -> float:
    try:
        zahl = float(str(wert).strip().replace(",", "."))
        return zahl if zahl > 0 else standard
    except (TypeError, ValueError):
        return standard

def positive_zahl_oder_none(wert: object) -> float | None:
    if wert in (None, ""):
        return None
    try:
        zahl = float(str(wert).strip().replace(",", "."))
        return zahl if zahl > 0 else None
    except (TypeError, ValueError):
        return None

def zahl_text(wert: float) -> str:
    return f"{wert:g}"

@dataclass(frozen=True)
class Unterricht:
    klasse: str
    fach: str
    fachname: str
    lehrer: str
    wochenstunden: float
    stundenplan_name: str = ""
    kopplung: str | None = None
    @property
    def anzeigename(self) -> str:
        return self.fachname.strip() or self.stundenplan_name.strip() or self.fach.strip()

@dataclass(frozen=True)
class Lehrkraft:
    kuerzel: str
    anrede: str = ""
    vorname: str = ""
    nachname: str = ""
    email: str = ""
    foto: str = ""
    @property
    def voller_name(self) -> str:
        return " ".join(x for x in (self.anrede.strip(), self.vorname.strip(), self.nachname.strip()) if x)
    @property
    def kurzer_name(self) -> str:
        return " ".join(x for x in (self.anrede.strip(), self.nachname.strip()) if x) or self.voller_name or self.kuerzel
    @property
    def anzeigename(self) -> str:
        return self.voller_name or self.kuerzel

@dataclass(frozen=True)
class Klasse:
    name: str
    klassenlehrer: tuple[str, ...] = ()

@dataclass(frozen=True)
class Fach:
    name: str
    kuerzel: str = ""

@dataclass
class Schule:
    unterricht: list[Unterricht]
    lehrkraeftekatalog: dict[str, Lehrkraft] = field(default_factory=dict)
    bewertungskatalog: Bewertungskatalog = field(default_factory=Bewertungskatalog)
    _klassen: tuple[str, ...] = field(init=False, repr=False)
    _lehrkraefte: tuple[str, ...] = field(init=False, repr=False)
    _faecher: tuple[str, ...] = field(init=False, repr=False)
    def __post_init__(self) -> None:
        self._klassen = tuple(sorted({e.klasse.strip() for e in self.unterricht if e.klasse.strip()}, key=str.casefold))
        self._lehrkraefte = tuple(sorted({e.lehrer.strip() for e in self.unterricht if e.lehrer.strip()}, key=str.casefold))
        self._faecher = tuple(sorted({e.anzeigename for e in self.unterricht if e.anzeigename}, key=str.casefold))
        self.lehrkraeftekatalog = {k.strip().casefold(): v for k, v in self.lehrkraeftekatalog.items()}
    def klassen(self): return list(self._klassen)
    def lehrkraefte(self): return list(self._lehrkraefte)
    def faecher(self): return list(self._faecher)
    def unterricht_der_klasse(self, name): return [e for e in self.unterricht if e.klasse.strip().casefold() == name.strip().casefold()]
    def unterricht_der_lehrkraft(self, k): return [e for e in self.unterricht if e.lehrer.strip().casefold() == k.strip().casefold()]
    def klasse(self, name):
        return next((Klasse(n) for n in self._klassen if n.casefold() == name.strip().casefold()), None)
    def lehrkraft(self, k):
        return self.lehrkraeftekatalog.get(k.strip().casefold(), Lehrkraft(kuerzel=k.strip()))
    def fach(self, name):
        return next((Fach(n) for n in self._faecher if n.casefold() == name.strip().casefold()), None)
    def bewertung_fuer_fach(self, name): return self.bewertungskatalog.fuer_fach(name)
