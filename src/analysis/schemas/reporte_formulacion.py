__all__ = [
    "ReporteFormulacionReport",
    "ReporteFormulacionDocument",
    "ReporteFormulacionFilter",
    "ReporteFormulacionLiteFilter",
]


from pydantic import BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class ReporteFormulacionReport(BaseModel):
    ejercicio: int
    estructura: str
    programa: str
    desc_programa: str
    desc_subprograma: str
    desc_proyecto: str
    desc_actividad: str
    grupo: str
    partida: str
    fuente: str
    credito_original: float
    credito_vigente: float
    comprometido: float
    ordenado: float
    saldo: float


# -------------------------------------------------
class ReporteFormulacionDocument(ReporteFormulacionReport):
    id: PydanticObjectId = Field(alias="_id")


# -------------------------------------------------
class ReporteFormulacionFilter(BaseFilterParams):
    ejercicio: int


# -------------------------------------------------
class ReporteFormulacionLiteFilter(CamelModel):
    ejercicio: int
