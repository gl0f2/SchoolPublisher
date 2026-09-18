from pathlib import Path
from pypdf import PdfWriter


class PdfMerger:

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def zusammenfassen(self) -> Path | None:
        pdfs = sorted(
            self.output_dir.glob("Notentransparenzblatt_*.pdf")
        )

        if not pdfs:
            return None

        writer = PdfWriter()

        for pdf in pdfs:
            writer.append(str(pdf))

        ziel = (
            self.output_dir
            / "Notentransparenzblaetter_alle_Klassen.pdf"
        )

        with open(ziel, "wb") as f:
            writer.write(f)

        return ziel