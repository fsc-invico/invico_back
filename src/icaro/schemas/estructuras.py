"""
Author : Fernando Corrales <fscpython@gmail.com>
Date   : 20-jun-2025
Purpose: Unified schema for Estructura (Prog + Subprog + Proy + Act) to be used in the future.
"""

__all__ = [
    "EstructurasReport",
    "EstructurasDocument",
    "EstructurasFilter",
]


from datetime import datetime, timezone
from typing import Optional

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
class EstructurasFilter(BaseFilterParams):
    nro_estructura: Optional[str] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class Rf602LiteFilter(CamelModel):
    query_filter: str = ""
    nro_estructura: Optional[str] = None
    # Aquí podrías añadir: incluir_detalles: bool = False
