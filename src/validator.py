"""
Prüfung der importierten Schuldaten.
"""

from models import Unterricht


class UnterrichtValidator:
    """
    Prüft Unterrichtseinträge auf fehlende oder unplausible Daten.
    """

    def pruefen(
        self,
        unterrichtsliste: list[Unterricht]
    ) -> list[str]:
        """
        Prüft alle Unterrichtseinträge.

        Gibt eine Liste mit Fehlermeldungen zurück.
        Ist die Liste leer, wurden keine Fehler gefunden.
        """

        fehlerliste: list[str] = []
        bekannte_eintraege: set[tuple[str, str, str]] = set()

        for zeilennummer, eintrag in enumerate(
            unterrichtsliste,
            start=2
        ):
            if not eintrag.klasse:
                fehlerliste.append(
                    f"Zeile {zeilennummer}: Klasse fehlt."
                )

            if not eintrag.fach:
                fehlerliste.append(
                    f"Zeile {zeilennummer}: Fachkennung fehlt."
                )

            if not eintrag.lehrer:
                fehlerliste.append(
                    f"Zeile {zeilennummer}: Lehrerkürzel fehlt."
                )

            if not eintrag.fachname:
                fehlerliste.append(
                    f"Zeile {zeilennummer}: Fachname fehlt."
                )

            if eintrag.wochenstunden < 0:
                fehlerliste.append(
                    f"Zeile {zeilennummer}: "
                    f"Wochenstunden dürfen nicht negativ sein."
                )

            schluessel = (
                eintrag.klasse,
                eintrag.fach,
                eintrag.lehrer,
            )

            if schluessel in bekannte_eintraege:
                fehlerliste.append(
                    f"Zeile {zeilennummer}: "
                    f"Doppelter Unterrichtseintrag "
                    f"({eintrag.klasse}, "
                    f"{eintrag.fach}, "
                    f"{eintrag.lehrer})."
                )
            else:
                bekannte_eintraege.add(schluessel)

        return fehlerliste