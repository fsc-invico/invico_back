__all__ = [
    "Rf602Report",
    "Rf602Document",
    "Rf602ValidationOutput",
    "Rf602Filter",
    "Rf602ExportFilter",
]


from typing import List, Optional

from pydantic import (
    BaseModel,
    Field,
    NonNegativeFloat,
)
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, ErrorsWithDocId
from .common import FuenteFinanciamientoSIIF


# -------------------------------------------------
class Rf602Report(BaseModel):
    ejercicio: int
    estructura: str
    fuente: FuenteFinanciamientoSIIF
    programa: str
    subprograma: str
    proyecto: str
    actividad: str
    grupo: str
    partida: str
    org: str
    credito_original: NonNegativeFloat
    credito_vigente: NonNegativeFloat
    comprometido: NonNegativeFloat
    ordenado: NonNegativeFloat
    saldo: float
    pendiente: float


# -------------------------------------------------
class Rf602Document(Rf602Report):
    id: PydanticObjectId = Field(alias="_id")


# Este se usa para la tabla (UI)
# -------------------------------------------------
class Rf602Filter(BaseFilterParams):
    ejercicio: Optional[int] = None


# Este se usa para el Excel (Sin limit/offset)
# -------------------------------------------------
class Rf602ExportFilter(BaseModel):
    query_filter: str = ""
    ejercicio: Optional[int] = None
    # Aquí podrías añadir: incluir_detalles: bool = False


# -------------------------------------------------
class Rf602ValidationOutput(BaseModel):
    errors: List[ErrorsWithDocId]
    validated: List[Rf602Document]
