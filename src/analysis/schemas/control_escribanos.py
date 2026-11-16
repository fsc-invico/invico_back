__all__ = [
    "ControlEscribanosSGFvsSSCCReport",
    "ControlEscribanosSGFvsSSCCDocument",
    "ControlEscribanosSIIFvsSGFReport",
    "ControlEscribanosSIIFvsSGFDocument",
    "ControlEscribanosFullFilter",
    "ControlEscribanosLiteFilter",
    "ControlEscribanosGenerateFilter",
    "ControlEscribanosFilter",
]

from typing import Optional

from pydantic import (
    AliasChoices,
    BaseModel,
    Field,
)
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# Salida real de compute_control_sgf_vs_sscc: cruce agregado por
# [ejercicio, mes] con el neto de cada sistema y su diferencia. Se
# persisten TODOS los meses, incluidos los que cuadran (dif=0): si solo
# se guardaran las filas con diferencia material, un ejercicio cerrado
# no tendría snapshot y la pestaña del front mostraría "sin resultados".
# -------------------------------------------------
class ControlEscribanosSGFvsSSCCReport(BaseModel):
    ejercicio: int
    mes: str
    sgf_importe_neto: float
    sscc_importe_neto: float
    dif_importe_neto: float


# -------------------------------------------------
class ControlEscribanosSGFvsSSCCDocument(ControlEscribanosSGFvsSSCCReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Salida real de compute_control_siif_vs_sgf: cruce outer por
# [ejercicio, mes, cuit] con la carga/pagos FEI del SIIF, los pagos del
# SGF y la diferencia entre ambos (se conservan todas las filas).
# -------------------------------------------------
class ControlEscribanosSIIFvsSGFReport(BaseModel):
    ejercicio: Optional[int] = None
    mes: Optional[str] = None
    cuit: Optional[str] = None
    carga_fei: Optional[float] = None
    pagos_fei: Optional[float] = None
    fei_impagos: Optional[float] = None
    pagos_sgf: Optional[float] = None
    dif_pagos: Optional[float] = None


# -------------------------------------------------
class ControlEscribanosSIIFvsSGFDocument(ControlEscribanosSIIFvsSGFReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para el Get All / Delete (Con limit/offset)
# -------------------------------------------------
class ControlEscribanosFullFilter(BaseFilterParams):
    ejercicio: Optional[int] = None


# Este se usa para el Export y Borrar (Sin limit/offset)
# -------------------------------------------------
class ControlEscribanosLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[int] = None


# Filtro de los endpoints /generate*: el backend arma el cruce on-demand
# -------------------------------------------------
class ControlEscribanosGenerateFilter(CamelModel):
    ejercicio: int


# Filtro legado (scripts originales con rango de ejercicios)
# -------------------------------------------------
class ControlEscribanosFilter(BaseFilterParams):
    ejercicio: Optional[int] = None
    fuente: Optional[int] = None
