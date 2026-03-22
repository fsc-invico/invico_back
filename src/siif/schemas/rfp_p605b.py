__all__ = [
    "RfpP605bReport",
    "RfpP605bDocument",
    "RfpP605bFullFilter",
    "RfpP605bLiteFilter",
]


from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class RfpP605bReport(BaseModel):
    ejercicio: int
    estructura: str
    fuente: str
    programa: str
    desc_programa: str
    subprograma: str
    desc_subprograma: str
    proyecto: str
    desc_proyecto: str
    actividad: str
    desc_actividad: str
    grupo: str
    partida: str
    formulado: float


# -------------------------------------------------
class RfpP605bDocument(RfpP605bReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class RfpP605bFullFilter(BaseFilterParams):
    ejercicio: Optional[int] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class RfpP605bLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[int] = None
    # Aquí podrías añadir: incluir_detalles: bool = False
