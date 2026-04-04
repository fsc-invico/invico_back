__all__ = [
    "Rvicon03Report",
    "Rvicon03Document",
    "Rvicon03FullFilter",
    "Rvicon03LiteFilter",
]


from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class Rvicon03Report(BaseModel):
    ejercicio: int
    nivel: str
    desc_nivel: Optional[str] = None
    cta_contable: str
    desc_cta_contable: Optional[str] = None
    saldo_inicial: float
    debe: float
    haber: float
    ajuste_debe: float
    ajuste_haber: float
    fondos_debe: float
    fondos_haber: float
    saldo_final: float


# -------------------------------------------------
class Rvicon03Document(Rvicon03Report):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class Rvicon03FullFilter(BaseFilterParams):
    ejercicio: Optional[str] = None
    # nivel: Optional[str] = None
    # cta_contable: Optional[str] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class Rvicon03LiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[str] = None
    # Aquí podrías añadir: incluir_detalles: bool = False
