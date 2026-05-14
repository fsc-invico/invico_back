__all__ = ["EstructurasService", "EstructurasServiceDependency"]

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, List

import pandas as pd
from bson import ObjectId
from fastapi import Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from ...config import logger
from ...utils import (
    BaseService,
    RouteReturnSchema,
    sync_validated_to_repository,
    validate_and_extract_data_from_list,
)
from ..repositories import EstructurasRepositoryDependency
from ..schemas import (
    EstructurasDocument,
    EstructurasFullFilter,
    EstructurasLiteFilter,
    EstructurasReport,
)


@dataclass
# -------------------------------------------------
class EstructurasService(
    BaseService[
        EstructurasReport,
        EstructurasDocument,
        EstructurasFullFilter,
        EstructurasLiteFilter,
    ]
):
    repository: EstructurasRepositoryDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=EstructurasFullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(self, data: List[EstructurasReport]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=EstructurasReport,
                field_id="estructura",  # O el campo que identifique la fila en caso de error
            )

            # 2. Determinar filtro de borrado (Idempotencia)
            # Si hay registros válidos, extraemos el ejercicio para limpiar antes de insertar
            delete_filter = {}

            # 3. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización ICARO ESTRUCTURAS",
                label="ESTRUCTURAS",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: EstructurasLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = EstructurasFullFilter(
            query_filter=params.query_filter,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "ICARO_ESTRUCTURAS")],
            filename="reporte_icaro_estructuras.xlsx",
        )

    # -------------------------------------------------
    async def add_one(self, estructura: EstructurasReport):
        try:
            # Invocamos save_one que ya maneja la conversión a dict y unicidad
            nueva_estructura = await self.repository.save_one(estructura)
            return nueva_estructura

        except ValueError as e:
            self._handle_error("Error de validación", e, status_code=400)
        except Exception as e:
            self._handle_error("Error inesperado en el servidor", e)

    # -------------------------------------------------
    async def update_one_safely(
        self, id: str, data: EstructurasReport
    ) -> EstructurasDocument:
        try:
            mongo_id = ObjectId(id)

            # 1. VERIFICACIÓN DE ID_OBRA DUPLICADO
            # Buscamos si existe otro documento con esa estructura que NO sea el nuestro
            duplicate = await self.repository.get_one_by_fields(
                {"estructura": data.estructura, "_id": {"$ne": mongo_id}}
            )

            if duplicate:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No se puede actualizar: La estructura '{data.estructura}' ya está siendo utilizada.",
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
    async def delete_one(self, id: str) -> EstructurasDocument:
        try:
            mongo_id = ObjectId(id)
            # 1. Buscamos el documento que se quiere borrar para saber su código de estructura
            target_doc = await self.repository.get_by_id(mongo_id)

            if not target_doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="La estructura no existe.",
                )

            # 2. Verificamos si tiene hijos
            # Buscamos cualquier documento que empiece con "codigo-", lo cual indica jerarquía
            codigo_padre = target_doc["estructura"]
            query_hijos = {"estructura": {"$regex": f"^{codigo_padre}-"}}

            tiene_hijos = await self.repository.collection.count_documents(query_hijos)

            if tiene_hijos > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No se puede eliminar: la estructura '{codigo_padre}' tiene {tiene_hijos} sub-niveles dependientes.",
                )

            # 3. Si no tiene hijos, procedemos al borrado
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


EstructurasServiceDependency = Annotated[EstructurasService, Depends()]
