__all__ = [
    "ControlHonorariosSIIFvsSlaveReport",
    "ControlHonorariosSIIFvsSlaveDocument",
    "ControlHonorariosSGFvsSlaveReport",
    "ControlHonorariosSGFvsSlaveDocument",
    "ControlHonorariosFullFilter",
    "ControlHonorariosLiteFilter",
]

from typing import Optional

from pydantic import BaseModel, Field
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
    id: PydanticObjectId = Field(alias="_id")


# -------------------------------------------------
class ControlHonorariosSGFvsSlaveReport(BaseModel):
    ejercicio: int
    mes: str
    cta_cte: str
    beneficiario: str
    importe_bruto: float
    iibb: float
    sellos: float
    seguro: float
    otras: float
    retenciones: float
    importe_neto: float


# -------------------------------------------------
class ControlHonorariosSGFvsSlaveDocument(ControlHonorariosSGFvsSlaveReport):
    id: PydanticObjectId = Field(alias="_id")


# -------------------------------------------------
class ControlHonorariosFullFilter(BaseFilterParams):
    ejercicio: Optional[int] = None


# -------------------------------------------------
class ControlHonorariosLiteFilter(CamelModel):
    ejercicio: int
    # Aquí podrías añadir: incluir_detalles: bool = False
