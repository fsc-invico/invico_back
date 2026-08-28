__all__ = [
    "FacturerosReport",
    "FacturerosDocument",
    "FacturerosLiteFilter",
    "FacturerosFullFilter",
]


from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class FacturerosReport(BaseModel):
    beneficiario: str
    actividad: str
    partida: str


# -------------------------------------------------
class FacturerosDocument(FacturerosReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class FacturerosFullFilter(BaseFilterParams):
    pass


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class FacturerosLiteFilter(CamelModel):
    query_filter: str = ""
    # Aquí podrías añadir: incluir_detalles: bool = False
