__all__ = [
    "Rfondo07tpReport",
    "Rfondo07tpDocument",
    "Rfondo07tpFullFilter",
    "Rfondo07tpLiteFilter",
]

from datetime import datetime
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel
from .common import TipoComprobanteSIIF


# -------------------------------------------------
class Rfondo07tpReport(BaseModel):
    ejercicio: int
    mes: str
    fecha: datetime
    tipo_comprobante: str
    nro_comprobante: str
    nro_fondo: str
    glosa: str
    ingresos: float
    egresos: float
    saldo: float


# -------------------------------------------------
class Rfondo07tpDocument(Rfondo07tpReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class Rfondo07tpFullFilter(BaseFilterParams):
    ejercicio: Optional[int] = None
    tipo_comprobante: TipoComprobanteSIIF = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class Rfondo07tpLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[int] = None
    tipo_comprobante: TipoComprobanteSIIF = None
    # Aquí podrías añadir: incluir_detalles: bool = False
