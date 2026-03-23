__all__ = [
    "BancoINVICOSdoFinalReport",
    "BancoINVICOSdoFinalDocument",
    "BancoINVICOSdoFinalFullFilter",
    "BancoINVICOSdoFinalLiteFilter",
]


from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class BancoINVICOSdoFinalReport(BaseModel):
    ejercicio: int
    cta_cte: str
    desc_cta_cte: str
    desc_banco: str
    saldo: float


# -------------------------------------------------
class BancoINVICOSdoFinalDocument(BancoINVICOSdoFinalReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class BancoINVICOSdoFinalFullFilter(BaseFilterParams):
    ejercicio: Optional[int] = None
    # cta_cte: Optional[str] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class BancoINVICOSdoFinalLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[int] = None
    # Aquí podrías añadir: incluir_detalles: bool = False
