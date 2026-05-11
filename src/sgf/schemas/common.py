__all__ = ["Origen", "OrigenAmpliado"]

from enum import Enum


# --------------------------------------------------
class Origen(str, Enum):
    epam = "EPAM"
    obras = "OBRAS"
    funcionamiento = "FUNCIONAMIENTO"


# --------------------------------------------------
class OrigenAmpliado(str, Enum):
    epam = "EPAM"
    obras = "OBRAS"
    funcionamiento = "FUNCIONAMIENTO"
    cetificados = "CERTIFICADOS"
