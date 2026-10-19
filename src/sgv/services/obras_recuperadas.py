__all__ = ["ObrasRecuperadasService", "ObrasRecuperadasServiceDependency"]

# import os
from dataclasses import dataclass
from datetime import datetime, timezone

# from io import BytesIO
from typing import Annotated, List

import pandas as pd
from bson import ObjectId
from fastapi import Depends, HTTPException, status
from fastapi.responses import StreamingResponse

# from pydantic import ValidationError
from ...config import logger
from ...utils import (
    BaseService,
    RouteReturnSchema,
    sync_validated_to_repository,
    validate_and_extract_data_from_list,
)
from ..repositories import ObrasRecuperadasRepositoryDependency
from ..schemas import (
    ObrasRecuperadasDocument,
    ObrasRecuperadasFullFilter,
    ObrasRecuperadasLiteFilter,
    ObrasRecuperadasReport,
)


@dataclass
# -------------------------------------------------
class ObrasRecuperadasService(
    BaseService[
        ObrasRecuperadasReport,
        ObrasRecuperadasDocument,
        ObrasRecuperadasFullFilter,
        ObrasRecuperadasLiteFilter,
    ]
):
    repository: ObrasRecuperadasRepositoryDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=ObrasRecuperadasFullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(self, data: List[ObrasRecuperadasReport]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=ObrasRecuperadasReport,
                field_id=[
                    "ejercicio",
                    "cod_barrio",
                ],  # O el campo que identifique la fila en caso de error
            )

            # 🔥 CONTROL CRÍTICO: Si no hay registros válidos, lanzamos un 400 Bad Request.
            # (Asumo que validation_result.validated es una lista vacía o None cuando falla todo)
            if not validation_result.validated:
                # Si validation_result tiene una lista de errores detallados, los exponemos al frontend
                detail_msg = "No se encontraron registros válidos para procesar."
                if hasattr(validation_result, "errors") and validation_result.errors:
                    # Formateamos los primeros errores para no saturar el log pero dar contexto claro
                    detail_msg += f" Errores detectados: {validation_result.errors[:2]}"

                raise HTTPException(status_code=400, detail=detail_msg)

            # 2. Determinar filtro de borrado (Idempotencia)
            # A esta altura ya es 100% seguro que al menos hay un registro válido en el índice [0]
            ejercicio_detectado = validation_result.validated[0].ejercicio
            delete_filter = {"ejercicio": ejercicio_detectado}

            # 3. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización SGV Obras Recuperadas",
                label="Obras Recuperadas",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: ObrasRecuperadasLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = ObrasRecuperadasFullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True) for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "SGV_Obras_Recuperadas")],
            filename="reporte_obras_recuperadas.xlsx",
        )

    # -------------------------------------------------
    async def add_one(self, obra_recuperada: ObrasRecuperadasReport):
        try:
            # Invocamos save_one que ya maneja la conversión a dict y unicidad
            nuevo_obra_recuperada = await self.repository.save_one(obra_recuperada)
            return nuevo_obra_recuperada

        except ValueError as e:
            self._handle_error("Error de validación", e, status_code=400)
        except Exception as e:
            self._handle_error("Error inesperado en el servidor", e)

    # -------------------------------------------------
    async def update_one_safely(
        self, id: str, data: ObrasRecuperadasReport
    ) -> ObrasRecuperadasDocument:
        try:
            mongo_id = ObjectId(id)

            # 1. VERIFICACIÓN DE ID_OBRA DUPLICADO
            # Buscamos si existe otro documento con el mismo código recuperos de barrio que NO sea el nuestro
            duplicate = await self.repository.get_one_by_fields(
                {"cod_barrio": data.cod_barrio, "_id": {"$ne": mongo_id}}
            )

            if duplicate:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No se puede actualizar: El Cod Barrio '{data.cod_barrio}' ya existe.",
                )

            # 2. INTENTO DE ACTUALIZACIÓN (Control de Concurrencia)
            new_data = data.model_dump(by_alias=True)
            new_data["updated_at"] = datetime.now(timezone.utc)

            updated_doc = await self.repository.find_one_and_update(
                filter={
                    "_id": mongo_id,
                    "updated_at": data.updated_at,  # El cerrojo
                },
                update_data=new_data,
                return_document=True,
            )

            if not updated_doc:
                # Si llegamos acá es porque el ID no existe o el updated_at cambió (Conflicto)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Conflicto de edición: Los datos fueron modificados por otro usuario. Por favor, recargue la página.",
                )

            return updated_doc
        except HTTPException:
            raise  # Re-lanzamos la excepción de FastAPI si ya la manejamos
        except Exception as e:
            logger.error(f"Error en update_one_safely: {str(e)}")
            self._handle_error("Error durante el proceso de update_one_safely", e)

    # -------------------------------------------------
    async def delete_one(self, id: str) -> ObrasRecuperadasDocument:
        try:
            mongo_id = ObjectId(id)
            document = await self.repository.delete_by_id(mongo_id)

            if not document:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="La Obra Recuperada no existe o ya fue eliminado.",
                )
            return document
        except HTTPException:
            raise  # Re-lanzamos la excepción de FastAPI si ya la manejamos
        except Exception as e:
            logger.error(f"Error en delete_one_hard: {str(e)}")
            self._handle_error("Error durante el proceso de delete_one_hard", e)


ObrasRecuperadasServiceDependency = Annotated[ObrasRecuperadasService, Depends()]
