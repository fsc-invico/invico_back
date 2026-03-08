__all__ = [
    "BancoINVICOReport",
    "BancoINVICODocument",
    "BancoINVICOFullFilter",
    "BancoINVICOLiteFilter",
]


from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class BancoINVICOReport(BaseModel):
    ejercicio: int
    mes: str
    fecha: datetime
    cta_cte: str
    movimiento: Optional[str] = None
    es_cheque: bool
    beneficiario: Optional[str] = None
    importe: float
    concepto: Optional[str] = None
    moneda: Optional[str] = None
    libramiento: Optional[str] = None
    cod_imputacion: str
    imputacion: str


# -------------------------------------------------
class BancoINVICODocument(BancoINVICOReport):
    id: PydanticObjectId = Field(alias="_id")


# Este se usa para la tabla (UI)
# -------------------------------------------------
class BancoINVICOFullFilter(BaseFilterParams):
    ejercicio: Optional[int] = None
    cta_cte: Optional[str] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class BancoINVICOLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[int] = None
    cta_cte: Optional[str] = None
