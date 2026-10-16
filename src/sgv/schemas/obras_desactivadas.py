__all__ = [
    "ObrasDesactivadasReport",
    "ObrasDesactivadasDocument",
    "ObrasDesactivadasFullFilter",
    "ObrasDesactivadasLiteFilter",
]


from datetime import datetime, timezone
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class ObrasDesactivadasReport(BaseModel):
    ejercicio: int
    cta_contable: str
    estructura: str
    importe: float
    notas: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# -------------------------------------------------
class ObrasDesactivadasDocument(ObrasDesactivadasReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class ObrasDesactivadasFullFilter(BaseFilterParams):
    ejercicio: Optional[str] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class ObrasDesactivadasLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[str] = None
