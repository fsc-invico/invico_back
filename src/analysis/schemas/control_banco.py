__all__ = [
    "ControlBancoParams",
    "ControlBancoSyncParams",
    "ControlBancoLiteFilter",
    "ControlBancoFullFilter",
    "ControlBancoCruzadoReport",
    "ControlBancoCruzadoDocument",
    "ControlBancoCruzadoLiteFilter",
    "ControlBancoCruzadoFullFilter",
    "ControlBancoSIIFReport",
    "ControlBancoSIIFDocument",
    "ControlBancoSIIFLiteFilter",
    "ControlBancoSIIFFullFilter",
    "ControlBancoSSCCReport",
    "ControlBancoSSCCDocument",
    "ControlBancoSSCCLiteFilter",
    "ControlBancoSSCCFullFilter",
]

import os
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel, get_sscc_cta_cte_path


# --------------------------------------------------
class ControlBancoParams(CamelModel):
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
    def check_range(self) -> "ControlBancoParams":
        if self.ejercicio_hasta < self.ejercicio_desde:
            raise ValueError("Ejercicio Desde no puede ser menor que Ejercicio Hasta")
        return self


# --------------------------------------------------
class ControlBancoSyncParams(ControlBancoParams):
    siif_username: Optional[str] = None
    siif_password: Optional[str] = None
    sscc_username: Optional[str] = None
    sscc_password: Optional[str] = None
    ctas_ctes_excel_path: Optional[str] = Field(
        default=os.path.join(get_sscc_cta_cte_path(), "cta_cte.xlsx"),
        description="Ruta al archivo Ctas Ctes EXCEL",
    )


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class ControlBancoLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[str] = None
    # Aquí podrías añadir: incluir_detalles: bool = False


# -------------------------------------------------
class ControlBancoFullFilter(BaseFilterParams):
    ejercicio: Optional[int] = None


# -------------------------------------------------
class ControlBancoCruzadoReport(BaseModel):
    ejercicio: int
    mes: str
    fecha: datetime
    clase: str
    cta_cte: str
    siif_importe: float
    sscc_importe: float
    diferencia: float


# -------------------------------------------------
class ControlBancoCruzadoDocument(ControlBancoCruzadoReport):
    id: PydanticObjectId = Field(alias="_id")


# -------------------------------------------------
class ControlBancoCruzadoFullFilter(BaseFilterParams):
    ejercicio: Optional[int] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class ControlBancoCruzadoLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[str] = None
    # Aquí podrías añadir: incluir_detalles: bool = False


# -------------------------------------------------
class ControlBancoSIIFReport(BaseModel):
    ejercicio: int
    fecha: datetime
    fecha_aprobado: datetime
    nro_entrada: str
    nro_original: str
    cta_contable: str
    creditos: float
    debitos: float
    saldo: float
    auxiliar_1: str
    auxiliar_2: str
    cta_cte: str
    desc_cta_contable: str
    clase: str


# -------------------------------------------------
class ControlBancoSIIFDocument(ControlBancoSIIFReport):
    id: PydanticObjectId = Field(alias="_id")


# -------------------------------------------------
class ControlBancoSIIFFullFilter(BaseFilterParams):
    ejercicio: Optional[int] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class ControlBancoSIIFLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[str] = None
    # Aquí podrías añadir: incluir_detalles: bool = False


# -------------------------------------------------
class ControlBancoSSCCReport(BaseModel):
    ejercicio: int
    mes: str
    fecha: datetime
    cta_cte: str
    movimiento: Optional[str] = None
    es_cheque: bool
    beneficiario: Optional[str] = None
    importe: float
    concepto: Optional[str] = None
    moneda: Optional[str] = None
    libramiento: Optional[str] = None
    cod_imputacion: str
    imputacion: str
    clase: str


# -------------------------------------------------
class ControlBancoSSCCDocument(ControlBancoSSCCReport):
    id: PydanticObjectId = Field(alias="_id")


# -------------------------------------------------
class ControlBancoSSCCFullFilter(BaseFilterParams):
    ejercicio: Optional[int] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class ControlBancoSSCCLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[str] = None
    # Aquí podrías añadir: incluir_detalles: bool = False
