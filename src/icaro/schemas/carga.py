__all__ = [
    "CargaReport",
    "CargaDocument",
    "CargaFullFilter",
    "CargaLiteFilter",
]

from datetime import datetime, timezone
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class CargaReport(BaseModel):
    ejercicio: int
    mes: str
    fecha: datetime
    id_carga: str
    nro_comprobante: str
    tipo: str
    fuente: str
    actividad: str
    partida: str
    cta_cte: str
    cuit: str
    importe: float
    fondo_reparo: float
    avance: float
    nro_certificado: Optional[str] = None
    desc_obra: str
    origen: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class CargaDocument(CargaReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# -------------------------------------------------
class CargaFullFilter(BaseFilterParams):
    ejercicio: Optional[str] = None
    # nro_comprobante: Optional[str] = None
    # cuit: Optional[str] = None
    # actividad: Optional[str] = None
    # desc_obra: Optional[str] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class CargaLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[str] = None
    # Aquí podrías añadir: incluir_detalles: bool = False
