__all__ = [
    "SaldosBarriosEvolucionReport",
    "SaldosBarriosEvolucionDocument",
    "SaldosBarriosEvolucionFullFilter",
    "SaldosBarriosEvolucionLiteFilter",
]


from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class SaldosBarriosEvolucionReport(BaseModel):
    ejercicio: int
    cod_barrio: str
    barrio: str
    saldo_inicial: float
    amortizacion: float
    cambios: float
    saldo_final: float


# -------------------------------------------------
class SaldosBarriosEvolucionDocument(SaldosBarriosEvolucionReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class SaldosBarriosEvolucionFullFilter(BaseFilterParams):
    ejercicio: Optional[str] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class SaldosBarriosEvolucionLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[str] = None
