__all__ = [
    "CtasCtesReport",
    "CtasCtesDocument",
    "CtasCtesFullFilter",
    "CtasCtesLiteFilter",
]

from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class CtasCtesReport(BaseModel):
    map_to: str
    sscc_cta_cte: Optional[str] = None
    real_cta_cte: Optional[str] = None
    siif_recursos_cta_cte: Optional[str] = None
    siif_gastos_cta_cte: Optional[str] = None
    siif_contabilidad_cta_cte: Optional[str] = None
    sgf_cta_cte: Optional[str] = None
    siif_cta_cte: Optional[str] = None
    icaro_cta_cte: Optional[str] = None


# -------------------------------------------------
class CtasCtesDocument(CtasCtesReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class CtasCtesFullFilter(BaseFilterParams):
    map_to: Optional[str] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class CtasCtesLiteFilter(CamelModel):
    query_filter: str = ""
    map_to: Optional[str] = None
    # Aquí podrías añadir: incluir_detalles: bool = False
