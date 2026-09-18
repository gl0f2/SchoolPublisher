"""SchoolPublisher Version 2.3.1 - Schoolmanager A/B."""

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
from bewertungen_importer import BewertungenImporter
from lehrkraefte_importer import LehrkraefteImporter
from models import Schule
from project import Projekt
from renderer import ElternabendHtmlRenderer, KlassenHtmlRenderer, KlassenTextRenderer
from validator import UnterrichtValidator


SCHOOLMANAGER_DATEN_DIR = Path(__file__).resolve().parent / "schoolmanager_daten"


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


def main() -> None:
    print("=" * 60)
    print("SchoolPublisher Version 2.3.1 - Schoolmanager A/B")
    print("=" * 60)

    try:
        unterrichtsliste = SchoolmanagerImporter(SCHOOLMANAGER_DATEN_DIR).load()
        fehlerliste = UnterrichtValidator().pruefen(unterrichtsliste)

        if fehlerliste:
            print("\nBei der Datenprüfung wurden Probleme gefunden:\n")
            for fehler in fehlerliste:
                print(f"- {fehler}")
            print("\nProgramm wird beendet.")
            return

        print("\n✓ Schoolmanager-Unterrichtsdaten erfolgreich geprüft.")

        lehrkraeftekatalog = LehrkraefteImporter(LEHRKRAEFTE_FILE).load()
        print(f"✓ Lehrkräftestammdaten eingelesen: {len(lehrkraeftekatalog)} Lehrkräfte")

        klassenkatalog = SchoolmanagerKlassenImporter(SCHOOLMANAGER_DATEN_DIR).load()
        print(f"✓ Klassen aus Schoolmanager eingelesen: {len(klassenkatalog)} Klassen")

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
        print(f"Lehrkräfte Stamm     : {len(lehrkraeftekatalog)}")
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
        for klassenname in projekt.schule.klassen():
            text_datei = text_renderer.rendern(projekt.schule, klassenname)
            html_datei = html_renderer.rendern(projekt.schule, klassenname)
            elternabend_datei = elternabend_renderer.rendern(projekt.schule, klassenname)

            print(f"Klasse {klassenname}")
            print(f"   Text        : {text_datei.name}")
            print(f"   HTML        : {html_datei.name}")
            pdf_datei = html_als_pdf_speichern(elternabend_datei)
            print(f"   Elternabend : {elternabend_datei.name}")
            print(f"   PDF         : {pdf_datei.name if pdf_datei else 'nicht erzeugt (Edge/Chrome nicht gefunden)'}\n")

        print("=" * 60)
        print("SchoolPublisher Version 2.3.1 erfolgreich beendet.")
        print("=" * 60)

    except (FileNotFoundError, ValueError, OSError, ImportError) as fehler:
        print("\n" + "=" * 60)
        print("SchoolPublisher konnte nicht gestartet werden.")
        print(f"Fehler: {fehler}")
        print("=" * 60)


if __name__ == "__main__":
    main()
