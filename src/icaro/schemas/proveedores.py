__all__ = [
    "ProveedoresReport",
    "ProveedoresDocument",
    "ProveedoresFullFilter",
    "ProveedoresLiteFilter",
]

from datetime import datetime, timezone
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class ProveedoresReport(BaseModel):
    codigo: int
    desc_proveedor: str
    domicilio: Optional[str] = None
    localidad: Optional[str] = None
    telefono: Optional[str] = None
    cuit: str
    condicion_iva: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# -------------------------------------------------
class ProveedoresDocument(ProveedoresReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class ProveedoresFullFilter(BaseFilterParams):
    pass


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class ProveedoresLiteFilter(CamelModel):
    query_filter: str = ""
    # Aquí podrías añadir: incluir_detalles: bool = False
