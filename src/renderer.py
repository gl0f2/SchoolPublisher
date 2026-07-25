"""
Renderer für SchoolPublisher.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from string import Template
from urllib.parse import quote

from models import Bewertungsinfo, Lehrkraft, Schule, Unterricht, zahl_text


def wochenstunden_text(
    wert: float,
) -> str:
    if float(wert) == 1:
        return "1 Wochenstunde"

    return f"{wert:g} Wochenstunden"


class KlassenTextRenderer:
    def __init__(
        self,
        output_dir: Path,
    ) -> None:
        self.output_dir = output_dir

    def rendern(
        self,
        schule: Schule,
        klassenname: str,
    ) -> Path:
        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        zeilen = [
            f"Klassenübersicht {klassenname}",
            "=" * 40,
            "",
        ]

        for eintrag in schule.unterricht_der_klasse(
            klassenname
        ):
            lehrkraft = schule.lehrkraft(
                eintrag.lehrer
            )

            zeilen.append(
                f"{eintrag.anzeigename}: "
                f"{lehrkraft.anzeigename}, "
                f"{wochenstunden_text(eintrag.wochenstunden)}"
            )

        dateipfad = (
            self.output_dir
            / f"Klassenuebersicht_{klassenname}.txt"
        )

        dateipfad.write_text(
            "\n".join(zeilen),
            encoding="utf-8",
        )

        return dateipfad


class KlassenHtmlRenderer:
    def __init__(
        self,
        output_dir: Path,
        image_dir: Path,
    ) -> None:
        self.output_dir = output_dir
        self.image_dir = image_dir

    def rendern(
        self,
        schule: Schule,
        klassenname: str,
    ) -> Path:
        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        zeilen = []

        for eintrag in schule.unterricht_der_klasse(
            klassenname
        ):
            lehrkraft = schule.lehrkraft(
                eintrag.lehrer
            )

            zeilen.append(
                "<tr>"
                f"<td>{escape(eintrag.anzeigename)}</td>"
                f"<td>{escape(lehrkraft.anzeigename)}</td>"
                f"<td>{escape(wochenstunden_text(eintrag.wochenstunden))}</td>"
                "</tr>"
            )

        html = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <title>Klassenübersicht {escape(klassenname)}</title>
    <style>
        body {{
            max-width: 1000px;
            margin: 40px auto;
            padding: 0 24px;
            font-family: Arial, sans-serif;
            color: #263640;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 12px;
            border-bottom: 1px solid #d9e2e8;
            text-align: left;
        }}
        th {{
            color: #173f5f;
            background: #eaf2f7;
        }}
    </style>
</head>
<body>
    <h1>Klassenübersicht {escape(klassenname)}</h1>
    <table>
        <thead>
            <tr>
                <th>Fach</th>
                <th>Lehrkraft</th>
                <th>Wochenstunden</th>
            </tr>
        </thead>
        <tbody>
            {''.join(zeilen)}
        </tbody>
    </table>
</body>
</html>
"""

        dateipfad = (
            self.output_dir
            / f"Klassenuebersicht_{klassenname}.html"
        )

        dateipfad.write_text(
            html,
            encoding="utf-8",
        )

        return dateipfad


class ElternabendHtmlRenderer:
    """
    Erstellt das professionelle Elternabendblatt.

    Mehrere Unterrichtseinträge desselben Anzeigefaches werden
    zu einer Karte zusammengeführt. Die Lehrerbilder erscheinen
    leicht überlappend nebeneinander.
    """

    BILD_ENDUNGEN = (
        ".jpeg",
        ".jpg",
        ".png",
        ".webp",
    )

    def __init__(
        self,
        output_dir: Path,
        image_dir: Path,
        template_dir: Path,
        fach_gruppen: dict[str, str] | None = None,
    ) -> None:
        self.output_dir = output_dir
        self.image_dir = image_dir
        self.template_dir = template_dir

        self._fach_gruppen = {
            fachname.strip().casefold(): gruppenname.strip()
            for fachname, gruppenname
            in (fach_gruppen or {}).items()
        }

    def rendern(
        self,
        schule: Schule,
        klassenname: str,
    ) -> Path:
        klasse = schule.klasse(
            klassenname
        )

        if klasse is None:
            raise ValueError(
                f"Die Klasse {klassenname!r} wurde nicht gefunden."
            )

        unterricht = schule.unterricht_der_klasse(
            klassenname
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        vorlagenpfad = (
            self.template_dir
            / "elternabend.html"
        )

        if not vorlagenpfad.is_file():
            raise FileNotFoundError(
                f"HTML-Vorlage nicht gefunden: {vorlagenpfad}"
            )

        vorlage = Template(
            vorlagenpfad.read_text(
                encoding="utf-8"
            )
        )

        fachgruppen = self._unterricht_gruppieren(
            unterricht
        )

        karten = [
            self._fachkarte_erstellen(
                schule=schule,
                fachname=fachname,
                eintraege=fachgruppen[fachname],
            )
            for fachname in sorted(
                fachgruppen,
                key=str.casefold,
            )
        ]

        html_inhalt = vorlage.safe_substitute(
            KLASSE=escape(klassenname),
            ANZAHL=len(unterricht),
            KARTEN="\n".join(karten),
        )

        dateipfad = (
            self.output_dir
            / f"Elternabend_{klassenname}.html"
        )

        dateipfad.write_text(
            html_inhalt,
            encoding="utf-8",
        )

        return dateipfad

    def _unterricht_gruppieren(
        self,
        unterricht: list[Unterricht],
    ) -> dict[str, list[Unterricht]]:
        gruppen: dict[str, list[Unterricht]] = {}

        for eintrag in unterricht:
            fachname = self._fach_anzeigename(
                eintrag.anzeigename
            )

            gruppen.setdefault(
                fachname,
                [],
            ).append(eintrag)

        return gruppen

    def _fach_anzeigename(
        self,
        fachname: str,
    ) -> str:
        return self._fach_gruppen.get(
            fachname.strip().casefold(),
            fachname.strip(),
        )

    def _fachkarte_erstellen(
        self,
        schule: Schule,
        fachname: str,
        eintraege: list[Unterricht],
    ) -> str:
        kuerzel_liste = self._eindeutige_lehrkraefte(
            eintraege
        )

        lehrkraefte = [
            schule.lehrkraft(kuerzel)
            for kuerzel in kuerzel_liste
        ]

        bilder_html = "\n".join(
            self._bild_html(lehrkraft)
            for lehrkraft in lehrkraefte
        )

        namen_html = "<br>".join(
            escape(lehrkraft.kurzer_name)
            for lehrkraft in lehrkraefte
        )

        bewertung = schule.bewertung_fuer_fach(
            fachname
        )

        bewertung_html = self._bewertung_html(
            bewertung
        )

        return f"""
        <article class="fachkarte">
            <div class="bildergruppe">
                {bilder_html}
            </div>

            <h3 class="fachname">
                {escape(fachname)}
            </h3>

            <p class="lehrkraefte">
                {namen_html}
            </p>

            {bewertung_html}
        </article>
        """

    @staticmethod
    def _bewertung_html(
        bewertung: Bewertungsinfo | None,
    ) -> str:
        if bewertung is None:
            return ""

        erhebungen = bewertung.vorhandene_erhebungen()
        erhebungen_html = "".join(
            ElternabendHtmlRenderer._leistungserhebung_html(e)
            for e in erhebungen
        )

        gewichtete = bewertung.gewichtete_erhebungen()
        untergewichtung_html = ""
        if len(gewichtete) >= 2:
            namen = " : ".join(escape(e.bezeichnung) for e in gewichtete)
            gewichte = " : ".join(zahl_text(e.gewicht or 0) for e in gewichtete)
            untergewichtung_html = f"""
                <p class="bewertungsueberschrift">Gewichtung der Leistungserhebungen</p>
                <p style="margin: 0;">{namen}</p>
                <p class="bewertungsverhaeltnis">{gewichte}</p>
            """

        erhebungen_block = ""
        if erhebungen:
            erhebungen_block = f"""
                <p class="bewertungsueberschrift">Leistungserhebungen</p>
                <div class="leistungserhebungen">{erhebungen_html}</div>
            """

        return f"""
            <section class="bewertungsinfo" style="margin-top:14px;padding-top:12px;border-top:1px solid #d9e2e8;">
                <p class="bewertungsueberschrift">Bewertung</p>
                <p style="margin:0;">{escape(bewertung.bezeichnung)}</p>
                <p class="bewertungsverhaeltnis">{escape(bewertung.verhaeltnis)}</p>
                {untergewichtung_html}
                {erhebungen_block}
            </section>
        """

    @staticmethod
    def _leistungserhebung_html(erhebung) -> str:
        bezeichnung = erhebung.bezeichnung.strip()
        if erhebung.anzahl == 1:
            singular = {
                "Klassenarbeiten": "Klassenarbeit",
                "Tests": "Test",
                "Projekte": "Projekt",
                "Praktische Arbeiten": "Praktische Arbeit",
            }
            bezeichnung = singular.get(bezeichnung, bezeichnung)
        return f'<p style="margin:4px 0 0;">{erhebung.anzahl} {escape(bezeichnung)}</p>'

    @staticmethod
    def _eindeutige_lehrkraefte(
        eintraege: list[Unterricht],
    ) -> list[str]:
        kuerzel: dict[str, str] = {}

        for eintrag in eintraege:
            wert = eintrag.lehrer.strip()

            if wert:
                kuerzel.setdefault(
                    wert.casefold(),
                    wert,
                )

        return sorted(
            kuerzel.values(),
            key=str.casefold,
        )

    @staticmethod
    def _wochenstunden_gruppe_text(
        eintraege: list[Unterricht],
    ) -> str:
        werte = sorted(
            {
                float(eintrag.wochenstunden)
                for eintrag in eintraege
            }
        )

        if not werte:
            return "Keine Wochenstunden angegeben"

        if len(werte) == 1:
            return wochenstunden_text(
                werte[0]
            )

        return (
            "Je nach Unterrichtsgruppe "
            + " / ".join(f"{wert:g}" for wert in werte)
            + " Wochenstunden"
        )

    def _bild_html(
        self,
        lehrkraft: Lehrkraft,
    ) -> str:
        bilddatei = self._bilddatei_finden(
            lehrkraft
        )

        name = lehrkraft.anzeigename

        if bilddatei is None:
            return (
                '<div class="bildplatzhalter" '
                f'title="{escape(name)}">'
                f"{escape(lehrkraft.kuerzel)}"
                "</div>"
            )

        # Die Ausgabedateien liegen in output/, die Bilder in images/.
        relativer_pfad = (
            Path("..")
            / "images"
            / bilddatei.name
        )

        bildquelle = quote(
            relativer_pfad.as_posix()
        )

        return (
            '<img class="lehrerbild" '
            f'src="{bildquelle}" '
            f'alt="{escape(name)}" '
            f'title="{escape(name)}">'
        )

    def _bilddatei_finden(
        self,
        lehrkraft: Lehrkraft,
    ) -> Path | None:
        # Bevorzugt den Dateinamen aus lehrer.xlsx.
        if lehrkraft.foto:
            dateipfad = (
                self.image_dir
                / lehrkraft.foto
            )

            if dateipfad.is_file():
                return dateipfad

        # Rückfall: Bild anhand des Kürzels suchen.
        for endung in self.BILD_ENDUNGEN:
            dateipfad = (
                self.image_dir
                / f"{lehrkraft.kuerzel}{endung}"
            )

            if dateipfad.is_file():
                return dateipfad

        return None
