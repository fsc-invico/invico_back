__all__ = [
    "SubprogramasReport",
    "SubprogramasDocument",
    "SubprogramasFullFilter",
    "SubprogramasLiteFilter",
]

from datetime import datetime, timezone
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class SubprogramasReport(BaseModel):
    subprograma: str
    desc_subprograma: str
    programa: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# -------------------------------------------------
class SubprogramasDocument(SubprogramasReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class SubprogramasFullFilter(BaseFilterParams):
    subprograma: Optional[str] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class SubprogramasLiteFilter(CamelModel):
    query_filter: str = ""
    # Aquí podrías añadir: incluir_detalles: bool = False
