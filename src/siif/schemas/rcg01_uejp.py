__all__ = [
    "Rcg01UejpReport",
    "Rcg01UejpDocument",
    "Rcg01UejpFullFilter",
    "Rcg01UejpLiteFilter",
]

from datetime import datetime
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel
from .common import FuenteFinanciamientoSIIF


# -------------------------------------------------
class Rcg01UejpReport(BaseModel):
    ejercicio: int
    mes: str
    fecha: datetime
    nro_comprobante: str
    importe: float
    fuente: FuenteFinanciamientoSIIF
    cta_cte: str
    cuit: str
    nro_expte: str
    nro_fondo: Optional[str] = None
    nro_entrada: Optional[str] = None
    nro_origen: Optional[str] = None
    clase_reg: str
    clase_mod: str
    clase_gto: str
    beneficiario: str
    es_comprometido: bool
    es_verificado: bool
    es_aprobado: bool
    es_pagado: bool


# -------------------------------------------------
class Rcg01UejpDocument(Rcg01UejpReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class Rcg01UejpFullFilter(BaseFilterParams):
    ejercicio: Optional[str] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class Rcg01UejpLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[str] = None
    # Aquí podrías añadir: incluir_detalles: bool = False
