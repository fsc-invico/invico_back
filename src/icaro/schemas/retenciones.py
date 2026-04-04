__all__ = [
    "RetencionesReport",
    "RetencionesDocument",
    "RetencionesFullFilter",
    "RetencionesLiteFilter",
]

from datetime import datetime, timezone
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class RetencionesReport(BaseModel):
    ejercicio: int
    codigo: str
    importe: float
    id_carga: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# -------------------------------------------------
class RetencionesDocument(RetencionesReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class RetencionesFullFilter(BaseFilterParams):
    ejercicio: Optional[str] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class RetencionesLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[str] = None

    # Aquí podrías añadir: incluir_detalles: bool = False
