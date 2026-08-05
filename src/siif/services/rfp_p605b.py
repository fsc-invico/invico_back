__all__ = ["RfpP605bService", "RfpP605bServiceDependency"]

# import os
from dataclasses import dataclass

# from io import BytesIO
from typing import Annotated, List

import pandas as pd
from fastapi import Depends, HTTPException
from fastapi.responses import StreamingResponse

# from pydantic import ValidationError
from ...config import logger
from ...utils import (
    BaseService,
    RouteReturnSchema,
    sync_validated_to_repository,
    validate_and_extract_data_from_list,
)
from ..repositories import RfpP605bRepositoryDependency
from ..schemas import (
    RfpP605bDocument,
    RfpP605bFullFilter,
    RfpP605bLiteFilter,
    RfpP605bReport,
)


@dataclass
# -------------------------------------------------
class RfpP605bService(
    BaseService[
        RfpP605bReport, RfpP605bDocument, RfpP605bFullFilter, RfpP605bLiteFilter
    ]
):
    repository: RfpP605bRepositoryDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=RfpP605bFullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(self, data: List[RfpP605bReport]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            # Usamos Rf602Report o Rf602Document para validar cada fila
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=RfpP605bReport,
                field_id="estructura",  # O el campo que identifique la fila en caso de error
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
                title="Sincronización SIIF RFPP605B",
                label=f"RFPP605B del Ejercicio {ejercicio_detectado}",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: RfpP605bLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = RfpP605bFullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "SIIF_RFPP605B")], filename="reporte_rfpp605b.xlsx"
        )


RfpP605bServiceDependency = Annotated[RfpP605bService, Depends()]
