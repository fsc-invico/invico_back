__all__ = [
    "CtasCtesReport",
    "CtasCtesDocument",
    "CtasCtesFullFilter",
    "CtasCtesLiteFilter",
]

from datetime import datetime
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class CtasCtesReport(BaseModel):
    map_to: str
    desc_cta_cte: Optional[str] = None
    sscc_cta_cte: Optional[str] = None
    real_cta_cte: Optional[str] = None
    siif_recursos_cta_cte: Optional[str] = None
    siif_gastos_cta_cte: Optional[str] = None
    siif_contabilidad_cta_cte: Optional[str] = None
    sgf_cta_cte: Optional[str] = None
    siif_cta_cte: Optional[str] = None
    icaro_cta_cte: Optional[str] = None
    # Cerrojo de edición (concurrencia optimista), paridad con
    # sgv.obras_recuperadas: los documentos históricos quedan en None y
    # el servicio omite el control cuando la BD no tiene timestamp.
    updated_at: Optional[datetime] = None


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
