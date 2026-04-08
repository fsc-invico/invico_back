__all__ = ["ProveedoresService", "ProveedoresServiceDependency"]

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
from ..repositories import ProveedoresRepositoryDependency
from ..schemas import (
    ProveedoresDocument,
    ProveedoresFullFilter,
    ProveedoresLiteFilter,
    ProveedoresReport,
)


@dataclass
# -------------------------------------------------
class ProveedoresService(
    BaseService[
        ProveedoresReport,
        ProveedoresDocument,
        ProveedoresFullFilter,
        ProveedoresLiteFilter,
    ]
):
    repository: ProveedoresRepositoryDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=ProveedoresFullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(self, data: List[ProveedoresReport]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=ProveedoresReport,
                field_id="cuit",  # O el campo que identifique la fila en caso de error
            )

            # 2. Determinar filtro de borrado (Idempotencia)
            # Si hay registros válidos, extraemos el ejercicio para limpiar antes de insertar
            delete_filter = {}

            # 3. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización ICARO PROVEEDORES",
                label="PROVEEDORES",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: ProveedoresLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = ProveedoresFullFilter(
            query_filter=params.query_filter,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "ICARO_PROVEEDORES")],
            filename="reporte_icaro_proveedores.xlsx",
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


ProveedoresServiceDependency = Annotated[ProveedoresService, Depends()]
