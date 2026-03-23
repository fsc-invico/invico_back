__all__ = ["Rpa03gService", "Rpa03gServiceDependency"]

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
from ..repositories import Rpa03gRepositoryDependency
from ..schemas import (
    Rpa03gDocument,
    Rpa03gFullFilter,
    Rpa03gLiteFilter,
    Rpa03gReport,
)


@dataclass
# -------------------------------------------------
class Rpa03gService(
    BaseService[Rpa03gReport, Rpa03gDocument, Rpa03gFullFilter, Rpa03gLiteFilter]
):
    repository: Rpa03gRepositoryDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=Rpa03gFullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(self, data: List[Rpa03gReport]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=Rpa03gReport,
                field_id="nro_comprobante",  # O el campo que identifique la fila en caso de error
            )

            # 2. Determinar filtro de borrado (Idempotencia)
            # Si hay registros válidos, extraemos el ejercicio para limpiar antes de insertar
            delete_filter = {}
            if validation_result.validated:
                # Tomamos el ejercicio del primer registro válido
                ejercicio_detectado = validation_result.validated[0].ejercicio
                grupo_detectado = validation_result.validated[0].grupo
                delete_filter = {
                    "ejercicio": ejercicio_detectado,
                    "grupo": grupo_detectado,
                }

            # 3. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización SIIF RPA03G",
                label="RPA03G",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: Rpa03gLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = Rpa03gFullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            grupo=params.grupo,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "SIIF_RPA03G")], filename="reporte_rpa03g.xlsx"
        )


Rpa03gServiceDependency = Annotated[Rpa03gService, Depends()]
