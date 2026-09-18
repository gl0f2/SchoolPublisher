"""
Renderer für SchoolPublisher.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from string import Template
from urllib.parse import quote
from datetime import date

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

        sortierte_fachnamen = sorted(
            fachgruppen,
            key=lambda fachname: self._fach_sortierschluessel(
                klassenname=klassenname,
                fachname=fachname,
                eintraege=fachgruppen[fachname],
            ),
        )

        karten = [
            self._fachkarte_erstellen(
                schule=schule,
                klasse=klasse,
                fachname=fachname,
                eintraege=fachgruppen[fachname],
            )
            for fachname in sortierte_fachnamen
        ]

        anzahl_faecher = len(karten)
        heute = date.today()
        schuljahr = self._schuljahr(heute)
        logo_pfad = quote((Path("..") / "images" / "MPGNürtingen.png").as_posix())
        qr_pfad = quote((Path("..") / "images" / "MPG_QR.png").as_posix())

        # Maximal 15 Karten pro A4-Seite. Weitere Karten werden auf einer
        # zweiten beziehungsweise weiteren Druckseite ausgegeben.
        kartenseiten = [karten[i:i + 15] for i in range(0, len(karten), 15)] or [[]]
        seiten_html = "\n".join(
            self._seite_html(
                klassenname=klassenname,
                karten=seite,
                seitennummer=index,
                seitenanzahl=len(kartenseiten),
                anzahl_faecher=anzahl_faecher,
                schuljahr=schuljahr,
                datum=heute.strftime("%d.%m.%Y"),
                logo_pfad=logo_pfad,
                qr_pfad=qr_pfad,
            )
            for index, seite in enumerate(kartenseiten, start=1)
        )

        html_inhalt = vorlage.safe_substitute(
            KLASSE=escape(klassenname),
            SEITEN=seiten_html,
        )

        dateipfad = (
            self.output_dir
            / f"Notentransparenzblatt_{klassenname}.html"
        )

        dateipfad.write_text(
            html_inhalt,
            encoding="utf-8",
        )

        return dateipfad

    @staticmethod
    def _seite_html(
        klassenname: str,
        karten: list[str],
        seitennummer: int,
        seitenanzahl: int,
        anzahl_faecher: int,
        schuljahr: str,
        datum: str,
        logo_pfad: str,
        qr_pfad: str,
    ) -> str:
        seitenhinweis = (
            f"<span>Seite {seitennummer} von {seitenanzahl}</span>"
            if seitenanzahl > 1
            else ""
        )
        return f"""
<main class="page">
<header class="hero">
  <div class="logo-wrap"><img class="logo" src="{logo_pfad}" alt="Max Planck Gymnasium Nürtingen"></div>
  <div class="hero-title"><h1>NOTENTRANSPARENZBLATT<br><span>Klasse {escape(klassenname)}</span></h1><div class="schoolyear">Schuljahr {escape(schuljahr)}</div></div>
  <div class="hero-side"><strong>Klasse {escape(klassenname)}</strong><span>{escape(datum)}</span><span>{anzahl_faecher} Fachkarten</span>{seitenhinweis}</div>
</header>
<section class="info-strip">
  <div class="info-item"><div class="info-icon">i</div><div class="info-copy"><h2>Liebe Eltern,</h2><p>auf diesem Blatt finden Sie eine Übersicht über die Fächer, Lehrkräfte und die wichtigsten Informationen zur Leistungsbewertung.</p></div></div>
  <div class="info-item"><div class="info-icon">★</div><div class="info-copy"><h2>Bewertung</h2><p>Die Angaben auf den Fachkarten stammen aus den hinterlegten Gewichtungen und tatsächlichen Leistungserhebungen.</p></div></div>
  <div class="info-item"><div class="info-icon">✉</div><div class="info-copy"><h2>Kontakt</h2><p>Bei Fragen können Sie sich per E-Mail an die jeweilige Lehrkraft wenden, sofern eine Adresse hinterlegt ist.</p></div></div>
</section>
<section class="cards grid-3">{"".join(karten)}</section>
<footer class="footer">
  <div class="foot-block"><div class="heart">♥</div><div><strong>Gemeinsam zum Erfolg</strong>Wir freuen uns auf eine gute Zusammenarbeit und ein erfolgreiches Schuljahr!</div></div>
  <div class="foot-block"><div style="font-size:18pt">⌂</div><div><strong>Max Planck Gymnasium Nürtingen</strong>Steinenbergstraße 20 &nbsp;|&nbsp; 72622 Nürtingen<br>07022 93236-0 &nbsp;|&nbsp; sekretariat@mpg-nuertingen.de</div></div>
  <div class="foot-block"><div class="globe">◎</div><div><strong>Weitere Informationen</strong>www.mpg-nuertingen.de</div><img class="qr" src="{qr_pfad}" alt="QR-Code zur Schulhomepage"></div>
</footer>
</main>
"""

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
        original = fachname.strip()
        key = original.casefold()

        if (
            "wirtschaft" in key
            and ("berufs" in key or "studienorientierung" in key)
        ):
            return "WBS"

        return self._fach_gruppen.get(key, original)

    def _fachkarte_erstellen(
        self,
        schule: Schule,
        klasse,
        fachname: str,
        eintraege: list[Unterricht],
    ) -> str:
        kuerzel_liste = self._eindeutige_lehrkraefte(eintraege)
        lehrkraefte = [schule.lehrkraft(kuerzel) for kuerzel in kuerzel_liste]
        bilder_html = "\n".join(self._bild_html(lehrkraft) for lehrkraft in lehrkraefte)
        namen_html = "<br>".join(escape(lehrkraft.kurzer_name) for lehrkraft in lehrkraefte)
        emails = [lehrkraft.email.strip() for lehrkraft in lehrkraefte if lehrkraft.email.strip()]
        email_html = " / ".join(escape(email) for email in emails) if emails else "E-Mail nicht hinterlegt"
        bewertung = schule.bewertung_fuer_fach(fachname, klasse.name)
        bewertung_html = self._bewertung_html(bewertung)
        accent, icon = self._fach_design(fachname)
        multi = " multi" if len(lehrkraefte) > 1 else ""
        mehrfach = " mehrere" if len(lehrkraefte) > 1 else ""
        anzahlklasse = f" count-{min(len(lehrkraefte), 5)}"
        klassenlehrer = {kuerzel.strip().casefold() for kuerzel in klasse.klassenlehrer}
        ist_klassenlehrerfach = any(
            kuerzel.strip().casefold() in klassenlehrer
            for kuerzel in kuerzel_liste
        )
        fachanzeige = f"{fachname} (KL)" if ist_klassenlehrerfach else fachname

        return f"""
        <article class="card" style="--accent:{accent}">
            <div class="card-head">
                <div class="subject-icon">{escape(icon)}</div>
                <h3 class="subject">{escape(fachanzeige)}</h3>
            </div>
            <div class="card-main{mehrfach}">
                <div class="photos{multi}{anzahlklasse}">{bilder_html}</div>
                <div class="details">
                    <p class="teacher">{namen_html}</p>
                    {bewertung_html}
                </div>
            </div>
            <div class="email">{email_html}</div>
        </article>
        """

    @staticmethod
    def _fach_sortierschluessel(
        klassenname: str,
        fachname: str,
        eintraege: list[Unterricht],
    ) -> tuple[int, int, float, str]:
        key = fachname.strip().casefold()
        wochenstunden = max(
            (float(eintrag.wochenstunden) for eintrag in eintraege),
            default=0.0,
        )

        if "deutsch" in key:
            return 0, 0, 0.0, key
        if "mathematik" in key:
            return 1, 0, 0.0, key
        if "englisch" in key:
            return 2, 0, 0.0, key
        if "latein" in key:
            return 3, 0, 0.0, key
        if "französisch" in key or "franzoesisch" in key:
            return 3, 1, 0.0, key

        klassenstufe_text = "".join(z for z in klassenname if z.isdigit())
        klassenstufe = int(klassenstufe_text) if klassenstufe_text else 0
        profilfaecher = (
            "nwt", "naturwissenschaft und technik", "italienisch", "imp",
            "informatik, mathematik, physik", "sportprofil",
        )
        ist_profil = any(name in key for name in profilfaecher) or (
            "sport" in key and wochenstunden >= 3.5
        )
        if klassenstufe >= 8 and ist_profil:
            return 4, 0, 0.0, key

        # Andere vierstündige Fächer folgen vor den zweistündigen Fächern.
        if wochenstunden >= 3.5:
            return 5, 0, -wochenstunden, key

        # Diese Fachfamilien stehen jeweils unmittelbar hintereinander.
        if "religion" in key:
            return 6, 0, 0.0, key
        if "ethik" in key:
            return 6, 1, 0.0, key

        if key == "ium" or "information und medien" in key:
            return 7, 0, 0.0, key
        if key == "nit" or "naturwissenschaftliches arbeiten" in key:
            return 7, 1, 0.0, key

        musische_gruppe = {
            "sport": 0,
            "bildende kunst": 1,
            "bk": 1,
            "musik": 2,
            "gesang": 3,
        }
        for name, unterrang in musische_gruppe.items():
            if key == name or name in key:
                return 8, unterrang, 0.0, key

        return 9, 0, -wochenstunden, key

    @staticmethod
    def _bewertung_html(bewertung: Bewertungsinfo | None) -> str:
        if bewertung is None:
            return '<p class="label">Bewertung</p><p class="ratio-name">Informationen folgen</p>'

        bereiche = [
            ("Mündlich", bewertung.gewicht_muendlich),
            ("Schriftlich", bewertung.gewicht_schriftlich),
        ]
        if bewertung.gewicht_praktisch is not None:
            bereiche.append(("Praktisch", bewertung.gewicht_praktisch))

        raster_elemente: list[str] = []
        for index, (bezeichnung, _) in enumerate(bereiche):
            if index:
                raster_elemente.append('<span class="ratio-colon">:</span>')
            raster_elemente.append(
                f'<span class="ratio-heading">{escape(bezeichnung)}</span>'
            )

        for index, (_, gewicht) in enumerate(bereiche):
            if index:
                raster_elemente.append('<span class="ratio-colon">:</span>')
            raster_elemente.append(
                f'<span class="ratio-value">{escape(zahl_text(gewicht))}</span>'
            )

        ratio_html = (
            f'<div class="ratio-grid ratio-{len(bereiche)}">'
            + "".join(raster_elemente)
            + "</div>"
        )

        erhebungen = bewertung.vorhandene_erhebungen()
        erhebungen_html = "".join(
            ElternabendHtmlRenderer._leistungserhebung_html(e) for e in erhebungen
        )
        zusatz_html = (
            f'<p class="additional-info">{escape(bewertung.zusatzinformation)}</p>'
            if bewertung.zusatzinformation.strip()
            else ""
        )
        return f"""
            <p class="label">Bewertung</p>
            {ratio_html}
            <div class="assessments">{erhebungen_html}</div>
            {zusatz_html}
        """

    @staticmethod
    def _leistungserhebung_html(erhebung) -> str:
        bezeichnung = erhebung.bezeichnung.strip()
        if erhebung.anzahl == 1:
            singular = {
                "Klassenarbeiten": "Klassenarbeit", "Tests": "Test",
                "Projekte": "Projekt", "Praktische Arbeiten": "Praktische Arbeit",
            }
            bezeichnung = singular.get(bezeichnung, bezeichnung)
        return f'<div class="assessment"><span class="dot">•</span><span>{erhebung.anzahl} {escape(bezeichnung)}</span></div>'

    @staticmethod
    def _raster_klasse(anzahl: int) -> str:
        if anzahl <= 15:
            return "grid-3"
        if anzahl <= 20:
            return "grid-4"
        return "grid-5"

    @staticmethod
    def _schuljahr(heute: date) -> str:
        start = heute.year if heute.month >= 8 else heute.year - 1
        return f"{start}/{str(start + 1)[-2:]}"

    @staticmethod
    def _fach_design(fachname: str) -> tuple[str, str]:
        key = fachname.strip().casefold()
        designs = {
            "mathematik": ("#1477d4", "√x"), "deutsch": ("#139d92", "D"),
            "englisch": ("#7642bd", "EN"), "französisch": ("#f28a00", "FR"),
            "latein": ("#e54848", "LA"), "geschichte": ("#159f9b", "G"),
            "geographie": ("#55ad2d", "Geo"), "biologie": ("#65b82e", "Bio"),
            "chemie": ("#2b8ee6", "Ch"), "physik": ("#edb300", "Ph"),
            "musik": ("#d92878", "♪"), "bildende kunst": ("#8048bd", "BK"),
            "sport": ("#11a7a5", "Sp"), "informatik": ("#2d82db", "IT"),
            "religion (ev.)": ("#e7b000", "†"), "religion": ("#e7b000", "†"),
        }
        for name, design in designs.items():
            if name in key:
                return design
        return "#2176bd", fachname[:2].upper()

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
