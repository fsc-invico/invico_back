__all__ = [
    "Rci02Report",
    "Rci02Document",
    "Rci02FullFilter",
    "Rci02LiteFilter",
]

from datetime import datetime
from typing import Optional

from pydantic import (
    AliasChoices,
    BaseModel,
    Field,
)
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class Rci02Report(BaseModel):
    ejercicio: int
    mes: str
    fecha: datetime
    fuente: str
    cta_cte: str
    nro_entrada: str
    importe: float
    glosa: str
    es_remanente: bool
    es_invico: bool
    es_verificado: bool
    clase_reg: str
    clase_mod: str


# -------------------------------------------------
class Rci02Document(Rci02Report):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class Rci02FullFilter(BaseFilterParams):
    ejercicio: Optional[str] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class Rci02LiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[str] = None
    # Aquí podrías añadir: incluir_detalles: bool = False
