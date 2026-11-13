__all__ = [
    "ControlDebitosBancariosReport",
    "ControlDebitosBancariosDocument",
    "ControlDebitosBancariosFilter",
    "ControlDebitosBancariosLiteFilter",
    "ControlDebitosBancariosGenerateFilter",
]


from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class ControlDebitosBancariosReport(BaseModel):
    ejercicio: int
    mes: str
    cta_cte: str
    ejecutado_siif: float
    debitos_sscc: float
    diferencia: float


# -------------------------------------------------
class ControlDebitosBancariosDocument(ControlDebitosBancariosReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para el Get All / Delete (Con limit/offset)
# -------------------------------------------------
class ControlDebitosBancariosFilter(BaseFilterParams):
    ejercicio: Optional[int] = None
    fuente: Optional[int] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class ControlDebitosBancariosLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[int] = None


# Filtro del endpoint /generate: el backend arma el cruce on-demand
# -------------------------------------------------
class ControlDebitosBancariosGenerateFilter(CamelModel):
    ejercicio: int
