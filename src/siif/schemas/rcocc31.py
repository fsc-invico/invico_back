__all__ = [
    "Rcocc31Report",
    "Rcocc31Document",
    "Rcocc31FullFilter",
    "Rcocc31LiteFilter",
    "Rcocc31SummarizedReport",
]

from datetime import datetime
from typing import Optional

from pydantic import (
    AliasChoices,
    BaseModel,
    Field,
)
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class Rcocc31Report(BaseModel):
    ejercicio: int
    mes: str
    fecha: datetime
    fecha_aprobado: datetime
    cta_contable: str
    nro_entrada: str
    nro_original: str
    auxiliar_1: str
    auxiliar_2: str
    tipo_comprobante: str
    creditos: float
    debitos: float
    saldo: float


# -------------------------------------------------
class Rcocc31Document(Rcocc31Report):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class Rcocc31FullFilter(BaseFilterParams):
    ejercicio: Optional[str] = None
    cta_contable: Optional[str] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class Rcocc31LiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[str] = None
    cta_contable: Optional[str] = None
    # Aquí podrías añadir: incluir_detalles: bool = False


# -------------------------------------------------
class Rcocc31SummarizedReport(BaseModel):
    ejercicio: Optional[int] = None
    mes: Optional[str] = None
    cta_contable: Optional[str] = None
    nro_entrada: Optional[str] = None
    nro_original: Optional[str] = None
    auxiliar_1: Optional[str] = None
    auxiliar_2: Optional[str] = None
    tipo_comprobante: Optional[str] = None
    creditos: float
    debitos: float
    saldo: float
