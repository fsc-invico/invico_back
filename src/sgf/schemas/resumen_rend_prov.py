__all__ = [
    "ResumenRendProvReport",
    "ResumenRendProvDocument",
    "ResumenRendProvFullFilter",
    "ResumenRendProvLiteFilter",
]


from datetime import datetime
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field, NonNegativeFloat
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel
from .common import Origen


# -------------------------------------------------
class ResumenRendProvReport(BaseModel):
    origen: Origen
    ejercicio: int
    mes: str
    fecha: datetime
    beneficiario: str
    destino: str
    libramiento_sgf: str
    movimiento: str
    cta_cte: str
    importe_bruto: NonNegativeFloat
    gcias: NonNegativeFloat
    sellos: NonNegativeFloat
    iibb: NonNegativeFloat
    suss: NonNegativeFloat
    invico: NonNegativeFloat
    seguro: NonNegativeFloat
    salud: NonNegativeFloat
    mutual: NonNegativeFloat
    otras: NonNegativeFloat
    retenciones: NonNegativeFloat
    importe_neto: NonNegativeFloat


# -------------------------------------------------
class ResumenRendProvDocument(ResumenRendProvReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class ResumenRendProvFullFilter(BaseFilterParams):
    origen: Optional[str] = None
    ejercicio: Optional[str] = None
    # beneficiario: Optional[str] = None
    # cta_cte: Optional[str] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class ResumenRendProvLiteFilter(CamelModel):
    query_filter: str = ""
    origen: Optional[str] = None
    ejercicio: Optional[str] = None
    # beneficiario: Optional[str] = None
    # cta_cte: Optional[str] = None
