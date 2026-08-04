__all__ = [
    "ReporteFormulacionReport",
    "ReporteFormulacionDocument",
    "ReporteFormulacionFilter",
    "ReporteFormulacionLiteFilter",
]

from typing import Optional

from pydantic import BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import CamelModel


# -------------------------------------------------
class ReporteFormulacionReport(BaseModel):
    desc_programa: Optional[str] = None
    desc_subprograma: Optional[str] = None
    desc_proyecto: Optional[str] = None
    desc_actividad: Optional[str] = None
    estructura: Optional[str] = None
    alta: str
    ejercicio: int
    ejecucion: float
    acum: float
    en_curso: float
    terminadas_ant: float
    terminadas_actual: float


# -------------------------------------------------
class ReporteFormulacionDocument(ReporteFormulacionReport):
    id: PydanticObjectId = Field(alias="_id")


# -------------------------------------------------
class ReporteFormulacionLiteFilter(CamelModel):
    ejercicio: int


# -------------------------------------------------
class ReporteFormulacionFilter(ReporteFormulacionLiteFilter):
    limit: Optional[int] = Field(default=100, ge=0)
