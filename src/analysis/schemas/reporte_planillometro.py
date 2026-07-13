__all__ = [
    "ReportePlanillometroFilter",
    "ReportePlanillometroReport",
    "ReportePlanillometroDocument",
    "ReportePlanillometroLiteFilter",
]


import datetime as dt
from typing import Optional

from pydantic import BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import CamelModel


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
    alta: int
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
class ReportePlanillometroFilter(CamelModel):
    limit: Optional[int] = Field(100, gte=0)
    ejercicio: Optional[str] = None
    desagregar_desc_subprog: bool = True
    desagregar_obras: bool = False
    desagregar_partida: bool = False
    desagregar_fuente: bool = False
    agregar_acum_2008: bool = True
    ultimos_ejercicios: Optional[int] = None
    date_up_to: Optional[dt.date] = None
    include_pa6: bool = False


# -------------------------------------------------
class ReportePlanillometroLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[str] = None
    # Aquí podrías añadir: incluir_detalles: bool = False
