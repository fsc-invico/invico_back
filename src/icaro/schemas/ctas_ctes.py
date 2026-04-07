__all__ = [
    "CtasCtesReport",
    "CtasCtesDocument",
    "CtasCtesFullFilter",
    "CtasCtesLiteFilter",
]

from datetime import datetime, timezone

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class CtasCtesReport(BaseModel):
    cta_cte_anterior: str
    cta_cte: str
    desc_cta_cte: str
    banco: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# -------------------------------------------------
class CtasCtesDocument(CtasCtesReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class CtasCtesFullFilter(BaseFilterParams):
    pass


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class CtasCtesLiteFilter(CamelModel):
    query_filter: str = ""
    # Aquí podrías añadir: incluir_detalles: bool = False
