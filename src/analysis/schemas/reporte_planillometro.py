__all__ = [
    "ReportePlanillometroFullFilter",
    "ReportePlanillometroReport",
    "ReportePlanillometroDocument",
    "ReportePlanillometroLiteFilter",
    "ReportePlanillometroGenerateFilter",
]


from typing import Optional

from pydantic import BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class ReportePlanillometroReport(BaseModel):
    desc_programa: Optional[str] = None
    desc_subprograma: Optional[str] = None
    desc_proyecto: Optional[str] = None
    desc_actividad: Optional[str] = None
    estructura: Optional[str] = None
    partida: Optional[str] = None
    desc_obra: Optional[str] = None
    fuente: Optional[str] = None
    alta: str
    ejercicio: int
    ejecucion: float
    acum: float
    en_curso: float
    terminadas_ant: float
    terminadas_actual: float


# -------------------------------------------------
class ReportePlanillometroDocument(ReportePlanillometroReport):
    id: PydanticObjectId = Field(alias="_id")


# -------------------------------------------------
class ReportePlanillometroGenerateFilter(CamelModel):
    limit: Optional[int] = Field(100, ge=0)
    ejercicio: int
    desagregar_desc_subprog: bool = True
    desagregar_obras: bool = False
    desagregar_partida: bool = False
    desagregar_fuente: bool = False
    agregar_acum_2008: bool = True
    # ultimos_ejercicios: Optional[int] = None
    # date_up_to: Optional[dt.date] = None
    include_pa6: bool = False


# -------------------------------------------------
class ReportePlanillometroFullFilter(BaseFilterParams):
    ejercicio: Optional[str] = None


# -------------------------------------------------
class ReportePlanillometroLiteFilter(CamelModel):
    ejercicio: int
    # Aquí podrías añadir: incluir_detalles: bool = False
