__all__ = [
    "ControlViaticosRendicionReport",
    "ControlViaticosRendicionDocument",
    "ControlViaticosFilter",
    "ControlViaticosLiteFilter",
    "ControlViaticosGenerateFilter",
]


from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class ControlViaticosRendicionReport(BaseModel):
    ejercicio: int
    # mes: str
    nro_expte: str
    siif_anticipo: float
    siif_rendicion: float
    siif_reversion: float
    siif_saldo_anticipo: float
    siif_reembolso: float
    siif_gasto_total: float
    sscc_anticipo: float
    sscc_reversion: float
    sscc_reembolso: float
    sscc_gasto_total: float
    dif_gasto_total: float


# -------------------------------------------------
class ControlViaticosRendicionDocument(ControlViaticosRendicionReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# -------------------------------------------------
class ControlViaticosFilter(BaseFilterParams):
    ejercicio: Optional[int] = None
    fuente: Optional[int] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class ControlViaticosLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[int] = None


# Filtro del endpoint /generate: el backend arma el cruce on-demand
# -------------------------------------------------
class ControlViaticosGenerateFilter(CamelModel):
    ejercicio: int
