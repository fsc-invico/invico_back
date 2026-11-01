__all__ = [
    "ObrasDesactivadasReport",
    "ObrasDesactivadasDocument",
    "ObrasDesactivadasFullFilter",
    "ObrasDesactivadasLiteFilter",
]


from datetime import datetime
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
    # Cerrojo de edición (concurrencia optimista). Sin default_factory a
    # propósito: si el front no lo envía, llega None y el servicio puede
    # detectarlo. Al crear, el servicio asigna el timestamp en el servidor.
    updated_at: Optional[datetime] = None


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
