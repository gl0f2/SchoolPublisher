"""SchoolPublisher Version 2.4.1 - integrierte Schoolmanager-Aktualisierung."""

from pathlib import Path
import shutil
import subprocess

from config import (
    BEWERTUNGEN_FILE,
    FACH_GRUPPEN,
    IMAGE_DIR,
    LEHRKRAEFTE_FILE,
    OUTPUT_DIR,
    TEMPLATE_DIR,
)
from schoolmanager_importer import SchoolmanagerImporter
from schoolmanager_klassen_importer import SchoolmanagerKlassenImporter
from schoolmanager_lehrkraefte_importer import SchoolmanagerLehrkraefteImporter
from bewertungen_importer import BewertungenImporter
from models import Schule
from project import Projekt
from renderer import ElternabendHtmlRenderer, KlassenHtmlRenderer, KlassenTextRenderer
from validator import UnterrichtValidator
from schoolmanager_updater import aktualisieren, letzter_import


SCHOOLMANAGER_DATEN_DIR = Path(__file__).resolve().parent / "schoolmanager_daten"
IGNORIERTE_LEHRER = {"HOEGY", "HOEGY2", "LLX"}


def html_als_pdf_speichern(html_datei: Path) -> Path | None:
    browser = None
    for name in (
        "google-chrome", "google-chrome-stable", "chromium",
        "chromium-browser", "microsoft-edge",
    ):
        gefunden = shutil.which(name)
        if gefunden:
            browser = Path(gefunden)
            break

    if browser is None:
        for kandidat in (
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
            Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        ):
            if kandidat.is_file():
                browser = kandidat
                break

    if browser is None:
        return None

    pdf_datei = html_datei.with_suffix(".pdf")
    befehl = [
        str(browser), "--headless", "--disable-gpu", "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_datei.resolve()}",
        html_datei.resolve().as_uri(),
    ]
    ergebnis = subprocess.run(befehl, capture_output=True, text=True, timeout=60)
    return pdf_datei if ergebnis.returncode == 0 and pdf_datei.is_file() else None



def pdfs_zusammenfuehren(pdf_dateien: list[Path], ziel: Path) -> Path | None:
    """Führt die Klassen-PDFs unter Linux mit pdfunite zu einem Dokument zusammen."""
    pdf_dateien = [p for p in pdf_dateien if p and p.is_file()]
    if not pdf_dateien:
        return None
    pdfunite = shutil.which("pdfunite")
    if not pdfunite:
        return None
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ergebnis = subprocess.run(
        [pdfunite, *map(str, pdf_dateien), str(ziel)],
        capture_output=True, text=True, timeout=120,
    )
    return ziel if ergebnis.returncode == 0 and ziel.is_file() else None

def main() -> None:
    print("=" * 60)
    print("SchoolPublisher Version 2.4.1 - Schoolmanager integriert")
    print("=" * 60)

    try:
        # Schoolmanager-Daten aktualisieren oder vorhandenen Stand verwenden.
        letzter = letzter_import(SCHOOLMANAGER_DATEN_DIR)
        if letzter:
            print(f"Letzter Schoolmanager-Import: {letzter}")
            antwort = input(
                "Schoolmanager jetzt aktualisieren? [j/N]: "
            ).strip().casefold()
            if antwort in {"j", "ja", "y", "yes"}:
                aktualisieren(SCHOOLMANAGER_DATEN_DIR)
            else:
                print("→ Vorhandene Schoolmanager-Daten werden verwendet.")
        else:
            print("Noch keine Schoolmanager-Daten vorhanden.")
            print("Eine Aktualisierung ist erforderlich.")
            aktualisieren(SCHOOLMANAGER_DATEN_DIR)

        # Unterricht: nur Klassenstufen 5-10 und keine externen Kooperationen.
        unterrichtsliste = SchoolmanagerImporter(SCHOOLMANAGER_DATEN_DIR).load()
        unterrichtsliste = [
            u for u in unterrichtsliste
            if u.klasse not in {"11", "12"}
            and u.lehrer not in IGNORIERTE_LEHRER
        ]

        fehlerliste = UnterrichtValidator().pruefen(unterrichtsliste)
        if fehlerliste:
            print("\nBei der Datenprüfung wurden Probleme gefunden:\n")
            for fehler in fehlerliste:
                print(f"- {fehler}")
            print("\nProgramm wird beendet.")
            return

        print("\n✓ Schoolmanager-Unterrichtsdaten erfolgreich geprüft.")

        # Klassen: Schoolmanager ist die aktuelle Quelle.
        klassenkatalog = SchoolmanagerKlassenImporter(SCHOOLMANAGER_DATEN_DIR).load()
        verwendete_klassen = {u.klasse.casefold() for u in unterrichtsliste}
        klassenkatalog = {
            key: klasse for key, klasse in klassenkatalog.items()
            if key in verwendete_klassen
        }
        print(
            f"✓ Klassen aus Schoolmanager eingelesen: "
            f"{len(klassenkatalog)} relevante Klassen"
        )

        # Lehrkräfte: Grunddaten aus Schoolmanager, lokale Datei nur für Zusatzdaten.
        alle_lehrkraefte = SchoolmanagerLehrkraefteImporter(
            SCHOOLMANAGER_DATEN_DIR,
            LEHRKRAEFTE_FILE,
        ).load()

        verwendete_lehrer = {u.lehrer.casefold() for u in unterrichtsliste}
        # Klassenlehrerteam ebenfalls behalten, auch wenn jemand in den
        # gefilterten Unterrichtsdaten nicht als Fachlehrkraft vorkommt.
        for klasse in klassenkatalog.values():
            verwendete_lehrer.update(k.casefold() for k in klasse.klassenlehrer)

        lehrkraeftekatalog = {
            key: lehrkraft for key, lehrkraft in alle_lehrkraefte.items()
            if key in verwendete_lehrer
        }
        print(
            f"✓ Lehrkräfte aus Schoolmanager + lokalen Zusatzdaten: "
            f"{len(lehrkraeftekatalog)} relevante Lehrkräfte"
        )

        bewertungskatalog = BewertungenImporter(BEWERTUNGEN_FILE).load()
        print(f"✓ Bewertungsregeln eingelesen: {len(bewertungskatalog.regeln)} Regeln")

        schule = Schule(
            unterricht=unterrichtsliste,
            lehrkraeftekatalog=lehrkraeftekatalog,
            klassenkatalog=klassenkatalog,
            bewertungskatalog=bewertungskatalog,
        )
        projekt = Projekt(name="Notentransparenzblatt", schule=schule)

        print(f"\nProjekt: {projekt.name}\n")
        print(f"Unterrichtseinträge  : {len(schule.unterricht)}")
        print(f"Klassen Unterricht   : {len(schule.klassen())}")
        print(f"Klassen Schoolmanager: {len(klassenkatalog)}")
        print(f"Lehrkräfte Unterricht: {len(schule.lehrkraefte())}")
        print(f"Lehrkräfte Katalog   : {len(lehrkraeftekatalog)}")
        print(f"Fächer               : {len(schule.faecher())}")

        print("\nKlassenlehrerteams:")
        for klassenname in schule.klassen():
            klasse = schule.klasse(klassenname)
            team = ", ".join(klasse.klassenlehrer) if klasse and klasse.klassenlehrer else "—"
            print(f"  {klassenname:>3}: {team}")

        fehlende_stammdaten = [
            kuerzel for kuerzel in schule.lehrkraefte()
            if not schule.lehrkraft(kuerzel).vorname
            and not schule.lehrkraft(kuerzel).nachname
        ]
        if fehlende_stammdaten:
            print("\nHinweis: Lehrkräftestammdaten fehlen für:")
            print("         " + ", ".join(fehlende_stammdaten))

        text_renderer = KlassenTextRenderer(output_dir=OUTPUT_DIR)
        html_renderer = KlassenHtmlRenderer(output_dir=OUTPUT_DIR, image_dir=IMAGE_DIR)
        elternabend_renderer = ElternabendHtmlRenderer(
            output_dir=OUTPUT_DIR,
            image_dir=IMAGE_DIR,
            template_dir=TEMPLATE_DIR,
            fach_gruppen=FACH_GRUPPEN,
        )

        print("\nDokumente werden erstellt:\n")
        erzeugte_pdfs: list[Path] = []
        for klassenname in projekt.schule.klassen():
            text_datei = text_renderer.rendern(projekt.schule, klassenname)
            html_datei = html_renderer.rendern(projekt.schule, klassenname)
            elternabend_datei = elternabend_renderer.rendern(
                projekt.schule, klassenname
            )

            print(f"Klasse {klassenname}")
            print(f"   Text        : {text_datei.name}")
            print(f"   HTML        : {html_datei.name}")
            pdf_datei = html_als_pdf_speichern(elternabend_datei)
            print(f"   Elternabend : {elternabend_datei.name}")
            print(
                f"   PDF         : "
                f"{pdf_datei.name if pdf_datei else 'nicht erzeugt (Edge/Chrome nicht gefunden)'}\n"
            )
            if pdf_datei:
                erzeugte_pdfs.append(pdf_datei)

        # Alle Klassen in derselben Reihenfolge zu einem fortlaufenden PDF verbinden.
        gesamt_pdf = pdfs_zusammenfuehren(
            erzeugte_pdfs, OUTPUT_DIR / "Alle_Klassen_5_bis_10.pdf"
        )
        if gesamt_pdf:
            print(f"✓ Fortlaufendes Gesamt-PDF: {gesamt_pdf}")
        elif erzeugte_pdfs:
            print("Hinweis: Gesamt-PDF nicht erzeugt. Unter Kubuntu ggf. 'sudo apt install poppler-utils' ausführen.")

        print("=" * 60)
        print("SchoolPublisher Version 2.4.1 erfolgreich beendet.")
        print("=" * 60)

    except (FileNotFoundError, ValueError, OSError, ImportError) as fehler:
        print("\n" + "=" * 60)
        print("SchoolPublisher konnte nicht gestartet werden.")
        print(f"Fehler: {fehler}")
        print("=" * 60)


if __name__ == "__main__":
    main()
