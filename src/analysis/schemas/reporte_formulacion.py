__all__ = [
    "ReporteFormulacionPlanillometroReport",
    "ReporteFormulacionRecursosReport",
    "ReporteFormulacionGastosReport",
    "ReporteFormulacionCargaReport",
    "ReporteFormulacionDocument",
    "ReporteFormulacionFilter",
    "ReporteFormulacionLiteFilter",
]

from typing import Optional

from pydantic import BaseModel, Field, NonNegativeFloat
from pydantic_mongo import PydanticObjectId

from ...utils import CamelModel


# -------------------------------------------------
class ReporteFormulacionPlanillometroReport(BaseModel):
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
class ReporteFormulacionRecursosReport(BaseModel):
    ejercicio: int
    tipo: str
    clase: str
    cod_recurso: str
    desc_recurso: str
    fuente: str
    org_fin: str
    ppto_inicial: float
    ppto_modif: float
    ppto_vigente: float
    ingreso: float
    saldo: float


# -------------------------------------------------
class ReporteFormulacionGastosReport(BaseModel):
    ejercicio: int
    estructura: str
    partida: str
    fuente: int
    desc_programa: str
    desc_subprograma: str
    desc_proyecto: str
    desc_actividad: str
    programa: int
    grupo: str
    credito_original: NonNegativeFloat
    credito_vigente: NonNegativeFloat
    comprometido: NonNegativeFloat
    ordenado: NonNegativeFloat
    saldo: float


# -------------------------------------------------
class ReporteFormulacionCargaReport(BaseModel):
    ejercicio: int
    estructura: str
    fuente: str
    programa: str
    desc_programa: str
    subprograma: str
    desc_subprograma: str
    proyecto: str
    desc_proyecto: str
    actividad: str
    desc_actividad: str
    grupo: str
    partida: str
    formulado: float


# -------------------------------------------------
class ReporteFormulacionDocument(ReporteFormulacionPlanillometroReport):
    id: PydanticObjectId = Field(alias="_id")


# -------------------------------------------------
class ReporteFormulacionLiteFilter(CamelModel):
    ejercicio: int


# -------------------------------------------------
class ReporteFormulacionFilter(ReporteFormulacionLiteFilter):
    limit: Optional[int] = Field(default=100, ge=0)
