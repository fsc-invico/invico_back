__all__ = [
    "ControlHonorariosSIIFvsSlaveReport",
    "ControlHonorariosSIIFvsSlaveDocument",
    "ControlHonorariosSGFvsSlaveReport",
    "ControlHonorariosSGFvsSlaveDocument",
    "ControlHonorariosFullFilter",
    "ControlHonorariosLiteFilter",
    "ControlHonorariosGenerateFilter",
]

from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class ControlHonorariosSIIFvsSlaveReport(BaseModel):
    ejercicio: int
    siif_nro: str
    slave_nro: str
    err_nro: bool
    siif_importe: float
    slave_importe: float
    err_importe: bool
    siif_mes: str
    slave_mes: str
    err_mes: bool


# -------------------------------------------------
class ControlHonorariosSIIFvsSlaveDocument(ControlHonorariosSIIFvsSlaveReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Salida real de compute_control_sgf_vs_slave: cruce agregado por
# [ejercicio, mes, cta_cte, beneficiario] con los importes de ambos
# sistemas y sus diferencias (solo se conservan filas con diferencia).
# -------------------------------------------------
class ControlHonorariosSGFvsSlaveReport(BaseModel):
    ejercicio: int
    mes: str
    cta_cte: str
    beneficiario: str
    sgf_importe_bruto: float
    slave_importe_bruto: float
    dif_importe_bruto: float
    sgf_importe_neto: float
    slave_importe_neto: float
    dif_importe_neto: float


# -------------------------------------------------
class ControlHonorariosSGFvsSlaveDocument(ControlHonorariosSGFvsSlaveReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para el Get All / Delete (Con limit/offset)
# -------------------------------------------------
class ControlHonorariosFullFilter(BaseFilterParams):
    ejercicio: Optional[int] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class ControlHonorariosLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[int] = None
    # Aquí podrías añadir: incluir_detalles: bool = False


# Filtro de los endpoints /generate*: el backend arma el cruce on-demand
# -------------------------------------------------
class ControlHonorariosGenerateFilter(CamelModel):
    ejercicio: int
