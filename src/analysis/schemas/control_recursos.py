__all__ = [
    "ControlRecursosReport",
    "ControlRecursosDocument",
    "ControlRecursosFullFilter",
    "ControlRecursosLiteFilter",
]


from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class ControlRecursosReport(BaseModel):
    ejercicio: int
    mes: str
    cta_cte: str
    grupo: str
    recursos_siif: float
    depositos_banco: float


# -------------------------------------------------
class ControlRecursosDocument(ControlRecursosReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class ControlRecursosFullFilter(BaseFilterParams):
    ejercicio: Optional[int] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class ControlRecursosLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[int] = None
    # Aquí podrías añadir: incluir_detalles: bool = False
