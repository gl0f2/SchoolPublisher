"""
Datenmodelle für SchoolPublisher.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Unterricht:
    """Ein Unterrichtseintrag aus der ASV-Matrix."""

    klasse: str
    fach: str
    fachname: str
    lehrer: str
    wochenstunden: float
    stundenplan_name: str = ""
    kopplung: str | None = None

    @property
    def anzeigename(self) -> str:
        return (
            self.fachname.strip()
            or self.stundenplan_name.strip()
            or self.fach.strip()
        )


@dataclass(frozen=True)
class Lehrkraft:
    """Stammdaten einer Lehrkraft."""

    kuerzel: str
    anrede: str = ""
    vorname: str = ""
    nachname: str = ""
    email: str = ""
    foto: str = ""

    @property
    def voller_name(self) -> str:
        teile = [
            self.anrede.strip(),
            self.vorname.strip(),
            self.nachname.strip(),
        ]
        return " ".join(teil for teil in teile if teil)

    @property
    def kurzer_name(self) -> str:
        teile = [
            self.anrede.strip(),
            self.nachname.strip(),
        ]
        name = " ".join(teil for teil in teile if teil)
        return name or self.voller_name or self.kuerzel

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
    """Zentrales Schulmodell."""

    unterricht: list[Unterricht]
    lehrkraeftekatalog: dict[str, Lehrkraft] = field(default_factory=dict)

    _klassen: tuple[str, ...] = field(init=False, repr=False)
    _lehrkraefte: tuple[str, ...] = field(init=False, repr=False)
    _faecher: tuple[str, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._klassen = tuple(
            sorted(
                {
                    eintrag.klasse.strip()
                    for eintrag in self.unterricht
                    if eintrag.klasse.strip()
                },
                key=str.casefold,
            )
        )

        self._lehrkraefte = tuple(
            sorted(
                {
                    eintrag.lehrer.strip()
                    for eintrag in self.unterricht
                    if eintrag.lehrer.strip()
                },
                key=str.casefold,
            )
        )

        self._faecher = tuple(
            sorted(
                {
                    eintrag.anzeigename
                    for eintrag in self.unterricht
                    if eintrag.anzeigename
                },
                key=str.casefold,
            )
        )

        self.lehrkraeftekatalog = {
            kuerzel.strip().casefold(): lehrkraft
            for kuerzel, lehrkraft in self.lehrkraeftekatalog.items()
        }

    def klassen(self) -> list[str]:
        return list(self._klassen)

    def lehrkraefte(self) -> list[str]:
        return list(self._lehrkraefte)

    def faecher(self) -> list[str]:
        return list(self._faecher)

    def unterricht_der_klasse(self, klassenname: str) -> list[Unterricht]:
        gesucht = klassenname.strip().casefold()
        return [
            eintrag
            for eintrag in self.unterricht
            if eintrag.klasse.strip().casefold() == gesucht
        ]

    def unterricht_der_lehrkraft(self, lehrerkuerzel: str) -> list[Unterricht]:
        gesucht = lehrerkuerzel.strip().casefold()
        return [
            eintrag
            for eintrag in self.unterricht
            if eintrag.lehrer.strip().casefold() == gesucht
        ]

    def klasse(self, klassenname: str) -> Klasse | None:
        gesucht = klassenname.strip().casefold()
        for name in self._klassen:
            if name.casefold() == gesucht:
                return Klasse(name=name)
        return None

    def lehrkraft(self, lehrerkuerzel: str) -> Lehrkraft:
        kuerzel = lehrerkuerzel.strip()
        return self.lehrkraeftekatalog.get(
            kuerzel.casefold(),
            Lehrkraft(kuerzel=kuerzel),
        )

    def fach(self, fachname: str) -> Fach | None:
        gesucht = fachname.strip().casefold()
        for name in self._faecher:
            if name.casefold() == gesucht:
                return Fach(name=name)
        return None
