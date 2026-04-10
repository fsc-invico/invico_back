__all__ = [
    "ResumenRendObrasReport",
    "ResumenRendObrasDocument",
    "ResumenRendObrasFullFilter",
    "ResumenRendObrasLiteFilter",
]


from datetime import datetime
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field, NonNegativeFloat
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel
from .common import Origen


# -------------------------------------------------
class ResumenRendObrasReport(BaseModel):
    origen: Origen
    ejercicio: int
    mes: str
    fecha: datetime
    beneficiario: str
    cod_obra: str
    desc_obra: str
    destino: str
    libramiento: str
    importe_bruto: NonNegativeFloat
    gcias: NonNegativeFloat
    sellos: NonNegativeFloat
    tl: NonNegativeFloat
    iibb: NonNegativeFloat
    suss: NonNegativeFloat
    seguro: NonNegativeFloat
    salud: NonNegativeFloat
    mutual: NonNegativeFloat
    otras: NonNegativeFloat
    retenciones: NonNegativeFloat
    importe_neto: NonNegativeFloat
    movimiento: str


# -------------------------------------------------
class ResumenRendObrasDocument(ResumenRendObrasReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class ResumenRendObrasFullFilter(BaseFilterParams):
    origen: Optional[str] = None
    ejercicio: Optional[str] = None
    # beneficiario: Optional[str] = None
    # cta_cte: Optional[str] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class ResumenRendObrasLiteFilter(CamelModel):
    query_filter: str = ""
    origen: Optional[str] = None
    ejercicio: Optional[str] = None
    # beneficiario: Optional[str] = None
    # cta_cte: Optional[str] = None
