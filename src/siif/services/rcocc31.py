__all__ = ["Rcocc31Service", "Rcocc31ServiceDependency"]

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
from ..repositories import Rcocc31RepositoryDependency
from ..schemas import (
    Rcocc31Document,
    Rcocc31FullFilter,
    Rcocc31LiteFilter,
    Rcocc31Report,
)


@dataclass
# -------------------------------------------------
class Rcocc31Service(
    BaseService[Rcocc31Report, Rcocc31Document, Rcocc31FullFilter, Rcocc31LiteFilter]
):
    repository: Rcocc31RepositoryDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=Rcocc31FullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(self, data: List[Rcocc31Report]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            # Usamos Rf602Report o Rf602Document para validar cada fila
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=Rcocc31Report,
                field_id="estructura",  # O el campo que identifique la fila en caso de error
            )

            # 2. Determinar filtro de borrado (Idempotencia)
            # Si hay registros válidos, extraemos el ejercicio para limpiar antes de insertar
            delete_filter = {}
            if validation_result.validated:
                # Tomamos el ejercicio del primer registro válido
                ejercicio_detectado = validation_result.validated[0].ejercicio
                delete_filter = {"ejercicio": ejercicio_detectado}

            # 3. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización SIIF RF602",
                label="RF602",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: Rcocc31LiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = Rcocc31FullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            cta_contable=params.cta_contable,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "SIIF_RCOCC31")], filename="reporte_rcocc31.xlsx"
        )


Rcocc31ServiceDependency = Annotated[Rcocc31Service, Depends()]
