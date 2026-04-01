__all__ = [
    "ObrasReport",
    "ObrasDocument",
    "ObrasFullFilter",
    "ObrasLiteFilter",
]

from datetime import datetime, timezone
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class ObrasReport(BaseModel):
    localidad: str
    cuit: str
    actividad: str
    partida: str
    fuente: str
    monto_contrato: Optional[float] = None
    monto_adicional: Optional[float] = None
    cta_cte: str
    norma_legal: Optional[str] = None
    desc_obra: str
    info_adicional: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# -------------------------------------------------
class ObrasDocument(ObrasReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class ObrasFullFilter(BaseFilterParams):
    pass


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class ObrasLiteFilter(CamelModel):
    query_filter: str = ""
    # Aquí podrías añadir: incluir_detalles: bool = False
