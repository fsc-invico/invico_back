__all__ = [
    "InformeContableReport",
    "InformeContableDocument",
    "InformeContableFullFilter",
    "InformeContableLiteFilter",
]

from datetime import datetime, timezone
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class InformeContableReport(BaseModel):
    ejercicio: int
    beneficiario: str
    desc_obra: str
    nro_certificado: str
    monto_certificado: float
    fondo_reparo: Optional[float] = None
    importe_bruto: float
    iibb: Optional[float] = None
    lp: Optional[float] = None
    suss: Optional[float] = None
    gcias: Optional[float] = None
    invico: Optional[float] = None
    otras_retenciones: Optional[float] = None
    importe_neto: float
    id_carga: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# -------------------------------------------------
class InformeContableDocument(InformeContableReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class InformeContableFullFilter(BaseFilterParams):
    pass


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class InformeContableLiteFilter(CamelModel):
    query_filter: str = ""
    # Aquí podrías añadir: incluir_detalles: bool = False
