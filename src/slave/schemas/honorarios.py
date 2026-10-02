__all__ = [
    "HonorariosReport",
    "HonorariosDocument",
    "HonorariosFullFilter",
    "HonorariosLiteFilter",
]

from datetime import datetime
from typing import List, Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class HonorariosReport(BaseModel):
    ejercicio: int
    mes: str
    fecha: datetime
    nro_comprobante: str
    tipo: str
    cta_cte: Optional[str] = None
    cuit: Optional[str] = None
    nombre_completo: str
    actividad: str
    partida: str
    importe_bruto: float
    iibb: float
    lp: float
    sellos: float
    seguro: float
    otras_retenciones: float
    anticipo: float
    descuento: float
    mutual: float
    embargo: float


# -------------------------------------------------
class HonorariosDocument(HonorariosReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# -------------------------------------------------
class HonorariosFullFilter(BaseFilterParams):
    ejercicio: Optional[str] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class HonorariosLiteFilter(CamelModel):
    query_filter: str = ""
    # ejercicio: Optional[str] = None
    # Aquí podrías añadir: incluir_detalles: bool = False


# -------------------------------------------------
class HonorariosBatchCreate(BaseModel):
    honorarios: List[HonorariosReport]
