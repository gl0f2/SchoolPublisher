"""SchoolPublisher Version 1.4.1."""

from config import (
    FACH_GRUPPEN,
    IMAGE_DIR,
    LEHRKRAEFTE_FILE,
    MATRIX_FILE,
    OUTPUT_DIR,
    TEMPLATE_DIR,
)
from importer import MatrixImporter
from lehrkraefte_importer import LehrkraefteImporter
from models import Bewertungskatalog, Schule
from project import Projekt
from renderer import ElternabendHtmlRenderer, KlassenHtmlRenderer, KlassenTextRenderer
from validator import UnterrichtValidator


def main() -> None:
    print("=" * 60)
    print("SchoolPublisher Version 1.4.1")
    print("=" * 60)

    try:
        unterrichtsliste = MatrixImporter(MATRIX_FILE).load()
        fehlerliste = UnterrichtValidator().pruefen(unterrichtsliste)

        if fehlerliste:
            print("\nBei der Datenprüfung wurden Probleme gefunden:\n")
            for fehler in fehlerliste:
                print(f"- {fehler}")
            print("\nProgramm wird beendet.")
            return

        print("\n✓ Unterrichtsdaten erfolgreich geprüft.")

        lehrkraeftekatalog = LehrkraefteImporter(LEHRKRAEFTE_FILE).load()
        print(
            "✓ Lehrkräftestammdaten eingelesen: "
            f"{len(lehrkraeftekatalog)} Lehrkräfte"
        )

        bewertungen_datei = MATRIX_FILE.parent / "bewertungen.json"
        bewertungskatalog = Bewertungskatalog.aus_json(bewertungen_datei)
        schule = Schule(
            unterricht=unterrichtsliste,
            lehrkraeftekatalog=lehrkraeftekatalog,
            bewertungskatalog=bewertungskatalog,
        )
        projekt = Projekt(name="Informationsblatt Elternabend", schule=schule)

        print(f"\nProjekt: {projekt.name}\n")
        print(f"Unterrichtseinträge : {len(schule.unterricht)}")
        print(f"Klassen             : {len(schule.klassen())}")
        print(f"Lehrkräfte Matrix   : {len(schule.lehrkraefte())}")
        print(f"Lehrkräfte Stamm    : {len(lehrkraeftekatalog)}")
        print(f"Fächer              : {len(schule.faecher())}")

        fehlende_stammdaten = [
            kuerzel
            for kuerzel in schule.lehrkraefte()
            if not schule.lehrkraft(kuerzel).vorname
            and not schule.lehrkraft(kuerzel).nachname
        ]
        if fehlende_stammdaten:
            print("\nHinweis: Stammdaten fehlen für:")
            print("         " + ", ".join(fehlende_stammdaten))

        text_renderer = KlassenTextRenderer(output_dir=OUTPUT_DIR)
        html_renderer = KlassenHtmlRenderer(
            output_dir=OUTPUT_DIR,
            image_dir=IMAGE_DIR,
        )
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
            elternabend_datei = elternabend_renderer.rendern(
                projekt.schule,
                klassenname,
            )
            print(f"Klasse {klassenname}")
            print(f"   Text        : {text_datei.name}")
            print(f"   HTML        : {html_datei.name}")
            print(f"   Elternabend : {elternabend_datei.name}\n")

        print("=" * 60)
        print("SchoolPublisher Version 1.4.1 erfolgreich beendet.")
        print("=" * 60)

    except (FileNotFoundError, ValueError, OSError, ImportError) as fehler:
        print("\n" + "=" * 60)
        print("SchoolPublisher konnte nicht gestartet werden.")
        print(f"Fehler: {fehler}")
        print("=" * 60)


if __name__ == "__main__":
    main()
