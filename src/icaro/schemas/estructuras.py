"""
Author : Fernando Corrales <fscpython@gmail.com>
Date   : 20-jun-2025
Purpose: Unified schema for Estructura (Prog + Subprog + Proy + Act) to be used in the future.
"""

__all__ = [
    "EstructurasReport",
    "EstructurasDocument",
    "EstructurasFullFilter",
    "EstructurasLiteFilter",
    "EstructurasPivot",
]


from datetime import datetime, timezone

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class EstructurasReport(BaseModel):
    estructura: str  # Example: 11, 11-00, 11-00-02, 11-00-02-79 (all in the same field)
    desc_estructura: str  # Example: "Programa de Salud", "Subprograma de Salud", "Proyecto de Salud", "Actividad de Salud"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# -------------------------------------------------
class EstructurasDocument(EstructurasReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class EstructurasFullFilter(BaseFilterParams):
    pass


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class EstructurasLiteFilter(CamelModel):
    query_filter: str = ""
    # Aquí podrías añadir: incluir_detalles: bool = False


# -------------------------------------------------
class EstructurasPivot(BaseModel):
    programa: str
    desc_programa: str
    nro_desc_programa: str
    subprograma: str
    desc_subprograma: str
    nro_desc_subprograma: str
    proyecto: str
    desc_proyecto: str
    nro_desc_proyecto: str
    actividad: str
    desc_actividad: str
    nro_desc_actividad: str
