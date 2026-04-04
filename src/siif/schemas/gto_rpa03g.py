__all__ = [
    "GtoRpa03gReport",
    "Rpa03gDocument",
    "Rpa03gFullFilter",
    "Rpa03gLiteFilter",
]

from datetime import datetime
from typing import Optional

from fastapi.params import Query
from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel
from .common import GrupoPartidaSIIF


# -------------------------------------------------
class GtoRpa03gReport(BaseModel):
    ejercicio: int
    mes: Optional[str] = None
    fecha: datetime
    nro_comprobante: Optional[str] = None
    importe: float
    grupo: Optional[GrupoPartidaSIIF] = None
    partida: Optional[str] = None
    nro_entrada: Optional[str] = None
    nro_origen: Optional[str] = None
    nro_expte: Optional[str] = None
    glosa: Optional[str] = None
    beneficiario: Optional[str] = None


# -------------------------------------------------
class Rpa03gDocument(GtoRpa03gReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class Rpa03gFullFilter(BaseFilterParams):
    ejercicio: Optional[str] = None
    grupo: Optional[str] = Query(
        None,
        description="ID del grupo. Para valores numéricos que son strings en DB, usar prefijo 'str:' (ej: str:2)",
        openapi_examples={
            "Ejemplo String": {"value": "str:2"},
            "Ejemplo Normal": {"value": "2"},
        },
    )


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class Rpa03gLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[str] = None
    grupo: Optional[str] = None
    # Aquí podrías añadir: incluir_detalles: bool = False
