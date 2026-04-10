__all__ = [
    "ResumenRendObrasReport",
    "ResumenRendObrasDocument",
    "ResumenRendObrasFullFilter",
    "ResumenRendObrasLiteFilter",
]

from datetime import datetime, timezone
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class ResumenRendObrasReport(BaseModel):
    ejercicio: Optional[int] = None
    mes: Optional[str] = None
    fecha: Optional[datetime] = None
    libramiento: Optional[str] = None
    beneficiario: Optional[str] = None
    desc_obra: Optional[str] = None
    destino: Optional[str] = None
    importe_bruto: float
    gcias: Optional[float] = None
    sellos: Optional[float] = None
    tl: Optional[float] = None
    iibb: Optional[float] = None
    suss: Optional[float] = None
    seguro: Optional[float] = None
    salud: Optional[float] = None
    mutual: Optional[float] = None
    importe_neto: Optional[float] = None
    movimiento: Optional[str] = None
    origen: Optional[str] = None
    id_carga: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# -------------------------------------------------
class ResumenRendObrasDocument(ResumenRendObrasReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class ResumenRendObrasFullFilter(BaseFilterParams):
    pass


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class ResumenRendObrasLiteFilter(CamelModel):
    query_filter: str = ""
    # Aquí podrías añadir: incluir_detalles: bool = False
