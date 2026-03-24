__all__ = [
    "ActividadesReport",
    "ActividadesDocument",
    "ActividadesFullFilter",
    "ActividadesLiteFilter",
]

from datetime import datetime, timezone
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class ActividadesReport(BaseModel):
    actividad: str
    desc_actividad: str
    proyecto: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# -------------------------------------------------
class ActividadesDocument(ActividadesReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class ActividadesFullFilter(BaseFilterParams):
    nro_act: Optional[str] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class ActividadesLiteFilter(CamelModel):
    query_filter: str = ""
    nro_act: Optional[str] = None
    # Aquí podrías añadir: incluir_detalles: bool = False
