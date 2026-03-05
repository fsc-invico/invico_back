__all__ = [
    "Rf602Report",
    "Rf602Document",
    "Rf602FullFilter",
    "Rf602LiteFilter",
]


from typing import Optional

from pydantic import (
    BaseModel,
    Field,
    NonNegativeFloat,
)
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams
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
class Rf602FullFilter(BaseFilterParams):
    ejercicio: Optional[int] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class Rf602LiteFilter(BaseModel):
    query_filter: str = ""
    ejercicio: Optional[int] = None
    # Aquí podrías añadir: incluir_detalles: bool = False
