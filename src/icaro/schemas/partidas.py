__all__ = [
    "PartidasReport",
    "PartidasDocument",
    "PartidasFullFilter",
]

from datetime import datetime, timezone
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class PartidasReport(BaseModel):
    grupo: str
    desc_grupo: str
    partida_parcial: str
    desc_partida_parcial: str
    partida: str
    desc_partida: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# -------------------------------------------------
class PartidasDocument(PartidasReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class PartidasFullFilter(BaseFilterParams):
    grupo: Optional[str] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class PartidasLiteFilter(CamelModel):
    query_filter: str = ""
    # Aquí podrías añadir: incluir_detalles: bool = False
