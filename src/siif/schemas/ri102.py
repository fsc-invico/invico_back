__all__ = [
    "Ri102Report",
    "Ri102Document",
    "Ri102FullFilter",
    "Ri102LiteFilter",
]

from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class Ri102Report(BaseModel):
    ejercicio: int
    tipo: str
    clase: str
    cod_recurso: str
    desc_recurso: str
    fuente: str
    org_fin: str
    ppto_inicial: float
    ppto_modif: float
    ppto_vigente: float
    ingreso: float
    saldo: float


# -------------------------------------------------
class Ri102Document(Ri102Report):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class Ri102FullFilter(BaseFilterParams):
    ejercicio: Optional[int] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class Ri102LiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[int] = None
    # Aquí podrías añadir: incluir_detalles: bool = False
