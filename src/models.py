"""Datenmodelle für SchoolPublisher."""
from __future__ import annotations
from dataclasses import dataclass, field
import re

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
    gewicht_muendlich: float
    gewicht_schriftlich: float
    gewicht_praktisch: float | None = None
    erhebungen: tuple[Leistungserhebung, ...] = ()
    zusatzinformation: str = ""

    @property
    def bezeichnung(self) -> str:
        bereiche = ["Mündlich", "Schriftlich"]
        if self.gewicht_praktisch is not None:
            bereiche.append("Praktisch")
        return " : ".join(bereiche)

    @property
    def verhaeltnis(self) -> str:
        gewichte = [self.gewicht_muendlich, self.gewicht_schriftlich]
        if self.gewicht_praktisch is not None:
            gewichte.append(self.gewicht_praktisch)
        return " : ".join(zahl_text(wert) for wert in gewichte)

    def vorhandene_erhebungen(self) -> list[Leistungserhebung]:
        return [e for e in self.erhebungen if e.vorhanden]


@dataclass
class Bewertungskatalog:
    regeln: dict[tuple[int, str, str], Bewertungsinfo] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.regeln = {
            (int(stufe), klasse.strip().casefold(), fach.strip().casefold()): info
            for (stufe, klasse, fach), info in self.regeln.items()
            if klasse.strip() and fach.strip()
        }

    def fuer_fach(self, fachname: str, klassenname: str) -> Bewertungsinfo | None:
        stufe = klassenstufe_aus_klassenname(klassenname)
        if stufe is None:
            return None
        fach = fachname.strip().casefold()
        klasse = klassenname.strip().casefold()
        return (
            self.regeln.get((stufe, klasse, fach))
            or self.regeln.get((stufe, "alle", fach))
        )


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

def klassenstufe_aus_klassenname(klassenname: str) -> int | None:
    treffer = re.match(r"\s*(\d+)", klassenname)
    return int(treffer.group(1)) if treffer else None


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
    klassenkatalog: dict[str, Klasse] = field(default_factory=dict)
    bewertungskatalog: Bewertungskatalog = field(default_factory=Bewertungskatalog)
    _klassen: tuple[str, ...] = field(init=False, repr=False)
    _lehrkraefte: tuple[str, ...] = field(init=False, repr=False)
    _faecher: tuple[str, ...] = field(init=False, repr=False)
    def __post_init__(self) -> None:
        self._klassen = tuple(sorted({e.klasse.strip() for e in self.unterricht if e.klasse.strip()}, key=str.casefold))
        self._lehrkraefte = tuple(sorted({e.lehrer.strip() for e in self.unterricht if e.lehrer.strip()}, key=str.casefold))
        self._faecher = tuple(sorted({e.anzeigename for e in self.unterricht if e.anzeigename}, key=str.casefold))
        self.lehrkraeftekatalog = {k.strip().casefold(): v for k, v in self.lehrkraeftekatalog.items()}
        self.klassenkatalog = {k.strip().casefold(): v for k, v in self.klassenkatalog.items()}
    def klassen(self): return list(self._klassen)
    def lehrkraefte(self): return list(self._lehrkraefte)
    def faecher(self): return list(self._faecher)
    def unterricht_der_klasse(self, name): return [e for e in self.unterricht if e.klasse.strip().casefold() == name.strip().casefold()]
    def unterricht_der_lehrkraft(self, k): return [e for e in self.unterricht if e.lehrer.strip().casefold() == k.strip().casefold()]
    def klasse(self, name):
        schluessel = name.strip().casefold()
        if schluessel in self.klassenkatalog:
            return self.klassenkatalog[schluessel]
        return next((Klasse(n) for n in self._klassen if n.casefold() == schluessel), None)
    def lehrkraft(self, k):
        return self.lehrkraeftekatalog.get(k.strip().casefold(), Lehrkraft(kuerzel=k.strip()))
    def fach(self, name):
        return next((Fach(n) for n in self._faecher if n.casefold() == name.strip().casefold()), None)
    def bewertung_fuer_fach(self, name, klassenname):
        return self.bewertungskatalog.fuer_fach(name, klassenname)
