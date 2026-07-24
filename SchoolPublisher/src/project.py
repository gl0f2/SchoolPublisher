"""
Projekte für SchoolPublisher.
"""

from dataclasses import dataclass

from models import Schule


@dataclass
class Projekt:
    """
    Basisklasse für eine konkrete Ausgabe.
    """

    name: str
    schule: Schule