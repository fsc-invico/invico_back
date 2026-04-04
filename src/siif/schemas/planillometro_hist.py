__all__ = [
    "PlanillometroHistReport",
    "PlanillometroHistDocument",
    "PlanillometroHistFullFilter",
    "PlanillometroHistLiteFilter",
]

from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class PlanillometroHistReport(BaseModel):
    desc_programa: str
    desc_subprograma: Optional[str] = None
    desc_proyecto: Optional[str] = None
    desc_actividad: Optional[str] = None
    actividad: Optional[str] = None
    partida: Optional[str] = None
    estructura: Optional[str] = None
    alta: Optional[str] = None
    acum_2008: Optional[float] = None


# -------------------------------------------------
class PlanillometroHistDocument(PlanillometroHistReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class PlanillometroHistFullFilter(BaseFilterParams):
    pass


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class PlanillometroHistLiteFilter(CamelModel):
    query_filter: str = ""
    pass
    # Aquí podrías añadir: incluir_detalles: bool = False
