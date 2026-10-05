__all__ = [
    "HonorariosReport",
    "HonorariosDocument",
    "HonorariosFullFilter",
    "HonorariosLiteFilter",
    "HonorariosUpdate",
]

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class HonorariosReport(BaseModel):
    ejercicio: int
    mes: str
    fecha: datetime
    nro_comprobante: str
    tipo: str
    cta_cte: Optional[str] = None
    cuit: Optional[str] = None
    nombre_completo: str
    actividad: str
    partida: str
    importe_bruto: float
    iibb: float
    lp: float
    sellos: float
    seguro: float
    otras_retenciones: float
    anticipo: float
    descuento: float
    mutual: float
    embargo: float
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# -------------------------------------------------
class HonorariosDocument(HonorariosReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# -------------------------------------------------
class HonorariosFullFilter(BaseFilterParams):
    ejercicio: Optional[str] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class HonorariosLiteFilter(CamelModel):
    query_filter: str = ""
    # ejercicio: Optional[str] = None
    # Aquí podrías añadir: incluir_detalles: bool = False


# -------------------------------------------------
class HonorariosBatchCreate(BaseModel):
    honorarios: List[HonorariosReport]


# -------------------------------------------------
class HonorariosUpdate(BaseModel):
    """Payload para actualizar en bloque todos los registros de un comprobante.

    El identificador (nro_comprobante) viene en la path de la ruta y el
    updated_at lo asigna el servidor, por eso no forman parte de este schema.
    """

    ejercicio: Optional[int] = None
    mes: Optional[str] = None
    fecha: Optional[datetime] = None
    tipo: str
    cta_cte: Optional[str] = None
    partida: Optional[str] = None
