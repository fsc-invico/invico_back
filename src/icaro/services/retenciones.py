__all__ = ["RetencionesService", "RetencionesServiceDependency"]

# import os
from dataclasses import dataclass

# from io import BytesIO
from typing import Annotated, List

import pandas as pd
from fastapi import Depends, HTTPException
from fastapi.responses import StreamingResponse

# from pydantic import ValidationError
from ...config import logger
from ...utils import (
    BaseService,
    RouteReturnSchema,
    sync_validated_to_repository,
    validate_and_extract_data_from_list,
)
from ..repositories import RetencionesRepositoryDependency
from ..schemas import (
    RetencionesDocument,
    RetencionesFullFilter,
    RetencionesLiteFilter,
    RetencionesReport,
)


@dataclass
# -------------------------------------------------
class RetencionesService(
    BaseService[
        RetencionesReport,
        RetencionesDocument,
        RetencionesFullFilter,
        RetencionesLiteFilter,
    ]
):
    repository: RetencionesRepositoryDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=RetencionesFullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def delete_many_by_carga_id(self, id_carga: str) -> dict:
        try:
            count = await self.repository.delete_by_fields({"id_carga": id_carga})

            return {
                "status": "success",
                "deleted_count": count,
                "message": f"Se eliminaron {count} retenciones asociadas.",
            }
        except HTTPException:
            raise  # Re-lanzamos la excepción de FastAPI si ya la manejamos
        except Exception as e:
            logger.error(f"Error en delete_many_by_carga_id: {str(e)}")
            self._handle_error("Error eliminando retenciones", e)

    # -------------------------------------------------
    async def add_many(self, data: List[RetencionesReport]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=RetencionesReport,
                field_id=[
                    "id_carga",
                    "codigo",
                ],  # O el campo que identifique la fila en caso de error
            )

            # 2. Determinar filtro de borrado (Idempotencia)
            # Si hay registros válidos, extraemos el ejercicio para limpiar antes de insertar
            delete_filter = {}

            # 3. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización ICARO RETENCIONES",
                label="RETENCIONES",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: RetencionesLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = RetencionesFullFilter(
            query_filter=params.query_filter,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "ICARO_RETENCIONES")],
            filename="reporte_icaro_retenciones.xlsx",
        )


RetencionesServiceDependency = Annotated[RetencionesService, Depends()]
