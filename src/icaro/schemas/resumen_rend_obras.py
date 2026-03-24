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
    id_carga: Optional[str] = None
    ejercicio: Optional[int] = None
    mes: Optional[str] = None
    fecha: Optional[datetime] = None
    origen: Optional[str] = None
    cod_obra: Optional[str] = None
    desc_obra: Optional[str] = None
    beneficiario: Optional[str] = None
    nro_libramiento_sgf: Optional[str] = None
    importe_bruto: float
    iibb: Optional[float] = None
    tl: Optional[float] = None
    sellos: Optional[float] = None
    suss: Optional[float] = None
    gcias: Optional[float] = None
    seguro: Optional[float] = None
    salud: Optional[float] = None
    mutual: Optional[float] = None
    importe_neto: Optional[float] = None
    destino: Optional[str] = None
    movimiento: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# -------------------------------------------------
class ResumenRendObrasDocument(ResumenRendObrasReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class ResumenRendObrasFullFilter(BaseFilterParams):
    ejercicio: Optional[int] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class ResumenRendObrasLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[int] = None
    # Aquí podrías añadir: incluir_detalles: bool = False
