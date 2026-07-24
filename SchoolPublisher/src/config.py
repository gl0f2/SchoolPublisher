"""
Zentrale Konfiguration für SchoolPublisher.
"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
IMAGE_DIR = PROJECT_ROOT / "images"
OUTPUT_DIR = PROJECT_ROOT / "output"
TEMPLATE_DIR = PROJECT_ROOT / "templates"

MATRIX_FILE = DATA_DIR / "Matrix_Test.xlsx"
LEHRKRAEFTE_FILE = DATA_DIR / "lehrer.xlsx"


# Mehrere Unterrichtsbezeichnungen können auf dem
# Elternabendblatt als ein gemeinsames Fach erscheinen.
FACH_GRUPPEN = {
    "Sport männlich": "Sport",
    "Sport weiblich": "Sport",
}
