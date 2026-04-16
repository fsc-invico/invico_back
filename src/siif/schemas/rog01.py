__all__ = [
    "Rog01Report",
    "Rog01Document",
    "Rog01LiteFilter",
    "Rog01FullFilter",
]

from typing import Optional

from pydantic import (
    AliasChoices,
    BaseModel,
    Field,
)
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class Rog01Report(BaseModel):
    grupo: str
    part_parcial: str
    desc_grupo: str
    partida: str
    desc_part_parcial: str
    desc_partida: str


# -------------------------------------------------
class Rog01Document(Rog01Report):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class Rog01FullFilter(BaseFilterParams):
    grupo: Optional[str] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class Rog01LiteFilter(CamelModel):
    query_filter: str = ""
    grupo: Optional[str] = None
