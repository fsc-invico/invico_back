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
    "ControlOtrosGastosCruceReport",
    "ControlOtrosGastosCruceDocument",
    "ControlOtrosGastosCruceFilter",
    "ControlOtrosGastosCruceLiteFilter",
    "ControlOtrosGastosCruceMensualReport",
    "ControlOtrosGastosCruceMensualDocument",
    "ControlOtrosGastosCruceMensualFilter",
    "ControlOtrosGastosCruceMensualLiteFilter",
    "ControlOtrosGastosCruceGenerateFilter",
    "ControlOtrosGastosCruceSnapshot",
    "ESTADO_PAREADO",
    "ESTADO_SIIF_SIN_SGF",
    "ESTADO_SGF_SIN_SIIF",
]

from typing import Any, Dict, List, Optional

from pydantic import AliasChoices, BaseModel, Field, field_validator
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# --------------------------------------------------
def _texto_o_none(valor: Any) -> Any:
    """Normaliza campos de texto en modo ``before`` (patrón del módulo).

    El frontend arma los payloads pasando las filas por un
    ``pd.DataFrame``: los campos opcionales ausentes llegan como
    ``float('nan')`` (httpx serializa ``NaN`` con ``allow_nan=True``).
    Sin esta coerción, Pydantic rechaza ``nan`` en campos ``str`` y el
    ``add_many`` descarta filas COMPLETAS en silencio (fue lo que dejó
    la tabla SIIF sin el resto y la SGF sin los cuit nulos).

    - ``None`` / ``NaN`` → ``None`` (opcionales aceptan nulo).
    - Enteros y floats enteros → ``str`` (``27.0`` → ``"27"``,
      ``900008022026`` → ``"900008022026"``).
    - Cualquier otro valor no-texto → ``str``.
    """
    if valor is None:
        return None
    if isinstance(valor, float):
        # valor != valor es True solo para NaN (sin dependencias)
        if valor != valor:
            return None
        if valor.is_integer():
            return str(int(valor))
        return str(valor)
    if isinstance(valor, int) and not isinstance(valor, bool):
        return str(valor)
    return valor


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

    # tolerancia a payloads con NaN/numéricos (ver _texto_o_none)
    @field_validator(
        "mes",
        "fecha",
        "nro_comprobante",
        "cta_cte",
        "cuit",
        "beneficiario",
        "clase_reg",
        "clase_mod",
        "clase_gto",
        "fuente",
        "nro_expte",
        "nro_fondo",
        "nro_entrada",
        "nro_origen",
        "grupo",
        "partida",
        "glosa",
        mode="before",
    )
    @classmethod
    def _coercer_texto(cls, valor: Any) -> Any:
        return _texto_o_none(valor)


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

    # tolerancia a payloads con NaN/numéricos (ver _texto_o_none).
    # El cuit nulo del SGF era exactamente lo que perdía el POST.
    @field_validator(
        "origen",
        "mes",
        "fecha",
        "beneficiario",
        "destino",
        "libramiento",
        "movimiento",
        "cta_cte",
        "cuit",
        mode="before",
    )
    @classmethod
    def _coercer_texto(cls, valor: Any) -> Any:
        return _texto_o_none(valor)


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
# Sheet con las 4 hojas (SIIF, SGF y los 2 cruces)
# -------------------------------------------------
class ControlOtrosGastosExportFilter(CamelModel):
    ejercicio: int


# -------------------------------------------------
# CRUCE SIIF <-> SGF
# -------------------------------------------------

# Estados del pareo 1:1 de la Capa 1 (resto: no fondos permanentes)
ESTADO_PAREADO: str = "PAREADO"
ESTADO_SIIF_SIN_SGF: str = "SIIF_SIN_SGF"
ESTADO_SGF_SIN_SIIF: str = "SGF_SIN_SIIF"


# Fila del pareo 1:1 (Capa 1). Cada fila trae el lado SIIF, el lado
# SGF, o ambos; los lados no usados quedan en None.
# -------------------------------------------------
class ControlOtrosGastosCruceReport(BaseModel):
    ejercicio: int
    estado: str
    # lado SIIF (None si la fila es SGF_SIN_SIIF)
    siif_nro_comprobante: Optional[str] = None
    siif_fecha: Optional[str] = None
    siif_mes: Optional[str] = None
    siif_cuit: Optional[str] = None
    siif_beneficiario: Optional[str] = None
    siif_cta_cte: Optional[str] = None
    siif_partida: Optional[str] = None
    siif_importe: Optional[float] = None
    # lado SGF (None si la fila es SIIF_SIN_SGF)
    sgf_libramiento: Optional[str] = None
    sgf_fecha: Optional[str] = None
    sgf_mes: Optional[str] = None
    sgf_cuit: Optional[str] = None
    sgf_beneficiario: Optional[str] = None
    sgf_cta_cte: Optional[str] = None
    sgf_importe_bruto: Optional[float] = None
    # solo PAREADO
    dias_dif: Optional[int] = None
    dif: Optional[float] = None


# -------------------------------------------------
class ControlOtrosGastosCruceDocument(ControlOtrosGastosCruceReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# -------------------------------------------------
class ControlOtrosGastosCruceFilter(BaseFilterParams):
    ejercicio: Optional[int] = None


# -------------------------------------------------
class ControlOtrosGastosCruceLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[int] = None


# Fila de la Capa 2: control mensual de fondos permanentes
# (SIIF rendido vs SGF pagado, con acumulados)
# -------------------------------------------------
class ControlOtrosGastosCruceMensualReport(BaseModel):
    ejercicio: int
    mes: str
    siif_rendido: float
    sgf_pagado: float
    dif_mes: float
    siif_acum: float
    sgf_acum: float
    dif_acum: float
    dif_pct: Optional[float] = None


# -------------------------------------------------
class ControlOtrosGastosCruceMensualDocument(ControlOtrosGastosCruceMensualReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# -------------------------------------------------
class ControlOtrosGastosCruceMensualFilter(BaseFilterParams):
    ejercicio: Optional[int] = None


# -------------------------------------------------
class ControlOtrosGastosCruceMensualLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[int] = None


# Filtro del /cruce/generate: tolerancias del pareo 1:1
# -------------------------------------------------
class ControlOtrosGastosCruceGenerateFilter(CamelModel):
    ejercicio: int
    importe_tol: float = Field(
        default=0.005,
        ge=0.0,
        le=1.0,
        description=(
            "Tolerancia relativa del pareo por importe (0.005 = 0.5%)."
        ),
    )
    ventana_dias: int = Field(
        default=30,
        ge=0,
        description="Ventana máxima en días entre fechas SIIF y SGF (0 = sin ventana).",
    )


# Cuerpo del POST /cruce: snapshot de AMBAS tablas del cruce en un solo
# envío (colecciones control_otros_gastos_cruce y ..._mensual).
# -------------------------------------------------
class ControlOtrosGastosCruceSnapshot(BaseModel):
    ejercicio: int
    pareos: List[Dict] = []
    mensual: List[Dict] = []
