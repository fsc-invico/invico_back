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


# --------------------------------------------------
def _normalize_lock_timestamp(value: datetime) -> datetime:
    """Normaliza un timestamp cerrojo a UTC aware con precisión de milisegundos.

    MongoDB almacena fechas en UTC con precisión de milisegundos y Motor las
    devuelve naive (sin tz). Para comparar el valor enviado por el front con el
    guardado en BD, ambos se convierten a UTC y se truncan los microsegundos.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    return value.replace(microsecond=(value.microsecond // 1000) * 1000)


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

            # El cerrojo de edición se asigna en el servidor al crear
            created_at = datetime.now(timezone.utc)
            for record in validation_result.validated:
                if record.updated_at is None:
                    record.updated_at = created_at

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
            # El cerrojo de edición se asigna en el servidor al crear
            if obra_recuperada.updated_at is None:
                obra_recuperada.updated_at = datetime.now(timezone.utc)
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

            # # 1. VERIFICACIÓN DE ID_OBRA DUPLICADO
            # # Buscamos si existe otro documento con el mismo código recuperos de barrio que NO sea el nuestro
            # duplicate = await self.repository.get_one_by_fields(
            #     {"cod_barrio": data.cod_barrio, "_id": {"$ne": mongo_id}}
            # )

            # if duplicate:
            #     raise HTTPException(
            #         status_code=status.HTTP_400_BAD_REQUEST,
            #         detail=f"No se puede actualizar: El Cod Barrio '{data.cod_barrio}' ya existe.",
            #     )

            # 1. EXISTENCIA DEL REGISTRO (distingue 404 de 409)
            current_doc = await self.repository.get_by_id(mongo_id)
            if not current_doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        "La Obra Recuperada ya no existe "
                        "(fue eliminada o re-sincronizada). "
                        "Recargue la página."
                    ),
                )

            db_lock = current_doc.get("updated_at")

            # 2. CERROJO AUSENTE EN LA BD (registro antiguo sin timestamp):
            #    no hay con qué comparar, se procede sin cerrojo.
            if db_lock is None:
                logger.warning(
                    f"update_one_safely: registro {id} sin updated_at en BD; "
                    "se omite el control de concurrencia."
                )
            else:
                # 3. CERROJO AUSENTE EN EL PAYLOAD (estricto):
                #    el front debe reenviar el updated_at original del registro.
                if data.updated_at is None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "No se recibió 'updated_at': el front debe enviar "
                            "el valor original del registro para evitar "
                            "conflictos de edición."
                        ),
                    )

                # 4. COMPARACIÓN NORMALIZADA (UTC + precisión de milisegundos)
                received_lock = _normalize_lock_timestamp(data.updated_at)
                stored_lock = _normalize_lock_timestamp(db_lock)
                if received_lock != stored_lock:
                    logger.warning(
                        f"update_one_safely: conflicto de cerrojo en registro "
                        f"{id}. Recibido={data.updated_at!r} | BD={db_lock!r}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Conflicto de edición: Los datos fueron modificados por otro usuario. Por favor, recargue la página.",
                    )

            # 5. INTENTO DE ACTUALIZACIÓN (re-chequeo atómico del cerrojo)
            new_data = data.model_dump(by_alias=True)
            new_data["updated_at"] = datetime.now(timezone.utc)

            update_filter: dict = {"_id": mongo_id}
            if db_lock is not None:
                # Valor crudo de la BD: coincidencia exacta en Mongo
                update_filter["updated_at"] = db_lock

            updated_doc = await self.repository.find_one_and_update(
                filter=update_filter,
                update_data=new_data,
                return_document=True,
            )

            if not updated_doc:
                # Carrera entre la verificación y esta actualización:
                # otro usuario modificó el registro en el ínterim.
                logger.warning(
                    f"update_one_safely: carrera detectada en registro {id}; "
                    "el cerrojo cambió entre la verificación y la "
                    "actualización."
                )
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
