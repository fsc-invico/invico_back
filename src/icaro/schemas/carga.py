__all__ = [
    "CargaReport",
    "CargaDocument",
    "CargaFullFilter",
    "CargaLiteFilter",
    "CargaAcumObraFilter",
    "CargaAcumObra",
    "CargaWithDescProveedor",
    "CargaFullDescSIIF",
]

from datetime import datetime, timezone
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field
from pydantic_mongo import PydanticObjectId

from ...utils import BaseFilterParams, CamelModel


# -------------------------------------------------
class CargaReport(BaseModel):
    ejercicio: int
    mes: str
    fecha: datetime
    id_carga: str
    nro_comprobante: str
    tipo: str
    fuente: str
    actividad: str
    partida: str
    cta_cte: str
    cuit: str
    importe: float
    fondo_reparo: float
    avance: float
    nro_certificado: Optional[str] = None
    desc_obra: str
    origen: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Este se usa para la tabla (UI)
# -------------------------------------------------
class CargaDocument(CargaReport):
    id: PydanticObjectId = Field(validation_alias=AliasChoices("_id", "id"))


# -------------------------------------------------
class CargaFullFilter(BaseFilterParams):
    ejercicio: Optional[str] = None
    # nro_comprobante: Optional[str] = None
    # cuit: Optional[str] = None
    # actividad: Optional[str] = None
    # desc_obra: Optional[str] = None


# Filtro del reporte agrupado por obra (/carga/acumObra)
# Nota: a propósito NO hereda de CargaFullFilter/BaseFilterParams: este
# endpoint no usa query_filter ni paginación offset/sort; sólo limit.
# -------------------------------------------------
class CargaAcumObraFilter(CamelModel):
    limit: Optional[int] = Field(
        None,
        ge=0,
        description="Máximo de grupos a devolver. Si se omite o es 0, sin límite.",
    )
    ejercicio_hasta: Optional[int] = Field(
        None,
        description="Trae los registros con ejercicio menor o igual a este valor (inclusive).",
    )
    actividad: Optional[str] = Field(
        None,
        description="Filtra por actividad (texto exacto). Admite varios valores "
        "separados por coma (ej: 100,200).",
    )
    partida: Optional[str] = Field(
        None,
        description="Filtra por partida (texto exacto, se almacena como string en "
        "la DB). Admite varios valores separados por coma (ej: 421,422).",
    )

    # -------------------------------------------------
    @staticmethod
    def _como_texto(valor: str) -> str:
        """Normaliza un valor del query param: sin espacios y sin prefijo 'str:'."""
        texto = valor.strip()
        return texto[4:] if texto.startswith("str:") else texto

    # -------------------------------------------------
    def get_full_filter(self) -> dict:
        """
        Genera el diccionario de filtro para MongoDB con los parámetros
        explícitos de este endpoint (sin query_filter libre):

        - `ejercicio_hasta` se traduce en un rango $lte (inclusive) sobre
          el campo `ejercicio` de la colección.
        - `actividad` y `partida` se manejan como texto, porque en icaro_carga
          se almacenan como strings (format_value los habría convertido a int).
        - `limit` no forma parte del filtro: se aplica como etapa $limit del
          pipeline de agregación en el servicio.
        """
        mongo_filter: dict = {}

        if self.ejercicio_hasta is not None:
            mongo_filter["ejercicio"] = {"$lte": self.ejercicio_hasta}

        for campo in ("actividad", "partida"):
            valor = getattr(self, campo, None)
            if valor is None:
                continue
            textos = [
                texto
                for texto in (self._como_texto(item) for item in valor.split(","))
                if texto
            ]
            if not textos:
                continue
            if len(textos) == 1:
                mongo_filter[campo] = textos[0]
            else:
                mongo_filter[campo] = {"$in": textos}

        return mongo_filter


# Respuesta del reporte agrupado por obra (/carga/acumObra)
# -------------------------------------------------
class CargaAcumObra(BaseModel):
    actividad: Optional[str] = None
    partida: Optional[str] = None
    desc_obra: Optional[str] = None
    importe: float = Field(0.0, description="Suma de importes del grupo.")
    ejercicio: Optional[int] = Field(None, description="Ejercicio mínimo del grupo.")
    avance: Optional[float] = Field(None, description="Avance máximo del grupo.")


# Este se usa para el Excel y Borrar (Sin limit/offset)
# -------------------------------------------------
class CargaLiteFilter(CamelModel):
    query_filter: str = ""
    ejercicio: Optional[str] = None
    # Aquí podrías añadir: incluir_detalles: bool = False


# -------------------------------------------------
class CargaWithDescProveedor(CargaReport):
    desc_proveedor: Optional[str] = None


# -------------------------------------------------
class CargaFullDescSIIF(CargaWithDescProveedor):
    desc_proveedor: Optional[str] = None
    desc_programa: Optional[str] = None
    desc_subprograma: Optional[str] = None
    desc_proyecto: Optional[str] = None
    desc_actividad: Optional[str] = None
