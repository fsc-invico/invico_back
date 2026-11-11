__all__ = [
    "ControlHaberesReport",
    "ControlHaberesDocument",
    "ControlHaberesFullFilter",
    "ControlHaberesLiteFilter",
    "ControlHaberesGenerateFilter",
]

from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class ControlHaberesReport(BaseModel):
    ejercicio: int
    mes: str
    ejecutado_siif: float
    pagado_sscc: float
    diferencia: float
    dif_acum: float


# -------------------------------------------------
class ControlHaberesDocument(ControlHaberesReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para el Get All / Delete (Con limit/offset)
# -------------------------------------------------
class ControlHaberesFullFilter(BaseFilterParams):
    ejercicio: Optional[int] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class ControlHaberesLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[int] = None
    # Aquí podrías añadir: incluir_detalles: bool = False


# Filtro del endpoint /generate: el backend arma el cruce on-demand
# -------------------------------------------------
class ControlHaberesGenerateFilter(CamelModel):
    ejercicio: int
