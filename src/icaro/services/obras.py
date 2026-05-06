__all__ = ["ObrasService", "ObrasServiceDependency"]

# import os
from dataclasses import dataclass

# from io import BytesIO
from datetime import datetime, timezone
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
from ..repositories import CargaRepositoryDependency, ObrasRepositoryDependency
from ..schemas import ObrasDocument, ObrasFullFilter, ObrasLiteFilter, ObrasReport


@dataclass
# -------------------------------------------------
class ObrasService(
    BaseService[ObrasReport, ObrasDocument, ObrasFullFilter, ObrasLiteFilter]
):
    repository: ObrasRepositoryDependency
    carga_repository: CargaRepositoryDependency

    def __post_init__(self):
        self.repository.unique_field = "desc_obra"
        super().__init__(
            repository=self.repository,
            filter_schema=ObrasFullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(self, data: List[ObrasReport]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=ObrasReport,
                field_id="desc_obra",  # O el campo que identifique la fila en caso de error
            )

            # 2. Determinar filtro de borrado (Idempotencia)
            # Si hay registros válidos, extraemos el ejercicio para limpiar antes de insertar
            delete_filter = {}

            # 3. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización ICARO OBRAS",
                label="OBRAS",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: ObrasLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = ObrasFullFilter(
            query_filter=params.query_filter,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "ICARO_OBRAS")], filename="reporte_icaro_obras.xlsx"
        )

    # -------------------------------------------------
    async def add_one(self, obra: ObrasReport):
        try:
            # Invocamos save_one que ya maneja la conversión a dict y unicidad
            nueva_obra = await self.repository.save_one(obra)
            return nueva_obra

        except ValueError as e:
            self._handle_error("Error de validación", e, status_code=400)
        except Exception as e:
            self._handle_error("Error inesperado en el servidor", e)

    # -------------------------------------------------
    async def update_one_safely(self, id: str, data: ObrasReport) -> ObrasDocument:
        try:
            mongo_id = ObjectId(id)

            # 1. Obtener el documento actual para comparar el nombre viejo
            current_doc = await self.repository.get_by_id(mongo_id)
            if not current_doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Obra no encontrada"
                )

            old_desc_obra = current_doc[
                "desc_obra"
            ]  # Guardamos el nombre viejo para la cascada

            # 2. VERIFICACIÓN DE ID_OBRA DUPLICADO
            # Buscamos si existe otro documento con ese desc_obra que NO sea el nuestro
            duplicate = await self.repository.get_one_by_fields(
                {"desc_obra": data.desc_obra, "_id": {"$ne": mongo_id}}
            )

            if duplicate:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No se puede actualizar: La obra '{data.desc_obra}' ya está siendo usado por otro comprobante.",
                )

            # 3. INTENTO DE ACTUALIZACIÓN (Control de Concurrencia)
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

            # 4. CASCADA: Si el nombre cambió, actualizamos 'carga'
            if old_desc_obra != data.desc_obra:
                try:  # Usamos el repositorio de carga inyectado
                    await self.carga_repository.update_many(
                        {"desc_obra": old_desc_obra},
                        {"desc_obra": data.desc_obra},
                    )
                    logger.info(
                        f"Cascada ejecutada: '{old_desc_obra}' -> '{data.desc_obra}' en colección 'carga'"
                    )
                except Exception as e:
                    logger.error(
                        f"Error en cascada de obra '{old_desc_obra}': {str(e)}"
                    )

            return updated_doc
        except HTTPException:
            raise  # Re-lanzamos la excepción de FastAPI si ya la manejamos
        except Exception as e:
            logger.error(f"Error en update_one_safely: {str(e)}")
            self._handle_error("Error durante el proceso de update_one_safely", e)

    # -------------------------------------------------
    async def delete_one(self, id: str) -> ObrasDocument:
        try:
            mongo_id = ObjectId(id)
            document = await self.repository.delete_by_id(mongo_id)

            if not document:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="El comprobante no existe o ya fue eliminado.",
                )
            return document
        except HTTPException:
            raise  # Re-lanzamos la excepción de FastAPI si ya la manejamos
        except Exception as e:
            logger.error(f"Error en delete_one_hard: {str(e)}")
            self._handle_error("Error durante el proceso de delete_one_hard", e)


ObrasServiceDependency = Annotated[ObrasService, Depends()]
