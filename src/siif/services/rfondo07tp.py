__all__ = ["Rfondo07tpService", "Rfondo07tpServiceDependency"]

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
from ..repositories import Rfondo07tpRepositoryDependency
from ..schemas import (
    Rfondo07tpDocument,
    Rfondo07tpFullFilter,
    Rfondo07tpLiteFilter,
    Rfondo07tpReport,
)


@dataclass
# -------------------------------------------------
class Rfondo07tpService(
    BaseService[
        Rfondo07tpReport, Rfondo07tpDocument, Rfondo07tpFullFilter, Rfondo07tpLiteFilter
    ]
):
    repository: Rfondo07tpRepositoryDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=Rfondo07tpFullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(self, data: List[Rfondo07tpReport]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=Rfondo07tpReport,
                field_id="nro_comprobante",  # O el campo que identifique la fila en caso de error
            )

            # 2. Determinar filtro de borrado (Idempotencia)
            # Si hay registros válidos, extraemos el ejercicio para limpiar antes de insertar
            delete_filter = {}
            if validation_result.validated:
                # Tomamos el ejercicio del primer registro válido
                ejercicio_detectado = validation_result.validated[0].ejercicio
                tipo_comprobante_detectado = validation_result.validated[
                    0
                ].tipo_comprobante
                delete_filter = {
                    "ejercicio": ejercicio_detectado,
                    "tipo_comprobante": tipo_comprobante_detectado,
                }

            # 3. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización SIIF RFONDO07TP",
                label="RFONDO07TP",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: Rfondo07tpLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = Rfondo07tpFullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            tipo_comprobante=params.tipo_comprobante,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "SIIF_RFONDO07TP")], filename="reporte_rfondo07tp.xlsx"
        )


Rfondo07tpServiceDependency = Annotated[Rfondo07tpService, Depends()]
