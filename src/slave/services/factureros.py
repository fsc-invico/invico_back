__all__ = ["FacturerosService", "FacturerosServiceDependency"]

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
from ..repositories import FacturerosRepositoryDependency
from ..schemas import (
    FacturerosDocument,
    FacturerosFullFilter,
    FacturerosLiteFilter,
    FacturerosReport,
)


@dataclass
# -------------------------------------------------
class FacturerosService(
    BaseService[
        FacturerosReport, FacturerosDocument, FacturerosFullFilter, FacturerosLiteFilter
    ]
):
    repository: FacturerosRepositoryDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=FacturerosFullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(self, data: List[FacturerosReport]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=FacturerosReport,
                field_id=[
                    "nombre_completo",
                    "actividad",
                    "partida",
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
            delete_filter = {}

            # 3. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización Nómina de Factureros SLAVE",
                label="Nómina de Factureros SLAVE",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: FacturerosLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = FacturerosFullFilter(
            query_filter=params.query_filter,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "SLAVE_FACTUREROS")], filename="slave_factureros.xlsx"
        )

    # -------------------------------------------------
    async def add_one(self, facturero: FacturerosReport):
        try:
            # Invocamos save_one que ya maneja la conversión a dict y unicidad
            nuevo_facturero = await self.repository.save_one(facturero)
            return nuevo_facturero

        except ValueError as e:
            self._handle_error("Error de validación", e, status_code=400)
        except Exception as e:
            self._handle_error("Error inesperado en el servidor", e)

    # -------------------------------------------------
    async def update_one_safely(
        self, id: str, data: FacturerosReport
    ) -> FacturerosDocument:
        try:
            mongo_id = ObjectId(id)

            # 1. VERIFICACIÓN DE ID_OBRA DUPLICADO
            # Buscamos si existe otro documento con esa estructura que NO sea el nuestro
            duplicate = await self.repository.get_one_by_fields(
                {"nombre_completo": data.nombre_completo, "_id": {"$ne": mongo_id}}
            )

            if duplicate:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No se puede actualizar: El facturero '{data.nombre_completo}' ya existe.",
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
    async def delete_one(self, id: str) -> FacturerosDocument:
        try:
            mongo_id = ObjectId(id)
            document = await self.repository.delete_by_id(mongo_id)

            if not document:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="El Agente no existe o ya fue eliminado.",
                )
            return document
        except HTTPException:
            raise  # Re-lanzamos la excepción de FastAPI si ya la manejamos
        except Exception as e:
            logger.error(f"Error en delete_one_hard: {str(e)}")
            self._handle_error("Error durante el proceso de delete_one_hard", e)

    # -------------------------------------------------
    async def get_actividades(self) -> List[str]:
        """Devuelve los valores únicos del campo 'actividad' en slave_honorarios.

        Usa el comando `distinct` de MongoDB para obtener las actividades
        sin traer toda la colección a la memoria.
        """
        try:
            # collection es el AsyncIOMotorCollection expuesto por BaseRepository.
            valores = await self.repository.collection.distinct("actividad")

            # Filtramos valores vacíos/nulos y forzamos la unicidad (por si el
            # backend no la garantiza), luego ordenamos alfabéticamente para
            # devolver una lista estable y predecible al frontend.
            return sorted({valor for valor in valores if valor})
        except Exception as e:
            self._handle_error("Error obteniendo las actividades", e)

    # -------------------------------------------------
    async def get_partidas(self) -> List[str]:
        """Devuelve los valores únicos del campo 'partida' en slave_honorarios.

        Usa el comando `distinct` de MongoDB para obtener las partidas
        sin traer toda la colección a la memoria.
        """
        try:
            # collection es el AsyncIOMotorCollection expuesto por BaseRepository.
            valores = await self.repository.collection.distinct("partida")

            # Filtramos valores vacíos/nulos y forzamos la unicidad (por si el
            # backend no la garantiza), luego ordenamos alfabéticamente para
            # devolver una lista estable y predecible al frontend.
            return sorted({valor for valor in valores if valor})
        except Exception as e:
            self._handle_error("Error obteniendo las partidas", e)


FacturerosServiceDependency = Annotated[FacturerosService, Depends()]
