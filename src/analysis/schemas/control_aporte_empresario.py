__all__ = [
    "ControlAporteEmpresarioReport",
    "ControlAporteEmpresarioDocument",
    "ControlAporteEmpresarioFilter",
    "ControlAporteEmpresarioLiteFilter",
]

from typing import Optional

from pydantic import BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class ControlAporteEmpresarioReport(BaseModel):
    ejercicio: int
    mes: str
    cta_cte: str
    recurso: float
    retencion: float


# -------------------------------------------------
class ControlAporteEmpresarioDocument(ControlAporteEmpresarioReport):
    id: PydanticObjectId = Field(alias="_id")


# -------------------------------------------------
class ControlAporteEmpresarioFilter(BaseFilterParams):
    ejercicio: Optional[int] = None


# -------------------------------------------------
class ControlAporteEmpresarioLiteFilter(CamelModel):
    ejercicio: int
    # Aquí podrías añadir: incluir_detalles: bool = False
