__all__ = [
    "Rf610Report",
    "Rf610Document",
    "Rf610LiteFilter",
    "Rf610FullFilter",
]

from typing import Optional

from pydantic import (
    BaseModel,
    Field,
    NonNegativeFloat,
)
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class Rf610Report(BaseModel):
    ejercicio: int
    estructura: str
    programa: str
    desc_programa: Optional[str] = None
    subprograma: str
    desc_subprograma: Optional[str] = None
    proyecto: str
    desc_proyecto: Optional[str] = None
    actividad: str
    desc_actividad: Optional[str] = None
    grupo: str
    desc_grupo: str
    partida: str
    desc_partida: str
    credito_original: NonNegativeFloat
    credito_vigente: NonNegativeFloat
    comprometido: NonNegativeFloat
    ordenado: NonNegativeFloat
    saldo: float


# -------------------------------------------------
class Rf610Document(Rf610Report):
    id: PydanticObjectId = Field(alias="_id")


# Este se usa para la tabla (UI)
# -------------------------------------------------
class Rf610FullFilter(BaseFilterParams):
    ejercicio: Optional[int] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class Rf610LiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[int] = None
