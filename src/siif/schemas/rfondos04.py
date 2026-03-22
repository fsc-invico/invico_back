__all__ = [
    "Rfondos04Report",
    "Rfondos04Document",
    "Rfondos04FullFilter",
    "Rfondos04LiteFilter",
]

from datetime import datetime
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel
from .common import TipoComprobanteSIIF


# -------------------------------------------------
class Rfondos04Report(BaseModel):
    ejercicio: int
    mes: str
    fecha: datetime
    tipo_comprobante: str
    nro_comprobante: str
    nro_fondo: str
    glosa: str
    importe: float
    saldo_c01: float
    saldo_asiento: float


# -------------------------------------------------
class Rfondos04Document(Rfondos04Report):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class Rfondos04FullFilter(BaseFilterParams):
    ejercicio: Optional[int] = None
    tipo_comprobante: TipoComprobanteSIIF = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class Rfondos04LiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[int] = None
    tipo_comprobante: TipoComprobanteSIIF = None
    # Aquí podrías añadir: incluir_detalles: bool = False
