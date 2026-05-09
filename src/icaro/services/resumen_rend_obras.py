__all__ = ["ResumenRendObrasService", "ResumenRendObrasServiceDependency"]

from dataclasses import dataclass
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
from ..repositories import ResumenRendObrasRepositoryDependency
from ..schemas import (
    ResumenRendObrasDocument,
    ResumenRendObrasFullFilter,
    ResumenRendObrasLiteFilter,
    ResumenRendObrasReport,
)


@dataclass
# -------------------------------------------------
class ResumenRendObrasService(
    BaseService[
        ResumenRendObrasReport,
        ResumenRendObrasDocument,
        ResumenRendObrasFullFilter,
        ResumenRendObrasLiteFilter,
    ]
):
    repository: ResumenRendObrasRepositoryDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=ResumenRendObrasFullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(self, data: List[ResumenRendObrasReport]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=ResumenRendObrasReport,
                field_id=[
                    "nro_libramiento_sgf",
                    "beneficiario",
                    "desc_obra",
                    "fecha",
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
                title="Sincronización ICARO REND_OBRAS",
                label="REND_OBRAS",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: ResumenRendObrasLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = ResumenRendObrasFullFilter(
            query_filter=params.query_filter,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "ICARO_REND_OBRAS")],
            filename="reporte_icaro_rend_obras.xlsx",
        )

    # -------------------------------------------------
    async def update_id_carga(self, ids: list[str], id_carga: str):
        try:
            # 1. Preparamos los datos de actualización
            update_data = {
                "id_carga": id_carga,
                "updated_at": datetime.now(timezone.utc),
            }

            # 2. Usamos el repositorio con el operador $in
            # El filtro busca cualquier documento cuyo _id esté en la lista recibida
            filtro = {"_id": {"$in": [ObjectId(id) for id in ids]}}

            modificados = await self.repository.update_many(filtro, update_data)

            if modificados == 0:
                logger.warning(
                    "No se modificó ningún registro para el batch de IDs enviado."
                )
            else:
                logger.info(
                    f"Sincronización masiva: {modificados} registros vinculados a la carga {id_carga}"
                )

            return {
                "status": "updated",
                "modified_count": modificados,
                "ids_procesados": ids,
            }

        except Exception as e:
            logger.error(f"Error en update_id_carga_batch: {str(e)}")
            self._handle_error("Error técnico al procesar la vinculación masiva", e)

    # -------------------------------------------------
    async def unlink_carga_value(self, id_carga: str):
        try:
            # Buscamos el documento que tiene ese id_carga y lo seteamos en ""
            update_data = {"id_carga": "", "updated_at": datetime.now(timezone.utc)}

            # Usamos update_many por si las dudas hubiera más de uno,
            # aunque lo normal es que sea uno solo.
            modificados = await self.repository.update_many(
                {"id_carga": id_carga}, update_data
            )
            if modificados > 0:
                logger.info(f"Se actualizaron {modificados} registros.")

            return {"status": "unlinked", "modified_count": modificados}
        except Exception as e:
            self._handle_error(f"Error al desvincular el id_carga {id_carga}", e)


ResumenRendObrasServiceDependency = Annotated[ResumenRendObrasService, Depends()]
