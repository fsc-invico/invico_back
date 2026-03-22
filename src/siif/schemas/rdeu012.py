__all__ = [
    "Rdeu012Report",
    "Rdeu012Document",
    "Rdeu012FullFilter",
    "Rdeu012LiteFilter",
]

from datetime import date, datetime
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class Rdeu012Report(BaseModel):
    ejercicio: int
    mes: str
    fecha: datetime
    mes_hasta: str
    fuente: str
    cta_cte: str
    nro_comprobante: str
    importe: float
    saldo: float
    cuit: str
    beneficiario: str
    glosa: str
    nro_expte: Optional[str] = None
    nro_entrada: str
    nro_origen: str
    fecha_aprobado: datetime
    fecha_desde: datetime
    fecha_hasta: datetime
    org_fin: str


# -------------------------------------------------
class Rdeu012Document(Rdeu012Report):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class Rdeu012FullFilter(BaseFilterParams):
    mes_hasta: Optional[str] = Field(
        alias="mesAño", default=date.today().strftime("%m/%Y")
    )


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class Rdeu012LiteFilter(CamelModel):
    query_filter: str = ""
    mes_hasta: Optional[str] = Field(
        alias="mesAño", default=date.today().strftime("%m/%Y")
    )
    # Aquí podrías añadir: incluir_detalles: bool = False
