__all__ = [
    "ControlOtrosGastosSiifReport",
    "ControlOtrosGastosSiifDocument",
    "ControlOtrosGastosSiifFilter",
    "ControlOtrosGastosSiifLiteFilter",
    "ControlOtrosGastosSgfReport",
    "ControlOtrosGastosSgfDocument",
    "ControlOtrosGastosSgfFilter",
    "ControlOtrosGastosSgfLiteFilter",
    "ControlOtrosGastosGenerateFilter",
    "ControlOtrosGastosExportFilter",
]

from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# Respuesta de detalle (fila a fila, sin agregar) del SIIF depurado:
# todo lo que quedó por fuera de los demás controles.
# -------------------------------------------------
class ControlOtrosGastosSiifReport(BaseModel):
    # fecha: el cómputo pasa por sanitize_dataframe_for_json_with_datetime,
    # que convierte fechas a texto dd/mm/aaaa (por eso es str y no datetime).
    ejercicio: int
    mes: str
    fecha: Optional[str] = None
    nro_comprobante: str
    importe: float
    cta_cte: str
    cuit: str
    beneficiario: str
    clase_reg: str
    clase_mod: str
    clase_gto: str
    es_comprometido: bool
    es_verificado: bool
    es_aprobado: bool
    es_pagado: bool
    fuente: Optional[str] = None
    nro_expte: Optional[str] = None
    nro_fondo: Optional[str] = None
    nro_entrada: Optional[str] = None
    nro_origen: Optional[str] = None
    grupo: Optional[str] = None
    partida: Optional[str] = None
    glosa: Optional[str] = None


# -------------------------------------------------
class ControlOtrosGastosSiifDocument(ControlOtrosGastosSiifReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para el Get All / Delete (Con limit/offset)
# -------------------------------------------------
class ControlOtrosGastosSiifFilter(BaseFilterParams):
    ejercicio: Optional[int] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class ControlOtrosGastosSiifLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[int] = None


# Respuesta de detalle (fila a fila, sin agregar) del SGF depurado:
# todo lo que quedó por fuera de los demás controles.
# -------------------------------------------------
class ControlOtrosGastosSgfReport(BaseModel):
    # fecha: el cómputo pasa por sanitize_dataframe_for_json_with_datetime,
    # que convierte fechas a texto dd/mm/aaaa (por eso es str y no datetime).
    origen: str
    ejercicio: int
    mes: str
    fecha: Optional[str] = None
    beneficiario: str
    destino: str
    libramiento: str
    movimiento: str
    cta_cte: str
    importe_bruto: float
    gcias: float
    sellos: float
    iibb: float
    suss: float
    invico: float
    seguro: float
    salud: float
    mutual: float
    otras: float
    retenciones: float
    importe_neto: float
    cuit: Optional[str] = None


# -------------------------------------------------
class ControlOtrosGastosSgfDocument(ControlOtrosGastosSgfReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# Este se usa para el Get All / Delete (Con limit/offset)
# -------------------------------------------------
class ControlOtrosGastosSgfFilter(BaseFilterParams):
    ejercicio: Optional[int] = None


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class ControlOtrosGastosSgfLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[int] = None


# Filtro de los endpoints /generate*: el backend arma cada tabla
# depurada on-demand (SIIF y SGF por separado)
# -------------------------------------------------
class ControlOtrosGastosGenerateFilter(CamelModel):
    ejercicio: int


# Filtro del /export unificado: una sola ruta sube un único Google
# Sheet con las 2 hojas (SIIF y SGF)
# -------------------------------------------------
class ControlOtrosGastosExportFilter(CamelModel):
    ejercicio: int
