__all__ = ["ResumenRendObrasService", "ResumenRendObrasServiceDependency"]

# import os
from dataclasses import dataclass

# from io import BytesIO
from typing import Annotated, List

import pandas as pd
from fastapi import Depends
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

    # # -------------------------------------------------
    # async def update_post_safely(db, post_id: str, old_timestamp: datetime, new_title: str):
    #     new_timestamp = datetime.now(timezone.utc)

    #     # Intentamos la actualización
    #     result = await db.posts.update_one(
    #         {
    #             "_id": ObjectId(post_id),
    #             "updated_at": old_timestamp,  # <--- AQUÍ ESTÁ LA MAGIA
    #         },
    #         {"$set": {"title": new_title, "updated_at": new_timestamp}},
    #     )

    #     if result.modified_count == 0:
    #         # Si modified_count es 0, significa que alguien cambió el updated_at
    #         # antes que nosotros y el filtro ya no coincidió.
    #         raise Exception(
    #             "Conflicto de edición: El registro fue modificado por otro usuario."
    #         )

    #     return "Actualizado con éxito"


ResumenRendObrasServiceDependency = Annotated[ResumenRendObrasService, Depends()]
