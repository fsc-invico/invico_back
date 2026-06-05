__all__ = [
    "ControlIcaroCompletoParams",
    "ControlIcaroCompletoSyncParams",
    "ControlIcaroAnualReport",
    "ControlIcaroAnualDocument",
    "ControlIcaroAnualFullFilter",
    "ControlIcaroAnualLiteFilter",
    "ControlIcaroComprobantesReport",
    "ControlIcaroComprobantesDocument",
    "ControlIcaroComprobantesFilter",
    "ControlIcaroPa6Report",
    "ControlIcaroPa6Document",
    "ControlIcaroPa6Filter",
]

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# --------------------------------------------------
class ControlIcaroCompletoParams(BaseModel):
    ejercicio_desde: int = Field(default=date.today().year)
    ejercicio_hasta: int = Field(default=date.today().year)

    @field_validator("ejercicio_desde", "ejercicio_hasta")
    @classmethod
    def validate_ejercicio_range(cls, v: int) -> int:
        current_year = date.today().year
        if not (2010 <= v <= current_year):
            raise ValueError(f"El ejercicio debe estar entre 2010 y {current_year}")
        return v

    @model_validator(mode="after")
    def check_range(self) -> "ControlIcaroCompletoParams":
        if self.ejercicio_hasta < self.ejercicio_desde:
            raise ValueError("Ejercicio Desde no puede ser menor que Ejercicio Hasta")
        return self


# --------------------------------------------------
class ControlIcaroCompletoSyncParams(ControlIcaroCompletoParams):
    siif_username: Optional[str] = None
    siif_password: Optional[str] = None


# -------------------------------------------------
class ControlIcaroAnualReport(BaseModel):
    ejercicio: int
    estructura: Optional[str] = None
    fuente: int
    ejecucion_siif: float
    ejecucion_icaro: float
    diferencia: float
    desc_actividad: Optional[str] = None
    desc_programa: Optional[str] = None
    desc_subprograma: Optional[str] = None
    desc_proyecto: Optional[str] = None


# -------------------------------------------------
class ControlIcaroAnualDocument(ControlIcaroAnualReport):
    id: PydanticObjectId = Field(alias="_id")


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class ControlIcaroAnualFullFilter(BaseFilterParams):
    ejercicio: Optional[int] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class ControlIcaroAnualLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[str] = None
    # Aquí podrías añadir: incluir_detalles: bool = False


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class ControlIcaroComprobantesReport(BaseModel):
    ejercicio: int
    siif_nro: Optional[str] = None
    icaro_nro: Optional[str] = None
    err_nro: bool
    siif_tipo: Optional[str] = None
    icaro_tipo: Optional[str] = None
    err_tipo: bool
    siif_fuente: Optional[str] = None
    icaro_fuente: Optional[str] = None
    err_fuente: bool
    siif_importe: Optional[float] = None
    icaro_importe: Optional[float] = None
    err_importe: bool
    siif_mes: Optional[str] = None
    icaro_mes: Optional[str] = None
    err_mes: bool
    siif_cta_cte: Optional[str] = None
    icaro_cta_cte: Optional[str] = None
    err_cta_cte: bool
    siif_cuit: Optional[str] = None
    icaro_cuit: Optional[str] = None
    err_cuit: bool
    siif_partida: Optional[str] = None
    icaro_partida: Optional[str] = None
    err_partida: bool


# -------------------------------------------------
class ControlIcaroComprobantesDocument(ControlIcaroComprobantesReport):
    id: PydanticObjectId = Field(alias="_id")


# -------------------------------------------------
class ControlIcaroComprobantesFilter(BaseFilterParams):
    ejercicio: Optional[int] = None
    fuente: Optional[int] = None


# -------------------------------------------------
class ControlIcaroPa6Report(BaseModel):
    ejercicio: int
    siif_nro_fondo: Optional[str] = None
    icaro_nro_fondo: Optional[str] = None
    err_nro_fondo: bool
    siif_mes_pa6: Optional[str] = None
    icaro_mes_pa6: Optional[str] = None
    err_mes_pa6: bool
    siif_importe_pa6: Optional[float] = None
    icaro_importe_pa6: Optional[float] = None
    err_importe_pa6: bool
    siif_nro_reg: Optional[str] = None
    icaro_nro_reg: Optional[str] = None
    err_nro_reg: bool
    siif_mes_reg: Optional[str] = None
    icaro_mes_reg: Optional[str] = None
    err_mes_reg: bool
    siif_importe_reg: Optional[float] = None
    icaro_importe_reg: Optional[float] = None
    err_importe_reg: bool
    siif_tipo: Optional[str] = None
    icaro_tipo: Optional[str] = None
    err_tipo: bool
    siif_fuente: Optional[str] = None
    icaro_fuente: Optional[str] = None
    err_fuente: bool
    siif_cta_cte: Optional[str] = None
    icaro_cta_cte: Optional[str] = None
    err_cta_cte: bool
    siif_cuit: Optional[str] = None
    icaro_cuit: Optional[str] = None
    err_cuit: bool


# -------------------------------------------------
class ControlIcaroPa6Document(ControlIcaroPa6Report):
    id: PydanticObjectId = Field(alias="_id")


# -------------------------------------------------
class ControlIcaroPa6Filter(BaseFilterParams):
    ejercicio: Optional[int] = None
