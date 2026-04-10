__all__ = [
    "InformeContableReport",
    "InformeContableDocument",
    "InformeContableFullFilter",
    "InformeContableLiteFilter",
]


from datetime import datetime
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field, NonNegativeFloat
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel
from .common import Origen


# -------------------------------------------------
class InformeContableReport(BaseModel):
    origen: Origen
    ejercicio: int
    beneficiario: str
    cod_obra: str
    desc_obra: str
    nro_certificado: str
    monto_certificado: float
    fondo_reparo: float
    otros: float
    importe_bruto: NonNegativeFloat
    iibb: NonNegativeFloat
    lp: NonNegativeFloat
    suss: NonNegativeFloat
    gcias: NonNegativeFloat
    invico: NonNegativeFloat
    retenciones: NonNegativeFloat
    importe_neto: NonNegativeFloat


# -------------------------------------------------
class InformeContableDocument(InformeContableReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class InformeContableFullFilter(BaseFilterParams):
    ejercicio: Optional[str] = None
    # beneficiario: Optional[str] = None
    # cta_cte: Optional[str] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class InformeContableLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[str] = None
    # beneficiario: Optional[str] = None
    # cta_cte: Optional[str] = None
