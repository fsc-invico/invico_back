__all__ = [
    "ControlHaberesReport",
    "ControlHaberesDocument",
    "ControlHaberesFilter",
    "ControlHaberesLiteFilter",
]

from typing import Optional

from pydantic import BaseModel, Field
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
    id: PydanticObjectId = Field(alias="_id")


# -------------------------------------------------
class ControlHaberesFilter(BaseFilterParams):
    ejercicio: Optional[int] = None


# -------------------------------------------------
class ControlHaberesLiteFilter(CamelModel):
    ejercicio: int
    # Aquí podrías añadir: incluir_detalles: bool = False
