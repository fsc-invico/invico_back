__all__ = [
    "Rff01Report",
    "Rff01Document",
    "Rff01LiteFilter",
    "Rff01FullFilter",
]

from pydantic import (
    AliasChoices,
    BaseModel,
    Field,
)
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class Rff01Report(BaseModel):
    fuente: str
    desc_fuente: str
    codigo: str


# -------------------------------------------------
class Rff01Document(Rff01Report):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class Rff01FullFilter(BaseFilterParams):
    pass


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class Rff01LiteFilter(CamelModel):
    query_filter: str = ""
