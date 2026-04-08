__all__ = [
    "CertificadosReport",
    "CertificadosDocument",
    "CertificadosFullFilter",
    "CertificadosLiteFilter",
]

from datetime import datetime, timezone
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class CertificadosReport(BaseModel):
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
    origen: str
    id_carga: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# -------------------------------------------------
class CertificadosDocument(CertificadosReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class CertificadosFullFilter(BaseFilterParams):
    pass


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class CertificadosLiteFilter(CamelModel):
    query_filter: str = ""
    # Aquí podrías añadir: incluir_detalles: bool = False
